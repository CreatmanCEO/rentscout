import asyncio
import json
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
daily_count = 0
MAX_DAILY = 100

TTK_DISTRICTS = {
    "Арбат":13,"Басманный":14,"Замоскворечье":15,"Красносельский":16,
    "Мещанский":17,"Пресненский":18,"Таганский":19,"Тверской":20,
    "Хамовники":21,"Якиманка":22,"Беговой":94,"Савёловский":96,
    "Марьина Роща":160,"Сокольники":149,"Лефортово":150,
    "Южнопортовый":154,"Даниловский":136,"Донской":137,"Дорогомилово":109
}

def get_sheets_client():
    creds = Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def add_to_sheet(data):
    try:
        client = get_sheets_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        ws = sheet.worksheet("Объекты")
        rows = ws.get_all_values()
        next_id = len(rows)
        row = [
            str(next_id),
            data.get("date", datetime.now().strftime("%d.%m.%Y")),
            "Циан",
            data.get("link", ""),
            data.get("address", "")[:80],
            data.get("district", "ЦАО"),
            str(data.get("area", "")),
            "",
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
        logger.error(f"Sheets error: {e}")
        return None

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="search")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])

@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await msg.answer("🏠 <b>RealtyHunter</b>\n\nПоиск недвижимости ТТК (ЦАО)", reply_markup=main_kb())

@dp.message(Command("stop"))
async def cmd_stop(msg: types.Message):
    global search_task
    if search_task:
        search_task.cancel()
        search_task = None
        await msg.answer("⏹ Поиск остановлен")
    else:
        await msg.answer("Поиск не запущен")

@dp.callback_query(F.data == "back")
async def cb_back(cb: types.CallbackQuery):
    await cb.message.edit_text("🏠 <b>RealtyHunter</b>", reply_markup=main_kb())
    await cb.answer()

@dp.callback_query(F.data == "settings")
async def cb_settings(cb: types.CallbackQuery):
    await cb.message.edit_text("⚙️ Районы: ТТК (19 районов)\nЛимит: 100/день", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️", callback_data="back")]]))
    await cb.answer()

@dp.callback_query(F.data == "stats")
async def cb_stats(cb: types.CallbackQuery):
    status = "активен" if search_task else "остановлен"
    txt = f"📊 <b>Статистика</b>\n\nНайдено: {len(parsed_ids)}\nСегодня: {daily_count}/{MAX_DAILY}\nПоиск: {status}"
    await cb.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️", callback_data="back")]]))
    await cb.answer()


async def parse_cian_page(page, page_num):
    url = "https://www.cian.ru/cat.php?deal_type=sale&offer_type=flat&region=1"
    url += "&minarea=38&maxarea=150&maxprice=100000000&floornl=1&object_type%5B0%5D=2"
    for d in TTK_DISTRICTS.values():
        url += f"&district%5B%5D={d}"
    url += f"&p={page_num}"
    
    results = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)
        
        # Try new Cian structure with data-testid
        cards = await page.query_selector_all('[data-testid="offer-card"]')
        if not cards:
            # Fallback to article tags
            cards = await page.query_selector_all("article[data-name='CardComponent']")
        if not cards:
            cards = await page.query_selector_all("article")
        
        logger.info(f"Page {page_num}: found {len(cards)} cards")
        
        for card in cards:
            try:
                link_el = await card.query_selector('a[href*="/flat/"]')
                if not link_el: continue
                link = await link_el.get_attribute("href")
                
                eid = re.search(r"/flat/(\d+)/", link)
                if not eid or eid.group(1) in parsed_ids: continue
                
                # Get all text from card
                text = await card.inner_text()
                
                # Parse rooms
                rooms_m = re.search(r'(\d+)-комн', text)
                rooms = rooms_m.group(1) if rooms_m else "?"
                
                # Parse area
                area_m = re.search(r'(\d+(?:[.,]\d+)?)\s*м[²2]?', text)
                area = float(area_m.group(1).replace(",", ".")) if area_m else 0
                
                # Parse floor
                floor_m = re.search(r'(\d+)/(\d+)\s*(?:этаж|эт)', text)
                floor = f"{floor_m.group(1)}/{floor_m.group(2)}" if floor_m else "?"
                
                # Parse price - find numbers in millions range
                price = 0
                price_patterns = [
                    r'(\d{1,3}[\s\xa0]?\d{3}[\s\xa0]?\d{3})',  # 100 000 000
                    r'(\d{2,3}[\s\xa0]?\d{3}[\s\xa0]?\d{3})',   # 50 000 000
                ]
                for pat in price_patterns:
                    price_m = re.search(pat, text)
                    if price_m:
                        price = int(re.sub(r'\D', '', price_m.group(1)))
                        if 1_000_000 < price < 200_000_000:
                            break
                        price = 0
                
                if price == 0:
                    # Alternative: find any 8+ digit number
                    all_nums = re.findall(r'\d[\d\s\xa0]{6,}', text)
                    for n in all_nums:
                        clean = int(re.sub(r'\D', '', n))
                        if 1_000_000 < clean < 200_000_000:
                            price = clean
                            break
                
                if price == 0 or area == 0:
                    continue
                
                # Get address
                addr = ""
                addr_el = await card.query_selector('[data-testid="address"]')
                if not addr_el:
                    addr_el = await card.query_selector('[class*="address"], [class*="geo"]')
                if addr_el:
                    addr = await addr_el.inner_text()
                else:
                    # Try to extract from text - look for street patterns
                    addr_m = re.search(r'(?:ул\.|улица|пер\.|бул\.|наб\.|пр-т)[^,\n]+', text)
                    if addr_m:
                        addr = addr_m.group(0)
                
                district = "ЦАО"
                for d in TTK_DISTRICTS.keys():
                    if d.lower() in addr.lower() or d.lower() in text.lower():
                        district = d
                        break
                
                results.append({
                    "external_id": eid.group(1),
                    "link": link,
                    "rooms": rooms,
                    "area": area,
                    "floor": floor,
                    "address": addr,
                    "district": district,
                    "price": price,
                    "price_m2": round(price / area) if area > 0 else 0,
                })
            except Exception as e:
                logger.warning(f"Card parse error: {e}")
                continue
    except Exception as e:
        logger.error(f"Page {page_num} error: {e}")
    
    return results
async def do_search(chat_id):
    global daily_count, parsed_ids
    
    if daily_count >= MAX_DAILY:
        await bot.send_message(chat_id, f"⚠️ Достигнут лимит {MAX_DAILY} объектов на сегодня")
        return
    
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="ru-RU"
    )
    page = await context.new_page()
    stealth = Stealth()
    await stealth.apply_stealth_async(page)
    
    new_count = 0
    try:
        for pn in range(1, 6):
            if daily_count >= MAX_DAILY:
                break
            
            await bot.send_message(chat_id, f"📄 Страница {pn}...")
            results = await parse_cian_page(page, pn)
            
            for r in results:
                if daily_count >= MAX_DAILY:
                    break
                if r["external_id"] in parsed_ids:
                    continue
                
                parsed_ids.add(r["external_id"])
                sheet_id = add_to_sheet(r)
                
                if sheet_id:
                    daily_count += 1
                    new_count += 1
                    txt = (
                        f"🏠 <b>{r['rooms']}к, {r['area']} м²</b>\n"
                        f"📍 {r['district']}\n"
                        f"🏢 {r['floor']} этаж\n"
                        f"💰 {r['price']//1000000:.1f} млн ({r['price_m2']:,} ₽/м²)\n"
                        f"<a href=\"{r['link']}\">Смотреть на Циан</a>\n"
                        f"✅ Добавлено в таблицу (#{sheet_id})"
                    )
                    await bot.send_message(chat_id, txt)
                    await asyncio.sleep(0.5)
            
            await asyncio.sleep(2)
    finally:
        await browser.close()
        await p.stop()
    
    await bot.send_message(chat_id, f"✅ Готово! Новых: {new_count}, всего сегодня: {daily_count}/{MAX_DAILY}")

async def search_loop(chat_id):
    while True:
        try:
            await do_search(chat_id)
        except Exception as e:
            logger.error(f"Search loop error: {e}")
            await bot.send_message(chat_id, f"❌ Ошибка: {str(e)[:100]}")
        await asyncio.sleep(1800)  # 30 min

@dp.callback_query(F.data == "search")
async def cb_search(cb: types.CallbackQuery):
    global search_task
    if search_task and not search_task.done():
        await cb.answer("Поиск уже запущен!")
        return
    await cb.answer("🔍 Запуск поиска...")
    await cb.message.edit_text("🔍 <b>Поиск запущен</b>\n/stop для остановки",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="back")]]))
    search_task = asyncio.create_task(search_loop(cb.message.chat.id))

async def main():
    logger.info("RealtyHunter v3 started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
