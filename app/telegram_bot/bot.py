import asyncio
import random
import logging
import re
import sys
import os
from datetime import datetime

sys.path.insert(0, "/root/rentscout")

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

load_dotenv("/root/rentscout/.env")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
CREDS_PATH = os.getenv("GOOGLE_CREDS_PATH")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

search_task = None
parsed_ids = set()
MAX_PER_SEARCH = 100

TTK_DISTRICTS = {
    "Арбат":13,"Басманный":14,"Замоскворечье":15,"Красносельский":16,
    "Мещанский":17,"Пресненский":18,"Таганский":19,"Тверской":20,
    "Хамовники":21,"Якиманка":22
}

def get_sheets_client():
    creds = Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def clean_url(url):
    if "?" in url:
        url = url.split("?")[0]
    if not url.endswith("/"):
        url += "/"
    return url

def load_existing_ids_from_sheet():
    global parsed_ids
    try:
        sheet = get_sheets_client().open_by_key(SPREADSHEET_ID).worksheet("Объекты")
        data = sheet.get_all_values()
        count = 0
        for row in data[1:]:
            if len(row) > 3 and row[3]:
                m = re.search(r"/flat/(\d+)", row[3])
                if m:
                    parsed_ids.add(m.group(1))
                    count += 1
        logger.info(f"Loaded {count} existing IDs from sheet")
        return count
    except Exception as e:
        logger.error(f"Error loading IDs: {e}")
        return 0

def add_to_sheet(data):
    try:
        client = get_sheets_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        ws = sheet.worksheet("Объекты")
        rows = ws.get_all_values()
        next_id = len(rows)

        clean_link = clean_url(data.get("link", ""))

        row = [
            str(next_id),
            data.get("date", datetime.now().strftime("%d.%m.%Y")),
            "Циан",
            clean_link,
            data.get("address", "")[:80],
            data.get("district", "ЦАО"),
            str(data.get("area", "")),
            str(data.get("area_living", "")),
            str(data.get("rooms", "?")),
            data.get("floor", "?"),
            data.get("building", ""),
            data.get("renovation", ""),
            data.get("parking", ""),
            data.get("seller", ""),
            str(data.get("price", 0)),
            str(data.get("price_m2", 0)),
            "Спарсено",
            ""
        ]
        ws.append_row(row)
        return next_id
    except Exception as e:
        logger.error(f"Sheet error: {e}")
        return None

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="search")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
    ])

@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await msg.answer("🏠 <b>RealtyHunter v4</b>\n\nПоиск недвижимости ЦАО", reply_markup=main_kb())

@dp.message(Command("search"))
async def cmd_search(msg: types.Message):
    global search_task
    if search_task and not search_task.done():
        await msg.answer("⚠️ Поиск уже запущен! /stop для остановки")
        return
    await msg.answer("🔍 Запуск поиска...")
    search_task = asyncio.create_task(do_search(msg.chat.id))

@dp.message(Command("stop"))
async def cmd_stop(msg: types.Message):
    global search_task
    if search_task:
        search_task.cancel()
        search_task = None
        await msg.answer("⏹ Поиск остановлен")
    else:
        await msg.answer("Поиск не запущен")

@dp.message(Command("reload"))
async def cmd_reload(msg: types.Message):
    count = load_existing_ids_from_sheet()
    await msg.answer(f"🔄 Загружено {count} ID из таблицы")

@dp.callback_query(F.data == "back")
async def cb_back(cb: types.CallbackQuery):
    await cb.message.edit_text("🏠 <b>RealtyHunter v4</b>", reply_markup=main_kb())
    await cb.answer()

@dp.callback_query(F.data == "settings")
async def cb_settings(cb: types.CallbackQuery):
    await cb.message.edit_text(f"⚙️ Районы: ЦАО (10)\nЛимит: {MAX_PER_SEARCH}/поиск\nID: {len(parsed_ids)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️", callback_data="back")]]))
    await cb.answer()

@dp.callback_query(F.data == "stats")
async def cb_stats(cb: types.CallbackQuery):
    status = "активен" if search_task and not search_task.done() else "остановлен"
    await cb.message.edit_text(f"📊 ID: {len(parsed_ids)}\nПоиск: {status}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️", callback_data="back")]]))
    await cb.answer()

@dp.callback_query(F.data == "search")
async def cb_search(cb: types.CallbackQuery):
    global search_task
    if search_task and not search_task.done():
        await cb.answer("Поиск уже запущен!")
        return
    await cb.answer("🔍 Запуск...")
    await cb.message.edit_text("🔍 <b>Поиск запущен</b>\n/stop для остановки",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️", callback_data="back")]]))
    search_task = asyncio.create_task(do_search(cb.message.chat.id))

async def parse_cian_page(page, page_num):
    url = "https://www.cian.ru/cat.php?deal_type=sale&offer_type=flat&region=1"
    url += "&decoration[0]=1&decoration[0]=2&decoration[0]=3"
    url += "&minarea=40&maxarea=150&maxprice=100000000&floornl=1"
    url += f"&p={page_num}"

    results = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(random.uniform(2, 4))

        cards = await page.query_selector_all('[data-testid="offer-card"]')
        if not cards:
            cards = await page.query_selector_all("article")

        logger.info(f"Page {page_num}: {len(cards)} cards")

        for card in cards:
            try:
                link_el = await card.query_selector('a[href*="/flat/"]')
                if not link_el: continue
                link = clean_url(await link_el.get_attribute("href"))

                eid = re.search(r"/flat/(\d+)/", link)
                if not eid: continue

                listing_id = eid.group(1)
                if listing_id in parsed_ids:
                    continue

                text = await card.inner_text()
                text_lower = text.lower()

                # Фильтр ЦАО
                cao = ['якиманка', 'замоскворечье', 'хамовники', 'арбат', 'таганский',
                       'пресненский', 'тверской', 'басманный', 'красносельский', 'мещанский']

                district = ""
                for d in cao:
                    if d in text_lower:
                        district = d.capitalize()
                        break

                if not district:
                    continue

                # Фильтр ремонта
                bad = ['без отделки', 'черновая', 'предчистовая', 'требует ремонта']
                if any(b in text_lower for b in bad):
                    continue

                # Парсинг данных
                rooms_m = re.search(r'(\d+)-комн', text)
                rooms = rooms_m.group(1) if rooms_m else ("Студия" if "студия" in text_lower else "?")

                area_m = re.search(r'(\d+(?:[.,]\d+)?)\s*м[²2]?', text)
                area = float(area_m.group(1).replace(",", ".")) if area_m else 0

                floor_m = re.search(r'(\d+)/(\d+)\s*(?:этаж|эт)', text)
                floor = f"{floor_m.group(1)}/{floor_m.group(2)}" if floor_m else "?"

                price = 0
                for pat in [r'(\d{1,3}[\s\xa0]?\d{3}[\s\xa0]?\d{3})']:
                    pm = re.search(pat, text)
                    if pm:
                        price = int(re.sub(r'\D', '', pm.group(1)))
                        if 5_000_000 < price < 200_000_000:
                            break
                        price = 0

                if price == 0 or area == 0:
                    continue

                addr = ""
                addr_el = await card.query_selector('[data-testid="address"], [class*="geo"]')
                if addr_el:
                    addr = await addr_el.inner_text()

                renovation = ""
                if "дизайнерский" in text_lower: renovation = "Дизайнерский"
                elif "евро" in text_lower: renovation = "Евро"
                elif "косметический" in text_lower: renovation = "Косметический"

                building = "Новый" if "новостройк" in text_lower or "застройщик" in text_lower else "Вторичка"

                parking = ""
                if "подземн" in text_lower and "парковк" in text_lower: parking = "Подземная"
                elif "парковк" in text_lower: parking = "Есть"

                seller = ""
                if "застройщик" in text_lower: seller = "Застройщик"
                elif "собственник" in text_lower: seller = "Собственник"
                elif "агент" in text_lower: seller = "Агентство"

                results.append({
                    "external_id": listing_id,
                    "link": link,
                    "rooms": rooms,
                    "area": area,
                    "floor": floor,
                    "address": addr,
                    "district": district,
                    "price": price,
                    "price_m2": round(price / area) if area > 0 else 0,
                    "renovation": renovation,
                    "building": building,
                    "parking": parking,
                    "seller": seller,
                })
            except Exception as e:
                continue
    except Exception as e:
        logger.error(f"Page {page_num} error: {e}")

    return results

async def do_search(chat_id):
    global parsed_ids

    await bot.send_message(chat_id, f"🔍 Поиск (лимит: {MAX_PER_SEARCH}, известных: {len(parsed_ids)})")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])

    stealth = Stealth()

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        viewport={"width": 1920, "height": 1080}
    )

    page = await context.new_page()
    await stealth.apply_stealth_async(page)

    new_count = 0

    try:
        for page_num in range(1, 6):
            if new_count >= MAX_PER_SEARCH:
                break

            results = await parse_cian_page(page, page_num)

            for r in results:
                if new_count >= MAX_PER_SEARCH:
                    break

                if r["external_id"] in parsed_ids:
                    continue

                parsed_ids.add(r["external_id"])
                sheet_id = add_to_sheet(r)

                if sheet_id:
                    new_count += 1
                    logger.info(f"+ #{sheet_id}: {r['district']}, {r['price']:,}")

                    txt = f"🏠 <b>{r['rooms']}к, {r['area']}м²</b>\n📍 {r['district']}\n💰 {r['price']:,}₽\n<a href=\"{r['link']}\">CIAN</a>"
                    await bot.send_message(chat_id, txt, disable_web_page_preview=True)
                    await asyncio.sleep(0.3)

            await asyncio.sleep(random.uniform(2, 4))

    except asyncio.CancelledError:
        logger.info("Search cancelled")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await bot.send_message(chat_id, f"❌ Ошибка: {str(e)[:100]}")
    finally:
        await browser.close()
        await p.stop()

    await bot.send_message(chat_id, f"✅ Готово! Добавлено: {new_count}")

async def main():
    load_existing_ids_from_sheet()
    logger.info(f"RealtyHunter v4 started (IDs: {len(parsed_ids)})")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
