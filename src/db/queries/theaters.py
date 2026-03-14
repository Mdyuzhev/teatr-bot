"""
SQL-запросы для работы с театрами.
"""
from datetime import date


async def get_all_theaters(pool) -> list[dict]:
    """Список всех театров с количеством предстоящих показов."""
    today = date.today()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.name, t.slug, t.address, t.metro, t.url,
                   COUNT(sd.id) AS upcoming_shows
            FROM theaters t
            LEFT JOIN shows s ON s.theater_id = t.id
            LEFT JOIN show_dates sd ON sd.show_id = s.id
                AND sd.date >= $1
                AND sd.is_cancelled = FALSE
            GROUP BY t.id
            ORDER BY upcoming_shows DESC, t.name
            """,
            today,
        )
    return [dict(r) for r in rows]


async def get_theater_by_slug(pool, slug: str) -> dict | None:
    """Найти театр по slug."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, slug, address, metro, url FROM theaters WHERE slug = $1",
            slug,
        )
    return dict(row) if row else None
