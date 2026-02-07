import asyncio
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- НАСТРОЙКИ ---
API_TOKEN = '8534127751:AAGPOa9Fy4zm64iv7JkM8ohY6ennGPC-SGE'
ADMIN_PASSWORD = '090180'
OWNER_PASSWORD = '0901805242' # <-- Пароль для Создателя (измени на свой)
DATA_FILE = 'data.json'
# -----------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {"users": {}, "admin_id": None, "owner_id": None}
    return {"users": {}, "admin_id": None, "owner_id": None}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_data()

class Form(StatesGroup):
    wait_password = State()
    wait_task_username = State()
    wait_task_text = State()
    wait_task_deadline = State()
    wait_report = State()

def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Я Создатель")
    kb.button(text="Я Глава")
    kb.button(text="Я Исполнитель")
    kb.button(text="🏆 Таблица лидеров")
    kb.button(text="🔄 Сбросить роль")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def cancel_kb():
    kb = ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True)
    return kb

async def notify_owner(text, message_to_copy=None):
    if db.get("owner_id"):
        try:
            await bot.send_message(db["owner_id"], f"👁 [ЛОГ СОЗДАТЕЛЯ]: {text}")
            if message_to_copy:
                await message_to_copy.copy_to(db["owner_id"])
        except: pass

@dp.message(Command("start"))
@dp.message(F.text == "❌ Отмена")
@dp.message(F.text == "🔄 Сбросить роль")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = str(message.from_user.id)
    if message.text == "🔄 Сбросить роль":
        db["users"].pop(uid, None)
        if db.get("admin_id") == message.from_user.id: db["admin_id"] = None
        if db.get("owner_id") == message.from_user.id: db["owner_id"] = None
        save_data(db)
        await message.answer("Роль сброшена.")
    await message.answer("Кто ты в этой системе?", reply_markup=main_kb())

@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def ask_password(message: types.Message, state: FSMContext):
    role = "Главы" if message.text == "Я Глава" else "Создателя"
    await message.answer(f"Введите пароль {role}:", reply_markup=cancel_kb())
    await state.update_data(logging_as=message.text)
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role_attempt = data.get('logging_as')
    uid = message.from_user.id

    if role_attempt == "Я Создатель" and message.text == OWNER_PASSWORD:
        db["owner_id"] = uid
        # Создатель автоматически становится и исполнителем, и главой в правах
        db["users"][str(uid)] = {'username': message.from_user.username or "Boss", 'score': db["users"].get(str(uid), {}).get('score', 0)}
        save_data(db)
        await state.clear()
        kb = ReplyKeyboardBuilder()
        kb.button(text="Дать задание")
        kb.button(text="Сдать работу")
        kb.button(text="🏆 Таблица лидеров")
        await message.answer("Добро пожаловать, Создатель. Вам доступно всё.", reply_markup=kb.as_markup(resize_keyboard=True))
    
    elif role_attempt == "Я Глава" and message.text == ADMIN_PASSWORD:
        db["admin_id"] = uid
        save_data(db)
        await state.clear()
        kb = ReplyKeyboardBuilder().button(text="Дать задание").button(text="🏆 Таблица лидеров").as_markup(resize_keyboard=True)
        await message.answer("Доступ Главы разрешен.", reply_markup=kb)
    else:
        await message.answer("Неверный пароль!")

@dp.message(F.text == "Я Исполнитель")
async def worker_login(message: types.Message):
    uid = str(message.from_user.id)
    db["users"][uid] = {'username': message.from_user.username or "Worker", 'score': db["users"].get(uid, {}).get('score', 0)}
    save_data(db)
    await message.answer("Вы в системе как исполнитель.")
    await notify_owner(f"Новый исполнитель: @{message.from_user.username}")

@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    if not db["users"]:
        await message.answer("Список пуст.")
        return
    sorted_users = sorted(db["users"].values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Лидеры:**\n\n"
    for i, user in enumerate(sorted_users, 1):
        text += f"{i}. @{user['username']} — {user.get('score', 0)}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Дать задание")
async def task_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in [db.get("admin_id"), db.get("owner_id")]: return
    await message.answer("Кому даем задание? (username без @):", reply_markup=cancel_kb())
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def task_user(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text.replace("@", "").strip().lower())
    await message.answer("Суть задания:")
    await state.set_state(Form.wait_task_text)

@dp.message(Form.wait_task_text)
async def task_text(message: types.Message, state: FSMContext):
    await state.update_data(txt=message.text)
    await message.answer("Дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ):")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def task_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    raw_date = message.text.replace("—", "-").strip()
    try:
        deadline_dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M")
    except:
        await message.answer("Ошибка формата! Пример: 2025-01-01 12:00")
        return

    target_id = next((uid for uid, info in db["users"].items() if info['username'].lower() == data['target']), None)
    if target_id:
        kb = ReplyKeyboardBuilder().button(text="Сдать работу").as_markup(resize_keyboard=True)
        msg_text = f"📥 ЗАДАНИЕ: {data['txt']}\n⏰ Срок: {raw_date}"
        await bot.send_message(int(target_id), msg_text, reply_markup=kb)
        
        # Уведомление Создателю
        await notify_owner(f"Глава/Создатель дал задание для @{data['target']}:\n{data['txt']}")

        for m in [120, 60, 30]:
            rem_t = deadline_dt - timedelta(minutes=m)
            if rem_t > datetime.now():
                scheduler.add_job(bot.send_message, 'date', run_date=rem_t, args=[int(target_id), f"⏰ Осталось {m} мин!"])
        await message.answer("Задание отправлено!")
    else:
        await message.answer("Исполнитель не найден.")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_start(message: types.Message, state: FSMContext):
    await message.answer("Пришлите ваш отчет:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def get_report(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    if uid in db["users"]:
        db["users"][uid]['score'] += 1
        save_data(db)
    
    report_header = f"✅ ОТЧЕТ от @{message.from_user.username}:"
    
    # Отправляем главе
    if db.get("admin_id"):
        try:
            await bot.send_message(db["admin_id"], report_header)
            await message.copy_to(db["admin_id"])
        except: pass
    
    # Отправляем создателю (если это не он сам прислал)
    if db.get("owner_id") and message.from_user.id != db["owner_id"]:
        await notify_owner(report_header, message)
        
    await message.answer("Работа сдана!", reply_markup=main_kb())
    await state.clear()

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    wait_task_username = State()
    wait_task_text = State()
    wait_task_deadline = State()
    wait_report = State()

def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Я Глава")
    kb.button(text="Я Исполнитель")
    kb.button(text="🏆 Таблица лидеров")
    kb.button(text="🔄 Сбросить роль")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def cancel_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True)

async def send_reminder(chat_id, text):
    try:
        await bot.send_message(chat_id, f"⏰ НАПОМИНАНИЕ: {text}")
    except: pass

@dp.message(Command("start"))
@dp.message(F.text == "❌ Отмена")
@dp.message(F.text == "🔄 Сбросить роль")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = str(message.from_user.id)
    if message.text == "🔄 Сбросить роль":
        if uid in db["users"]:
            del db["users"][uid]
            save_data(db)
        await message.answer("Роль сброшена.")
    await message.answer("Выберите действие:", reply_markup=main_kb())

@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    if not db["users"]:
        await message.answer("Список пуст.")
        return
    
    sorted_users = sorted(db["users"].values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Таблица лидеров:**\n\n"
    for i, user in enumerate(sorted_users, 1):
        text += f"{i}. @{user['username']} — {user.get('score', 0)} вып.\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Я Глава")
async def ask_password(message: types.Message, state: FSMContext):
    await message.answer("Введите пароль:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        db["admin_id"] = message.from_user.id
        save_data(db)
        await state.clear()
        kb = ReplyKeyboardBuilder()
        kb.button(text="Дать задание")
        kb.button(text="🏆 Таблица лидеров")
        kb.button(text="🔄 Сбросить роль")
        await message.answer("Доступ разрешен, Глава.", reply_markup=kb.as_markup(resize_keyboard=True))
    else:
        await message.answer("Неверно.")

@dp.message(F.text == "Я Исполнитель")
async def worker_login(message: types.Message):
    uid = str(message.from_user.id)
    db["users"][uid] = {'username': message.from_user.username or "NoName", 'score': db["users"].get(uid, {}).get('score', 0)}
    save_data(db)
    await message.answer(f"Вы вошли как исполнитель @{message.from_user.username}.")
    if db["admin_id"]:
        await bot.send_message(db["admin_id"], f"⚡️ Исполнитель @{message.from_user.username} в сети!")

@dp.message(F.text == "Дать задание")
async def task_start(message: types.Message, state: FSMContext):
    if message.from_user.id != db["admin_id"]: return
    await message.answer("Введите username исполнителя (БЕЗ @):", reply_markup=cancel_kb())
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def task_user(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text.replace("@", "").strip().lower())
    await message.answer("Суть задания:")
    await state.set_state(Form.wait_task_text)

@dp.message(Form.wait_task_text)
async def task_text(message: types.Message, state: FSMContext):
    await state.update_data(txt=message.text)
    await message.answer("Дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ):\nПример: 2025-12-31 18:00")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def task_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # Авто-исправление тире и пробелов
    raw_date = message.text.replace("—", "-").replace("–", "-").strip()
    
    try:
        deadline_dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Ошибка! Используйте дефис и пробел:\n`2025-12-31 18:00`", parse_mode="Markdown")
        return

    target_id = next((uid for uid, info in db["users"].items() if info['username'].lower() == data['target']), None)
    
    if target_id:
        kb = ReplyKeyboardBuilder().button(text="Сдать работу").as_markup(resize_keyboard=True)
        await bot.send_message(int(target_id), f"📥 ЗАДАНИЕ: {data['txt']}\n⏰ Срок: {raw_date}", reply_markup=kb)
        
        for m in:
            rem_t = deadline_dt - timedelta(minutes=m)
            if rem_t > datetime.now():
                scheduler.add_job(send_reminder, 'date', run_date=rem_t, args=[int(target_id), f"Осталось {m} мин!"])
        await message.answer("Отправлено!", reply_markup=main_kb())
    else:
        await message.answer("Исполнитель не найден в базе.")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_start(message: types.Message, state: FSMContext):
    await message.answer("Пришлите отчет:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def get_report(message: types.Message, state: FSMContext):
    if db["admin_id"]:
        uid = str(message.from_user.id)
        if uid in db["users"]:
            db["users"][uid]['score'] += 1
            save_data(db)
        await bot.send_message(db["admin_id"], f"✅ ОТЧЕТ от @{message.from_user.username}:")
        await message.copy_to(db["admin_id"])
        await message.answer("Принято! +1 балл.", reply_markup=main_kb())
    await state.clear()

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
        kb.button(text="➕ Назначить задачу")
        kb.button(text="🏆 Таблица лидеров")
    elif role == 'worker':
        kb.button(text="🙋 Запросить работу")
        kb.button(text="🏆 Таблица лидеров")
    else:
        kb.button(text="Я Глава")
        kb.button(text="Я Исполнитель")
    
    kb.button(text="Сбросить мою роль")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def cancel_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True)

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
@dp.message(F.text == "❌ Отмена")
@dp.message(F.text == "Сбросить мою роль")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    if message.text == "Сбросить мою роль":
        users.pop(message.from_user.id, None)
    await message.answer("Выберите действие:", reply_markup=main_kb(message.from_user.id))

# Регистрация ролей
@dp.message(F.text == "Я Глава")
async def ask_password(message: types.Message, state: FSMContext):
    await message.answer("Введите пароль доступа:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    global admin_id
    if message.text == ADMIN_PASSWORD:
        admin_id = message.from_user.id
        users[message.from_user.id] = {'role': 'admin', 'username': message.from_user.username}
        await message.answer("✅ Доступ получен!", reply_markup=main_kb(message.from_user.id))
        await state.clear()
    else:
        await message.answer("❌ Неверный пароль!")

@dp.message(F.text == "Я Исполнитель")
async def set_worker(message: types.Message):
    users[message.from_user.id] = {'role': 'worker', 'username': message.from_user.username}
    if message.from_user.id not in stats:
        stats[message.from_user.id] = 0
    await message.answer("✅ Вы зарегистрированы как Исполнитель!", reply_markup=main_kb(message.from_user.id))

# Логика Главы: Назначение задачи
@dp.message(F.text == "➕ Назначить задачу")
async def start_task(message: types.Message, state: FSMContext):
    if users.get(message.from_user.id, {}).get('role') != 'admin': return
    await message.answer("Введите @username исполнителя:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def process_username(message: types.Message, state: FSMContext):
    target_username = message.text.replace("@", "")
    target_id = next((uid for uid, info in users.items() if info.get('username') == target_username), None)
    
    if not target_id:
        await message.answer("❌ Пользователь не найден в базе бота.")
        return
    
    await state.update_data(worker_id=target_id)
    await message.answer("Введите текст задачи:")
    await state.set_state(Form.wait_task_text)

@dp.message(Form.wait_task_text)
async def process_task_text(message: types.Message, state: FSMContext):
    await state.update_data(task_text=message.text)
    await message.answer("Укажите дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ)\nПример: 2025-06-20 18:00")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def process_deadline(message: types.Message, state: FSMContext):
    try:
        # ИСПРАВЛЕННЫЙ ФОРМАТ (с пробелом)
        dt = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        data = await state.get_data()
        
        # Уведомляем работника
        await bot.send_message(data['worker_id'], f"📥 НОВАЯ ЗАДАЧА:\n{data['task_text']}\n\nДедлайн: {message.text}")
        
        # Засчитываем работу (здесь можно добавить логику подтверждения выполнения)
        stats[data['worker_id']] = stats.get(data['worker_id'], 0) + 1
        
        await message.answer("✅ Задача отправлена и учтена в статистике!", reply_markup=main_kb(message.from_user.id))
        await state.clear()
    except ValueError:
        await message.answer("❌ Ошибка формата! Используйте: ГГГГ-ММ-ДД ЧЧ:ММ")

# Логика Исполнителя: Запрос работы
@dp.message(F.text == "🙋 Запросить работу")
async def request_work(message: types.Message):
    if admin_id:
        await bot.send_message(admin_id, f"🔔 Исполнитель @{message.from_user.username} просит дать ему задачу!")
        await message.answer("✅ Запрос отправлен Главе.")
    else:
        await message.answer("❌ Глава еще не зарегистрирован.")

# Таблица лидеров
@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    if not stats:
        await message.answer("Статистика пока пуста.")
        return

    # Сортировка по количеству работ
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    
    text = "🏆 **ТАБЛИЦА ЛИДЕРОВ**\n\n"
    for i, (uid, count) in enumerate(sorted_stats, 1):
        username = users.get(uid, {}).get('username', 'ID: ' + str(uid))
        text += f"{i}. @{username} — {count} задач(и)\n"
    
    await message.answer(text, parse_mode="Markdown")

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
