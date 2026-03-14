"""
SQL-запросы для работы с RSS-новостями театров.
"""
from datetime import date, timedelta


async def get_recent_news(pool, days: int = 7, limit: int = 20) -> list[dict]:
    """Новости за последние N дней."""
    since = date.today() - timedelta(days=days)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT rn.title, rn.summary, rn.url, rn.published_at,
                   t.name AS theater_name, t.slug AS theater_slug
            FROM rss_news rn
            JOIN theaters t ON t.id = rn.theater_id
            WHERE rn.published_at >= $1 OR rn.collected_at >= $1
            ORDER BY COALESCE(rn.published_at, rn.collected_at) DESC
            LIMIT $2
            """,
            since, limit,
        )
    return [dict(r) for r in rows]


async def get_news_for_theater(pool, theater_slug: str,
                               limit: int = 10) -> list[dict]:
    """Новости конкретного театра."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT rn.title, rn.summary, rn.url, rn.published_at
            FROM rss_news rn
            JOIN theaters t ON t.id = rn.theater_id
            WHERE t.slug = $1
            ORDER BY COALESCE(rn.published_at, rn.collected_at) DESC
            LIMIT $2
            """,
            theater_slug, limit,
        )
    return [dict(r) for r in rows]


async def get_news_count(pool) -> int:
    """Общее количество новостей."""
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT count(*) FROM rss_news")
