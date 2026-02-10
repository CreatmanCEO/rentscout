import asyncio
import json
import re
from playwright.async_api import async_playwright
from datetime import datetime

TTK_DISTRICTS = [
    "Арбат", "Басманный", "Замоскворечье", "Красносельский", "Мещанский",
    "Пресненский", "Таганский", "Тверской", "Хамовники", "Якиманка",
    "Беговой", "Савёловский", "Марьина Роща", "Сокольники", "Лефортово",
    "Южнопортовый", "Даниловский", "Донской", "Дорогомилово"
]

TTK_DISTRICT_IDS = {
    "Арбат": 13, "Басманный": 14, "Замоскворечье": 15, "Красносельский": 16,
    "Мещанский": 17, "Пресненский": 18, "Таганский": 19, "Тверской": 20,
    "Хамовники": 21, "Якиманка": 22, "Беговой": 94, "Савёловский": 96,
    "Марьина Роща": 160, "Сокольники": 149, "Лефортово": 150,
    "Южнопортовый": 154, "Даниловский": 136, "Донской": 137, "Дорогомилово": 109
}

async def parse_listing_page(page, url):
    """Parse single listing page for full details"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(2)
        h = await page.content()
        
        data = {'link': url, 'source': 'Циан'}
        
        # Title - rooms and area
        t = re.search(r'(\d+)-комн[^\d]*(\d+(?:,\d+)?)\s*м', h)
        if t:
            data['rooms'] = t.group(1)
            data['area'] = t.group(2).replace(',', '.')
        
        # Price
        pr = re.search(r'"price":(\d+)', h)
        if pr:
            data['price'] = int(pr.group(1))
            if data.get('area'):
                data['price_m2'] = int(data['price'] / float(data['area']))
        
        # Address
        addr = re.search(r'Москва,\s*ЦАО[^"]{10,120}', h)
        if addr:
            data['address'] = addr.group(0).split('На карте')[0].strip()
        
        # District
        for d in TTK_DISTRICTS:
            if d.lower() in h.lower():
                data['district'] = d
                break
        
        # Floor
        fl = re.search(r'Этаж\s*</span>[^<]*<[^>]*>(\d+)\s*из\s*(\d+)', h)
        if fl:
            data['floor'] = f"{fl.group(1)}/{fl.group(2)}"
        else:
            fl2 = re.search(r'>(\d+)/(\d+)\s*этаж', h)
            if fl2:
                data['floor'] = f"{fl2.group(1)}/{fl2.group(2)}"
        
        # Renovation
        rem = re.search(r'(Дизайнерский|Евроремонт|Евро|Косметический|Без ремонта)', h, re.I)
        if rem:
            data['renovation'] = rem.group(1)
        
        # Parking
        park = re.search(r'(Подземн\w*|Наземн\w*|Многоуровнев\w*)\s*парк', h, re.I)
        if park:
            data['parking'] = park.group(1) + ' паркинг'
        elif 'паркинг' in h.lower() or 'parking' in h.lower():
            data['parking'] = 'Есть'
        
        # Seller
        if 'Застройщик' in h:
            data['seller'] = 'Застройщик'
        elif 'Собственник' in h:
            data['seller'] = 'Собственник'
        elif 'Риелтор' in h or 'Агент' in h:
            data['seller'] = 'Агентство'
        
        # Building type
        if 'Новостройка' in h:
            data['building'] = 'Новостройка'
        else:
            data['building'] = 'Вторичка'
        
        # External ID
        eid = re.search(r'/flat/(\d+)/', url)
        if eid:
            data['external_id'] = eid.group(1)
        
        return data
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return None

async def get_listing_urls(page, max_items=100):
    """Get listing URLs from search results"""
    urls = []
    district_ids = list(TTK_DISTRICT_IDS.values())
    
    base_url = "https://www.cian.ru/cat.php?deal_type=sale&offer_type=flat&region=1&engine_version=2"
    base_url += "&minarea=38&maxarea=150&maxprice=100000000&floornl=1"
    
    # Add districts
    for did in district_ids:
        base_url += f"&district%5B%5D={did}"
    
    page_num = 1
    while len(urls) < max_items:
        url = f"{base_url}&p={page_num}"
        print(f"Loading page {page_num}...")
        
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
            
            links = await page.query_selector_all("a[href*='/flat/']")
            page_urls = set()
            for link in links:
                href = await link.get_attribute('href')
                if href and '/flat/' in href and 'sale' in href:
                    # Clean URL
                    clean = re.match(r'(https://www\.cian\.ru/sale/flat/\d+/)', href)
                    if clean:
                        page_urls.add(clean.group(1))
            
            if not page_urls:
                break
                
            urls.extend(list(page_urls))
            print(f"Found {len(page_urls)} listings, total: {len(urls)}")
            
            if len(urls) >= max_items:
                break
                
            page_num += 1
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            break
    
    return urls[:max_items]

async def main():
    print("Starting full parse...")
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = await browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    # Get URLs
    urls = await get_listing_urls(page, max_items=100)
    print(f"\nTotal URLs to parse: {len(urls)}")
    
    # Parse each listing
    results = []
    for i, url in enumerate(urls):
        print(f"Parsing {i+1}/{len(urls)}: {url}")
        data = await parse_listing_page(page, url)
        if data and data.get('price') and data.get('area'):
            data['date'] = datetime.now().strftime('%d.%m.%Y')
            results.append(data)
            print(f"  OK: {data.get('rooms', '?')}к, {data.get('area')}м², {data.get('price', 0)/1e6:.1f}М")
        await asyncio.sleep(1)
    
    await browser.close()
    await p.stop()
    
    # Save results
    with open('/root/rentscout/parsed_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nDone! Parsed {len(results)} listings")
    print("Results saved to /root/rentscout/parsed_results.json")

if __name__ == "__main__":
    asyncio.run(main())
