"""
Коллектор KudaGo API.
Собирает афишу московских театров на N дней вперёд.

API: https://kudago.com/public-api/v1.4/events/
Параметры: location=msk&categories=theater&expand=place,dates
"""
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

from src.config import Config


KUDAGO_API = "https://kudago.com/public-api/v1.4/events/"

MSK = timezone(timedelta(hours=3))


class KudaGoCollector:

    def __init__(self, config: Config):
        self.config = config

    # ── публичные методы ──

    def fetch_events(self, days_ahead: int | None = None) -> list[dict]:
        """Загрузить события из KudaGo с пагинацией. Возвращает сырой список event-ов."""
        if days_ahead is None:
            days_ahead = self.config.KUDAGO_DAYS_AHEAD

        now = datetime.now(MSK)
        since = int(now.timestamp())
        until = int((now + timedelta(days=days_ahead)).timestamp())

        all_events: list[dict] = []
        offset = 0
        page_size = self.config.KUDAGO_PAGE_SIZE

        while True:
            params = {
                "location": "msk",
                "categories": "theater",
                "expand": "place,dates",
                "page_size": page_size,
                "offset": offset,
                "actual_since": since,
                "actual_until": until,
                "fields": "id,title,slug,body_text,tags,age_restriction,price,place,dates,images",
            }
            data = self._request_with_retry(params)
            if data is None:
                break

            results = data.get("results", [])
            if not results:
                break

            # Фильтруем события без площадки
            for event in results:
                if event.get("place") and isinstance(event["place"], dict):
                    all_events.append(event)

            offset += page_size
            count = data.get("count", 0)
            if offset >= count:
                break

        logger.info("KudaGo: загружено {} событий на {} дней вперёд", len(all_events), days_ahead)
        return all_events

    async def save_to_db(self, events: list[dict], pool) -> dict:
        """Сохранить события в БД. Возвращает статистику."""
        stats = {"theaters": 0, "shows": 0, "dates": 0}

        async with pool.acquire() as conn:
            for event in events:
                try:
                    theater = self._parse_theater(event.get("place", {}))
                    show = self._parse_show(event)
                    dates = self._parse_dates(event)

                    # Upsert theater
                    theater_id = await conn.fetchval(
                        """
                        INSERT INTO theaters (name, slug, address, metro, url, source)
                        VALUES ($1, $2, $3, $4, $5, 'kudago')
                        ON CONFLICT (slug) DO UPDATE SET
                            name = EXCLUDED.name,
                            address = EXCLUDED.address,
                            metro = EXCLUDED.metro,
                            url = EXCLUDED.url
                        RETURNING id
                        """,
                        theater["name"], theater["slug"], theater["address"],
                        theater["metro"], theater["url"],
                    )
                    stats["theaters"] += 1

                    # Upsert show
                    show_id = await conn.fetchval(
                        """
                        INSERT INTO shows (theater_id, title, slug, age_rating, description,
                                           is_premiere, image_url, source)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, 'kudago')
                        ON CONFLICT (slug) DO UPDATE SET
                            title = EXCLUDED.title,
                            description = EXCLUDED.description,
                            is_premiere = EXCLUDED.is_premiere,
                            image_url = COALESCE(EXCLUDED.image_url, shows.image_url)
                        RETURNING id
                        """,
                        theater_id, show["title"], show["slug"],
                        show["age_rating"], show["description"], show["is_premiere"],
                        show.get("image_url"),
                    )
                    stats["shows"] += 1

                    # Insert dates
                    for d in dates:
                        result = await conn.execute(
                            """
                            INSERT INTO show_dates (show_id, date, time, price_min, price_max)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (show_id, date, time, stage) DO NOTHING
                            """,
                            show_id, d["date"], d["time"], d["price_min"], d["price_max"],
                        )
                        if result == "INSERT 0 1":
                            stats["dates"] += 1

                except Exception as e:
                    logger.warning("Ошибка сохранения события {}: {}", event.get("slug", "?"), e)

        logger.info("Сохранено: {} театров, {} спектаклей, {} дат", stats["theaters"], stats["shows"], stats["dates"])
        return stats

    # ── парсеры ──

    def _parse_theater(self, place: dict) -> dict:
        return {
            "name": place.get("title", "Неизвестная площадка"),
            "slug": place.get("slug", "unknown"),
            "address": place.get("address", ""),
            "metro": place.get("subway", ""),
            "url": place.get("site_url", ""),
        }

    def _parse_show(self, event: dict) -> dict:
        raw_tags = event.get("tags", [])
        # KudaGo возвращает tags как массив строк, не объектов
        tags = []
        for t in raw_tags:
            if isinstance(t, dict):
                tags.append(t.get("slug", ""))
            else:
                tags.append(str(t).lower())
        is_premiere = "premera" in tags or "премьера" in tags or "премьеры" in tags

        age = event.get("age_restriction")
        if isinstance(age, str) and age:
            age_rating = age if "+" in age else f"{age}+"
        elif isinstance(age, (int, float)) and age > 0:
            age_rating = f"{int(age)}+"
        else:
            age_rating = None

        # Парсим первое изображение
        image_url = None
        images = event.get("images", [])
        if images and isinstance(images, list):
            first = images[0]
            if isinstance(first, dict):
                thumbnails = first.get("thumbnail", {})
                image_url = (
                    thumbnails.get("640x384")
                    or thumbnails.get("144x96")
                    or first.get("image")
                )

        return {
            "title": event.get("title", ""),
            "slug": event.get("slug", ""),
            "description": (event.get("body_text") or "")[:2000],
            "age_rating": age_rating,
            "is_premiere": is_premiere,
            "image_url": image_url,
        }

    def _parse_dates(self, event: dict) -> list[dict]:
        result = []
        price_str = event.get("price", "")
        event_price_min, event_price_max = self._parse_price(price_str)

        for d in event.get("dates", []):
            start_ts = d.get("start")
            if not start_ts:
                continue

            dt = datetime.fromtimestamp(start_ts, tz=MSK)
            date_val = dt.date()
            time_val = dt.time()

            # Цена из конкретной даты, если есть
            date_price = d.get("price", "")
            if date_price:
                p_min, p_max = self._parse_price(date_price)
            else:
                p_min, p_max = event_price_min, event_price_max

            result.append({
                "date": date_val,
                "time": time_val,
                "price_min": p_min,
                "price_max": p_max,
            })
        return result

    @staticmethod
    def _parse_price(price_str: str) -> tuple[int | None, int | None]:
        """Парсинг строки цены в (min, max)."""
        if not price_str:
            return None, None

        price_str = price_str.strip().lower()

        if "бесплатно" in price_str:
            return 0, 0

        # "от 5600 до 6900 рублей"
        m = re.search(r"от\s+(\d[\d\s]*)\s+до\s+(\d[\d\s]*)", price_str)
        if m:
            p_min = int(m.group(1).replace(" ", ""))
            p_max = int(m.group(2).replace(" ", ""))
            return p_min, p_max

        # "500-3500 руб" или "500 — 3500"
        m = re.search(r"(\d[\d\s]*)\s*[-–—]\s*(\d[\d\s]*)", price_str)
        if m:
            p_min = int(m.group(1).replace(" ", ""))
            p_max = int(m.group(2).replace(" ", ""))
            return p_min, p_max

        # "от 1000 руб"
        m = re.search(r"от\s+(\d[\d\s]*)", price_str)
        if m:
            return int(m.group(1).replace(" ", "")), None

        # Просто число: "300"
        m = re.search(r"(\d[\d\s]*)", price_str)
        if m:
            return int(m.group(1).replace(" ", "")), None

        return None, None

    # ── HTTP ──

    def _request_with_retry(self, params: dict, retries: int = 3) -> dict | None:
        """GET-запрос с retry и backoff."""
        for attempt in range(retries):
            try:
                resp = requests.get(KUDAGO_API, params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                wait = 2 ** attempt
                logger.warning("KudaGo запрос #{}: {} — повтор через {}с", attempt + 1, e, wait)
                if attempt < retries - 1:
                    time.sleep(wait)

        logger.error("KudaGo: все {} попыток исчерпаны", retries)
        return None
