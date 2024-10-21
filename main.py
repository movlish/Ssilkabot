import logging
import re
import os
import asyncio
import phonenumbers
from phonenumbers import geocoder, carrier
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from aiogram.filters import Command

# Load environment variables
load_dotenv()

# Get values from environment
API_TOKEN = os.getenv('API_TOKEN')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS').split(',')))  # Process list of IDs
DATABASE_URL = os.getenv('SQLALCHEMY_URL')

# Set up logging
logging.basicConfig(level=logging.INFO)

# Create the model and database
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True)
    user_name = Column(String)

# Create a database connection
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Create tables
async def init_db():
    async with engine.begin() as conn:
        logging.info("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        logging.info("Tables created successfully.")

# Initialize database
asyncio.run(init_db())

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Set commands
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="admin", description="Admin panel"),
        BotCommand(command="id", description="Get your ID")
    ]
    await bot.set_my_commands(commands)

# Function to format phone number
def format_phone_number(phone_number: str) -> str:
    cleaned_number = re.sub(r'\D', '', phone_number)  # Remove non-numeric characters
    if len(cleaned_number) == 9:  # If the number consists of 9 digits
        cleaned_number = f'+998{cleaned_number}'  # Add country code for Uzbekistan
    elif not cleaned_number.startswith('+'):  # If it doesn't start with +
        cleaned_number = f'+{cleaned_number}'
    return cleaned_number

# Function to generate search URLs
def generate_search_urls(phone_number: str):
    query = f"{phone_number}"
    google_url = f"https://www.google.com/search?q={query}"
    yandex_url = f"https://yandex.com/search/?text={query}"
    youtube_url = f"https://www.youtube.com/results?search_query={query}"
    orginfo_url = f"https://orginfo.uz/uz/search/all/?q={query}" 
    reyting_url = f"https://reyting.mc.uz/new-ratings?type=0&page=1&stir={query}" 
    gov_uz_url = f"https://my.gov.uz/oz/service/all-services?ServiceFilterForm%5Ball_title%5D={query}" 
    return google_url, yandex_url, youtube_url, orginfo_url, reyting_url, gov_uz_url

# Function for getting phone info
def get_phone_info(phone_number: str):
    phone_number_obj = phonenumbers.parse(phone_number)
    country = geocoder.description_for_number(phone_number_obj, "en")
    operator = carrier.name_for_number(phone_number_obj, "en")
    return country, operator

# Function to generate Telegram link
def generate_telegram_link(phone_number: str) -> str:
    return f"https://t.me/{phone_number}"

# Function to generate WhatsApp link
def generate_whatsapp_link(phone_number: str) -> str:
    return f"https://wa.me/{phone_number}"

# Function for sending admin notifications
async def notify_admins(message: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message)
        except Exception as e:
            logging.error(f"Failed to send message to admin {admin_id}: {e}")

# Handler for the /start command
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    username = message.from_user.username

    # Create Telegram profile link for the user
    if username:
        user_link = f'<a href="https://t.me/{username}">{user_name}</a>'
    else:
        user_link = f'{user_name} (Username Ð¾Ñ‚ÑÑƒÑ‚ÑÑ‚Ð²ÑƒÐµÑ‚)'

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(User).filter(User.user_id == user_id))
            existing_user = result.scalars().first()

            if not existing_user:
                new_user = User(user_id=user_id, user_name=user_name)
                session.add(new_user)
                await session.commit()

            # Count total users
            result = await session.execute(select(User.id))
            user_count = len(result.scalars().all())

    # Notify admin about new user
    await notify_admins(
        f"User {user_link} (ID: {user_id}) started the bot. Total users: {user_count}"
    )

    # Reply to the user
    if user_id in ADMIN_IDS:
        await message.answer("ÐŸÑ€Ð¸Ð²ÐµÑ‚, Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¾Ñ€! Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹Ñ‚Ðµ ÐºÐ¾Ð¼Ð°Ð½Ð´Ñƒ /admin Ð´Ð»Ñ Ð¾Ñ‚Ð¿Ñ€Ð°Ð²ÐºÐ¸ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ð¹ Ð²ÑÐµÐ¼ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»ÑÐ¼.")
    else:
        await message.answer("ÐŸÑ€Ð¸Ð²ÐµÑ‚! ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ð¼Ð½Ðµ Ð»ÑŽÐ±Ð¾Ð¹ Ð½Ð¾Ð¼ÐµÑ€ Ñ‚ÐµÐ»ÐµÑ„Ð¾Ð½Ð°, Ð¸ Ñ ÑÐ¾Ð·Ð´Ð°Ð¼ ÑÑÑ‹Ð»ÐºÐ¸ Ð½Ð° Telegram Ð¸ WhatsApp.")




# Handle phone number input
@dp.message()
async def handle_phone_number(message: types.Message):
    phone_number = message.text.strip()
    formatted_phone_number = format_phone_number(phone_number)

    logging.info(f"Received phone number: {phone_number}")
    logging.info(f"Formatted phone number: {formatted_phone_number}")

    # Remove non-digit characters for checking
    cleaned_number = re.sub(r'\D', '', phone_number)

    try:
        phone_number_obj = phonenumbers.parse(formatted_phone_number)

        # Check if the number is valid
        if not phonenumbers.is_valid_number(phone_number_obj):
            # Handle the case when the number is not valid
            if len(cleaned_number) == 9:
                # Generate search URLs for the 9-digit number on reyting.mc.uz and orginfo.uz
                reyting_url = f"https://reyting.mc.uz/new-ratings?type=0&page=1&stir={cleaned_number}"
                orginfo_url = f"https://orginfo.uz/uz/search/all/?q={cleaned_number}"

                await message.reply(
                    f"ÐžÑˆÐ¸Ð±ÐºÐ°: ÐÐµÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½Ñ‹Ð¹ Ð½Ð¾Ð¼ÐµÑ€ Ñ‚ÐµÐ»ÐµÑ„Ð¾Ð½Ð°. ÐÐ¾ Ð½Ð¾Ð¼ÐµÑ€ ÑÐ¾Ð´ÐµÑ€Ð¶Ð¸Ñ‚ 9 Ñ†Ð¸Ñ„Ñ€.\n"
                    f"Ð’Ð¾Ñ‚ ÑÑÑ‹Ð»ÐºÐ¸ Ð´Ð»Ñ Ð¿Ð¾Ð¸ÑÐºÐ° Ð½Ð¾Ð¼ÐµÑ€Ð°:\n"
                    f"*Tashkilotlar reytingi haqida ma'lumot*ðŸ“Š [Reyting]({reyting_url})\n"
                    f"*Tashkilotlar haqida ma'lumot*ðŸ“‹ [Orginfo.uz]({orginfo_url})",
                    parse_mode='Markdown'
                )
                return  # Stop further processing
            else:
                raise ValueError("ÐÐµÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½Ñ‹Ð¹ Ð½Ð¾Ð¼ÐµÑ€ Ñ‚ÐµÐ»ÐµÑ„Ð¾Ð½Ð°.")
        
        # If the number is valid, proceed to gather additional info
        country = geocoder.description_for_number(phone_number_obj, "en")
        operator = carrier.name_for_number(phone_number_obj, "en")

        telegram_link = generate_telegram_link(formatted_phone_number)
        whatsapp_link = generate_whatsapp_link(formatted_phone_number)

        response = (
            f"Ð¢ÐµÐ»ÐµÑ„Ð¾Ð½: {formatted_phone_number}\n"
            f"Ð¡Ñ‚Ñ€Ð°Ð½Ð°: {country}\n"
            f"ÐžÐ¿ÐµÑ€Ð°Ñ‚Ð¾Ñ€: {operator}\n"
            f"Telegram: {telegram_link}\n"
            f"WhatsApp: {whatsapp_link}\n"
        )

        await message.reply(response, parse_mode='HTML')

    except phonenumbers.NumberParseException as e:
        logging.info(f"Cleaned number for parsing: {cleaned_number}")  # Log cleaned number

        if len(cleaned_number) == 9:
            # Generate search URLs for the 9-digit number on reyting.mc.uz and orginfo.uz
            reyting_url = f"https://reyting.mc.uz/new-ratings?type=0&page=1&stir={cleaned_number}"
            orginfo_url = f"https://orginfo.uz/uz/search/all/?q={cleaned_number}"

            await message.reply(
                f"ÐžÑˆÐ¸Ð±ÐºÐ°: ÐÐµÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½Ñ‹Ð¹ Ð½Ð¾Ð¼ÐµÑ€ Ñ‚ÐµÐ»ÐµÑ„Ð¾Ð½Ð°. ÐÐ¾ Ð½Ð¾Ð¼ÐµÑ€ ÑÐ¾Ð´ÐµÑ€Ð¶Ð¸Ñ‚ 9 Ñ†Ð¸Ñ„Ñ€.\n"
                f"Ð’Ð¾Ñ‚ ÑÑÑ‹Ð»ÐºÐ¸ Ð´Ð»Ñ Ð¿Ð¾Ð¸ÑÐºÐ° Ð½Ð¾Ð¼ÐµÑ€Ð°:\n"
                f"*Tashkilotlar reytingi haqida ma'lumot*ðŸ“Š [Reyting]({reyting_url})\n"
                f"*Tashkilotlar haqida*ðŸ“‹ [Orginfo.uz]({orginfo_url})",
                parse_mode='Markdown'
            )
        else:
            # Generate general search URLs if not 9 digits
            google_url = f"https://www.google.com/search?q={phone_number}"
            yandex_url = f"https://yandex.com/search/?text={phone_number}"
            youtube_url = f"https://www.youtube.com/results?search_query={phone_number}"
            orginfo_url = f"https://orginfo.uz/uz/search/all/?q={phone_number}"
            gov_uz_url = f"https://my.gov.uz/oz/service/all-services?ServiceFilterForm%5Ball_title%5D={phone_number}"

            search_response = (
                f"ÐžÑˆÐ¸Ð±ÐºÐ°: ÐÐµÐ²ÐµÑ€Ð½Ñ‹Ð¹ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚ Ð½Ð¾Ð¼ÐµÑ€Ð° Ñ‚ÐµÐ»ÐµÑ„Ð¾Ð½Ð°.\n"
                f"Ð’Ð¾Ñ‚ ÑÑÑ‹Ð»ÐºÐ¸ Ð´Ð»Ñ Ð¿Ð¾Ð¸ÑÐºÐ° Ð½Ð¾Ð¼ÐµÑ€Ð°:\n"
                f"ðŸ” [Google]({google_url})\n"
                f"ðŸ” [Yandex]({yandex_url})\n"
                f"ðŸŽ¥ [YouTube]({youtube_url})\n"
                f"*Tashkilot haqida malumot*ðŸ“‹ [Orginfo.uz]({orginfo_url})\n"
                f"*Hukumat portali*ðŸ“‹ [My.gov.uz]({gov_uz_url})\n"
            )
            await message.reply(search_response, parse_mode='Markdown')

        await notify_admins(f"Parsing error for number from user {message.from_user.id}: {str(e)}")
        logging.error(f"Parsing error: {e}")

    except ValueError as e:
        await message.reply(f"ÐžÑˆÐ¸Ð±ÐºÐ°: {str(e)}")
        await notify_admins(f"Validation error for number from user {message.from_user.id}: {str(e)}")

    except Exception as e:
        await message.reply(f"ÐžÑˆÐ¸Ð±ÐºÐ°: {str(e)}")
        await notify_admins(f"General error from user {message.from_user.id}: {str(e)}")


# Start the bot
async def main():
    try:
        await set_commands(bot)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
