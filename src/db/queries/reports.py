"""
SQL-запросы для формирования дайджестов.
Агрегированные выборки для передачи в digest_builder.py.
"""
from datetime import date


async def get_digest_data(pool, date_from: date, date_to: date, limit: int = 20) -> dict:
    """Агрегированные данные для дайджеста за период.

    Возвращает dict с ключами:
    - shows: список показов с театрами
    - premieres: список премьер
    - stats: общая статистика (theaters_count, shows_count, dates_count)
    """
    async with pool.acquire() as conn:
        # Все показы за период
        shows = await conn.fetch(
            """
            SELECT s.title, s.slug, s.age_rating, s.is_premiere,
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
            LIMIT $3
            """,
            date_from, date_to, limit,
        )

        # Статистика
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT t.id) AS theaters_count,
                COUNT(DISTINCT s.id) AS shows_count,
                COUNT(sd.id) AS dates_count
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE sd.date BETWEEN $1 AND $2
              AND sd.is_cancelled = FALSE
            """,
            date_from, date_to,
        )

        # Премьеры за период
        premieres = await conn.fetch(
            """
            SELECT DISTINCT s.title, t.name AS theater_name,
                   MIN(sd.date) AS first_date
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE s.is_premiere = TRUE
              AND sd.date BETWEEN $1 AND $2
              AND sd.is_cancelled = FALSE
            GROUP BY s.id, s.title, t.name
            ORDER BY first_date
            """,
            date_from, date_to,
        )

    return {
        "shows": [dict(r) for r in shows],
        "premieres": [dict(r) for r in premieres],
        "stats": dict(stats) if stats else {"theaters_count": 0, "shows_count": 0, "dates_count": 0},
    }


async def get_bot_stats(pool) -> dict:
    """Статистика для команды /status."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                (SELECT count(*) FROM theaters) AS theaters,
                (SELECT count(*) FROM shows) AS shows,
                (SELECT count(*) FROM show_dates WHERE date >= CURRENT_DATE) AS upcoming_dates,
                (SELECT count(*) FROM show_dates WHERE date >= CURRENT_DATE AND is_cancelled = FALSE) AS active_dates,
                (SELECT max(created_at) FROM show_dates) AS last_collected
            """
        )
    return dict(row) if row else {}
