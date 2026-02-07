import asyncio
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
# -----------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

users = {}  # {user_id: {'role': 'worker', 'username': '...'}}
admin_id = None

class Form(StatesGroup):
    wait_password = State()
    wait_task_username = State()
    wait_task_text = State()
    wait_task_deadline = State()
    wait_report = State()

def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Я Глава")
    kb.button(text="Я Исполнитель")
    kb.button(text="Сбросить мою роль")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def cancel_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True)

async def send_reminder(chat_id, text):
    try:
        await bot.send_message(chat_id, f"⏰ НАПОМИНАНИЕ: {text}")
    except:
        pass

@dp.message(Command("start"))
@dp.message(F.text == "❌ Отмена")
@dp.message(F.text == "Сбросить мою роль")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    if message.text == "Сбросить мою роль":
        users.pop(message.from_user.id, None)
    await message.answer("Выберите вашу роль или действие:", reply_markup=main_kb())

@dp.message(F.text == "Я Глава")
async def ask_password(message: types.Message, state: FSMContext):
    await message.answer("Введите пароль доступа:", reply_markup=cancel_kb())
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    global admin_id
    if message.text == ADMIN_PASSWORD:
        admin_id = message.from_user.id
        await state.clear()
        kb = ReplyKeyboardBuilder()
        kb.button(text="Дать задание")
        kb.button(text="Сбросить мою роль")
        await message.answer("Доступ разрешен, Глава.", reply_markup=kb.as_markup(resize_keyboard=True))
    else:
        await message.answer("Неверно. Попробуйте еще раз или нажмите Отмена.")

@dp.message(F.text == "Я Исполнитель")
async def worker_login(message: types.Message):
    users[message.from_user.id] = {'username': message.from_user.username, 'role': 'worker'}
    await message.answer("Вы зарегистрированы как исполнитель. Ждите заданий.", reply_markup=main_kb())
    if admin_id:
        await bot.send_message(admin_id, f"⚡️ Исполнитель @{message.from_user.username} в сети!")

@dp.message(F.text == "Дать задание")
async def task_start(message: types.Message, state: FSMContext):
    if message.from_user.id != admin_id: return
    await message.answer("Введите username исполнителя (без @):", reply_markup=cancel_kb())
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def task_user(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text)
    await message.answer("Опишите задание:")
    await state.set_state(Form.wait_task_text)

@dp.message(Form.wait_task_text)
async def task_text(message: types.Message, state: FSMContext):
    await state.update_data(txt=message.text)
    await message.answer("Укажите дедлайн в формате ГГГГ-ММ-ДД ЧЧ:ММ\nПример: 2025-06-20 18:00")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def task_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        deadline_dt = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
    except:
        await message.answer("❌ Ошибка формата! Введи дату как в примере: 2025-06-20 18:00")
        return

    target_id = next((uid for uid, info in users.items() if info['username'] == data['target']), None)
    
    if target_id:
        kb = ReplyKeyboardBuilder()
        kb.button(text="Сдать работу")
        await bot.send_message(target_id, f"📥 ЗАДАНИЕ: {data['txt']}\nСрок: {message.text}", 
                               reply_markup=kb.as_markup(resize_keyboard=True))
        
        # Планируем напоминания
        for minutes in [120, 60, 30]:
            rem_time = deadline_dt - timedelta(minutes=minutes)
            if rem_time > datetime.now():
                scheduler.add_job(send_reminder, 'date', run_date=rem_time, 
                                  args=[target_id, f"До дедлайна осталось {minutes} мин!"])
        
        await message.answer("Задание отправлено и напоминания установлены!")
    else:
        await message.answer("Исполнитель не найден.")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_start(message: types.Message, state: FSMContext):
    await message.answer("Пришлите ваш отчет (текст, фото или файл):", reply_markup=cancel_kb())
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def get_report(message: types.Message, state: FSMContext):
    if admin_id:
        await bot.send_message(admin_id, f"✅ Отчет от @{message.from_user.username}:")
        await message.copy_to(admin_id)
        await message.answer("Отправлено!", reply_markup=main_kb())
    await state.clear()

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
