import argparse
import asyncio
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright


WKU_LAT = 35.96944
WKU_LNG = 126.95735

DEFAULT_QUERIES = [
    "원광대학교 음식점",
    "원광대학교 카페",
    "원광대 음식점",
    "원광대 카페",
    "원광대 맛집",
]

FOOD_CATEGORY_WORDS = [
    "음식점",
    "카페",
    "디저트",
    "베이커리",
    "한식",
    "양식",
    "분식",
    "일식",
    "중식",
    "아시아",
    "햄버거",
    "샌드위치",
    "도시락",
    "컵밥",
    "국밥",
    "냉면",
    "칼국수",
    "만두",
    "아이스크림",
    "테이크아웃커피",
    "과일",
    "주스",
    "차",
    "피자",
    "치킨",
    "돈가스",
    "떡볶이",
    "고기",
]


def distance_meters(lat1, lng1, lat2, lng2):
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_food_or_cafe(item):
    category_text = " ".join(item.get("category") or [])
    return any(word in category_text for word in FOOD_CATEGORY_WORDS)


def classify_place(item):
    text = " ".join([item.get("name", ""), *item.get("category", [])])
    cafe_words = ["카페", "디저트", "커피", "베이커리", "아이스크림", "빵", "제과", "음료"]
    return "cafe" if any(word in text for word in cafe_words) else "restaurant"


def status_text(item):
    status = (item.get("businessStatus") or {}).get("status") or {}
    return status.get("text") or ""


def status_detail(item):
    status = (item.get("businessStatus") or {}).get("status") or {}
    return status.get("detailInfo") or ""


def normalize_place(item, query):
    lat = float(item.get("y") or 0)
    lng = float(item.get("x") or 0)
    place_id = str(item.get("id") or "")
    business = item.get("businessStatus") or {}

    return {
        "id": place_id,
        "name": item.get("name") or "",
        "type": classify_place(item),
        "categories": item.get("category") or [],
        "road_address": item.get("roadAddress") or "",
        "address": item.get("address") or "",
        "phone": item.get("telDisplay") or item.get("tel") or item.get("virtualTelDisplay") or item.get("virtualTel") or "",
        "lat": lat,
        "lng": lng,
        "distance_m": round(distance_meters(WKU_LAT, WKU_LNG, lat, lng)),
        "business_status": status_text(item),
        "business_status_detail": status_detail(item),
        "business_hours": business.get("businessHours") or "",
        "break_time": business.get("breakTime") or "",
        "last_order": business.get("lastOrder") or "",
        "review_count": item.get("reviewCount") or 0,
        "place_review_count": item.get("placeReviewCount") or 0,
        "menu_exists": bool(item.get("menuExist")),
        "menu_info": item.get("menuInfo") or "",
        "thumbnail_url": item.get("thumUrl") or "",
        "thumbnail_urls": item.get("thumUrls") or [],
        "homepage": item.get("homePage") or "",
        "naver_map_url": f"https://map.naver.com/p/entry/place/{place_id}" if place_id else "",
        "mobile_place_url": f"https://m.place.naver.com/restaurant/{place_id}/home" if place_id else "",
        "source_queries": [query],
    }


async def extract_places_for_query(browser, query, timeout_ms):
    context = await browser.new_context(
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    places = []
    first_meta = None

    async def handle_response(response):
        nonlocal places, first_meta
        if "/p/api/search/allSearch" not in response.url:
            return
        try:
            data = await response.json()
        except Exception:
            return
        result = data.get("result") or {}
        place = result.get("place") or {}
        items = place.get("list") or []
        if items and not places:
            places = items
            first_meta = {
                "query": query,
                "url": response.url,
                "page": place.get("page"),
                "total_count": place.get("totalCount"),
                "feedback": place.get("feedback"),
                "boundary": place.get("boundary"),
            }

    page.on("response", handle_response)

    url = f"https://map.naver.com/p/search/{quote(query)}"
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    waited = 0
    while waited < timeout_ms and not places:
        await page.wait_for_timeout(500)
        waited += 500

    await page.close()
    await context.close()
    return first_meta, places


async def crawl_places(queries, radius_meters, timeout_ms):
    results_by_id = {}
    query_meta = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/google-chrome",
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )

        for query in queries:
            meta, raw_places = await extract_places_for_query(browser, query, timeout_ms)
            if meta:
                query_meta.append(meta)
            for item in raw_places:
                if not is_food_or_cafe(item):
                    continue
                normalized = normalize_place(item, query)
                if normalized["distance_m"] > radius_meters:
                    continue
                existing = results_by_id.get(normalized["id"])
                if existing:
                    if query not in existing["source_queries"]:
                        existing["source_queries"].append(query)
                    continue
                results_by_id[normalized["id"]] = normalized
            await asyncio.sleep(1.2)

        await browser.close()

    results = sorted(results_by_id.values(), key=lambda place: (place["distance_m"], place["name"]))
    return query_meta, results


def write_outputs(places, query_meta, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    payload = {
        "captured_at": captured_at,
        "source": "Naver Map / Place search responses",
        "center": {"name": "원광대학교", "lat": WKU_LAT, "lng": WKU_LNG},
        "query_meta": query_meta,
        "count": len(places),
        "places": places,
    }

    json_path = output_dir / "naver_wku_places.json"
    csv_path = output_dir / "naver_wku_places.csv"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "id",
        "name",
        "type",
        "categories",
        "road_address",
        "address",
        "phone",
        "lat",
        "lng",
        "distance_m",
        "business_status",
        "business_status_detail",
        "review_count",
        "place_review_count",
        "menu_exists",
        "menu_info",
        "thumbnail_url",
        "homepage",
        "naver_map_url",
        "mobile_place_url",
        "source_queries",
    ]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for place in places:
            row = {field: place.get(field, "") for field in fields}
            row["categories"] = " > ".join(place.get("categories") or [])
            row["source_queries"] = " | ".join(place.get("source_queries") or [])
            writer.writerow(row)

    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser(description="Crawl Wonkwang University nearby food and cafe places from Naver Map.")
    parser.add_argument("--query", action="append", dest="queries", help="검색어. 여러 번 지정 가능.")
    parser.add_argument("--radius-meters", type=int, default=2000, help="원광대 기준 포함 반경. 기본 2000m.")
    parser.add_argument("--timeout-ms", type=int, default=20000, help="검색어당 대기 시간. 기본 20000ms.")
    parser.add_argument("--output-dir", default="crawl_output", help="결과 저장 폴더.")
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    query_meta, places = asyncio.run(crawl_places(queries, args.radius_meters, args.timeout_ms))
    json_path, csv_path = write_outputs(places, query_meta, Path(args.output_dir))

    restaurant_count = sum(1 for place in places if place["type"] == "restaurant")
    cafe_count = sum(1 for place in places if place["type"] == "cafe")
    print(f"Saved {len(places)} places: {restaurant_count} restaurants, {cafe_count} cafes")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
