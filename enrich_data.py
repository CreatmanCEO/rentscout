import asyncio
import os
from dotenv import load_dotenv
load_dotenv("/root/rentscout/.env")
import random
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CREDS_PATH = "/root/rentscout/config/google_creds.json"
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")

def get_sheet():
    creds = Credentials.from_service_account_file(
        CREDS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).worksheet("Объекты")

async def parse_listing_page(page, url):
    """Parse detailed info from a single listing page"""
    data = {}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2)
        
        text = await page.inner_text("body")
        
        # Address - look for full address
        addr_el = await page.query_selector('[data-name="AddressContainer"], [class*="address"], [data-testid="address"]')
        if addr_el:
            data["address"] = (await addr_el.inner_text()).strip().replace("\n", ", ")
        else:
            addr_m = re.search(r'Москва[^»\n]{5,100}', text)
            if addr_m:
                data["address"] = addr_m.group(0).strip()
        
        # Living area
        living_m = re.search(r'жилая[:\s]+(\d+[.,]?\d*)\s*м', text, re.I)
        if living_m:
            data["living_area"] = living_m.group(1).replace(",", ".")
        
        # Building type (Фонд)
        if re.search(r'новостройк|сдан в \d{4}|строящ', text, re.I):
            data["building_type"] = "Новый"
        elif re.search(r'вторичк|старый фонд|сталинк|хрущ|брежн|панель', text, re.I):
            data["building_type"] = "Вторичка"
        
        # Year built
        year_m = re.search(r'год постройки[:\s]+(\d{4})|построен в (\d{4})|сдача[:\s]+(\d{4})', text, re.I)
        if year_m:
            year = year_m.group(1) or year_m.group(2) or year_m.group(3)
            if int(year) >= 2020:
                data["building_type"] = "Новый"
            else:
                data["building_type"] = "Вторичка"
        
        # Renovation
        if re.search(r'дизайнерский\s*(ремонт)?', text, re.I):
            data["renovation"] = "Дизайнерский"
        elif re.search(r'евроремонт|евро\s*ремонт', text, re.I):
            data["renovation"] = "Евро"
        elif re.search(r'косметический', text, re.I):
            data["renovation"] = "Косметический"
        elif re.search(r'без\s*ремонт|требует\s*ремонт|черновая', text, re.I):
            data["renovation"] = "Без ремонта"
        
        # Parking
        if re.search(r'подземн\w*\s*парк|паркинг|машиноместо', text, re.I):
            data["parking"] = "Подземная"
        elif re.search(r'наземн\w*\s*парк', text, re.I):
            data["parking"] = "Наземная"
        elif re.search(r'парковк|стоянк', text, re.I):
            data["parking"] = "Есть"
        
        # Seller type
        if re.search(r'застройщик|девелопер', text, re.I):
            data["seller"] = "Застройщик"
        elif re.search(r'собственник|прямая продажа', text, re.I):
            data["seller"] = "Собственник"
        elif re.search(r'агент|риелтор|агентство', text, re.I):
            data["seller"] = "Агентство"
            
    except Exception as e:
        logger.error(f"Error parsing {url}: {e}")
    
    return data

async def enrich_records():
    sheet = get_sheet()
    all_data = sheet.get_all_values()
    
    # Find column indices
    headers = all_data[0]
    col_map = {h: i for i, h in enumerate(headers)}
    
    link_col = col_map.get("Ссылка", 3)
    addr_col = col_map.get("Адрес", 4)
    living_col = col_map.get("S жилая м²", 7)
    building_col = col_map.get("Фонд", 10)
    reno_col = col_map.get("Ремонт", 11)
    parking_col = col_map.get("Парковка", 12)
    seller_col = col_map.get("Продавец", 13)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU"
        )
        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        
        updates = []
        for row_idx, row in enumerate(all_data[1:], start=2):
            if len(row) <= link_col:
                continue
                
            link = row[link_col]
            if not link or "cian.ru" not in link:
                continue
            
            # Check if needs enrichment (empty address or other fields)
            needs_update = (
                (len(row) <= addr_col or not row[addr_col]) or
                (len(row) <= living_col or not row[living_col]) or
                (len(row) <= building_col or not row[building_col])
            )
            
            if not needs_update:
                continue
            
            logger.info(f"Enriching row {row_idx}: {link[:50]}...")
            
            data = await parse_listing_page(page, link)
            
            if data:
                # Prepare cell updates
                if data.get("address") and (len(row) <= addr_col or not row[addr_col]):
                    updates.append({"range": f"E{row_idx}", "values": [[data["address"][:100]]]})
                if data.get("living_area") and (len(row) <= living_col or not row[living_col]):
                    updates.append({"range": f"H{row_idx}", "values": [[data["living_area"]]]})
                if data.get("building_type") and (len(row) <= building_col or not row[building_col]):
                    updates.append({"range": f"K{row_idx}", "values": [[data["building_type"]]]})
                if data.get("renovation") and (len(row) <= reno_col or not row[reno_col]):
                    updates.append({"range": f"L{row_idx}", "values": [[data["renovation"]]]})
                if data.get("parking") and (len(row) <= parking_col or not row[parking_col]):
                    updates.append({"range": f"M{row_idx}", "values": [[data["parking"]]]})
                if data.get("seller") and (len(row) <= seller_col or not row[seller_col]):
                    updates.append({"range": f"N{row_idx}", "values": [[data["seller"]]]})
                
                logger.info(f"  Found: {data}")
            
            # Delay between requests
            await asyncio.sleep(random.uniform(3, 6))
            
            # Batch update every 10 rows
            if len(updates) >= 10:
                for upd in updates:
                    sheet.update(upd["range"], upd["values"])
                logger.info(f"Updated {len(updates)} cells")
                updates = []
        
        # Final update
        if updates:
            for upd in updates:
                sheet.update(upd["range"], upd["values"])
            logger.info(f"Final update: {len(updates)} cells")
        
        await browser.close()
    
    logger.info("Enrichment complete!")

if __name__ == "__main__":
    asyncio.run(enrich_records())
