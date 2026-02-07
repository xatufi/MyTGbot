import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
API_TOKEN = '8534127751:AAGPOa9Fy4zm64iv7JkM8ohY6ennGPC-SGE'
ADMIN_PASSWORD = '090180'
# -----------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# База данных в памяти (после перезагрузки обнулится)
users = {}  # {user_id: {'role': 'worker', 'username': '...'}}
tasks = []  # [{'worker_username': '...', 'text': '...', 'deadline': '...'}]
admin_id = None

class Form(StatesGroup):
    wait_password = State()
    wait_task_username = State()
    wait_task_text = State()
    wait_task_deadline = State()
    wait_report = State()

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = [
        [types.KeyboardButton(text="Я Глава")],
        [types.KeyboardButton(text="Я Исполнитель")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Добро пожаловать! Кто ты?", reply_markup=keyboard)

@dp.message(F.text == "Я Глава")
async def ask_password(message: types.Message, state: FSMContext):
    await message.answer("Введите пароль доступа:")
    await state.set_state(Form.wait_password)

@dp.message(Form.wait_password)
async def check_password(message: types.Message, state: FSMContext):
    global admin_id
    if message.text == ADMIN_PASSWORD:
        admin_id = message.from_user.id
        await state.clear()
        kb = [[types.KeyboardButton(text="Дать задание")]]
        await message.answer("Пароль верный, Глава. Ожидайте отчетов.", 
                             reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
    else:
        await message.answer("Неверно. Попробуй еще раз или выбери 'Исполнитель'")

@dp.message(F.text == "Я Исполнитель")
async def worker_login(message: types.Message):
    users[message.from_user.id] = {'username': message.from_user.username, 'role': 'worker'}
    await message.answer("Вы вошли как исполнитель. Ждите заданий.")
    if admin_id:
        await bot.send_message(admin_id, f"⚡️ Исполнитель @{message.from_user.username} в сети!")

@dp.message(F.text == "Дать задание")
async def task_start(message: types.Message, state: FSMContext):
    if message.from_user.id != admin_id: return
    await message.answer("Введите username исполнителя (без @):")
    await state.set_state(Form.wait_task_username)

@dp.message(Form.wait_task_username)
async def task_user(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text)
    await message.answer("Опишите задание:")
    await state.set_state(Form.wait_task_text)

@dp.message(Form.wait_task_text)
async def task_text(message: types.Message, state: FSMContext):
    await state.update_data(txt=message.text)
    await message.answer("Укажите дедлайн (например, 18:00):")
    await state.set_state(Form.wait_task_deadline)

@dp.message(Form.wait_task_deadline)
async def task_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_username = data['target']
    
    # Поиск ID исполнителя по username в нашей мини-базе
    target_id = next((uid for uid, info in users.items() if info['username'] == target_username), None)
    
    if target_id:
        kb = [[types.KeyboardButton(text="Сдать работу")]]
        await bot.send_message(target_id, f"📥 НОВОЕ ЗАДАНИЕ!\n{data['txt']}\nДедлайн: {message.text}",
                               reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
        await message.answer("Задание отправлено!")
    else:
        await message.answer("Исполнитель еще не зашел в бот. Задание не доставлено.")
    await state.clear()

@dp.message(F.text == "Сдать работу")
async def report_start(message: types.Message, state: FSMContext):
    await message.answer("Пришлите ваш отчет (текст, фото или файл):")
    await state.set_state(Form.wait_report)

@dp.message(Form.wait_report)
async def get_report(message: types.Message, state: FSMContext):
    if admin_id:
        await bot.send_message(admin_id, f"✅ Отчет от @{message.from_user.username}:")
        await message.copy_to(admin_id) # Пересылает сообщение как есть (фото, текст и т.д.)
        await message.answer("Работа отправлена главе!")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
