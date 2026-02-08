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
    if not os.path.exists(DATA_FILE): return default
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            c = f.read().strip()
            if not c: return default
            data = json.loads(c)
            if "tasks" not in data: data["tasks"] = []
            return data
    except: return default

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
        await message.answer("Роль сброшена.")
    await message.answer("Главное меню:", reply_markup=main_kb(uid))

# --- ЛОГИКА АВТОРИЗАЦИИ ---
@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def role_pass(message: types.Message, state: FSMContext):
    await state.update_data(role=message.text)
    await message.answer(f"Введите пароль:", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_pass(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role, uid = data.get("role"), message.from_user.id
    pwd = OWNER_PASSWORD if role == "Я Создатель" else ADMIN_PASSWORD
    if message.text == pwd:
        if role == "Я Создатель": db["owner_id"] = uid
        else: db["admin_id"] = uid
        db["users"][str(uid)] = {"username": message.from_user.username or "User", "score": 0}
        save_data(db)
        await state.clear()
        await message.answer(f"✅ Доступ {role} открыт!", reply_markup=main_kb(uid))
    else: await message.answer("❌ Неверно.")

@dp.message(F.text == "Я Исполнитель")
async def worker_reg(message: types.Message):
    db["users"][str(message.from_user.id)] = {"username": message.from_user.username or "Worker", "score": 0}
    save_data(db)
    await message.answer("✅ Вы зарегистрированы!", reply_markup=main_kb(message.from_user.id))

# --- РАБОТА С ЗАДАНИЯМИ ---
@dp.message(F.text == "Дать задание")
async def task_init(message: types.Message, state: FSMContext):
    if message.from_user.id not in [db.get("admin_id"), db.get("owner_id")]: return
    await message.answer("Кому? (username без @):", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def task_user(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text.replace("@", "").strip().lower())
    await message.answer("Прикрепите файлы и напишите текст задания:")
    await state.set_state(Form.wait_task_content)

@dp.message(Form.wait_task_content)
async def task_content(message: types.Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, task_text=message.text or message.caption or "Файл без описания")
    await message.answer("Дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ):")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def task_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        dt_str = message.text.replace("—", "-").strip()
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        t_uid = next((u for u, i in db["users"].items() if i.get("username", "").lower() == data["target"]), None)
        if t_uid:
            t_id = len(db["tasks"])
            db["tasks"].append({
                "id": t_id, "worker": t_uid, "content_msg": data["msg_id"], 
                "deadline": dt_str, "status": "active", "boss_id": message.from_user.id,
                "desc": data["task_text"][:30] + "..."
            })
            save_data(db)
            await bot.send_message(int(t_uid), f"📥 **ВАМ ДАЛИ ЗАДАНИЕ!**\nСрок: {dt_str}\nПросмотр в '📋 Мои задания'")
            await message.answer("✅ Отправлено.", reply_markup=main_kb(message.from_user.id))
        else: await message.answer("Исполнитель не найден.")
    except: await message.answer("Ошибка даты.")
    await state.clear()

@dp.message(F.text == "📋 Мои задания")
async def my_tasks(message: types.Message):
    uid = str(message.from_user.id)
    u_tasks = [t for t in db["tasks"] if t["worker"] == uid and t["status"] == "active"]
    if not u_tasks: return await message.answer("Активных заданий нет.")
    
    for t in u_tasks:
        ikb = InlineKeyboardBuilder().button(text="❓ Спросить по этому заданию", callback_data=f"ask_{t['id']}").as_markup()
        await bot.copy_message(message.chat.id, t["boss_id"], t["content_msg"])
        await message.answer(f"🆔 Задание №{t['id']}\n⏰ Срок: {t['deadline']}", reply_markup=ikb)

# --- СДАЧА РАБОТЫ (ВЫБОР ИЗ СПИСКА) ---
@dp.message(F.text == "✅ Сдать работу")
async def report_select(message: types.Message):
    uid = str(message.from_user.id)
    u_tasks = [t for t in db["tasks"] if t["worker"] == uid and t["status"] == "active"]
    if not u_tasks: return await message.answer("Вам нечего сдавать.")
    
    ikb = InlineKeyboardBuilder()
    for t in u_tasks:
        ikb.button(text=f"Задание №{t['id']}: {t['desc']}", callback_data=f"submit_{t['id']}")
    ikb.adjust(1)
    await message.answer("Выберите задание, по которому сдаете отчет:", reply_markup=ikb.as_markup())

@dp.callback_query(F.data.startswith("submit_"))
async def report_init(callback: types.CallbackQuery, state: FSMContext):
    t_id = int(callback.data.split("_")[1])
    await state.update_data(submit_task_id=t_id)
    await callback.message.answer(f"Пришлите отчет по заданию №{t_id} (текст/фото/файл):", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def report_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    t_id = data["submit_task_id"]
    uid = str(message.from_user.id)
    
    # Обновляем статус задания и баллы
    task = next((t for t in db["tasks"] if t["id"] == t_id), None)
    if task:
        task["status"] = "completed"
        db["users"][uid]["score"] += 1
        save_data(db)
        
        info = f"✅ **ОТЧЕТ ПРИНЯТ**\nОт: @{message.from_user.username}\nЗадание №{t_id}: {task['desc']}"
        targets = list(set(filter(None, [db.get("admin_id"), db.get("owner_id")])))
        for r_id in targets:
            if r_id != message.from_user.id:
                try:
                    await bot.send_message(r_id, info)
                    await message.copy_to(r_id)
                except: pass
        await message.answer("✅ Работа сдана и удалена из списка активных!", reply_markup=main_kb(message.from_user.id))
    await state.clear()

# --- ВОПРОСЫ И ОТВЕТЫ ---
@dp.callback_query(F.data.startswith("ask_"))
async def ask_click(callback: types.CallbackQuery, state: FSMContext):
    t_id = callback.data.split("_")[1]
    await state.update_data(ask_task_id=t_id)
    await callback.message.answer(f"Введите вопрос по заданию №{t_id}:")
    await state.set_state(Form.wait_question)

@dp.message(Form.wait_question)
async def send_q(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task = next((t for t in db["tasks"] if t["id"] == int(data['ask_task_id'])), None)
    q_text = f"❓ **ВОПРОС**\nОт: @{message.from_user.username}\nЗадание №{data['ask_task_id']} ({task['desc'] if task else ''})\n\nТекст: {message.text}"
    ikb = InlineKeyboardBuilder().button(text="✍️ Ответить", callback_data=f"reply_{message.from_user.id}").as_markup()
    for target in filter(None, [db.get("admin_id"), db.get("owner_id")]):
        try: await bot.send_message(target, q_text, reply_markup=ikb)
        except: pass
    await message.answer("✅ Отправлено.")
    await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def reply_click(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(reply_to=callback.data.split("_")[1])
    await callback.message.answer("Введите ответ:")
    await state.set_state(Form.wait_answer)

@dp.message(Form.wait_answer)
async def send_a(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(int(data['reply_to']), f"✉️ **ОТВЕТ:**\n{message.text}")
        await message.answer("✅ Доставлено.")
    except: pass
    await state.clear()

@dp.message(F.text == "🏆 Таблица лидеров")
async def leaderboard(message: types.Message):
    if not db["users"]: return await message.answer("Пусто.")
    sorted_u = sorted(db["users"].values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Лидеры:**\n\n" + "\n".join([f"{i}. @{u['username']} — {u['score']}" for i, u in enumerate(sorted_u, 1)])
    await message.answer(text)

@dp.message(F.text == "📢 Рассылка")
async def broad_do(message: types.Message, state: FSMContext):
    if message.from_user.id != db.get("owner_id"): return
    await message.answer("Текст рассылки:")
    await state.set_state(Form.wait_broadcast)

@dp.message(Form.wait_broadcast)
async def broad_send(message: types.Message, state: FSMContext):
    for u in db["users"].keys():
        try: await message.copy_to(int(u))
        except: pass
    await state.clear()
    await message.answer("✅ Готово.")

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
