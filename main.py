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
OWNER_PASSWORD = '0901805242' 
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
    return ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True)

async def notify_owner(text, message_to_copy=None):
    if db.get("owner_id"):
        try:
            await bot.send_message(db["owner_id"], f"👁 [ЛОГ]: {text}")
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
        if uid in db["users"]: del db["users"][uid]
        if db.get("admin_id") == message.from_user.id: db["admin_id"] = None
        if db.get("owner_id") == message.from_user.id: db["owner_id"] = None
        save_data(db)
        await message.answer("Роль сброшена.")
    await message.answer("Кто ты в системе?", reply_markup=main_kb())

@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def ask_password(message: types.Message, state: FSMContext):
    await message.answer(f"Введите пароль:", reply_markup=cancel_kb())
    await state.update_data(logging_as=message.text)
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get('logging_as')
    uid = message.from_user.id

    if role == "Я Создатель" and message.text == OWNER_PASSWORD:
        db["owner_id"] = uid
        db["users"][str(uid)] = {'username': message.from_user.username or "Boss", 'score': db["users"].get(str(uid), {}).get('score', 0)}
        save_data(db)
        await state.clear()
        kb = ReplyKeyboardBuilder().button(text="Дать задание").button(text="Сдать работу").button(text="🏆 Таблица лидеров").as_markup(resize_keyboard=True)
        await message.answer("Добро пожаловать, Создатель!", reply_markup=kb)
    elif role == "Я Глава" and message.text == ADMIN_PASSWORD:
        db["admin_id"] = uid
        save_data(db)
        await state.clear()
        kb = ReplyKeyboardBuilder().button(text="Дать задание").button(text="🏆 Таблица лидеров").as_markup(resize_keyboard=True)
        await message.answer("Доступ Главы разрешен.", reply_markup=kb)
    else:
        await message.answer("Неверно!")

@dp.message(F.text == "Я Исполнитель")
async def worker_login(message: types.Message):
    uid = str(message.from_user.id)
    db["users"][uid] = {'username': message.from_user.username or "Worker", 'score': db["users"].get(uid, {}).get('score', 0)}
    save_data(db)
    await message.answer("Вы вошли как исполнитель.")
    await notify_owner(f"Новый исполнитель: @{message.from_user.username}")

@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    if not db["users"]:
        return await message.answer("Список пуст.")
    sorted_users = sorted(db["users"].values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Лидеры:**\n\n"
    for i, user in enumerate(sorted_users, 1):
        text += f"{i}. @{user['username']} — {user.get('score', 0)}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Дать задание")
async def task_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in [db.get("admin_id"), db.get("owner_id")]: return
    await message.answer("Username исполнителя (без @):", reply_markup=cancel_kb())
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
        return await message.answer("Ошибка! Пример: 2025-01-01 12:00")

    target_id = next((uid for uid, info in db["users"].items() if info['username'].lower() == data['target']), None)
    if target_id:
        kb = ReplyKeyboardBuilder().button(text="Сдать работу").as_markup(resize_keyboard=True)
        await bot.send_message(int(target_id), f"📥 ЗАДАНИЕ: {data['txt']}\n⏰ Срок: {raw_date}", reply_markup=kb)
        await notify_owner(f"Выдано задание для @{data['target']}: {data['txt']}")

        # ИСПРАВЛЕННЫЙ БЛОК НАПОМИНАНИЙ
        remind_minutes = [120, 60, 30]
        for m in remind_minutes:
            rem_t = deadline_dt - timedelta(minutes=m)
            if rem_t > datetime.now():
                scheduler.add_job(bot.send_message, 'date', run_date=rem_t, args=[int(target_id), f"⏰ До дедлайна {m} мин!"])
        
        await message.answer("Задание отправлено!", reply_markup=main_kb())
    else:
        await message.answer("Исполнитель не найден.")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_start(message: types.Message, state: FSMContext):
    await message.answer("Пришлите отчет:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def get_report(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    if uid in db["users"]:
        db["users"][uid]['score'] += 1
        save_data(db)
    
    header = f"✅ ОТЧЕТ от @{message.from_user.username}:"
    if db.get("admin_id"):
        try:
            await bot.send_message(db["admin_id"], header)
            await message.copy_to(db["admin_id"])
        except: pass
    if db.get("owner_id") and message.from_user.id != db["owner_id"]:
        await notify_owner(header, message)
        
    await message.answer("Работа сдана!", reply_markup=main_kb())
    await state.clear()

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
