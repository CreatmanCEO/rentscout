import asyncio
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


class CianParser:
    BASE_URL = "https://www.cian.ru"

    def __init__(self):
        self.browser: Optional[Browser] = None

    async def init_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

    async def close(self):
        if self.browser:
            await self.browser.close()

    def _build_url(self, filters: dict) -> str:
        base = f"{self.BASE_URL}/cat.php?deal_type=sale&offer_type=flat&region=1"
        if filters.get("min_area"):
            base += f"&minarea={filters['min_area']}"
        if filters.get("max_area"):
            base += f"&maxarea={filters['max_area']}"
        if filters.get("max_price"):
            base += f"&maxprice={filters['max_price']}"
        if filters.get("not_first_floor"):
            base += "&floornl=1"
        if filters.get("from_owner"):
            base += "&is_by_homeowner=1"
        return base

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def parse_listings(self, filters: dict, max_pages: int = 5) -> list[CianListing]:
        if not self.browser:
            await self.init_browser()
        ctx = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await ctx.new_page()
        listings = []
        try:
            for p_num in range(1, max_pages + 1):
                url = self._build_url(filters) + f"&p={p_num}"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_selector("article[data-name='CardComponent']", timeout=10000)
                items = await page.query_selector_all("article[data-name='CardComponent']")
                for item in items:
                    listing = await self._parse_card(item)
                    if listing:
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
            price_el = await item.query_selector("[data-name='Price']")
            price_txt = await price_el.inner_text() if price_el else "0"
            price = float(re.sub(r"[^\d]", "", price_txt) or 0)
            area_m = re.search(r"(\d+(?:,\d+)?)\s*м", title)
            area = float(area_m.group(1).replace(",", ".")) if area_m else 0
            rooms_m = re.search(r"(\d+)-комн", title)
            rooms = int(rooms_m.group(1)) if rooms_m else 0
            floor_m = re.search(r"(\d+)/(\d+)\s*этаж", title)
            floor = int(floor_m.group(1)) if floor_m else 0
            total_fl = int(floor_m.group(2)) if floor_m else 0
            ppm2 = round(price / area, 0) if area > 0 else 0
            return CianListing(
                external_id=ext_id.group(1), title=title, address=address,
                area=area, floor=floor, total_floors=total_fl, rooms=rooms,
                price=price, price_per_m2=ppm2, link=link, photos=[]
            )
        except:
            return None


STEINIK_FILTERS = {
    "min_area": 38, "max_area": 150, "max_price": 100000000,
    "rooms": [1, 2, 3, 4], "not_first_floor": True, "from_owner": True
}
