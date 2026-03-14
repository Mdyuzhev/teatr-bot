"""
SQL-запросы для работы со спектаклями и датами показов.
Все функции принимают asyncpg pool и возвращают list[dict].
"""
from datetime import date, timedelta


async def get_shows_by_period(pool, date_from: date, date_to: date) -> list[dict]:
    """Все показы в заданном периоде с инфой о театре."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.title, s.slug, s.genre, s.age_rating, s.is_premiere,
                   s.description,
                   t.name AS theater_name, t.slug AS theater_slug,
                   t.address, t.metro,
                   sd.date, sd.time, sd.price_min, sd.price_max
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE sd.date BETWEEN $1 AND $2
              AND sd.is_cancelled = FALSE
            ORDER BY sd.date, sd.time
            """,
            date_from, date_to,
        )
    return [dict(r) for r in rows]


async def get_shows_by_theater(pool, theater_slug: str, date_from: date, date_to: date) -> list[dict]:
    """Показы конкретного театра в периоде."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.title, s.slug, s.age_rating, s.is_premiere, s.description,
                   sd.date, sd.time, sd.price_min, sd.price_max
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE t.slug = $1
              AND sd.date BETWEEN $2 AND $3
              AND sd.is_cancelled = FALSE
            ORDER BY sd.date, sd.time
            """,
            theater_slug, date_from, date_to,
        )
    return [dict(r) for r in rows]


async def get_premieres(pool, days: int = 30) -> list[dict]:
    """Только спектакли с is_premiere=True в ближайшие N дней."""
    today = date.today()
    until = today + timedelta(days=days)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.title, s.slug, s.age_rating, s.description,
                   t.name AS theater_name, t.slug AS theater_slug, t.metro,
                   sd.date, sd.time, sd.price_min, sd.price_max
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE s.is_premiere = TRUE
              AND sd.date BETWEEN $1 AND $2
              AND sd.is_cancelled = FALSE
            ORDER BY sd.date, sd.time
            """,
            today, until,
        )
    return [dict(r) for r in rows]
