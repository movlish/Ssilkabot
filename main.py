import logging
import re
import os
import asyncio
import phonenumbers
from phonenumbers import geocoder, carrier
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from aiogram.filters import Command

# Загрузка переменных окружения
load_dotenv()

# Получение значений переменных
API_TOKEN = os.getenv('API_TOKEN')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS').split(',')))  # Обработка списка ID
DATABASE_URL = os.getenv('SQLALCHEMY_URL')

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Создание модели и базы данных
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True)
    user_name = Column(String)

# Создание подключения к базе данных
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Создание таблиц
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Инициализация базы данных
asyncio.run(init_db())

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Установка команд
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="admin", description="Панель администратора"),
        BotCommand(command="id", description="Получение ID")
    ]
    await bot.set_my_commands(commands)

# Функция для проверки и форматирования номера
def format_phone_number(phone_number: str) -> str:
    cleaned_number = re.sub(r'\D', '', phone_number)  # Удаляем все нецифровые символы
    if len(cleaned_number) == 9:  # Если номер состоит из 9 цифр
        cleaned_number = f'+998{cleaned_number}'  # Добавляем код страны для Узбекистана
    elif not cleaned_number.startswith('+'):  # Если нет символа +
        cleaned_number = f'+{cleaned_number}'
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

# Функция для отправки сообщения админу
async def notify_admins(message: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message)
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

# Обработчик команды /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    username = message.from_user.username

    # Формирование ссылки на Telegram профиль пользователя через username
    if username:
        user_link = f'<a href="https://t.me/{username}">{user_name}</a>'
    else:
        user_link = f'{user_name} (Username отсутствует)'




    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Проверяем, существует ли пользователь
            result = await session.execute(
                select(User).filter(User.user_id == user_id)
            )
            existing_user = result.scalars().first()

            if not existing_user:
                new_user = User(user_id=user_id, user_name=user_name)
                session.add(new_user)
                await session.commit()

            # Подсчёт количества пользователей
            result = await session.execute(
                select(User.id)
            )
            user_count = len(result.scalars().all())

    # Отправка сообщения админу с ссылкой на профиль пользователя
    await notify_admins(
        f"Пользователь {user_link} (ID: {user_id}) нажал /start. Всего пользователей: {user_count}"
    )
    # Отправка сообщения админу
    # await notify_admins(f"Пользователь {user_name} (ID: {user_id}) нажал /start. Всего пользователей: {user_count}")




    # Ответ пользователю
    if user_id in ADMIN_IDS:
        await message.answer("Привет, администратор! Используйте команду /admin для отправки сообщений всем пользователям.")
    else:
        await message.answer("Привет! Отправьте мне любой номер телефона, и я создам ссылки на Telegram и WhatsApp.")

# Функция для отправки сообщений всем пользователям
async def broadcast_message(content: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.user_id))
        user_ids = [row[0] for row in result.fetchall()]

    if not user_ids:
        logging.warning("Нет пользователей для отправки сообщения.")
        return

    logging.info(f"Найдено {len(user_ids)} пользователей. Начинаем отправку сообщения.")

    # batch_size = 50  # Размер пакета сообщений
    # for i in range(0, len(user_ids), batch_size):
    #     batch = user_ids[i:i + batch_size]
    #     for user_id in batch:
    #         try:
    #             response = await bot.send_message(user_id, content)
    #             logging.info(f"Сообщение отправлено пользователю {user_id}. Ответ от API: {response}")
    #         except Exception as e:
    #             logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {string(e0}")
    async def send_message(user_id):
        try:
            await bot.send_message(user_id, content)
            logging.info(f"Сообщение отправлено пользователю {user_id}")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {str(e)}")

    await asyncio.gather(*[send_message(user_id) for user_id in user_ids])


    logging.info("Сообщение отправлено всем пользователям.")

class AdminStates(StatesGroup):
    waiting_for_message = State()

@dp.message(Command("admin"))
async def admin_command_handler(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User.user_id))
            user_ids = [row[0] for row in result.fetchall()]

        await message.answer(f"Введите сообщение, которое вы хотите отправить всем пользователям. Количество пользователей: {len(user_ids)}")
        await AdminStates.waiting_for_message.set()  # Устанавливаем состояние ожидания сообщения
    else:
        await message.answer("У вас нет доступа к этой команде.")

@dp.message(AdminStates.waiting_for_message)
async def handle_admin_message(message: types.Message, state: FSMContext):
    if message.from_user.id in ADMIN_IDS:
        content = message.text.strip()

        if content:
            await broadcast_message(content)
            await message.answer("Сообщение отправлено всем пользователям.")
        else:
            await message.answer("Сообщение не может быть пустым.")

        await state.clear()  # Очищаем состояние после отправки
    else:
        await message.answer("У вас нет доступа к этой команде.")
        await state.clear()  # На случай, если кто-то неадекватно использует



# /id yuborganda foydalanuvchining id sini chiqaradi
@dp.message(Command("id"))
async def cmd_start(message: types.Message):
    await message.answer(f'{message.from_user.id}')


# Обработка номера телефона для всех остальных случаев
@dp.message()
async def handle_phone_number(message: types.Message):
    phone_number = message.text.strip()
    formatted_phone_number = format_phone_number(phone_number)

    logging.info(f"Получен номер телефона: {phone_number}")
    logging.info(f"Форматированный номер телефона: {formatted_phone_number}")

    try:
        phone_number_obj = phonenumbers.parse(formatted_phone_number)
        if not phonenumbers.is_valid_number(phone_number_obj):
            raise ValueError("Некорректный номер телефона.")

        country = geocoder.description_for_number(phone_number_obj, "en")
        operator = carrier.name_for_number(phone_number_obj, "en")

        telegram_link = generate_telegram_link(formatted_phone_number)
        whatsapp_link = generate_whatsapp_link(formatted_phone_number)

        response = (
            f"Телефон: {formatted_phone_number}\n"
            f"Страна: {country}\n"
            f"Оператор: {operator}\n"
            f"Telegram: {telegram_link}\n"
            f"WhatsApp: {whatsapp_link}\n"
        )

        await message.reply(response, parse_mode='HTML')

    except phonenumbers.NumberParseException as e:
        await message.reply(f"Ошибка: Неверный формат номера телефона. Убедитесь, что номер в международном формате.")
        await notify_admins(f"Ошибка разбора номера от пользователя {message.from_user.id}: {str(e)}")
        logging.error(f"Ошибка разбора номера: {e}")

    except ValueError as e:
        await message.reply(f"Ошибка: {str(e)}")
        await notify_admins(f"Ошибка проверки номера от пользователя {message.from_user.id}: {str(e)}")

    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")
        await notify_admins(f"Общая ошибка от пользователя {message.from_user.id}: {str(e)}")

# Функция для закрытия сессий
async def shutdown(bot: Bot):
    await bot.session.close()

# Точка входа
async def main():
    try:
        await set_commands(bot)
        await dp.start_polling(bot)
    finally:
        await shutdown(bot)

if __name__ == '__main__':
    asyncio.run(init_db())
    asyncio.run(main())
