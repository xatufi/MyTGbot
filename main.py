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
    default = {"users": {}, "admin_id": None, "owner_id": None}
    if not os.path.exists(DATA_FILE): return default
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "users" not in data: data["users"] = {}
            return data
    except: return default

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
    wait_broadcast = State()

def main_kb(user_id=None):
    builder = ReplyKeyboardBuilder()
    uid = str(user_id)
    
    if user_id == db.get("owner_id"):
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="📢 Рассылка всем"))
        builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"), types.KeyboardButton(text="Сдать работу"))
    elif user_id == db.get("admin_id"):
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="🏆 Таблица лидеров"))
    elif uid in db["users"]:
        builder.row(types.KeyboardButton(text="📋 Мои задания"), types.KeyboardButton(text="Сдать работу"))
        builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"))
    else:
        builder.row(types.KeyboardButton(text="Я Создатель"), types.KeyboardButton(text="Я Глава"))
        builder.row(types.KeyboardButton(text="Я Исполнитель"))
    
    builder.row(types.KeyboardButton(text="🔄 Сбросить роль"))
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
@dp.message(F.text == "❌ Отмена")
@dp.message(F.text == "🔄 Сбросить роль")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = str(message.from_user.id)
    if message.text == "🔄 Сбросить роль":
        db["users"].pop(uid, None)
        if db.get("admin_id") == message.from_user.id: db["admin_id"] = None
        if db.get("owner_id") == message.from_user.id: db["owner_id"] = None
        save_data(db)
        await message.answer("Роль сброшена.")
    await message.answer("Меню управления:", reply_markup=main_kb(message.from_user.id))

@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def role_pass(message: types.Message, state: FSMContext):
    await state.update_data(role=message.text)
    await message.answer(f"Пароль для {message.text}:", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_pass(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role, uid = data.get("role"), message.from_user.id
    if (role == "Я Создатель" and message.text == OWNER_PASSWORD) or (role == "Я Глава" and message.text == ADMIN_PASSWORD):
        if role == "Я Создатель": db["owner_id"] = uid
        else: db["admin_id"] = uid
        save_data(db)
        await state.clear()
        await message.answer(f"✅ Доступ {role} разрешен!", reply_markup=main_kb(uid))
    else: await message.answer("❌ Неверно.")

@dp.message(F.text == "Я Исполнитель")
async def worker_reg(message: types.Message):
    uid = str(message.from_user.id)
    db["users"][uid] = {"username": message.from_user.username or "Worker", "score": 0}
    save_data(db)
    await message.answer("✅ Вы исполнитель.", reply_markup=main_kb(message.from_user.id))

@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    if not db["users"]: return await message.answer("Пусто.")
    sorted_u = sorted(db["users"].values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Лидеры:**\n\n"
    for i, u in enumerate(sorted_u, 1):
        text += f"{i}. @{u.get('username')} — {u.get('score', 0)} баллов\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📋 Мои задания")
async def my_tasks(message: types.Message):
    uid = str(message.from_user.id)
    score = db["users"].get(uid, {}).get("score", 0)
    kb = ReplyKeyboardBuilder().button(text="🙋‍♂️ Запросить задание").button(text="❌ Отмена").adjust(1)
    await message.answer(f"Ваш рейтинг: {score} выполненных работ.\nЕсли у вас нет активных заданий, нажмите кнопку ниже.", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "🙋‍♂️ Запросить задание")
async def request_task(message: types.Message):
    text = f"📢 Исполнитель @{message.from_user.username} запрашивает работу!"
    for target in [db.get("admin_id"), db.get("owner_id")]:
        if target:
            try: await bot.send_message(target, text)
            except: pass
    await message.answer("Запрос отправлен руководству.")

@dp.message(F.text == "📢 Рассылка всем")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != db.get("owner_id"): return
    await message.answer("Введите сообщение для рассылки (текст/фото/видео):", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_broadcast)

@dp.message(Form.wait_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    count = 0
    for uid in db["users"].keys():
        try:
            await message.copy_to(int(uid))
            count += 1
        except: pass
    await state.clear()
    await message.answer(f"✅ Рассылка завершена. Получили: {count} чел.", reply_markup=main_kb(message.from_user.id))

@dp.message(F.text == "Дать задание")
async def task_init(message: types.Message, state: FSMContext):
    if message.from_user.id not in [db.get("admin_id"), db.get("owner_id")]: return
    await message.answer("Username исполнителя (без @):", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
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
        dt = datetime.strptime(message.text.replace("—", "-").strip(), "%Y-%m-%d %H:%M")
        target_uid = next((uid for uid, info in db["users"].items() if info.get("username", "").lower() == data["target"]), None)
        if target_uid:
            await bot.send_message(int(target_uid), f"📥 **НОВОЕ ЗАДАНИЕ!**\n{data['txt']}\n⏰ Срок: {message.text}", parse_mode="Markdown")
            reminders = [120, 60, 30]
            for m in reminders:
                trigger = dt - timedelta(minutes=m)
                if trigger > datetime.now():
                    scheduler.add_job(bot.send_message, 'date', run_date=trigger, args=[int(target_uid), f"⏰ До дедлайна {m} мин!"])
            await message.answer("✅ Задание отправлено.", reply_markup=main_kb(message.from_user.id))
        else: await message.answer("Исполнитель не найден.")
    except: await message.answer("Ошибка даты! Пример: 2025-01-01 12:00")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_init(message: types.Message, state: FSMContext):
    await message.answer("Пришлите ваш отчет:", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def report_done(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    if uid in db["users"]:
        db["users"][uid]["score"] += 1
        save_data(db)
    targets = list(set(filter(None, [db.get("admin_id"), db.get("owner_id")])))
    for r_id in targets:
        if r_id != message.from_user.id:
            try:
                await bot.send_message(r_id, f"✅ ОТЧЕТ от @{message.from_user.username}:")
                await message.copy_to(r_id)
            except: pass
    await message.answer("✅ Отправлено!", reply_markup=main_kb(message.from_user.id))
    await state.clear()

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
