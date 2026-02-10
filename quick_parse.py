import asyncio, json, re, sys
from playwright.async_api import async_playwright
from datetime import datetime

DISTRICTS = [13,14,15,16,17,18,19,20,21,22,94,96,160,149,150,154,136,137,109]

async def main():
    print('Starting...', flush=True)
    p = await async_playwright().start()
    b = await p.chromium.launch(headless=True, args=['--no-sandbox'])
    pg = await b.new_page()
    
    url = 'https://www.cian.ru/cat.php?deal_type=sale&offer_type=flat&region=1'
    url += '&minarea=38&maxarea=150&maxprice=100000000&floornl=1'
    for d in DISTRICTS: url += f'&district%5B%5D={d}'
    
    results = []
    
    for pn in range(1, 6):
        print(f'Page {pn}...', flush=True)
        try:
            await pg.goto(f'{url}&p={pn}', timeout=30000)
            await asyncio.sleep(2)
            
            cards = await pg.query_selector_all('article')
            print(f'  Cards: {len(cards)}', flush=True)
            
            for card in cards[:25]:
                try:
                    h = await card.inner_html()
                    link = re.search(r'href="(https://www.cian.ru/sale/flat/[^"]+)"', h)
                    title = re.search(r'>([^<]*комн[^<]*м²[^<]*)<', h)
                    price = re.search(r'>([\d\s]+)\s*₽<', h)
                    
                    if link and price:
                        pr = int(re.sub(r'\D', '', price.group(1)))
                        ar = re.search(r'(\d+(?:,\d+)?)\s*м', title.group(1) if title else '')
                        if pr > 0 and ar:
                            a = float(ar.group(1).replace(',','.'))
                            results.append({'link': link.group(1), 'price': pr, 'area': a, 'price_m2': int(pr/a)})
                except: pass
            
            if len(results) >= 100: break
        except Exception as e:
            print(f'Error: {e}', flush=True)
    
    await b.close()
    with open('parsed_results.json', 'w') as f:
        json.dump(results, f)
    print(f'Done: {len(results)}', flush=True)

asyncio.run(main())
