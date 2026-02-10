"""
Cian API Parser - uses internal JSON API instead of HTML scraping
"""
import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# TTK districts IDs for Cian
TTK_DISTRICTS = {
    "Арбат": 13,
    "Басманный": 14,
    "Замоскворечье": 15,
    "Красносельский": 16,
    "Мещанский": 17,
    "Пресненский": 18,
    "Таганский": 19,
    "Тверской": 20,
    "Хамовники": 21,
    "Якиманка": 22,
    "Беговой": 95,
    "Савёловский": 107,
    "Хорошёвский": 116,
    "Аэропорт": 120,
    "Сокол": 140,
    "Дорогомилово": 150,
    "Раменки": 156,
    "Даниловский": 163,
    "Донской": 164,
    "Лефортово": 175,
}

API_URL = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://www.cian.ru",
    "Referer": "https://www.cian.ru/",
}

def build_search_query(page: int = 1, rooms: Optional[List[int]] = None) -> dict:
    """Build JSON query for Cian API"""
    query = {
        "jsonQuery": {
            "_type": "flatSale",
            "engine_version": {"type": "term", "value": 2},
            "region": {"type": "terms", "value": [1]},  # Moscow
            "geo": {
                "type": "geo",
                "value": [{"type": "district", "id": d} for d in TTK_DISTRICTS.values()]
            },
            "total_area": {"type": "range", "value": {"gte": 38, "lte": 150}},
            "price": {"type": "range", "value": {"lte": 100000000}},
            "floor": {"type": "range", "value": {"gte": 2}},  # not first floor
            "is_first_floor": {"type": "term", "value": False},
            "object_type": {"type": "terms", "value": [2]},  # secondary market (вторичка)
            "page": {"type": "term", "value": page},
            "sort": {"type": "term", "value": "creation_date_desc"},
        }
    }
    
    if rooms:
        query["jsonQuery"]["room"] = {"type": "terms", "value": rooms}
    
    return query


async def fetch_cian_api(session: aiohttp.ClientSession, page: int, rooms: Optional[List[int]] = None) -> List[Dict]:
    """Fetch listings from Cian API"""
    results = []
    query = build_search_query(page, rooms)
    
    try:
        async with session.post(API_URL, json=query, headers=HEADERS, timeout=30) as resp:
            if resp.status != 200:
                logger.error(f"API error: {resp.status}")
                return []
            
            data = await resp.json()
            offers = data.get("data", {}).get("offersSerialized", [])
            
            logger.info(f"Page {page}: got {len(offers)} offers from API")
            
            for offer in offers:
                try:
                    # Extract data from API response
                    geo = offer.get("geo", {})
                    address_parts = []
                    
                    # Build address
                    if geo.get("address"):
                        for addr in geo["address"]:
                            if addr.get("type") in ["location", "street", "house"]:
                                address_parts.append(addr.get("fullName", ""))
                    
                    address = ", ".join(filter(None, address_parts))
                    
                    # Get district
                    district = "ЦАО"
                    districts = geo.get("districts", [])
                    if districts:
                        district = districts[0].get("name", "ЦАО")
                    
                    # Get price info
                    bargain = offer.get("bargainTerms", {})
                    price = bargain.get("price", 0)
                    price_per_m = bargain.get("pricePerMeter", 0)
                    
                    # Get flat info
                    total_area = offer.get("totalArea", 0)
                    living_area = offer.get("livingArea", 0)
                    rooms_count = offer.get("roomsCount", 0)
                    floor_num = offer.get("floorNumber", 0)
                    floors_total = offer.get("building", {}).get("floorsCount", 0)
                    
                    # Building info
                    building = offer.get("building", {})
                    build_year = building.get("buildYear", 0)
                    building_type = "Новый" if build_year and build_year >= 2015 else "Вторичка"
                    
                    # Renovation/repair
                    repair = offer.get("decoration", "")
                    repair_map = {
                        "design": "Дизайнерский",
                        "euro": "Евро",
                        "cosmetic": "Косметический",
                        "without": "Без ремонта",
                        "fine": "Чистовая",
                    }
                    renovation = repair_map.get(repair, "")
                    
                    # Parking
                    parking = ""
                    if offer.get("parking"):
                        parking_type = offer.get("parking", {}).get("type", "")
                        if "underground" in parking_type:
                            parking = "Подземная"
                        elif "ground" in parking_type:
                            parking = "Наземная"
                        else:
                            parking = "Есть"
                    
                    # Seller type
                    seller = ""
                    offer_type = offer.get("offerType", "")
                    if offer.get("isDeveloper"):
                        seller = "Застройщик"
                    elif offer.get("isFromBuilder"):
                        seller = "Застройщик"
                    elif "agent" in str(offer.get("user", {})).lower():
                        seller = "Агентство"
                    else:
                        seller = "Собственник"
                    
                    result = {
                        "external_id": str(offer.get("id", "")),
                        "link": f"https://www.cian.ru/sale/flat/{offer.get('cianId', offer.get('id'))}/",
                        "address": address,
                        "district": district,
                        "area": total_area,
                        "living_area": living_area,
                        "rooms": str(rooms_count) if rooms_count else "?",
                        "floor": f"{floor_num}/{floors_total}" if floors_total else str(floor_num),
                        "building_type": building_type,
                        "renovation": renovation,
                        "parking": parking,
                        "seller": seller,
                        "price": price,
                        "price_m2": price_per_m or (round(price / total_area) if total_area else 0),
                    }
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.warning(f"Parse offer error: {e}")
                    continue
                    
    except asyncio.TimeoutError:
        logger.error(f"API timeout on page {page}")
    except Exception as e:
        logger.error(f"API error: {e}")
    
    return results


async def search_cian_api(max_pages: int = 5, rooms_filter: Optional[List[int]] = None) -> List[Dict]:
    """Search Cian using API, returns all results"""
    all_results = []
    
    async with aiohttp.ClientSession() as session:
        for page in range(1, max_pages + 1):
            results = await fetch_cian_api(session, page, rooms_filter)
            all_results.extend(results)
            
            if len(results) < 20:  # Less than full page = no more results
                break
                
            await asyncio.sleep(2)  # Delay between requests
    
    return all_results


# Test
if __name__ == "__main__":
    async def test():
        results = await search_cian_api(max_pages=2)
        print(f"Total: {len(results)}")
        if results:
            print(f"Sample: {results[0]}")
    
    asyncio.run(test())
