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
OWNER_PASSWORD = '0901805242' # Твой новый пароль
DATA_FILE = 'data.json'
# -----------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                c = f.read().strip()
                data = json.loads(c) if c else {}
                if "users" not in data: data["users"] = {}
                return data
        except: pass
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
    await message.answer("Выберите роль:", reply_markup=main_kb())

@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def ask_password(message: types.Message, state: FSMContext):
    await state.update_data(role_target=message.text)
    await message.answer(f"Введите пароль для {message.text}:", 
                         reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target = data.get("role_target")
    uid = message.from_user.id
    uid_s = str(uid)

    if target == "Я Создатель" and message.text == OWNER_PASSWORD:
        db["owner_id"] = uid
        if uid_s not in db["users"]:
            db["users"][uid_s] = {"username": message.from_user.username or "Boss", "score": 0}
        save_data(db)
        await state.clear()
        kb = ReplyKeyboardBuilder().button(text="Дать задание").button(text="Сдать работу").button(text="🏆 Таблица лидеров").as_markup(resize_keyboard=True)
        await message.answer("✅ Пароль верный! Вы Создатель.", reply_markup=kb)
        
    elif target == "Я Глава" and message.text == ADMIN_PASSWORD:
        db["admin_id"] = uid
        save_data(db)
        await state.clear()
        kb = ReplyKeyboardBuilder().button(text="Дать задание").button(text="🏆 Таблица лидеров").as_markup(resize_keyboard=True)
        await message.answer("✅ Пароль верный! Вы Глава.", reply_markup=kb)
    else:
        await message.answer("❌ Неверный пароль! Попробуйте еще раз или нажмите /start")

@dp.message(F.text == "Я Исполнитель")
async def worker_login(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"username": message.from_user.username or "Worker", "score": 0}
    save_data(db)
    await message.answer("✅ Вы зарегистрированы как исполнитель.")

@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    if not db["users"]: return await message.answer("Список пуст.")
    sorted_u = sorted(db["users"].values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Лидеры:**\n\n"
    for i, u in enumerate(sorted_u, 1):
        text += f"{i}. @{u.get('username')} — {u.get('score', 0)}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Дать задание")
async def task_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in [db.get("admin_id"), db.get("owner_id")]: return
    await message.answer("Введите username (без @):")
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
    try:
        clean_date = message.text.replace("—", "-").strip()
        dt = datetime.strptime(clean_date, "%Y-%m-%d %H:%M")
        target_id = next((u_id for u_id, info in db["users"].items() if info.get('username','').lower() == data['target']), None)
        
        if target_id:
            kb = ReplyKeyboardBuilder().button(text="Сдать работу").as_markup(resize_keyboard=True)
            await bot.send_message(int(target_id), f"📥 ЗАДАНИЕ: {data['txt']}\n⏰ Срок: {clean_date}", reply_markup=kb)
            
            # ИСПРАВЛЕННЫЙ ЦИКЛ НАПОМИНАНИЙ
            minutes_list =
            for m in minutes_list:
                rem_t = dt - timedelta(minutes=m)
                if rem_t > datetime.now():
                    scheduler.add_job(bot.send_message, 'date', run_date=rem_t, args=[int(target_id), f"⏰ До дедлайна {m} мин!"])
            
            await message.answer("✅ Задание отправлено!")
        else:
            await message.answer("Исполнитель не найден.")
    except:
        await message.answer("Ошибка даты! Пример: 2025-01-01 12:00")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_start(message: types.Message, state: FSMContext):
    await message.answer("Пришлите отчет:")
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def get_report(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    if uid in db["users"]:
        db["users"][uid]['score'] = db["users"][uid].get('score', 0) + 1
        save_data(db)
    
    header = f"✅ ОТЧЕТ от @{message.from_user.username}:"
    targets = []
    if db.get("admin_id"): targets.append(db["admin_id"])
    if db.get("owner_id"): targets.append(db["owner_id"])
    
    for target in set(targets): # set чтобы не слать дважды если админ и овнер одно лицо
        if target != message.from_user.id:
            try:
                await bot.send_message(target, header)
                await message.copy_to(target)
            except: pass
            
    await message.answer("✅ Отправлено!", reply_markup=main_kb())
    await state.clear()

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
