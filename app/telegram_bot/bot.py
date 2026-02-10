import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.enums import ParseMode
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TEMLGRAM_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_CHAT_ID")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🏠 Добро пожаловать в RealtyHunter!\n\n"
        "Команды::\n"
        "/filters - текущие фильтры\n"
        "/search - запустить поиск\n"
        "/stop - остановить уведомления\n"
        "/stats - статистика"
    )


@dp.message(Command("filters"))
async def cmd_filters(message: types.Message):
    filters_text = (
        "🎯 Текущие фильтры:\n\n"
        "📍 Расположение: Москва, внутри ТТК\n"
        "📊 Площадь: 38-150 м²\n"
        "🏢 Этаж: не первый, не последний\n"
        "💰 Цена: до 100 млн ₽\n"
        "🏠 Ремонт: дизайнерский/euro\n"
        "🚗 Продавец: собственник/-застройщик"
    )
    await message.answer(filters_text)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    await message.answer(
        "📈 Статистика:\n"
        "Объектов найдено: 0\n"
        "Новых за сегодня: 0\n"
        "Последнее обновление: -"
    )


async def send_listing(chat_id: int, listing: dict):
    """Send listing to chat"""
    text = (
        f"<b>🏠 Новый объект!</b>\n\n"
        f"<b>{listing['title']}</b>\n"
        f"📍 Адреу: {listing['address']}\n"
        f"📊 Площадь: {listing['area']} м²\n"
        f"🏢 Этак: {listing['floor']}/{listing['total_floors']}\n"
        f"💰 Цена: {listing['price']::,.f} руб.\n"
        f"💵 Цена за м²: {listing['price_per_m2']::,.f} руб.\n"
        f"\n🔗 <a href='{listing['link']}'>Ссылка</a>"
    )
    await bot.send_message(chat_id, text)


async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
