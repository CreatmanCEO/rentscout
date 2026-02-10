import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
FILTERS_PATH = os.getenv("FILTERS_PATH", "/tmp/steinik_filters.json")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def load_filters():
    try:
        with open(FILTERS_PATH) as f:
            return json.load(f)
    except:
        return {"area_range": {"min": 38, "max": 150}, "price_max": 100000000}

def save_filters(filters):
    with open(FILTERS_PATH, "w") as f:
        json.dump(filters, f, indent=2)

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="search")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])

def settings_kb(f):
    a = f.get("area_range", {})
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📐 {a.get('min',38)}-{a.get('max',150)} м²", callback_data="set_area")],
        [InlineKeyboardButton(text=f"💰 до {f.get('price_max',100000000)//1000000} млн", callback_data="set_price")],
        [InlineKeyboardButton(text=f"⏱ {f.get('interval',30)} мин", callback_data="set_interval")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])

@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await msg.answer("🏠 <b>RealtyHunter</b>\n\nПоиск недвижимости Циан/Авито", reply_markup=main_kb())

@dp.callback_query(F.data == "settings")
async def cb_settings(cb: types.CallbackQuery):
    await cb.message.edit_text("⚙️ <b>Настройки</b>", reply_markup=settings_kb(load_filters()))
    await cb.answer()

@dp.callback_query(F.data == "back")
async def cb_back(cb: types.CallbackQuery):
    await cb.message.edit_text("🏠 <b>RealtyHunter</b>", reply_markup=main_kb())
    await cb.answer()

@dp.callback_query(F.data == "set_area")
async def cb_area(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="30-80 м²", callback_data="area_30_80")],
        [InlineKeyboardButton(text="38-150 м²", callback_data="area_38_150")],
        [InlineKeyboardButton(text="50-200 м²", callback_data="area_50_200")],
        [InlineKeyboardButton(text="◀️", callback_data="settings")]
    ])
    await cb.message.edit_text("📐 Площадь:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("area_"))
async def cb_area_set(cb: types.CallbackQuery):
    p = cb.data.split("_"); f = load_filters()
    f["area_range"] = {"min": int(p[1]), "max": int(p[2])}
    save_filters(f); await cb.answer(f"✅ {p[1]}-{p[2]} м²")
    await cb.message.edit_text("⚙️ <b>Настройки</b>", reply_markup=settings_kb(f))

@dp.callback_query(F.data == "set_price")
async def cb_price(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 млн", callback_data="price_50")],
        [InlineKeyboardButton(text="100 млн", callback_data="price_100")],
        [InlineKeyboardButton(text="150 млн", callback_data="price_150")],
        [InlineKeyboardButton(text="◀️", callback_data="settings")]
    ])
    await cb.message.edit_text("💰 Макс цена:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("price_"))
async def cb_price_set(cb: types.CallbackQuery):
    v = int(cb.data.split("_")[1]) * 1000000; f = load_filters()
    f["price_max"] = v; save_filters(f)
    await cb.answer(f"✅ до {v//1000000} млн")
    await cb.message.edit_text("⚙️ <b>Настройки</b>", reply_markup=settings_kb(f))

@dp.callback_query(F.data == "set_interval")
async def cb_int(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="15 мин", callback_data="int_15")],
        [InlineKeyboardButton(text="30 мин", callback_data="int_30")],
        [InlineKeyboardButton(text="60 мин", callback_data="int_60")],
        [InlineKeyboardButton(text="◀️", callback_data="settings")]
    ])
    await cb.message.edit_text("⏱ Интервал:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("int_"))
async def cb_int_set(cb: types.CallbackQuery):
    v = int(cb.data.split("_")[1]); f = load_filters()
    f["interval"] = v; save_filters(f)
    await cb.answer(f"✅ {v} мин")
    await cb.message.edit_text("⚙️ <b>Настройки</b>", reply_markup=settings_kb(f))

@dp.callback_query(F.data == "stats")
async def cb_stats(cb: types.CallbackQuery):
    await cb.message.edit_text("📊 Объектов: 0\nНовых: 0", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️", callback_data="back")]]))
    await cb.answer()

@dp.callback_query(F.data == "search")
async def cb_search(cb: types.CallbackQuery):
    await cb.answer("🔍 Поиск запущен!")
    await cb.message.edit_text("🔍 Поиск запущен...\n/stop для остановки", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="back")]]))

async def main():
    logger.info("RealtyHunter started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
