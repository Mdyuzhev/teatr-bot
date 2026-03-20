"""
SQL-запросы для работы со спектаклями и датами показов.
Все функции принимают asyncpg pool и возвращают list[dict].
"""
from datetime import date, timedelta


async def get_shows_by_period(pool, date_from: date, date_to: date) -> list[dict]:
    """Уникальные спектакли в заданном периоде с инфой о театре (ближайшая дата)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM (
                SELECT DISTINCT ON (s.id)
                       s.id AS show_id, s.title, s.slug, s.genre,
                       s.age_rating, s.is_premiere, s.description,
                       s.image_url,
                       t.id AS theater_id, t.name AS theater_name,
                       t.slug AS theater_slug, t.address, t.metro,
                       sd.date, sd.time, sd.price_min, sd.price_max,
                       sd.tickets_url
                FROM show_dates sd
                JOIN shows s ON s.id = sd.show_id
                JOIN theaters t ON t.id = s.theater_id
                WHERE sd.date BETWEEN $1 AND $2
                  AND sd.is_cancelled = FALSE
                ORDER BY s.id, sd.date, sd.time
            ) sub
            ORDER BY date, time
            """,
            date_from, date_to,
        )
    return [dict(r) for r in rows]


async def get_shows_by_theater(pool, theater_slug: str, date_from: date, date_to: date) -> list[dict]:
    """Уникальные спектакли конкретного театра в периоде (ближайшая дата)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM (
                SELECT DISTINCT ON (s.id)
                       s.id AS show_id, s.title, s.slug, s.age_rating,
                       s.is_premiere, s.description, s.image_url,
                       t.id AS theater_id, t.name AS theater_name,
                       sd.date, sd.time, sd.price_min, sd.price_max,
                       sd.tickets_url
                FROM show_dates sd
                JOIN shows s ON s.id = sd.show_id
                JOIN theaters t ON t.id = s.theater_id
                WHERE t.slug = $1
                  AND sd.date BETWEEN $2 AND $3
                  AND sd.is_cancelled = FALSE
                ORDER BY s.id, sd.date, sd.time
            ) sub
            ORDER BY date, time
            """,
            theater_slug, date_from, date_to,
        )
    return [dict(r) for r in rows]


async def get_premieres(pool, days: int = 30) -> list[dict]:
    """Уникальные премьеры в ближайшие N дней (ближайшая дата)."""
    today = date.today()
    until = today + timedelta(days=days)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM (
                SELECT DISTINCT ON (s.id)
                       s.id AS show_id, s.title, s.slug, s.age_rating,
                       s.description, s.image_url,
                       t.id AS theater_id, t.name AS theater_name,
                       t.slug AS theater_slug, t.metro,
                       sd.date, sd.time, sd.price_min, sd.price_max,
                       sd.tickets_url
                FROM show_dates sd
                JOIN shows s ON s.id = sd.show_id
                JOIN theaters t ON t.id = s.theater_id
                WHERE s.is_premiere = TRUE
                  AND sd.date BETWEEN $1 AND $2
                  AND sd.is_cancelled = FALSE
                ORDER BY s.id, sd.date, sd.time
            ) sub
            ORDER BY date, time
            """,
            today, until,
        )
    return [dict(r) for r in rows]
