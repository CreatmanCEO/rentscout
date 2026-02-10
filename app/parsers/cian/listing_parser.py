import asyncio
import json
from playwright.async_api import async_playwright, Browser
from typing import Optional
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
import re


class CianListing(BaseModel):
    external_id: str
    source: str = "cian"
    title: str
    address: str
    district: Optional[str] = None
    metro: Optional[str] = None
    area: float
    floor: int
    total_floors: int
    rooms: int
    price: float
    price_per_m2: float
    renovation: Optional[str] = None
    has_parking: bool = False
    seller_type: Optional[str] = None
    link: str
    photos: list[str] = []


TTK_DISTRICT_IDS = {
    "Арбат": 13, "Басманный": 14, "Замоскворечье": 15,
    "Красносельский": 16, "Мещанский": 17, "Пресненский": 18,
    "Таганский": 19, "Тверской": 20, "Хамовники": 21, "Якиманка": 22,
    "Беговой": 94, "Савёловский": 96, "Марьина Роща": 160,
    "Сокольники": 149, "Лефортово": 150, "Южнопортовый": 154,
    "Даниловский": 136, "Донской": 137, "Дорогомилово": 109,
}

TTK_DISTRICT_NAMES = list(TTK_DISTRICT_IDS.keys())


class CianParser:
    BASE_URL = "https://www.cian.ru"

    def __init__(self, filters_path: str = "/root/rentscout/config/steinik_filters.json"):
        self.browser: Optional[Browser] = None
        self.filters_path = filters_path
        self.filters = self._load_filters()

    def _load_filters(self) -> dict:
        try:
            with open(self.filters_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    async def init_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

    async def close(self):
        if self.browser:
            await self.browser.close()

    def _get_ttk_districts(self) -> list[str]:
        districts = []
        ttk = self.filters.get("ttk_districts", {})
        districts.extend(ttk.get("cao", []))
        districts.extend(ttk.get("partial", []))
        return districts if districts else TTK_DISTRICT_NAMES

    def _build_url(self, district_ids: list[int] = None) -> str:
        cfg = self.filters
        area = cfg.get("area_range", {})
        params = ["deal_type=sale", "offer_type=flat", "region=1", "engine_version=2"]
        if area.get("min"):
            params.append(f"minarea={area['min']}")
        if area.get("max"):
            params.append(f"maxarea={area['max']}")
        if cfg.get("price_max"):
            params.append(f"maxprice={cfg['price_max']}")
        floor = cfg.get("floor", {})
        if floor.get("not_first"):
            params.append("floornl=1")
        if district_ids:
            for did in district_ids:
                params.append(f"district%5B%5D={did}")
        return f"{self.BASE_URL}/cat.php?" + "&".join(params)

    def _is_in_ttk(self, address: str, district: str = None) -> bool:
        ttk_districts = self._get_ttk_districts()
        if district:
            for d in ttk_districts:
                if d.lower() in district.lower():
                    return True
        if address:
            addr_lower = address.lower()
            for d in ttk_districts:
                if d.lower() in addr_lower:
                    return True
            if "цао" in addr_lower or "центральный" in addr_lower:
                return True
        return False

    def _extract_district(self, address: str) -> Optional[str]:
        for district in TTK_DISTRICT_NAMES:
            if district.lower() in address.lower():
                return district
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def parse_listings(self, max_pages: int = 3) -> list[CianListing]:
        if not self.browser:
            await self.init_browser()
        ttk_districts = self._get_ttk_districts()
        district_ids = [TTK_DISTRICT_IDS[d] for d in ttk_districts if d in TTK_DISTRICT_IDS]
        ctx = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await ctx.new_page()
        listings = []
        try:
            for p_num in range(1, max_pages + 1):
                url = self._build_url(district_ids) + f"&p={p_num}"
                print(f"[Cian] Page {p_num}...")
                await page.goto(url, wait_until="networkidle", timeout=45000)
                await asyncio.sleep(2)
                try:
                    await page.wait_for_selector("article[data-name='CardComponent']", timeout=15000)
                except:
                    break
                items = await page.query_selector_all("article[data-name='CardComponent']")
                print(f"[Cian] Found {len(items)} items")
                for item in items:
                    listing = await self._parse_card(item)
                    if listing and self._is_in_ttk(listing.address, listing.district):
                        listings.append(listing)
                await asyncio.sleep(3)
        finally:
            await ctx.close()
        return listings

    async def _parse_card(self, item) -> Optional[CianListing]:
        try:
            link_el = await item.query_selector("a[href*='/flat/']")
            if not link_el:
                return None
            link = await link_el.get_attribute("href")
            ext_id = re.search(r"/flat/(\d+)/", link)
            if not ext_id:
                return None
            title_el = await item.query_selector("[data-name='TitleComponent']")
            title = await title_el.inner_text() if title_el else ""
            addr_el = await item.query_selector("[data-name='GeoLabel']")
            address = await addr_el.inner_text() if addr_el else ""
            district = self._extract_district(address)
            price_el = await item.query_selector("[data-name='Price']")
            price_txt = await price_el.inner_text() if price_el else "0"
            price = float(re.sub(r"[^\d]", "", price_txt) or 0)
            area_m = re.search(r"(\d+(?:[,.]\d+)?)\s*м", title)
            area = float(area_m.group(1).replace(",", ".")) if area_m else 0
            rooms_m = re.search(r"(\d+)-комн", title)
            rooms = int(rooms_m.group(1)) if rooms_m else 0
            floor_m = re.search(r"(\d+)/(\d+)\s*этаж", title)
            floor = int(floor_m.group(1)) if floor_m else 0
            total_fl = int(floor_m.group(2)) if floor_m else 0
            ppm2 = round(price / area, 0) if area > 0 else 0
            cfg = self.filters.get("floor", {})
            if cfg.get("not_first") and floor == 1:
                return None
            if cfg.get("not_last") and floor == total_fl and total_fl > 0:
                return None
            return CianListing(
                external_id=ext_id.group(1), title=title, address=address,
                district=district, area=area, floor=floor, total_floors=total_fl,
                rooms=rooms, price=price, price_per_m2=ppm2, link=link, photos=[]
            )
        except:
            return None

