import asyncio, json, re
from playwright.async_api import async_playwright

async def parse():
    p = await async_playwright().start()
    b = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
    pg = await b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    url = "https://www.cian.ru/cat.php?deal_type=sale&offer_type=flat&region=1&minarea=38&maxarea=150&maxprice=100000000"
    url += "&district%5B%5D=13&district%5B%5D=14&district%5B%5D=15&district%5B%5D=16&district%5B%5D=17"
    url += "&district%5B%5D=18&district%5B%5D=19&district%5B%5D=20&district%5B%5D=21&district%5B%5D=22"
    
    results = []
    for pn in range(1, 6):
        print(f"Page {pn}...", flush=True)
        try:
            await pg.goto(f"{url}&p={pn}", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)
            
            articles = await pg.query_selector_all("article")
            print(f"  {len(articles)} articles", flush=True)
            
            for art in articles:
                try:
                    link_el = await art.query_selector("a[href*=\"/flat/\"]")
                    if not link_el: continue
                    link = await link_el.get_attribute("href")
                    
                    title_el = await art.query_selector("[data-name=\TitleComponent\]")
                    title = await title_el.inner_text() if title_el else ""
                    
                    addr_el = await art.query_selector("[data-name=\GeoLabel\]")
                    addr = await addr_el.inner_text() if addr_el else ""
                    
                    price_el = await art.query_selector("[data-name=\Price\]")
                    price_txt = await price_el.inner_text() if price_el else "0"
                    price = int(re.sub(r"\\D", "", price_txt) or 0)
                    
                    area_m = re.search(r"(\\d+(?:,\\d+)?)\\s*м", title)
                    rooms_m = re.search(r"(\\d+)-комн", title)
                    floor_m = re.search(r"(\\d+)/(\\d+)", title)
                    
                    if price and area_m:
                        a = float(area_m.group(1).replace(",","."))
                        results.append({"link": link, "price": price, "area": a, 
                            "rooms": rooms_m.group(1) if rooms_m else "?",
                            "floor": floor_m.group(1)+"/"+floor_m.group(2) if floor_m else "?",
                            "address": addr[:80], "price_m2": int(price/a)})
                except: pass
            
            print(f"  Total: {len(results)}", flush=True)
            if len(results) >= 100: break
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  Error: {e}", flush=True)
            break
    
    await b.close()
    print(f"Final: {len(results)}", flush=True)
    with open("parsed_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

asyncio.run(parse())
