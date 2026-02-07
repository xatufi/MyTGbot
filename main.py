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
    if not os.path.exists(DATA_FILE):
        return default
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return default
            data = json.loads(content)
            if "users" not in data:
                data["users"] = {}
            return data
    except Exception:
        return default

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения: {e}")

db = load_data()

class Form(StatesGroup):
    wait_password = State()
    wait_task_username = State()
    wait_task_text = State()
    wait_task_deadline = State()
    wait_report = State()

def main_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Я Создатель"), types.KeyboardButton(text="Я Глава"))
    builder.row(types.KeyboardButton(text="Я Исполнитель"))
    builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"), types.KeyboardButton(text="🔄 Сбросить роль"))
    return builder.as_markup(resize_keyboard=True)

def cancel_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
@dp.message(F.text == "❌ Отмена")
@dp.message(F.text == "🔄 Сбросить роль")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = str(message.from_user.id)
    if message.text == "🔄 Сбросить роль":
        if uid in db["users"]:
            del db["users"][uid]
        if db.get("admin_id") == message.from_user.id:
            db["admin_id"] = None
        if db.get("owner_id") == message.from_user.id:
            db["owner_id"] = None
        save_data(db)
        await message.answer("Ваша роль и данные сброшены.")
    
    await message.answer("Добро пожаловать! Выберите вашу роль в системе:", reply_markup=main_kb())

@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def process_role_choice(message: types.Message, state: FSMContext):
    await state.update_data(chosen_role=message.text)
    await message.answer(f"Введите пароль для роли '{message.text}':", reply_markup=cancel_kb())
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get("chosen_role")
    uid = message.from_user.id
    uid_s = str(uid)

    if role == "Я Создатель" and message.text == OWNER_PASSWORD:
        db["owner_id"] = uid
        if uid_s not in db["users"]:
            db["users"][uid_s] = {"username": message.from_user.username or "Boss", "score": 0}
        save_data(db)
        await state.clear()
        builder = ReplyKeyboardBuilder()
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="Сдать работу"))
        builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"), types.KeyboardButton(text="🔄 Сбросить роль"))
        await message.answer("✅ Авторизация успешна! Вы вошли как Создатель.", reply_markup=builder.as_markup(resize_keyboard=True))
    
    elif role == "Я Глава" and message.text == ADMIN_PASSWORD:
        db["admin_id"] = uid
        save_data(db)
        await state.clear()
        builder = ReplyKeyboardBuilder()
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="🏆 Таблица лидеров"))
        builder.row(types.KeyboardButton(text="🔄 Сбросить роль"))
        await message.answer("✅ Авторизация успешна! Вы вошли как Глава.", reply_markup=builder.as_markup(resize_keyboard=True))
    else:
        await message.answer("❌ Неверный пароль. Попробуйте еще раз или нажмите '❌ Отмена'.")

@dp.message(F.text == "Я Исполнитель")
async def worker_login(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"username": message.from_user.username or "Worker", "score": 0}
    save_data(db)
    await message.answer("✅ Вы успешно зарегистрированы как Исполнитель. Ожидайте заданий от руководства.")

@dp.message(F.text == "🏆 Таблица лидеров")
async def leaderboard(message: types.Message):
    if not db["users"]:
        return await message.answer("В базе пока нет исполнителей.")
    
    sorted_users = sorted(db["users"].values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Рейтинг исполнителей:**\n\n"
    for i, user in enumerate(sorted_users, 1):
        text += f"{i}. @{user.get('username')} — {user.get('score', 0)} вып. работ\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Дать задание")
async def task_init(message: types.Message, state: FSMContext):
    is_admin = message.from_user.id == db.get("admin_id")
    is_owner = message.from_user.id == db.get("owner_id")
    if not (is_admin or is_owner):
        return
    
    await message.answer("Введите @username исполнителя или просто имя пользователя (без @):", reply_markup=cancel_kb())
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def task_set_user(message: types.Message, state: FSMContext):
    target = message.text.replace("@", "").strip().lower()
    await state.update_data(target_user=target)
    await message.answer("Опишите суть задания:")
    await state.set_state(Form.wait_task_text)

@dp.message(Form.wait_task_text)
async def task_set_text(message: types.Message, state: FSMContext):
    await state.update_data(task_desc=message.text)
    await message.answer("Укажите дедлайн в формате: ГГГГ-ММ-ДД ЧЧ:ММ\nПример: 2025-05-25 14:00")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def task_finalize(message: types.Message, state: FSMContext):
    data = await state.get_data()
    date_str = message.text.replace("—", "-").strip()
    
    try:
        deadline_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return await message.answer("❌ Ошибка формата даты. Пожалуйста, используйте: ГГГГ-ММ-ДД ЧЧ:ММ")

    target_uid = None
    for uid, info in db["users"].items():
        if info.get("username", "").lower() == data["target_user"]:
            target_uid = int(uid)
            break
    
    if target_uid:
        builder = ReplyKeyboardBuilder()
        builder.row(types.KeyboardButton(text="Сдать работу"))
        await bot.send_message(target_uid, f"📥 **НОВОЕ ЗАДАНИЕ!**\n\n{data['task_desc']}\n\n⏰ Срок: {date_str}", reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")
        
        # Напоминания за 120, 60 и 30 минут
        reminders = [120, 60, 30]
        for minutes in reminders:
            trigger_time = deadline_dt - timedelta(minutes=minutes)
            if trigger_time > datetime.now():
                scheduler.add_job(bot.send_message, 'date', run_date=trigger_time, args=[target_uid, f"⏰ Напоминание! До дедлайна осталось {minutes} минут."])
        
        await message.answer(f"✅ Задание успешно отправлено пользователю @{data['target_user']}.", reply_markup=main_kb())
    else:
        await message.answer(f"❌ Пользователь @{data['target_user']} не найден. Он должен сначала зайти в бот и нажать 'Я Исполнитель'.")
    
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_init(message: types.Message, state: FSMContext):
    await message.answer("Отправьте отчет (текст, фото или файл):", reply_markup=cancel_kb())
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def report_receive(message: types.Message, state: FSMContext):
    uid_s = str(message.from_user.id)
    if uid_s in db["users"]:
        db["users"][uid_s]["score"] = db["users"][uid_s].get("score", 0) + 1
        save_data(db)
    
    caption = f"✅ **ОТЧЕТ ПО ЗАДАНИЮ** от @{message.from_user.username}:"
    
    recipients = []
    if db.get("admin_id"): recipients.append(db["admin_id"])
    if db.get("owner_id"): recipients.append(db["owner_id"])
    
    for r_id in set(recipients):
        if r_id != message.from_user.id:
            try:
                await bot.send_message(r_id, caption, parse_mode="Markdown")
                await message.copy_to(r_id)
            except Exception:
                pass
                
    await message.answer("✅ Ваша работа отправлена на проверку!", reply_markup=main_kb())
    await state.clear()

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
        
