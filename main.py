import asyncio
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
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
    default = {"users": {}, "admin_id": None, "owner_id": None, "tasks": []}
    if not os.path.exists(DATA_FILE):
        return default
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content: return default
            data = json.loads(content)
            # Гарантируем наличие всех ключей
            for key in default:
                if key not in data:
                    data[key] = default[key]
            return data
    except Exception:
        return default

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_data()

class Form(StatesGroup):
    wait_password = State()
    wait_task_username = State()
    wait_task_content = State()
    wait_task_deadline = State()
    wait_report = State()
    wait_broadcast = State()
    wait_question = State()
    wait_answer = State()

def main_kb(uid):
    builder = ReplyKeyboardBuilder()
    u_str = str(uid)
    
    is_owner = (uid == db.get("owner_id"))
    is_admin = (uid == db.get("admin_id"))
    is_worker = (u_str in db.get("users", {}))

    if is_owner:
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="📢 Рассылка"))
        builder.row(types.KeyboardButton(text="📋 Мои задания"), types.KeyboardButton(text="✅ Сдать работу"))
        builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"), types.KeyboardButton(text="🔄 Сброс"))
    elif is_admin:
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="🏆 Таблица лидеров"))
        builder.row(types.KeyboardButton(text="🔄 Сброс"))
    elif is_worker:
        builder.row(types.KeyboardButton(text="📋 Мои задания"), types.KeyboardButton(text="✅ Сдать работу"))
        builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"), types.KeyboardButton(text="🔄 Сброс"))
    else:
        builder.row(types.KeyboardButton(text="Я Создатель"), types.KeyboardButton(text="Я Глава"), types.KeyboardButton(text="Я Исполнитель"))
    
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
@dp.message(F.text == "❌ Отмена")
@dp.message(F.text == "🔄 Сброс")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if message.text == "🔄 Сброс":
        db["users"].pop(str(uid), None)
        if db.get("admin_id") == uid: db["admin_id"] = None
        if db.get("owner_id") == uid: db["owner_id"] = None
        save_data(db)
        await message.answer("Все ваши данные и роль в этом боте сброшены.")
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=main_kb(uid))

@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def role_pass(message: types.Message, state: FSMContext):
    await state.update_data(role=message.text)
    await message.answer(f"Введите пароль доступа:", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_pass(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    role = state_data.get("role")
    uid = message.from_user.id
    u_str = str(uid)
    
    correct_pwd = OWNER_PASSWORD if role == "Я Создатель" else ADMIN_PASSWORD
    
    if message.text == correct_pwd:
        if role == "Я Создатель":
            db["owner_id"] = uid
        else:
            db["admin_id"] = uid
        
        # Авто-регистрация в списке пользователей для таблицы лидеров
        if "users" not in db: db["users"] = {}
        if u_str not in db["users"]:
            db["users"][u_str] = {"username": message.from_user.username or "Boss", "score": 0}
            
        save_data(db)
        await state.clear()
        await message.answer(f"✅ Доступ {role} подтвержден!", reply_markup=main_kb(uid))
    else:
        await message.answer("❌ Неверный пароль. Попробуйте еще раз или нажмите /start")

@dp.message(F.text == "Я Исполнитель")
async def worker_reg(message: types.Message):
    u_str = str(message.from_user.id)
    if "users" not in db: db["users"] = {}
    db["users"][u_str] = {"username": message.from_user.username or "Worker", "score": 0}
    save_data(db)
    await message.answer("✅ Вы зарегистрированы как исполнитель.", reply_markup=main_kb(message.from_user.id))

@dp.message(F.text == "Дать задание")
async def task_init(message: types.Message, state: FSMContext):
    if message.from_user.id not in [db.get("admin_id"), db.get("owner_id")]: return
    await message.answer("Введите username исполнителя (без @):", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def task_user(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text.replace("@", "").strip().lower())
    await message.answer("Прикрепите файлы (фото/док) и напишите текст задания в одном сообщении:")
    await state.set_state(Form.wait_task_content)

@dp.message(Form.wait_task_content)
async def task_content(message: types.Message, state: FSMContext):
    task_desc = message.text or message.caption or "Файл без описания"
    await state.update_data(msg_id=message.message_id, task_text=task_desc)
    await message.answer("Введите дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ):")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def task_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        clean_date = message.text.replace("—", "-").strip()
        dt = datetime.strptime(clean_date, "%Y-%m-%d %H:%M")
        
        target_uid = None
        for uid, info in db.get("users", {}).items():
            if info.get("username", "").lower() == data["target"]:
                target_uid = uid
                break
        
        if target_uid:
            t_id = len(db["tasks"])
            db["tasks"].append({
                "id": t_id, "worker": target_uid, "content_msg": data["msg_id"], 
                "deadline": clean_date, "status": "active", "boss_id": message.from_user.id,
                "desc": data["task_text"][:30] + "..."
            })
            save_data(db)
            await bot.send_message(int(target_uid), f"📥 **ВАМ ПРИШЛО ЗАДАНИЕ!**\nСрок: {clean_date}\nСмотрите подробности в '📋 Мои задания'")
            
            # Напоминания
            remind_m =
            for m in remind_m:
                rem_t = dt - timedelta(minutes=m)
                if rem_t > datetime.now():
                    scheduler.add_job(bot.send_message, 'date', run_date=rem_t, args=[int(target_uid), f"⏰ Напоминание! До дедлайна {m} мин."])
            
            await message.answer("✅ Задание успешно отправлено.", reply_markup=main_kb(message.from_user.id))
        else:
            await message.answer("❌ Исполнитель не найден. Убедитесь, что он нажал кнопку 'Я Исполнитель'.")
    except Exception:
        await message.answer("❌ Ошибка в дате. Пример: 2025-05-20 18:00")
    await state.clear()

@dp.message(F.text == "📋 Мои задания")
async def my_tasks(message: types.Message):
    u_str = str(message.from_user.id)
    u_tasks = [t for t in db.get("tasks", []) if t["worker"] == u_str and t["status"] == "active"]
    if not u_tasks: return await message.answer("У вас нет активных заданий.")
    
    for t in u_tasks:
        ikb = InlineKeyboardBuilder().button(text="❓ Задать вопрос", callback_data=f"ask_{t['id']}").as_markup()
        await bot.copy_message(message.chat.id, t["boss_id"], t["content_msg"])
        await message.answer(f"🆔 Задание №{t['id']}\n⏰ Дедлайн: {t['deadline']}", reply_markup=ikb)

@dp.message(F.text == "✅ Сдать работу")
async def report_select(message: types.Message):
    u_str = str(message.from_user.id)
    u_tasks = [t for t in db.get("tasks", []) if t["worker"] == u_str and t["status"] == "active"]
    if not u_tasks: return await message.answer("Список активных заданий пуст.")
    
    ikb = InlineKeyboardBuilder()
    for t in u_tasks:
        ikb.button(text=f"Задание №{t['id']}", callback_data=f"submit_{t['id']}")
    ikb.adjust(1)
    await message.answer("Выберите задание для сдачи отчета:", reply_markup=ikb.as_markup())

@dp.callback_query(F.data.startswith("submit_"))
async def report_init(callback: types.CallbackQuery, state: FSMContext):
    t_id = int(callback.data.split("_"))
    await state.update_data(submit_task_id=t_id)
    await callback.message.answer(f"Пришлите отчет по заданию №{t_id} (текст, фото или файл):", 
                                 reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def report_done(message: types.Message, state: FSMContext):
    s_data = await state.get_data()
    t_id = s_data.get("submit_task_id")
    u_str = str(message.from_user.id)
    
    task = next((t for t in db["tasks"] if t["id"] == t_id), None)
    if task:
        task["status"] = "completed"
        if u_str in db["users"]:
            db["users"][u_str]["score"] = db["users"][u_str].get("score", 0) + 1
        save_data(db)
        
        info = f"✅ **ОТЧЕТ ПО ЗАДАНИЮ №{t_id}**\nИсполнитель: @{message.from_user.username}\nСуть задания: {task['desc']}"
        targets = set(filter(None, [db.get("admin_id"), db.get("owner_id")]))
        for r_id in targets:
            if r_id != message.from_user.id:
                try:
                    await bot.send_message(r_id, info)
                    await message.copy_to(r_id)
                except Exception: pass
        await message.answer("✅ Отчет успешно отправлен и задание закрыто!", reply_markup=main_kb(message.from_user.id))
    await state.clear()

@dp.callback_query(F.data.startswith("ask_"))
async def ask_click(callback: types.CallbackQuery, state: FSMContext):
    t_id = callback.data.split("_")
    await state.update_data(ask_task_id=t_id)
    await callback.message.answer(f"Введите ваш вопрос по заданию №{t_id}:")
    await state.set_state(Form.wait_question)

@dp.message(Form.wait_question)
async def send_q(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_text = f"❓ **ВОПРОС ПО ЗАДАНИЮ №{data['ask_task_id']}**\nОт: @{message.from_user.username}\nВопрос: {message.text}"
    ikb = InlineKeyboardBuilder().button(text="✍️ Ответить", callback_data=f"reply_{message.from_user.id}").as_markup()
    
    targets = set(filter(None, [db.get("admin_id"), db.get("owner_id")]))
    for target in targets:
        try: await bot.send_message(target, q_text, reply_markup=ikb)
        except Exception: pass
    await message.answer("✅ Вопрос передан руководству.")
    await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def reply_click(callback: types.CallbackQuery, state: FSMContext):
    target_id = callback.data.split("_")
    await state.update_data(reply_to=target_id)
    await callback.message.answer("Введите ваш ответ исполнителю:")
    await state.set_state(Form.wait_answer)

@dp.message(Form.wait_answer)
async def send_a(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(int(data['reply_to']), f"✉️ **ОТВЕТ ОТ РУКОВОДСТВА:**\n\n{message.text}")
        await message.answer("✅ Ответ отправлен.")
    except Exception: await message.answer("❌ Ошибка доставки.")
    await state.clear()

@dp.message(F.text == "🏆 Таблица лидеров")
async def leaderboard(message: types.Message):
    usrs = db.get("users", {})
    if not usrs: return await message.answer("В таблице пока нет данных.")
    sorted_u = sorted(usrs.values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Рейтинг (выполненные задания):**\n\n"
    for i, u in enumerate(sorted_u, 1):
        text += f"{i}. @{u['username']} — {u['score']}\n"
    await message.answer(text)

@dp.message(F.text == "📢 Рассылка")
async def broad_start(message: types.Message, state: FSMContext):
    if message.from_user.id != db.get("owner_id"): return
    await message.answer("Отправьте сообщение для рассылки всем исполнителям:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_broadcast)

@dp.message(Form.wait_broadcast)
async def broad_send(message: types.Message, state: FSMContext):
    count = 0
    for u_id in db.get("users", {}).keys():
        try:
            await message.copy_to(int(u_id))
            count += 1
        except Exception: pass
    await state.clear()
    await message.answer(f"✅ Рассылка завершена. Получили: {count} чел.", reply_markup=main_kb(message.from_user.id))

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
