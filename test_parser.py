import asyncio
import random
import logging
import re
import sys
import os
import sqlite3
from datetime import datetime

sys.path.insert(0, "/root/rentscout")

import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv

load_dotenv("/root/rentscout/.env")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
CREDS_PATH = os.getenv("GOOGLE_CREDS_PATH")
DB_PATH = "/root/rentscout/parsed_listings.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS parsed_listings (
            listing_id TEXT PRIMARY KEY, parsed_date TEXT, link TEXT, price INTEGER, district TEXT)""")
    conn.commit()
    conn.close()
    logger.info(f"Database initialized: {DB_PATH}")

def is_listing_parsed(listing_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM parsed_listings WHERE listing_id = ?", (listing_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_listing_to_db(listing_id, link, price, district):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""INSERT OR IGNORE INTO parsed_listings (listing_id, parsed_date, link, price, district)
            VALUES (?, ?, ?, ?, ?)""", (listing_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), link, price, district))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding to DB: {e}")

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
        logger.info(f"✅ Added to sheet #{next_id}: {data.get('address', 'N/A')[:50]}")
        return next_id
    except Exception as e:
        logger.error(f"Sheets error: {e}")
        return None

async def parse_cian_page(page, page_num):
    url = "https://www.cian.ru/cat.php?deal_type=sale&offer_type=flat&region=1"
    url += "&decoration[0]=1&decoration[0]=2&decoration[0]=3"
    url += "&minarea=40&maxarea=150"
    url += "&maxprice=100000000"
    url += "&floornl=1"
    url += f"&p={page_num}"

    results = []
    try:
        logger.info(f"Loading page {page_num}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(random.uniform(2, 4))

        cards = await page.query_selector_all('[data-testid="offer-card"]')
        if not cards:
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
                if not eid or is_listing_parsed(eid.group(1)): continue

                text = await card.inner_text()

                rooms_m = re.search(r'(\d+)-комн', text)
                rooms = rooms_m.group(1) if rooms_m else "?"

                area_m = re.search(r'(\d+(?:[.,]\d+)?)\s*м[²2]?', text)
                area = float(area_m.group(1).replace(",", ".")) if area_m else 0

                area_living = 0
                living_patterns = [
                    r'(?:жилая|living)[^\d]*(\d+(?:[.,]\d+)?)\s*м',
                    r'(\d+(?:[.,]\d+)?)\s*м[²2]?[^\d]*жил',
                ]
                for pat in living_patterns:
                    living_m = re.search(pat, text, re.I)
                    if living_m:
                        area_living = float(living_m.group(1).replace(',', '.'))
                        break

                floor_m = re.search(r'(\d+)/(\d+)\s*(?:этаж|эт)', text)
                floor = f"{floor_m.group(1)}/{floor_m.group(2)}" if floor_m else "?"

                price = 0
                price_patterns = [
                    r'(\d{1,3}[\s\xa0]?\d{3}[\s\xa0]?\d{3})',
                    r'(\d{2,3}[\s\xa0]?\d{3}[\s\xa0]?\d{3})',
                ]
                for pat in price_patterns:
                    price_m = re.search(pat, text)
                    if price_m:
                        price = int(re.sub(r'\D', '', price_m.group(1)))
                        if 1_000_000 < price < 200_000_000:
                            break
                        price = 0

                if price == 0:
                    all_nums = re.findall(r'\d[\d\s\xa0]{6,}', text)
                    for n in all_nums:
                        clean = int(re.sub(r'\D', '', n))
                        if 1_000_000 < clean < 200_000_000:
                            price = clean
                            break

                if price == 0 or area == 0:
                    continue

                addr = ""

                addr_el = await card.query_selector('[data-testid="address"]')
                if addr_el:
                    addr = (await addr_el.inner_text()).strip()

                if not addr:
                    addr_el = await card.query_selector('[class*="geo"], [class*="address"], a[href*="address"]')
                    if addr_el:
                        addr = (await addr_el.inner_text()).strip()

                if not addr:
                    addr_patterns = [
                        r'((?:ЦАО|ЮАО|САО|ВАО|ЗАО|СВАО|ЮВАО|СЗАО|ЮЗАО),?\s+р-н\s+[^,\n]+(?:,\s+[^,\n]+){1,3})',
                        r'((?:Якиманка|Замоскворечье|Хамовники|Арбат|Таганский|Пресненский|Тверской|Басманный|Красносельский|Мещанский)[^,\n]*,\s*[^,\n]+)',
                        r'((?:ул\.|улица|пер\.|переулок|проезд|наб\.|набережная|бул\.|бульвар|пр-т|просп\.|проспект)\s*[^,\n]+(?:,\s*\d+[^,\n]*)?)',
                    ]
                    for pattern in addr_patterns:
                        m = re.search(pattern, text, re.I)
                        if m:
                            addr = m.group(1).strip()
                            break

                if not addr:
                    addr_m = re.search(r'([А-Яа-я\s]+,\s*\d+[А-Яа-я\s,]*)', text)
                    if addr_m:
                        addr = addr_m.group(1).strip()

                renovation = ""
                text_lower = text.lower()
                if 'дизайнерск' in text_lower: renovation = "Дизайнерский"
                elif 'евроремонт' in text_lower or 'евро' in text_lower: renovation = "Евро"
                elif 'косметическ' in text_lower: renovation = "Косметический"
                elif 'чистовая' in text_lower or 'чистовой' in text_lower: renovation = "Чистовая"
                elif 'предчистовая' in text_lower or 'предчистовой' in text_lower: renovation = "Предчистовая"
                elif 'под отделку' in text_lower or 'без отделки' in text_lower or 'черновая' in text_lower: renovation = "Без ремонта"
                elif 'требует ремонт' in text_lower: renovation = "Требует ремонта"

                building = ""
                if 'новостройк' in text_lower or 'новый фонд' in text_lower or 'от застройщик' in text_lower:
                    building = "Новый"
                elif 'вторичн' in text_lower or 'вторичка' in text_lower:
                    building = "Вторичка"
                else:
                    building = "Вторичка"

                parking = ""
                if 'подземн' in text_lower and 'парковк' in text_lower: parking = "Подземная"
                elif 'наземн' in text_lower and 'парковк' in text_lower: parking = "Наземная"
                elif 'машиномест' in text_lower: parking = "Есть"
                elif 'парковк' in text_lower: parking = "Есть"

                seller = ""
                if 'застройщик' in text_lower: seller = "Застройщик"
                elif 'собственник' in text_lower: seller = "Собственник"
                elif 'агент' in text_lower or 'агентство' in text_lower: seller = "Агентство"
                elif building == "Новый": seller = "Застройщик"

                district = "ЦАО"
                cao_districts = ['якиманка', 'замоскворечье', 'хамовники', 'арбат', 'таганский',
                                'пресненский', 'тверской', 'басманный', 'красносельский', 'мещанский']

                in_cao = False
                for cao_d in cao_districts:
                    if cao_d in text_lower or cao_d in addr.lower():
                        in_cao = True
                        district = cao_d.capitalize()
                        break

                if not in_cao:
                    logger.info(f"🚫 Skipped (not CAO): {addr[:50] if addr else 'N/A'}")
                    continue

                bad_keywords = ['без отделки', 'черновая', 'предчистовая', 'под ремонт', 'требует ремонта']
                if any(bad in text_lower for bad in bad_keywords):
                    logger.info(f"🚫 Skipped (no renovation): {addr[:50] if addr else 'N/A'}")
                    continue

                results.append({
                    "external_id": eid.group(1),
                    "link": link,
                    "rooms": rooms,
                    "area": area,
                    "area_living": area_living,
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
                logger.warning(f"Card parse error: {e}")
                continue
    except Exception as e:
        logger.error(f"Page {page_num} error: {e}")

    return results

async def main():
    init_db()
    logger.info("=" * 60)
    logger.info("ТЕСТОВЫЙ ЗАПУСК ПАРСЕРА")
    logger.info("=" * 60)

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

    total_added = 0
    total_found = 0
    stats = {
        "address_filled": 0,
        "building_filled": 0,
        "renovation_filled": 0,
        "parking_filled": 0,
        "seller_filled": 0,
        "area_living_filled": 0,
    }

    try:
        for pn in range(1, 3):  # Только 2 страницы для теста
            results = await parse_cian_page(page, pn)
            total_found += len(results)

            for r in results:
                sheet_id = add_to_sheet(r)
                add_listing_to_db(r["external_id"], r["link"], r["price"], r["district"])

                if sheet_id:
                    total_added += 1
                    if r.get("address"): stats["address_filled"] += 1
                    if r.get("building"): stats["building_filled"] += 1
                    if r.get("renovation"): stats["renovation_filled"] += 1
                    if r.get("parking"): stats["parking_filled"] += 1
                    if r.get("seller"): stats["seller_filled"] += 1
                    if r.get("area_living"): stats["area_living_filled"] += 1

                    logger.info(f"  • Фонд: {r.get('building', 'N/A')}, Ремонт: {r.get('renovation', 'N/A')}, Парковка: {r.get('parking', 'N/A')}, Продавец: {r.get('seller', 'N/A')}")

            await asyncio.sleep(random.uniform(2, 4))
    finally:
        await browser.close()
        await p.stop()

    logger.info("=" * 60)
    logger.info(f"РЕЗУЛЬТАТЫ ТЕСТА:")
    logger.info(f"  Найдено объектов: {total_found}")
    logger.info(f"  Добавлено в таблицу: {total_added}")
    if total_added > 0:
        logger.info(f"  Заполнение полей:")
        logger.info(f"    Адрес: {stats['address_filled']}/{total_added} ({stats['address_filled']*100//total_added}%)")
        logger.info(f"    Фонд: {stats['building_filled']}/{total_added} ({stats['building_filled']*100//total_added}%)")
        logger.info(f"    Ремонт: {stats['renovation_filled']}/{total_added} ({stats['renovation_filled']*100//total_added}%)")
        logger.info(f"    Парковка: {stats['parking_filled']}/{total_added} ({stats['parking_filled']*100//total_added}%)")
        logger.info(f"    Продавец: {stats['seller_filled']}/{total_added} ({stats['seller_filled']*100//total_added}%)")
        logger.info(f"    Жилая площадь: {stats['area_living_filled']}/{total_added} ({stats['area_living_filled']*100//total_added}%)")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
