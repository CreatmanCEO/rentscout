import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
FILTERS_PATH = os.getenv("FILTERS_PATH", "/app/config/steinik_filters.json")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


def load_filters() -> dict:
    try:
        with open(FILTERS_PATH, "r") as f:
            return json.load(f)
    except:
        return {}


def save_filters(filters: dict):
    with open(FILTERS_PATH, "w") as f:
        json.dump(filters, f, indent=2, ensure_ascii=False)


def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Запустить поиск", callback_data="search")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🛑 Остановить", callback_data="stop")]
    ])


def get_settings_keyboard(filters: dict):
    area = filters.get("area_range", {})
    price = filters.get("price_max", 100000000)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"📐 Площадь: {area.get('min', 38)}-{area.get('max', 150)} м²",
            callback_data="set_area"
        )],
        [InlineKeyboardButton(
            text=f"💰 Макс. цена: {price:,} ₽".replace(",", " "),
            callback_data="set_price"
        )],
        [InlineKeyboardButton(
            text=f"🏠 Ремонт: {', '.join(filters.get('renovation', []))}",
            callback_data="set_renovation"
        )],
        [InlineKeyboardButton(
            text=f"🅿️ Парковка: {'Да' if filters.get('parking') == 'required' else 'Желательно'}",
            callback_data="set_parking"
        )],
        [InlineKeyboardButton(
            text=f"⏱ Интервал: {filters.get('update_interval_minutes', 30)} мин",
            callback_data="set_interval"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🏠 <b>RealtyHunter</b> — поиск недвижимости\n\n"
        "Бот ищет квартиры на Циан и Авито по вашим фильтрам "
        "и отправляет уведомления о новых объектах.\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )


@dp.callback_query(F.data == "settings")
async def cb_settings(callback: types.CallbackQuery):
    filters = load_filters()
    await callback.message.edit_text(
        "⚙️ <b>Настройки поиска</b>\n\n"
        "Нажмите на параметр для изменения:",
        reply_markup=get_settings_keyboard(filters)
    )
    await callback.answer()


@dp.callback_query(F.data == "back")
async def cb_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏠 <b>RealtyHunter</b>\n\nВыберите действие:",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "set_area")
async def cb_set_area(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="30-80 м²", callback_data="area_30_80")],
        [InlineKeyboardButton(text="38-150 м² (текущий)", callback_data="area_38_150")],
        [InlineKeyboardButton(text="50-200 м²", callback_data="area_50_200")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings")]
    ])
    await callback.message.edit_text("📐 Выберите диапазон площади:", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("area_"))
async def cb_area_select(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    min_area, max_area = int(parts[1]), int(parts[2])
    filters = load_filters()
    filters["area_range"] = {"min": min_area, "max": max_area}
    save_filters(filters)
    await callback.answer(f"✅ Площадь: {min_area}-{max_area} м²")
    await cb_settings(callback)


@dp.callback_query(F.data == "set_price")
async def cb_set_price(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 млн ₽", callback_data="price_50000000")],
        [InlineKeyboardButton(text="100 млн ₽ (текущий)", callback_data="price_100000000")],
        [InlineKeyboardButton(text="150 млн ₽", callback_data="price_150000000")],
        [InlineKeyboardButton(text="200 млн ₽", callback_data="price_200000000")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings")]
    ])
    await callback.message.edit_text("💰 Выберите максимальную цену:", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("price_"))
async def cb_price_select(callback: types.CallbackQuery):
    price = int(callback.data.split("_")[1])
    filters = load_filters()
    filters["price_max"] = price
    save_filters(filters)
    await callback.answer(f"✅ Макс. цена: {price:,} ₽".replace(",", " "))
    await cb_settings(callback)


@dp.callback_query(F.data == "set_interval")
async def cb_set_interval(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="15 мин", callback_data="interval_15")],
        [InlineKeyboardButton(text="30 мин (текущий)", callback_data="interval_30")],
        [InlineKeyboardButton(text="60 мин", callback_data="interval_60")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings")]
    ])
    await callback.message.edit_text("⏱ Интервал проверки:", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("interval_"))
async def cb_interval_select(callback: types.CallbackQuery):
    interval = int(callback.data.split("_")[1])
    filters = load_filters()
    filters["update_interval_minutes"] = interval
    save_filters(filters)
    await callback.answer(f"✅ Интервал: {interval} мин")
    await cb_settings(callback)


@dp.callback_query(F.data == "stats")
async def cb_stats(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Статистика</b>\n\n"
        "Объектов найдено: 0\n"
        "Новых за сегодня: 0\n"
        "Последнее обновление: —",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "search")
async def cb_search(callback: types.CallbackQuery):
    await callback.answer("🔍 Поиск запущен!")
    await callback.message.edit_text(
        "🔍 <b>Поиск запущен</b>\n\n"
        "Бот будет отправлять новые объекты по мере их появления.\n"
        "Для остановки нажмите /stop",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Остановить", callback_data="stop")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="back")]
        ])
    )


@dp.callback_query(F.data == "stop")
async def cb_stop(callback: types.CallbackQuery):
    await callback.answer("🛑 Поиск остановлен")
    await cb_back(callback)


async def send_listing(chat_id: int, listing: dict):
    text = (
        f"<b>🏠 Новый объект!</b>\n\n"
        f"<b>{listing.get('title', 'Без названия')}</b>\n"
        f"📍 {listing.get('address', '—')}\n"
        f"📐 Площадь: {listing.get('area', 0)} м²\n"
        f"🏢 Этаж: {listing.get('floor', 0)}/{listing.get('total_floors', 0)}\n"
        f"💰 Цена: {listing.get('price', 0):,.0f} ₽\n"
        f"💵 Цена за м²: {listing.get('price_per_m2', 0):,.0f} ₽\n"
        f"\n🔗 <a href='{listing.get('link', '')}'>Открыть объявление</a>"
    )
    await bot.send_message(chat_id, text)


@dp.message(Command("filters"))
async def cmd_filters(message: types.Message):
    filters = load_filters()
    area = filters.get("area_range", {})
    text = (
        "🎯 <b>Текущие фильтры:</b>\n\n"
        f"📍 Расположение: Москва, ТТК\n"
        f"📐 Площадь: {area.get('min', 38)}-{area.get('max', 150)} м²\n"
        f"🏢 Этаж: не первый, не последний\n"
        f"💰 Цена: до {filters.get('price_max', 100000000):,} ₽\n"
        f"🏠 Ремонт: {', '.join(filters.get('renovation', []))}\n"
        f"🅿️ Парковка: {filters.get('parking', 'preferred')}\n"
        f"👤 Продавец: {', '.join(filters.get('seller_type', []))}"
    ).replace(",", " ")
    await message.answer(text)


async def main():
    logger.info("Starting RealtyHunter bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
