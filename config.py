import logging
import os

BOT_TOKEN = "7894586530:AAF60uw90frKjc2tOv-qij_QA3PCvc6LvmI"
ADMIN_IDS = [6711974469]

CRYPTO_PAY_TOKEN = "363420:AAZwWmbbqikQ1IgHZnnAYI2syEOqYMMH9Vn"
PRICE_PER_ATTEMPT = {
    "amount": 0.1,
    "currency": "USDT"
}
INVOICE_LIFETIME_SECONDS = 3600

PRIZE_CHANCES = [
    (10, '💎 Приз A (Крупный)'),
    (30, '💰 Приз B (Средний)'),
    (60, '🎁 Приз C (Малый)'),
]

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "user_data.json")
LOG_FILE = os.path.join(DATA_DIR, "bot.log")
LOG_LEVEL = logging.INFO

WELCOME_TEXT = """
🎉 Добро пожаловать в нашу Рулетку Удачи! 🎉

Испытай свою удачу и выигрывай призы!

📜 **Правила:**
1. Для вращения рулетки нужны попытки.
2. Попытки можно приобрести за криптовалюту через CryptoBot.
3. Нажмите "Крутить!", чтобы испытать удачу.
4. Выигранные призы можно запросить на вывод во вкладке "Моя статистика".

👇 Используйте кнопки ниже для навигации.
"""

SPIN_EMOJIS = ["🎰", "🎲", "✨", "💰", "💎", "🎁", "🤞", "🍀"]
ROLLING_TEXTS = [
    "🎰 Кручу верчу...",
    "✨ Магия случайности...",
    "🎲 Бросаем кости...",
    "🤞 Держим кулачки...",
    "💰 Ищем золото...",
    "🍀 Ловим удачу за хвост...",
]
NO_ATTEMPTS_TEXT = "😕 У вас закончились попытки. Нужно пополнить!"
PURCHASE_PROMPT_TEXT = "Выберите количество попыток для покупки:"
PAYMENT_CHECK_TEXT = "⏳ Проверяем ваш платеж..."
PAYMENT_SUCCESS_TEXT = "✅ Оплата прошла успешно! Попытки ({count}) зачислены."
PAYMENT_PENDING_TEXT = "⏳ Платеж еще не подтвержден. Попробуйте проверить чуть позже."
PAYMENT_FAILED_TEXT = "❌ Не удалось найти подтвержденный платеж для этого счета."
CLAIM_REQUEST_TEXT = "✅ Ваш запрос на получение приза '{prize}' отправлен администратору."
CLAIM_CONFIRMED_USER_TEXT = "🎉 Администратор подтвердил ваш приз '{prize}'!"
CLAIM_CONFIRMED_ADMIN_TEXT = "✅ Приз '{prize}' для пользователя {user_id} подтвержден."

os.makedirs(DATA_DIR, exist_ok=True)