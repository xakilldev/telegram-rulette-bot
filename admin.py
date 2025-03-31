import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import storage
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

async def give_attempts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_user = update.effective_user
    logger.info(f"Админ {admin_user.id} вызвал /give с аргументами: {context.args}")

    if len(context.args) != 2:
        await update.message.reply_text("Неверный формат. Используйте: `/give <user_id> <количество>`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError("Количество должно быть положительным.")
    except ValueError:
        await update.message.reply_text("Ошибка: `user_id` и `количество` должны быть целыми положительными числами.", parse_mode=ParseMode.MARKDOWN)
        return

    target_user_data = storage.get_user(target_user_id)
    target_username = target_user_data.get("username", f"ID: {target_user_id}")

    await storage.add_attempts(target_user_id, amount)
    await update.message.reply_text(f"✅ Успешно выдано {amount} попыток пользователю {target_username} ({target_user_id}).")

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🎉 Администратор начислил вам {amount} попыток!"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о начислении попыток пользователю {target_user_id}: {e}")


async def take_attempts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_user = update.effective_user
    logger.info(f"Админ {admin_user.id} вызвал /take с аргументами: {context.args}")

    if len(context.args) != 2:
        await update.message.reply_text("Неверный формат. Используйте: `/take <user_id> <количество>`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError("Количество должно быть положительным.")
    except ValueError:
        await update.message.reply_text("Ошибка: `user_id` и `количество` должны быть целыми положительными числами.", parse_mode=ParseMode.MARKDOWN)
        return

    target_user_data = storage.get_user(target_user_id)
    target_username = target_user_data.get("username", f"ID: {target_user_id}")
    current_attempts = target_user_data.get("attempts", 0)

    if current_attempts == 0:
         await update.message.reply_text(f"⚠ У пользователя {target_username} ({target_user_id}) и так 0 попыток.")
         return

    taken_amount = min(amount, current_attempts)

    await storage.take_attempts(target_user_id, amount)
    await update.message.reply_text(f"✅ Успешно забрано {taken_amount} попыток у пользователя {target_username} ({target_user_id}).")

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"⚠ Администратор забрал у вас {taken_amount} попыток."
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление об изъятии попыток пользователю {target_user_id}: {e}")


async def reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_user = update.effective_user
    logger.info(f"Админ {admin_user.id} вызвал /reset с аргументами: {context.args}")

    if len(context.args) != 1:
        await update.message.reply_text("Неверный формат. Используйте: `/reset <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Ошибка: `user_id` должен быть целым числом.", parse_mode=ParseMode.MARKDOWN)
        return

    target_user_data = storage.get_user(target_user_id)
    target_username = target_user_data.get("username", f"ID: {target_user_id}")

    await storage.reset_user(target_user_id)
    await update.message.reply_text(f"✅ Данные пользователя {target_username} ({target_user_id}) сброшены (статус бана сохранен, если был).")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_user = update.effective_user
    logger.info(f"Админ {admin_user.id} вызвал /ban с аргументами: {context.args}")

    if len(context.args) != 1:
        await update.message.reply_text("Неверный формат. Используйте: `/ban <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        target_user_id = int(context.args[0])
        if target_user_id in ADMIN_IDS:
             await update.message.reply_text("⛔ Нельзя забанить другого администратора.")
             return
    except ValueError:
        await update.message.reply_text("Ошибка: `user_id` должен быть целым числом.", parse_mode=ParseMode.MARKDOWN)
        return

    target_user_data = storage.get_user(target_user_id)
    target_username = target_user_data.get("username", f"ID: {target_user_id}")

    if storage.is_user_banned(target_user_id):
        await update.message.reply_text(f"⚠ Пользователь {target_username} ({target_user_id}) уже забанен.")
    else:
        await storage.ban_user(target_user_id)
        await update.message.reply_text(f"✅ Пользователь {target_username} ({target_user_id}) успешно забанен.")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_user = update.effective_user
    logger.info(f"Админ {admin_user.id} вызвал /unban с аргументами: {context.args}")

    if len(context.args) != 1:
        await update.message.reply_text("Неверный формат. Используйте: `/unban <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Ошибка: `user_id` должен быть целым числом.", parse_mode=ParseMode.MARKDOWN)
        return

    target_user_data = storage.get_user(target_user_id)
    target_username = target_user_data.get("username", f"ID: {target_user_id}")

    if not storage.is_user_banned(target_user_id):
        await update.message.reply_text(f"⚠ Пользователь {target_username} ({target_user_id}) не забанен.")
    else:
        await storage.unban_user(target_user_id)
        await update.message.reply_text(f"✅ Пользователь {target_username} ({target_user_id}) успешно разбанен.")


async def view_pending_claims(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_user = update.effective_user
    logger.info(f"Админ {admin_user.id} запросил список ожидающих заявок /claims")

    pending_claims = storage.get_pending_claims()

    if not pending_claims:
        await update.message.reply_text("✅ Нет активных заявок на вывод призов.")
        return

    response_text = "⏳ **Заявки на вывод, ожидающие подтверждения:**\n\n"
    keyboard_buttons = []

    for claim in pending_claims:
        user_id = claim['user_id']
        username = claim['username']
        win_index = claim['win_index']
        prize = claim['prize']
        request_time_str = claim.get('request_time', 'N/A')
        try:
            request_time_dt = datetime.fromisoformat(request_time_str)
            request_time_formatted = request_time_dt.strftime('%Y-%m-%d %H:%M')
        except (ValueError, TypeError):
            request_time_formatted = "Неверная дата"

        response_text += (
            f"👤 **Пользователь:** {username} (`{user_id}`)\n"
            f"🎁 **Приз:** {prize}\n"
            f"🗓️ **Запрошено:** {request_time_formatted}\n"
            f"🔑 **ID заявки (для кнопки):** `{user_id}_{win_index}`\n\n"
        )
        callback_data = f"admin_confirm_claim_{user_id}_{win_index}"
        keyboard_buttons.append([
            InlineKeyboardButton(f"✅ Подтвердить для {username} ({prize})", callback_data=callback_data)
        ])

    reply_markup = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
    await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def handle_confirm_claim_button(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id_to_confirm: int, win_index_to_confirm: int):
    query = update.callback_query
    admin_user = query.from_user
    logger.info(f"Админ {admin_user.id} нажал кнопку подтверждения для заявки user={user_id_to_confirm}, index={win_index_to_confirm}")

    success, message, target_username = await storage.confirm_claim(admin_user.id, user_id_to_confirm, win_index_to_confirm)

    if success:
        prize_name = message
        await query.answer(f"✅ Заявка для {target_username} подтверждена!", show_alert=True)
        await query.edit_message_text(f"{query.message.text}\n\n---\n✅ Заявка на '{prize_name}' для {target_username} (`{user_id_to_confirm}`) подтверждена вами.",
                                      reply_markup=None)

        try:
            from config import CLAIM_CONFIRMED_USER_TEXT
            await context.bot.send_message(
                chat_id=user_id_to_confirm,
                text=CLAIM_CONFIRMED_USER_TEXT.format(prize=prize_name)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о подтверждении приза пользователю {user_id_to_confirm}: {e}")
    else:
        await query.answer(f"⚠️ {message}", show_alert=True)
        await query.edit_message_text(f"{query.message.text}\n\n---\n⚠️ Не удалось подтвердить заявку user={user_id_to_confirm}, index={win_index_to_confirm}. Причина: {message}")