import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
 breathes import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- НАСТРОЙКИ ---
API_TOKEN = '8534127751:AAGPOa9Fy4zm64iv7JkM8ohY6ennGPC-SGE'
ADMIN_PASSWORD = '090180'
# -----------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

users = {}  # {user_id: {'role': 'worker', 'username': '...'}}
stats = {}  # {user_id: count} - статистика выполненных работ
admin_id = None

class Form(StatesGroup):
    wait_password = State()
    wait_task_username = State()
    wait_task_text = State()
    wait_task_deadline = State()
    wait_report = State()

# --- КЛАВИАТУРЫ ---

def main_kb(user_id):
    kb = ReplyKeyboardBuilder()
    role = users.get(user_id, {}).get('role')
    
    if role == 'admin':
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
    
