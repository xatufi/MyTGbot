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
            if "users" not in data: data["users"] = {}
            if "tasks" not in data: data["tasks"] = []
            return data
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
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
    
    # Проверяем роли с защитой .get()
    is_owner = (uid == db.get("owner_id"))
    is_admin = (uid == db.get("admin_id"))
    is_worker = (u_str in db.get("users", {}))

    if is_owner:
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="📢 Рассылка"))
        builder.row(types.KeyboardButton(text="📋 Мои задания"), types.KeyboardButton(text="Сдать работу"))
        builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"), types.KeyboardButton(text="🔄 Сброс"))
    elif is_admin:
        builder.row(types.KeyboardButton(text="Дать задание"), types.KeyboardButton(text="🏆 Таблица лидеров"))
        builder.row(types.KeyboardButton(text="🔄 Сброс"))
    elif is_worker:
        builder.row(types.KeyboardButton(text="📋 Мои задания"), types.KeyboardButton(text="Сдать работу"))
        builder.row(types.KeyboardButton(text="🏆 Таблица лидеров"), types.KeyboardButton(text="🔄 Сброс"))
    else:
        builder.row(types.KeyboardButton(text="Я Создатель"), types.KeyboardButton(text="Я Глава"))
        builder.row(types.KeyboardButton(text="Я Исполнитель"))
    
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
    await message.answer("Меню:", reply_markup=main_kb(uid))

@dp.message(F.text.in_({"Я Глава", "Я Создатель"}))
async def role_pass(message: types.Message, state: FSMContext):
    await state.update_data(role=message.text)
    await message.answer(f"Пароль:", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_pass(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role, uid = data.get("role"), message.from_user.id
    pwd = OWNER_PASSWORD if role == "Я Создатель" else ADMIN_PASSWORD
    
    if message.text == pwd:
        if role == "Я Создатель": db["owner_id"] = uid
        else: db["admin_id"] = uid
        # Руководство тоже может быть исполнителем
        db["users"][str(uid)] = {"username": message.from_user.username or "Boss", "score": 0}
        save_data(db)
        await state.clear()
        await message.answer(f"✅ Доступ {role} разрешен!", reply_markup=main_kb(uid))
    else:
        await message.answer("❌ Неверный пароль.")

@dp.message(F.text == "Я Исполнитель")
async def worker_reg(message: types.Message):
    db["users"][str(message.from_user.id)] = {"username": message.from_user.username or "Worker", "score": 0}
    save_data(db)
    await message.answer("✅ Вы зарегистрированы как исполнитель.", reply_markup=main_kb(message.from_user.id))

@dp.message(F.text == "🏆 Таблица лидеров")
async def show_leaderboard(message: types.Message):
    usrs = db.get("users", {})
    if not usrs: return await message.answer("Список пуст.")
    sorted_u = sorted(usrs.values(), key=lambda x: x.get('score', 0), reverse=True)
    text = "🏆 **Лидеры:**\n\n"
    for i, u in enumerate(sorted_u, 1):
        text += f"{i}. @{u.get('username')} — {u.get('score', 0)} баллов\n"
    await message.answer(text, parse_mode="Markdown")

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
    await state.update_data(msg_id=message.message_id)
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
            task_entry = {"id": len(db["tasks"]), "worker": t_uid, "content_msg": data["msg_id"], "deadline": dt_str, "status": "active", "boss_id": message.from_user.id}
            db["tasks"].append(task_entry)
            save_data(db)
            await bot.send_message(int(t_uid), f"📥 **НОВОЕ ЗАДАНИЕ!**\nСрок: {dt_str}\nСмотрите в '📋 Мои задания'")
            
            # Напоминания
            for m in [120, 60, 30]:
                rem_t = dt - timedelta(minutes=m)
                if rem_t > datetime.now():
                    scheduler.add_job(bot.send_message, 'date', run_date=rem_t, args=[int(t_uid), f"⏰ До дедлайна {m} мин!"])
            
            await message.answer("✅ Отправлено.", reply_markup=main_kb(message.from_user.id))
        else: await message.answer("Исполнитель не найден.")
    except: await message.answer("Ошибка даты.")
    await state.clear()

@dp.message(F.text == "📋 Мои задания")
async def my_tasks(message: types.Message):
    uid = str(message.from_user.id)
    u_tasks = [t for t in db["tasks"] if t["worker"] == uid and t["status"] == "active"]
    if not u_tasks: return await message.answer("Заданий нет.")
    
    for t in u_tasks:
        ikb = InlineKeyboardBuilder().button(text="❓ Спросить", callback_data=f"ask_{t['id']}").as_markup()
        await bot.copy_message(message.chat.id, t["boss_id"], t["content_msg"])
        await message.answer(f"⏰ Срок: {t['deadline']}", reply_markup=ikb)

@dp.callback_query(F.data.startswith("ask_"))
async def ask_click(callback: types.CallbackQuery, state: FSMContext):
    t_id = callback.data.split("_")[1]
    await state.update_data(ask_task_id=t_id)
    await callback.message.answer("Ваш вопрос руководству:")
    await state.set_state(Form.wait_question)

@dp.message(Form.wait_question)
async def send_q(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_text = f"❓ **ВОПРОС (Задание #{data['ask_task_id']})**\nОт: @{message.from_user.username}\nТекст: {message.text}"
    ikb = InlineKeyboardBuilder().button(text="✍️ Ответить", callback_data=f"reply_{message.from_user.id}").as_markup()
    
    for target in filter(None, [db.get("admin_id"), db.get("owner_id")]):
        try: await bot.send_message(target, q_text, reply_markup=ikb)
        except: pass
    await message.answer("✅ Отправлено.", reply_markup=main_kb(message.from_user.id))
    await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def reply_click(callback: types.CallbackQuery, state: FSMContext):
    target_id = callback.data.split("_")[1]
    await state.update_data(reply_to=target_id)
    await callback.message.answer("Введите ответ исполнителю:")
    await state.set_state(Form.wait_answer)

@dp.message(Form.wait_answer)
async def send_a(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(int(data['reply_to']), f"✉️ **ОТВЕТ от руководства:**\n\n{message.text}")
        await message.answer("✅ Доставлено.")
    except: await message.answer("❌ Ошибка доставки.")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_init(message: types.Message, state: FSMContext):
    await message.answer("Пришлите отчет:", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def report_done(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    if uid in db["users"]:
        db["users"][uid]["score"] += 1
        save_data(db)
    for r_id in filter(None, [db.get("admin_id"), db.get("owner_id")]):
        if r_id != message.from_user.id:
            try:
                await bot.send_message(r_id, f"✅ ОТЧЕТ от @{message.from_user.username}:")
                await message.copy_to(r_id)
            except: pass
    await message.answer("✅ Сдано!", reply_markup=main_kb(message.from_user.id))
    await state.clear()

@dp.message(F.text == "📢 Рассылка")
async def broad_init(message: types.Message, state: FSMContext):
    if message.from_user.id != db.get("owner_id"): return
    await message.answer("Текст рассылки:", reply_markup=ReplyKeyboardBuilder().button(text="❌ Отмена").as_markup(resize_keyboard=True))
    await state.set_state(Form.wait_broadcast)

@dp.message(Form.wait_broadcast)
async def broad_do(message: types.Message, state: FSMContext):
    for u in db["users"].keys():
        try: await message.copy_to(int(u))
        except: pass
    await state.clear()
    await message.answer("✅ Готово.", reply_markup=main_kb(message.from_user.id))

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
