import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
import storage
import roulette
import admin
from config import (
    WELCOME_TEXT, PRICE_PER_ATTEMPT, ADMIN_IDS, PURCHASE_PROMPT_TEXT,
    CLAIM_REQUEST_TEXT, PAYMENT_CHECK_TEXT, PAYMENT_SUCCESS_TEXT,
    PAYMENT_FAILED_TEXT, PAYMENT_PENDING_TEXT
)

def get_crypto_pay_client(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get('crypto_pay')

logger = logging.getLogger(__name__)

def create_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    unclaimed_prizes = storage.get_unclaimed_prizes(user_id)
    claim_button = []
    if unclaimed_prizes:
        claim_button = [InlineKeyboardButton("🏆 Запросить приз", callback_data="claim_options")]

    keyboard = [
        [InlineKeyboardButton("📊 Моя статистика", callback_data="show_stats")],
        claim_button,
        [InlineKeyboardButton("💰 Купить попытки", callback_data="buy_options")],
        [InlineKeyboardButton("🎰 Крутить! 🎰", callback_data="spin_roulette")]
    ]
    keyboard = [row for row in keyboard if row]
    return InlineKeyboardMarkup(keyboard)

def create_buy_options_keyboard() -> InlineKeyboardMarkup:
    options = [1, 5, 10]
    currency = PRICE_PER_ATTEMPT['currency']
    base_price = PRICE_PER_ATTEMPT['amount']
    keyboard = []
    for count in options:
        price = round(base_price * count, 4)
        keyboard.append([
            InlineKeyboardButton(
                f"{count} попыт{'ка' if count == 1 else ('ки' if count < 5 else 'ок')} (~{price} {currency})",
                callback_data=f"confirm_buy_{count}"
            )
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def create_claim_options_keyboard(user_id: int) -> InlineKeyboardMarkup:
    unclaimed_prizes = storage.get_unclaimed_prizes(user_id)
    keyboard = []
    if not unclaimed_prizes:
        return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]])

    for index, win_data in unclaimed_prizes[:5]:
        prize_name = win_data.get('prize', 'Неизвестный приз')
        try:
            win_time = datetime.fromisoformat(win_data['timestamp']).strftime('%d.%m %H:%M')
            button_text = f"'{prize_name}' ({win_time})"
        except:
            button_text = f"'{prize_name}'"

        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"request_claim_{index}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name

    logger.info(f"Пользователь {user_id} ({username}) запустил бота командой /start.")

    storage.get_user(user_id)
    storage.update_user_username(user_id, user.username)

    if storage.is_user_banned(user_id):
        await update.message.reply_text("❌ Вы заблокированы.")
        logger.warning(f"Заблокированный пользователь {user_id} попытался использовать /start.")
        return

    keyboard = create_main_keyboard(user_id)
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    data = query.data

    logger.debug(f"Пользователь {user_id} ({user.username}) нажал кнопку: {data}")

    if storage.is_user_banned(user_id) and not data.startswith("admin_"):
        await query.message.reply_text("❌ Вы заблокированы.")
        logger.warning(f"Заблокированный пользователь {user_id} попытался нажать кнопку {data}.")
        return

    if data == "back_to_main":
        keyboard = create_main_keyboard(user_id)
        try:
            await query.edit_message_text(WELCOME_TEXT, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            logger.warning(f"Не удалось вернуться в гл. меню для {user_id}: {e}. Отправляю новое сообщение.")
            await context.bot.send_message(user_id, WELCOME_TEXT, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    elif data == "show_stats":
        stats_text = storage.get_user_stats(user_id)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]])
        try:
            await query.edit_message_text(stats_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
             logger.warning(f"Не удалось показать статистику для {user_id}: {e}.")
             await context.bot.send_message(user_id, stats_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    elif data == "spin_roulette":
        await roulette.spin_roulette(update, context)

    elif data == "buy_options":
        keyboard = create_buy_options_keyboard()
        try:
            await query.edit_message_text(PURCHASE_PROMPT_TEXT, reply_markup=keyboard)
        except BadRequest as e:
             logger.warning(f"Не удалось показать опции покупки для {user_id}: {e}.")
             await context.bot.send_message(user_id, PURCHASE_PROMPT_TEXT, reply_markup=keyboard)

    elif data.startswith("confirm_buy_"):
        try:
            attempts_to_buy = int(data.split("_")[2])
            if attempts_to_buy <= 0: raise ValueError
        except (IndexError, ValueError):
            logger.error(f"Некорректный callback для покупки: {data} от {user_id}")
            await query.message.reply_text("Произошла ошибка при выборе количества попыток.")
            return

        crypto_pay = get_crypto_pay_client(context)
        if not crypto_pay:
            logger.error("Crypto Pay клиент не инициализирован в bot_data!")
            await query.message.reply_text("К сожалению, система оплаты временно недоступна. Попробуйте позже.")
            return

        currency = PRICE_PER_ATTEMPT['currency']
        amount = round(PRICE_PER_ATTEMPT['amount'] * attempts_to_buy, 8)

        try:
            payload_data = f"{user_id}_{attempts_to_buy}"
            invoice = await crypto_pay.create_invoice(
                asset=currency,
                amount=amount,
                description=f"Покупка {attempts_to_buy} попыток в Рулетке Удачи",
                payload=payload_data,
            )

            if not invoice or 'invoice_id' not in invoice or 'pay_url' not in invoice:
                 raise Exception("Некорректный ответ от Crypto Pay API при создании инвойса.")

            invoice_id = invoice['invoice_id']
            pay_url = invoice['pay_url']

            await storage.add_pending_invoice(user_id, invoice_id, amount, currency, attempts_to_buy)

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Перейти к оплате", url=pay_url)],
                [InlineKeyboardButton("✅ Я оплатил, проверить", callback_data=f"check_payment_{invoice_id}")],
                [InlineKeyboardButton("⬅️ Отмена", callback_data="back_to_main")]
            ])
            await query.edit_message_text(
                f"🧾 Ваш счет на оплату {amount} {currency} за {attempts_to_buy} попыт{'ок' if attempts_to_buy > 4 else 'ки'}:\n"
                f"Нажмите кнопку ниже для перехода к оплате.",
                reply_markup=keyboard
            )
            logger.info(f"Создан инвойс {invoice_id} для пользователя {user_id} на {attempts_to_buy} попыток ({amount} {currency}).")

        except Exception as e:
            logger.error(f"Ошибка при создании инвойса Crypto Pay для {user_id}: {e}", exc_info=True)
            await query.message.reply_text("Произошла ошибка при создании счета на оплату. Попробуйте еще раз позже.")

    elif data.startswith("check_payment_"):
        try:
            invoice_id = int(data.split("_")[2])
        except (IndexError, ValueError):
            logger.error(f"Некорректный callback для проверки платежа: {data} от {user_id}")
            return

        crypto_pay = get_crypto_pay_client(context)
        if not crypto_pay:
            logger.error("Crypto Pay клиент не инициализирован в bot_data!")
            await query.message.reply_text("Ошибка: Не удается проверить платеж.")
            return

        invoice_data = storage.get_pending_invoice_data(user_id, invoice_id)
        if not invoice_data:
             logger.warning(f"Попытка проверить неизвестный или уже обработанный инвойс {invoice_id} пользователем {user_id}")
             await query.answer("Не удалось найти информацию об этом счете.", show_alert=True)
             keyboard = create_main_keyboard(user_id)
             await query.edit_message_text(WELCOME_TEXT, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
             return

        await query.answer(PAYMENT_CHECK_TEXT)

        try:
            invoices = await crypto_pay.get_invoices(invoice_ids=[invoice_id])
            if invoices and invoices[0].status == 'paid':
                logger.info(f"Инвойс {invoice_id} для пользователя {user_id} подтвержден как оплаченный.")
                attempts_to_add = invoice_data['attempts']
                await storage.add_attempts(user_id, attempts_to_add)
                await storage.remove_pending_invoice(user_id, invoice_id)
                keyboard = create_main_keyboard(user_id)
                await query.edit_message_text(
                    PAYMENT_SUCCESS_TEXT.format(count=attempts_to_add),
                    reply_markup=keyboard
                )

            elif invoices and invoices[0].status == 'expired':
                logger.warning(f"Инвойс {invoice_id} для пользователя {user_id} истек.")
                await storage.remove_pending_invoice(user_id, invoice_id)
                keyboard = create_main_keyboard(user_id)
                await query.edit_message_text(
                     f"❌ Срок действия счета {invoice_id} истек.",
                     reply_markup=keyboard
                )
            else:
                logger.info(f"Инвойс {invoice_id} для пользователя {user_id} еще не оплачен (статус: {invoices[0].status if invoices else 'не найден'}).")
                pay_url = invoices[0].pay_url if invoices else "#"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Перейти к оплате", url=pay_url)],
                    [InlineKeyboardButton("🔄 Проверить еще раз", callback_data=f"check_payment_{invoice_id}")],
                    [InlineKeyboardButton("⬅️ Отмена", callback_data="back_to_main")]
                ])
                await query.edit_message_text(
                    f"{query.message.text}\n\n{PAYMENT_PENDING_TEXT}",
                    reply_markup=keyboard
                )

        except Exception as e:
            logger.error(f"Ошибка при проверке инвойса {invoice_id} для {user_id}: {e}", exc_info=True)
            await query.message.reply_text("Произошла ошибка при проверке платежа. Попробуйте еще раз позже.")
            keyboard = InlineKeyboardMarkup([
                 [InlineKeyboardButton("🔄 Проверить еще раз", callback_data=f"check_payment_{invoice_id}")],
                 [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
            ])
            await query.edit_message_reply_markup(reply_markup=keyboard)

    elif data == "claim_options":
        keyboard = create_claim_options_keyboard(user_id)
        unclaimed_count = len(storage.get_unclaimed_prizes(user_id))
        text = "🏆 Выберите приз, который хотите получить:" if unclaimed_count > 0 else "У вас нет доступных призов для вывода."
        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except BadRequest as e:
             logger.warning(f"Не удалось показать опции вывода призов для {user_id}: {e}.")
             await context.bot.send_message(user_id, text, reply_markup=keyboard)

    elif data.startswith("request_claim_"):
        try:
            win_index = int(data.split("_")[2])
        except (IndexError, ValueError):
            logger.error(f"Некорректный callback для запроса приза: {data} от {user_id}")
            return

        prize_name = await storage.request_claim(user_id, win_index)

        if prize_name:
            await query.answer("✅ Запрос отправлен!", show_alert=True)
            keyboard = create_main_keyboard(user_id)
            user_info = storage.get_user(user_id)
            username = user_info.get('username', f"`{user_id}`")

            admin_message = (f"🔔 Новый запрос на вывод приза!\n"
                             f"👤 Пользователь: {username} (`{user_id}`)\n"
                             f"🎁 Приз: {prize_name}\n"
                             f"Для просмотра всех заявок используйте /claims")
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(admin_id, admin_message, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление админу {admin_id} о запросе приза: {e}")

            try:
                await query.edit_message_text(
                    CLAIM_REQUEST_TEXT.format(prize=prize_name) + "\n\n" + WELCOME_TEXT,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
            except BadRequest as e:
                logger.warning(f"Не удалось обновить сообщение после запроса приза для {user_id}: {e}")
                await context.bot.send_message(user_id, CLAIM_REQUEST_TEXT.format(prize=prize_name))
                await context.bot.send_message(user_id, WELCOME_TEXT, reply_markup=create_main_keyboard(user_id), parse_mode=ParseMode.MARKDOWN)

        else:
            await query.answer("⚠️ Не удалось отправить запрос. Возможно, приз уже запрошен или получен.", show_alert=True)
            keyboard = create_main_keyboard(user_id)
            try:
                 await query.edit_message_reply_markup(reply_markup=keyboard)
            except BadRequest:
                 pass

    elif data.startswith("admin_confirm_claim_"):
         if user_id not in ADMIN_IDS:
              await query.answer("⛔ Доступ запрещен.", show_alert=True)
              logger.warning(f"Пользователь {user_id} (не админ) попытался нажать админскую кнопку: {data}")
              return
         try:
              parts = data.split("_")
              user_id_to_confirm = int(parts[3])
              win_index_to_confirm = int(parts[4])
              await admin.handle_confirm_claim_button(update, context, user_id_to_confirm, win_index_to_confirm)
         except (IndexError, ValueError):
              logger.error(f"Некорректный callback для подтверждения админом: {data}")
              await query.answer("⚠️ Ошибка в данных кнопки.", show_alert=True)

    else:
        logger.warning(f"Неизвестный callback_data '{data}' от пользователя {user_id}")
        await query.answer("Неизвестное действие.")