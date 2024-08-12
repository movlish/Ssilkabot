import logging
import re
import os
import sqlite3
import phonenumbers
from phonenumbers import geocoder, carrier
from aiogram import Bot, Dispatcher, types

from aiogram.enums.parse_mode import ParseMode
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from aiogram.fsm.state import State, StatesGroup
from pyrogram import Client
from aiogram.fsm.storage.memory import MemoryStorage
from app import database

from aiogram.filters import Command


# from database import User  # Импортируйте вашу модель User
# from loader import bot, dp  # Импортируйте bot и dp из вашего проекта
# from . import database  # Импортируем наш модуль для работы с базой данных
from dotenv import load_dotenv
from aiogram.types import BotCommand, BotCommandScopeDefault
load_dotenv()


# Получение значений переменных
API_TOKEN = os.getenv('API_TOKEN')
ADMIN_IDS = int(os.getenv('ADMIN_IDS'))
SQLALCHEMY_URL = os.getenv('SQLALCHEMY_URL')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')

# Список ID администраторов
# ADMIN_IDS = [123456789]  # Замените на реальные ID администраторов

# Создание таблицы пользователей, если она не существует
def create_table():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE
    )
    ''')
    conn.commit()
    conn.close()

# Добавление нового пользователя в базу данных
def add_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Пользователь уже существует в базе данных
    conn.close()

# Получение количества пользователей
def get_user_count():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Вызов создания таблицы при импорте модуля
create_table()



# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация Pyrogram Client
app = Client("my_account", api_id=API_ID, api_hash=API_HASH, phone_number=PHONE_NUMBER)

# Установка команд
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="admin", description="Панель администратора"),
        BotCommand(command="id", description="Получения для ID")
    ]
    await bot.set_my_commands(commands)




# Функция для валидации и форматирования номера телефона
def format_phone_number(phone_number: str) -> str:
    # Удаляем все символы, кроме цифр
    cleaned_number = re.sub(r'\D', '', phone_number)
    # Проверяем, есть ли "+" в начале, если нет, добавляем
    if not cleaned_number.startswith('+'):
        cleaned_number = '+' + cleaned_number
    return cleaned_number


# Функция для получения информации о номере телефона
def get_phone_info(phone_number: str):
    phone_number_obj = phonenumbers.parse(phone_number)
    country = geocoder.description_for_number(phone_number_obj, "en")
    operator = carrier.name_for_number(phone_number_obj, "en")
    return country, operator

# Функция для генерации ссылки на Telegram
def generate_telegram_link(phone_number: str) -> str:
    return f"https://t.me/{phone_number}"

# Функция для генерации ссылки на WhatsApp
def generate_whatsapp_link(phone_number: str) -> str:
    return f"https://wa.me/{phone_number}"

# Функция для получения информации о пользователе Telegram
async def get_telegram_user_info(user_id: int):
    try:
        user = await bot.get_chat(user_id)
        user_info = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "id": user.id
        }
        return user_info
    except Exception as e:
        return str(e)





# Стартовая команда
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_IDS:
        await message.answer("Привет, администратор! Используйте команду /admin для отправки сообщений всем пользователям.")
    else:
        await message.answer("Привет! Отправьте мне сообщение, содержащее номер телефона, и я проверю его существование и регистрацию в социальных сетях.")

# Состояния для администратора
class AdminStates(StatesGroup):
    waiting_for_message = State()

# Команда /admin для администратора
@dp.message(Command("admin"))
async def admin_command_handler(message: types.Message):
    if message.from_user.id == ADMIN_IDS:
        user_count = database.get_user_count()
        await message.answer(f"Введите сообщение, которое вы хотите отправить всем пользователям.   Количество пользователей: {user_count}")
        # await message.answer(f"Количество пользователей: {user_count}")
        await AdminStates.waiting_for_message.set()
    else:
        await message.answer("У вас нет доступа к этой команде.")


# /id yuborganda foydalanuvchining id sini chiqaradi
@dp.message(Command("id"))
async def cmd_start(message: types.Message):
    await message.answer(f'{message.from_user.id}')





# Обработка номера телефона от пользователя
@dp.message()
async def handle_phone_number(message: types.Message):
    phone_number = message.text.strip()
    formatted_phone_number = format_phone_number(phone_number)

    try:
        country, operator = get_phone_info(formatted_phone_number)
        
        telegram_link = generate_telegram_link(formatted_phone_number)
        whatsapp_link = generate_whatsapp_link(formatted_phone_number)
        # user_count = get_user_count()

        response = (
            f"Телефон: {formatted_phone_number}\n"
            f"Страна: {country}\n"
            f"Оператор: {operator}\n"
            f"Telegram: {telegram_link}\n"
            f"WhatsApp: {whatsapp_link}\n"
            # f"Количество пользователей: {user_count}"
        )
        
        await message.reply(response, parse_mode=ParseMode.HTML)
    
    except Exception as e:
        await message.reply(f"Ошибка: Отправьте номер телефона для получения информации.")



async def broadcast_message(content: str):
    user_ids = database.get_all_users()
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, content)
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

# Точка входа
async def main():
    await set_commands(bot)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())