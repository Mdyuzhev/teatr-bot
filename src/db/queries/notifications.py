"""
SQL-запросы для лога уведомлений (антиспам).
UNIQUE(user_id, type, ref_id) не даёт отправить одно уведомление дважды.
"""


async def is_notification_sent(pool, user_id: int, type_: str, ref_id: int) -> bool:
    """Проверить, отправлялось ли уведомление."""
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            """
            SELECT 1 FROM notification_log
            WHERE user_id = $1 AND type = $2 AND ref_id = $3
            """,
            user_id, type_, ref_id,
        )
    return val is not None


async def log_notification(pool, user_id: int, type_: str, ref_id: int) -> None:
    """Записать отправленное уведомление."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO notification_log (user_id, type, ref_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            user_id, type_, ref_id,
        )


async def get_new_show_dates(pool, hours: int = 24) -> list[dict]:
    """Новые даты показов за последние N часов (для уведомлений)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sd.id AS show_date_id, sd.date, sd.time,
                   s.id AS show_id, s.title,
                   t.id AS theater_id, t.name AS theater_name
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE sd.created_at >= NOW() - ($1 || ' hours')::INTERVAL
              AND sd.is_cancelled = FALSE
            ORDER BY sd.date
            """,
            str(hours),
        )
    return [dict(r) for r in rows]


async def get_last_chance_shows(pool) -> list[dict]:
    """Спектакли с ровно 2 оставшимися показами (триггер last_chance)."""
    from datetime import date as date_type
    today = date_type.today()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.id AS show_id, s.title,
                   t.id AS theater_id, t.name AS theater_name,
                   COUNT(sd.id) AS remaining
            FROM shows s
            JOIN theaters t ON t.id = s.theater_id
            JOIN show_dates sd ON sd.show_id = s.id
                AND sd.date >= $1 AND sd.is_cancelled = FALSE
            GROUP BY s.id, s.title, t.id, t.name
            HAVING COUNT(sd.id) = 2
            """,
            today,
        )
    return [dict(r) for r in rows]
