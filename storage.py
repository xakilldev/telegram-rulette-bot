import json
import logging
import asyncio
from datetime import datetime
import os
from config import DATA_FILE, ADMIN_IDS

logger = logging.getLogger(__name__)

_file_lock = asyncio.Lock()
_user_data = {}

async def load_data():
    global _user_data
    async with _file_lock:
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        _user_data = json.loads(content)
                        logger.info(f"Данные пользователей успешно загружены из {DATA_FILE}")
                    else:
                        _user_data = {}
                        logger.info(f"Файл {DATA_FILE} пуст, инициализированы пустые данные.")
            else:
                _user_data = {}
                logger.info(f"Файл {DATA_FILE} не найден, инициализированы пустые данные.")
        except json.JSONDecodeError:
            logger.error(f"Ошибка декодирования JSON в файле {DATA_FILE}. Создан бэкап, используется пустой словарь.", exc_info=True)
            try:
                backup_path = DATA_FILE + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(DATA_FILE, backup_path)
                logger.info(f"Создан бэкап поврежденного файла: {backup_path}")
            except OSError as e:
                logger.error(f"Не удалось создать бэкап файла {DATA_FILE}: {e}")
            _user_data = {}
        except Exception as e:
            logger.error(f"Не удалось загрузить данные из {DATA_FILE}: {e}", exc_info=True)
            _user_data = {}

async def save_data():
    async with _file_lock:
        try:
            temp_file = DATA_FILE + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(_user_data, f, ensure_ascii=False, indent=4)
            os.replace(temp_file, DATA_FILE)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных в {DATA_FILE}: {e}", exc_info=True)

def _get_default_user_structure():
    return {
        "username": None,
        "attempts": 0,
        "wins": [],
        "is_banned": False,
        "first_seen": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat(),
        "pending_invoices": {}
    }

def get_user(user_id: int) -> dict:
    user_id_str = str(user_id)
    if user_id_str not in _user_data:
        _user_data[user_id_str] = _get_default_user_structure()
        logger.info(f"Новый пользователь {user_id_str} зарегистрирован.")
    _user_data[user_id_str]['last_seen'] = datetime.now().isoformat()
    return _user_data[user_id_str]

def update_user_username(user_id: int, username: str | None):
    user_id_str = str(user_id)
    user = get_user(user_id)
    if user.get("username") != username:
        user["username"] = username
        logger.info(f"Обновлен username для {user_id_str} на {username}")

def is_user_banned(user_id: int) -> bool:
    return get_user(user_id).get("is_banned", False)

async def add_attempts(user_id: int, amount: int):
    if amount <= 0:
        logger.warning(f"Попытка добавить некорректное количество попыток ({amount}) для {user_id}")
        return
    user = get_user(user_id)
    user["attempts"] = user.get("attempts", 0) + amount
    logger.info(f"Пользователю {user_id} добавлено {amount} попыток. Текущий баланс: {user['attempts']}")
    await save_data()

async def use_attempt(user_id: int) -> bool:
    user = get_user(user_id)
    if user.get("attempts", 0) > 0:
        user["attempts"] -= 1
        logger.info(f"Пользователь {user_id} использовал попытку. Осталось: {user['attempts']}")
        await save_data()
        return True
    else:
        logger.warning(f"У пользователя {user_id} нет попыток для использования.")
        return False

async def take_attempts(user_id: int, amount: int):
    if amount <= 0:
        logger.warning(f"Попытка забрать некорректное количество попыток ({amount}) у {user_id}")
        return
    user = get_user(user_id)
    current_attempts = user.get("attempts", 0)
    taken_amount = min(amount, current_attempts)
    if taken_amount > 0:
        user["attempts"] -= taken_amount
        logger.info(f"У пользователя {user_id} забрано {taken_amount} попыток. Осталось: {user['attempts']}")
        await save_data()
    else:
         logger.info(f"У пользователя {user_id} нет попыток для изъятия.")

async def add_win(user_id: int, prize_name: str, roll: int):
    user = get_user(user_id)
    win_record = {
        "prize": prize_name,
        "timestamp": datetime.now().isoformat(),
        "roll": roll,
        "claimed": False,
        "claim_requested": False,
        "claim_request_timestamp": None,
        "claim_confirmed_timestamp": None
    }
    user.setdefault("wins", []).append(win_record)
    logger.info(f"Пользователь {user_id} выиграл '{prize_name}' (ролл: {roll})")
    await save_data()

def get_user_stats(user_id: int) -> str:
    user = get_user(user_id)
    username = user.get("username", f"ID: {user_id}")
    attempts = user.get("attempts", 0)
    wins_list = user.get("wins", [])
    total_wins = len(wins_list)
    claimed_wins = sum(1 for w in wins_list if w.get("claimed"))
    pending_claims = sum(1 for w in wins_list if w.get("claim_requested") and not w.get("claimed"))

    stats_text = f"📊 **Статистика для {username}**\n\n"
    stats_text += f"🎟️ **Доступно попыток:** {attempts}\n\n"
    stats_text += f"🏆 **Всего выигрышей:** {total_wins}\n"
    stats_text += f"✅ **Получено призов:** {claimed_wins}\n"
    stats_text += f"⏳ **Запрошено на вывод:** {pending_claims}\n\n"

    if not wins_list:
        stats_text += "Вы пока ничего не выиграли.\n"
    else:
        stats_text += "📜 **История выигрышей:**\n"
        for i, win in enumerate(reversed(wins_list[-10:])):
            status = ""
            if win.get('claimed'):
                status = "✅ Получен"
            elif win.get('claim_requested'):
                status = "⏳ Ожидает подтверждения"
            else:
                status = "🎁 Доступен к выводу"

            try:
                win_time = datetime.fromisoformat(win['timestamp']).strftime('%Y-%m-%d %H:%M')
                stats_text += f"- {win['prize']} ({win_time}) - {status}\n"
            except (ValueError, TypeError):
                 stats_text += f"- {win['prize']} (Неверная дата) - {status}\n"

    return stats_text

def get_unclaimed_prizes(user_id: int) -> list[tuple[int, dict]]:
    user = get_user(user_id)
    wins = user.get("wins", [])
    unclaimed = []
    for index, win in enumerate(wins):
        if not win.get("claimed") and not win.get("claim_requested"):
            unclaimed.append((index, win))
    return unclaimed

async def request_claim(user_id: int, win_index: int) -> str | None:
    user = get_user(user_id)
    wins = user.get("wins", [])
    if 0 <= win_index < len(wins):
        win = wins[win_index]
        if not win.get("claimed") and not win.get("claim_requested"):
            win["claim_requested"] = True
            win["claim_request_timestamp"] = datetime.now().isoformat()
            logger.info(f"Пользователь {user_id} запросил вывод приза '{win['prize']}' (индекс {win_index})")
            await save_data()
            return win['prize']
        else:
            logger.warning(f"Попытка запросить уже запрошенный/полученный приз (индекс {win_index}) пользователем {user_id}")
            return None
    else:
        logger.error(f"Неверный индекс приза ({win_index}) для запроса на вывод пользователем {user_id}")
        return None

def get_pending_claims() -> list[dict]:
    pending = []
    for user_id_str, user_data in _user_data.items():
        wins = user_data.get("wins", [])
        for index, win in enumerate(wins):
            if win.get("claim_requested") and not win.get("claimed"):
                claim_info = {
                    "user_id": int(user_id_str),
                    "username": user_data.get("username", "N/A"),
                    "win_index": index,
                    "prize": win.get("prize", "N/A"),
                    "request_time": win.get("claim_request_timestamp")
                }
                pending.append(claim_info)
    pending.sort(key=lambda x: x.get("request_time") or "")
    return pending

async def confirm_claim(admin_id: int, user_id_to_confirm: int, win_index_to_confirm: int) -> tuple[bool, str, str | None]:
    user = get_user(user_id_to_confirm)
    wins = user.get("wins", [])
    if 0 <= win_index_to_confirm < len(wins):
        win = wins[win_index_to_confirm]
        if win.get("claim_requested") and not win.get("claimed"):
            win["claimed"] = True
            win["claim_confirmed_timestamp"] = datetime.now().isoformat()
            win["confirmed_by_admin"] = admin_id
            prize_name = win.get('prize', 'Неизвестный приз')
            logger.info(f"Администратор {admin_id} подтвердил приз '{prize_name}' (индекс {win_index_to_confirm}) для пользователя {user_id_to_confirm}")
            await save_data()
            return True, prize_name, user.get("username", str(user_id_to_confirm))
        else:
            logger.warning(f"Администратор {admin_id} попытался подтвердить уже подтвержденную или не запрошенную заявку (индекс {win_index_to_confirm}) для пользователя {user_id_to_confirm}")
            return False, "Заявка не найдена или уже обработана.", None
    else:
        logger.error(f"Неверный индекс приза ({win_index_to_confirm}) при подтверждении заявки администратором {admin_id} для пользователя {user_id_to_confirm}")
        return False, "Неверный индекс приза.", None

async def ban_user(user_id: int):
    user = get_user(user_id)
    if not user["is_banned"]:
        user["is_banned"] = True
        logger.info(f"Пользователь {user_id} забанен.")
        await save_data()

async def unban_user(user_id: int):
    user = get_user(user_id)
    if user["is_banned"]:
        user["is_banned"] = False
        logger.info(f"Пользователь {user_id} разбанен.")
        await save_data()

async def reset_user(user_id: int):
    user_id_str = str(user_id)
    if user_id_str in _user_data:
        is_banned = _user_data[user_id_str].get("is_banned", False)
        first_seen = _user_data[user_id_str].get("first_seen")
        _user_data[user_id_str] = _get_default_user_structure()
        _user_data[user_id_str]["is_banned"] = is_banned
        _user_data[user_id_str]["first_seen"] = first_seen if first_seen else datetime.now().isoformat()
        logger.info(f"Данные пользователя {user_id} сброшены (кроме статуса бана).")
        await save_data()
    else:
        logger.warning(f"Попытка сбросить данные несуществующего пользователя {user_id}.")

async def add_pending_invoice(user_id: int, invoice_id: int, amount: float, currency: str, attempts: int):
    user = get_user(user_id)
    user.setdefault("pending_invoices", {})[str(invoice_id)] = {
        "amount": amount,
        "currency": currency,
        "attempts": attempts,
        "created_at": datetime.now().isoformat()
    }
    logger.info(f"Для пользователя {user_id} создан ожидающий инвойс {invoice_id} на {attempts} попыток.")
    await save_data()

async def remove_pending_invoice(user_id: int, invoice_id: int) -> dict | None:
    user = get_user(user_id)
    invoice_id_str = str(invoice_id)
    pending_invoices = user.get("pending_invoices", {})
    if invoice_id_str in pending_invoices:
        invoice_data = pending_invoices.pop(invoice_id_str)
        logger.info(f"Инвойс {invoice_id} удален из ожидающих для пользователя {user_id}.")
        await save_data()
        return invoice_data
    return None

def get_pending_invoice_data(user_id: int, invoice_id: int) -> dict | None:
    user = get_user(user_id)
    return user.get("pending_invoices", {}).get(str(invoice_id))