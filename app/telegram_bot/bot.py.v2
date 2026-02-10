import asyncio
import json
import logging
import sys
sys.path.insert(0, "/root/rentscout")

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
import os
from dotenv import load_dotenv

from app.parsers.cian.listing_parser import CianParser

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
FILTERS_PATH = os.getenv("FILTERS_PATH", "/root/rentscout/config/steinik_filters.json")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

search_task = None
found_ids = set()

def load_filters():
    try:
        with open(FILTERS_PATH) as f:
            return json.load(f)
    except:
        return {"area_range": {"min": 38, "max": 150}, "price_max": 100000000}

def save_filters(filters):
    with open(FILTERS_PATH, "w") as f:
        json.dump(filters, f, indent=2, ensure_ascii=False)

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Poisk", callback_data="search")],
        [InlineKeyboardButton(text="Nastroyki", callback_data="settings")],
        [InlineKeyboardButton(text="Statistika", callback_data="stats")]
    ])

def settings_kb(f):
    a = f.get("area_range", {})
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{a.get(chr(39)+min+chr(39),38)}-{a.get(chr(39)+max+chr(39),150)} m2", callback_data="set_area")],
        [InlineKeyboardButton(text=f"do {f.get(chr(39)+price_max+chr(39),100000000)//1000000} mln", callback_data="set_price")],
        [InlineKeyboardButton(text=f"{f.get(chr(39)+parse_interval_minutes+chr(39),30)} min", callback_data="set_interval")],
        [InlineKeyboardButton(text="Nazad", callback_data="back")]
    ])

@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await msg.answer("<b>RealtyHunter</b>\n\nPoisk nedvizhimosti po TTK (CAO)", reply_markup=main_kb())

@dp.message(Command("stop"))
async def cmd_stop(msg: types.Message):
    global search_task
    if search_task:
        search_task.cancel()
        search_task = None
        await msg.answer("Poisk ostanovlen")
    else:
        await msg.answer("Poisk ne zapushen")

@dp.callback_query(F.data == "settings")
async def cb_settings(cb: types.CallbackQuery):
    await cb.message.edit_text("<b>Nastroyki</b>\nRayony: TTK (CAO + chast)", reply_markup=settings_kb(load_filters()))
    await cb.answer()

@dp.callback_query(F.data == "back")
async def cb_back(cb: types.CallbackQuery):
    await cb.message.edit_text("<b>RealtyHunter</b>", reply_markup=main_kb())
    await cb.answer()

@dp.callback_query(F.data == "set_area")
async def cb_area(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="30-80 m2", callback_data="area_30_80")],
        [InlineKeyboardButton(text="38-150 m2", callback_data="area_38_150")],
        [InlineKeyboardButton(text="50-200 m2", callback_data="area_50_200")],
        [InlineKeyboardButton(text="<", callback_data="settings")]
    ])
    await cb.message.edit_text("Ploshad:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("area_"))
async def cb_area_set(cb: types.CallbackQuery):
    p = cb.data.split("_"); f = load_filters()
    f["area_range"] = {"min": int(p[1]), "max": int(p[2])}
    save_filters(f); await cb.answer(f"OK {p[1]}-{p[2]} m2")
    await cb.message.edit_text("<b>Nastroyki</b>", reply_markup=settings_kb(f))

@dp.callback_query(F.data == "set_price")
async def cb_price(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 mln", callback_data="price_50")],
        [InlineKeyboardButton(text="100 mln", callback_data="price_100")],
        [InlineKeyboardButton(text="150 mln", callback_data="price_150")],
        [InlineKeyboardButton(text="<", callback_data="settings")]
    ])
    await cb.message.edit_text("Max cena:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("price_"))
async def cb_price_set(cb: types.CallbackQuery):
    v = int(cb.data.split("_")[1]) * 1000000; f = load_filters()
    f["price_max"] = v; save_filters(f)
    await cb.answer(f"OK do {v//1000000} mln")
    await cb.message.edit_text("<b>Nastroyki</b>", reply_markup=settings_kb(f))

@dp.callback_query(F.data == "set_interval")
async def cb_int(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="15 min", callback_data="int_15")],
        [InlineKeyboardButton(text="30 min", callback_data="int_30")],
        [InlineKeyboardButton(text="60 min", callback_data="int_60")],
        [InlineKeyboardButton(text="<", callback_data="settings")]
    ])
    await cb.message.edit_text("Interval:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("int_"))
async def cb_int_set(cb: types.CallbackQuery):
    v = int(cb.data.split("_")[1]); f = load_filters()
    f["parse_interval_minutes"] = v; save_filters(f)
    await cb.answer(f"OK {v} min")
    await cb.message.edit_text("<b>Nastroyki</b>", reply_markup=settings_kb(f))

@dp.callback_query(F.data == "stats")
async def cb_stats(cb: types.CallbackQuery):
    status = "aktiven" if search_task else "ostanovlen"
    txt = f"<b>Statistika</b>\n\nNaydeno: {len(found_ids)}\nPoisk: {status}"
    await cb.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="<", callback_data="back")]]))
    await cb.answer()

async def do_search(chat_id: int):
    global found_ids
    parser = CianParser(FILTERS_PATH)
    try:
        listings = await parser.parse_listings(max_pages=2)
        new_count = 0
        for l in listings:
            if l.external_id not in found_ids:
                found_ids.add(l.external_id)
                new_count += 1
                district = l.district or "CAO"
                txt = (
                    f"<b>{l.rooms}-komn, {l.area} m2</b>\n"
                    f"Rayon: {district}\n"
                    f"Etazh: {l.floor}/{l.total_floors}\n"
                    f"Cena: {l.price/1e6:.1f} mln rub ({int(l.price_per_m2):,} rub/m2)\n"
                    f"Adres: {l.address[:80]}\n\n"
                    f"<a href=\"{l.link}\">Smotret na Cian</a>"
                )
                await bot.send_message(chat_id, txt)
                await asyncio.sleep(0.5)
        return len(listings), new_count
    finally:
        await parser.close()

async def search_loop(chat_id: int):
    while True:
        try:
            total, new_count = await do_search(chat_id)
            logger.info(f"Parsed: {total}, new: {new_count}")
            if new_count == 0:
                await bot.send_message(chat_id, f"Novyh obyektov net. Provereno: {total}")
        except Exception as e:
            logger.error(f"Search error: {e}")
            await bot.send_message(chat_id, f"Oshibka: {str(e)[:100]}")
        f = load_filters()
        interval = f.get("parse_interval_minutes", 30)
        await asyncio.sleep(interval * 60)

@dp.callback_query(F.data == "search")
async def cb_search(cb: types.CallbackQuery):
    global search_task
    if search_task and not search_task.done():
        await cb.answer("Poisk uzhe zapushen!")
        return
    await cb.answer("Poisk zapushen!")
    await cb.message.edit_text(
        "<b>Poisk zapushen...</b>\n\nRayony: TTK (CAO + chast)\n/stop dlya ostanovki",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="< Menu", callback_data="back")]])
    )
    search_task = asyncio.create_task(search_loop(cb.message.chat.id))

async def main():
    logger.info("RealtyHunter started - TTK mode")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
