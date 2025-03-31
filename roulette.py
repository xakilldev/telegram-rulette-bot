
import asyncio
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
import storage
from config import PRIZE_CHANCES, SPIN_EMOJIS, ROLLING_TEXTS, NO_ATTEMPTS_TEXT

logger = logging.getLogger(__name__)

def determine_prize(roll: int) -> str | None:
    for upper_bound, prize_name in PRIZE_CHANCES:
        if roll <= upper_bound:
            return prize_name
    return None

async def spin_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = user.id

    logger.info(f"Пользователь {user_id} ({user.username}) нажал 'Крутить!'")

    if storage.is_user_banned(user_id):
        await query.answer("❌ Вы заблокированы и не можете играть.", show_alert=True)
        logger.warning(f"Заблокированный пользователь {user_id} попытался крутить рулетку.")
        return

    can_spin = await storage.use_attempt(user_id)

    if not can_spin:
        await query.answer(NO_ATTEMPTS_TEXT, show_alert=True)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Купить попытки", callback_data="buy_options")]
        ])
        try:
            await query.edit_message_text(
                text=f"{query.message.text}\n\n{NO_ATTEMPTS_TEXT}",
                reply_markup=keyboard
            )
        except BadRequest:
             await context.bot.send_message(
                 chat_id=user_id,
                 text=NO_ATTEMPTS_TEXT,
                 reply_markup=keyboard
            )
        return

    await query.answer("✨ Удачи!")

    try:
        rolling_message = await query.edit_message_text(
            text=random.choice(ROLLING_TEXTS),
            reply_markup=None
        )
        message_id = rolling_message.message_id
        chat_id = rolling_message.chat.id
    except BadRequest as e:
        logger.warning(f"Не удалось отредактировать сообщение для анимации для {user_id}: {e}. Отправляю новое.")
        fallback_message = await context.bot.send_message(
            chat_id=user_id,
            text=random.choice(ROLLING_TEXTS)
        )
        message_id = fallback_message.message_id
        chat_id = fallback_message.chat.id

    spin_duration = 3
    animation_steps = 5
    for i in range(animation_steps):
        try:
            text = f"{random.choice(ROLLING_TEXTS)} {random.choice(SPIN_EMOJIS)}"
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text
            )
        except BadRequest:
             logger.warning(f"Сообщение {message_id} стало недоступно во время анимации для {user_id}")
             break
        await asyncio.sleep(spin_duration / animation_steps)

    roll = random.randint(1, 100)
    prize = determine_prize(roll)

    from handlers import create_main_keyboard
    reply_markup = create_main_keyboard(user_id)

    result_text = ""
    if prize:
        await storage.add_win(user_id, prize, roll)
        result_text = f"🎉 **Поздравляем!** 🎉\n\nВы выиграли: **{prize}**\n(Результат ролла: {roll})"
        logger.info(f"Пользователь {user_id} ВЫИГРАЛ '{prize}' (Ролл: {roll})")
    else:
        result_text = f"😕 Увы, в этот раз не повезло...\nПопробуйте еще!\n(Результат ролла: {roll})"
        logger.info(f"Пользователь {user_id} ПРОИГРАЛ (Ролл: {roll})")

    user_data = storage.get_user(user_id)
    remaining_attempts = user_data.get("attempts", 0)
    result_text += f"\n\n🎟️ Осталось попыток: {remaining_attempts}"

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=result_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except BadRequest:
        logger.warning(f"Не удалось отредактировать финальное сообщение {message_id} для {user_id}. Отправляю новое.")
        await context.bot.send_message(
            chat_id=user_id,
            text=result_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )