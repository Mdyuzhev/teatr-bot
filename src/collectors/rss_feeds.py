"""
RSS-коллектор новостей московских театров.

Собирает новости из RSS-фидов, связывает с театрами в БД по имени,
сохраняет в таблицу rss_news. Graceful degradation — если фид
недоступен, пропускаем и идём дальше.
"""
import re
from datetime import datetime, timezone

import feedparser
import requests
from loguru import logger


# Фиды с привязкой к театру (theater_slug → url)
# slug должен совпадать с theaters.slug в БД (из KudaGo)
RSS_FEEDS: dict[str, dict] = {
    "teatr-sats": {
        "url": "https://teatr-sats.ru/feed",
        "theater_name": "Театр им. Н.И. Сац",
    },
}

# Фиды без привязки к конкретному театру (общие театральные новости)
GENERAL_FEEDS: list[dict] = []


class RssCollector:
    """Коллектор RSS-новостей театров."""

    def __init__(self, feeds: dict[str, dict] | None = None):
        self.feeds = feeds or RSS_FEEDS

    def collect_all(self) -> list[dict]:
        """Собрать новости из всех фидов. Возвращает список записей."""
        all_news: list[dict] = []

        for slug, feed_info in self.feeds.items():
            url = feed_info["url"]
            theater_name = feed_info.get("theater_name", slug)
            try:
                entries = self._fetch_feed(url)
                for entry in entries:
                    news = self._parse_entry(entry, slug, theater_name)
                    if news:
                        all_news.append(news)
            except Exception as e:
                logger.warning("RSS {}: ошибка — {}", slug, e)

        logger.info("RSS: собрано {} новостей из {} фидов",
                     len(all_news), len(self.feeds))
        return all_news

    async def save_to_db(self, news: list[dict], pool) -> dict:
        """Сохранить новости в rss_news. Возвращает статистику."""
        stats = {"saved": 0, "skipped": 0, "no_theater": 0}

        async with pool.acquire() as conn:
            for item in news:
                # Найти theater_id по slug или имени
                theater_id = await conn.fetchval(
                    "SELECT id FROM theaters WHERE slug = $1",
                    item["theater_slug"],
                )
                if not theater_id:
                    # Попробовать по имени (нечёткий поиск)
                    theater_id = await conn.fetchval(
                        "SELECT id FROM theaters WHERE LOWER(name) LIKE $1 LIMIT 1",
                        f"%{item['theater_name'].lower()[:20]}%",
                    )
                if not theater_id:
                    stats["no_theater"] += 1
                    continue

                # Upsert по url (UNIQUE)
                result = await conn.execute(
                    """
                    INSERT INTO rss_news (theater_id, title, summary, url, published_at)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (url) DO NOTHING
                    """,
                    theater_id,
                    item["title"][:500],
                    item.get("summary", "")[:2000],
                    item["url"],
                    item.get("published_at"),
                )
                if result == "INSERT 0 1":
                    stats["saved"] += 1
                else:
                    stats["skipped"] += 1

        logger.info("RSS в БД: {} новых, {} дубликатов, {} без театра",
                     stats["saved"], stats["skipped"], stats["no_theater"])
        return stats

    def _fetch_feed(self, url: str) -> list:
        """Загрузить и распарсить RSS-фид."""
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "TeatrBot/1.0 (RSS collector)",
        })
        resp.raise_for_status()

        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            logger.warning("RSS {}: невалидный фид", url)
            return []

        return feed.entries

    def _parse_entry(self, entry, theater_slug: str,
                     theater_name: str) -> dict | None:
        """Распарсить одну запись RSS."""
        title = entry.get("title", "").strip()
        if not title:
            return None

        link = entry.get("link", "")
        if not link:
            return None

        # summary: может быть HTML — очистим
        summary = entry.get("summary", "") or entry.get("description", "")
        summary = _strip_html(summary).strip()

        # Дата публикации
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        published_at = None
        if published:
            try:
                published_at = datetime(*published[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        return {
            "theater_slug": theater_slug,
            "theater_name": theater_name,
            "title": title,
            "summary": summary[:2000],
            "url": link,
            "published_at": published_at,
        }


def _strip_html(text: str) -> str:
    """Удалить HTML-теги из текста."""
    return re.sub(r"<[^>]+>", "", text)
