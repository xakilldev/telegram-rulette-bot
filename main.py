import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from aiocryptopay import AioCryptoPay, Networks

import config
import storage
import handlers
import admin

logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

async def post_init(application: Application):
    logger.info("Загрузка данных пользователей...")
    await storage.load_data()
    logger.info("Данные пользователей загружены.")

    logger.info("Инициализация клиента Crypto Pay...")
    try:
        crypto_pay = AioCryptoPay(token=config.CRYPTO_PAY_TOKEN, network=Networks.MAIN_NET)
        application.bot_data['crypto_pay'] = crypto_pay
        me = await crypto_pay.get_me()
        logger.info(f"Успешная инициализация Crypto Pay для приложения: {me.app_id} ({me.name})")
    except Exception as e:
        logger.error(f"Ошибка инициализации Crypto Pay: {e}", exc_info=True)
        application.bot_data['crypto_pay'] = None
        logger.warning("Бот будет работать без функции покупки попыток!")

    logger.info("Бот готов к работе!")

async def pre_shutdown(application: Application):
    logger.info("Начало процесса остановки бота...")
    crypto_pay = application.bot_data.get('crypto_pay')
    if crypto_pay:
        logger.info("Закрытие сессии Crypto Pay...")
        await crypto_pay.close()
        logger.info("Сессия Crypto Pay закрыта.")
    logger.info("Сохранение данных пользователей перед выходом...")
    await storage.save_data()
    logger.info("Данные сохранены. Бот завершает работу.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Исключение при обработке обновления:", exc_info=context.error)

def main() -> None:
    logger.info("Запуск бота...")

    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)       # Функция после инициализации
        .post_shutdown(pre_shutdown) # <--- ПРАВИЛЬНО (используем функцию pre_shutdown для post_shutdown хука)
        .build()
    )

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.button_handler))

    admin_filter = filters.User(user_id=config.ADMIN_IDS)
    application.add_handler(CommandHandler("give", admin.give_attempts, filters=admin_filter))
    application.add_handler(CommandHandler("take", admin.take_attempts, filters=admin_filter))
    application.add_handler(CommandHandler("reset", admin.reset_user, filters=admin_filter))
    application.add_handler(CommandHandler("ban", admin.ban_user, filters=admin_filter))
    application.add_handler(CommandHandler("unban", admin.unban_user, filters=admin_filter))
    application.add_handler(CommandHandler("claims", admin.view_pending_claims, filters=admin_filter))

    application.add_error_handler(error_handler)

    logger.info("Запуск polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == "__main__":
    main()