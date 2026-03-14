"""
SQL-запросы для пользовательских предпочтений (избранное / вишлист).

type='favorite' + ref_type='theater' — подписка на театр
type='watchlist' + ref_type='show'   — конкретный спектакль в интересном
"""
from datetime import date


async def toggle_preference(pool, user_id: int, type_: str,
                            ref_id: int, ref_type: str) -> bool:
    """Toggle: добавить если нет, удалить если есть. Возвращает True = активно."""
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            """
            SELECT id FROM user_preferences
            WHERE user_id = $1 AND type = $2 AND ref_id = $3 AND ref_type = $4
            """,
            user_id, type_, ref_id, ref_type,
        )
        if existing:
            await conn.execute(
                "DELETE FROM user_preferences WHERE id = $1", existing,
            )
            return False
        else:
            await conn.execute(
                """
                INSERT INTO user_preferences (user_id, type, ref_id, ref_type)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
                """,
                user_id, type_, ref_id, ref_type,
            )
            return True


async def has_preference(pool, user_id: int, type_: str,
                         ref_id: int, ref_type: str) -> bool:
    """Проверить наличие записи."""
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            """
            SELECT 1 FROM user_preferences
            WHERE user_id = $1 AND type = $2 AND ref_id = $3 AND ref_type = $4
            """,
            user_id, type_, ref_id, ref_type,
        )
    return val is not None


async def get_user_favorites(pool, user_id: int) -> list[dict]:
    """Избранные театры с количеством предстоящих показов."""
    today = date.today()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.name, t.slug, t.metro,
                   COUNT(sd.id) AS upcoming_shows
            FROM user_preferences up
            JOIN theaters t ON t.id = up.ref_id
            LEFT JOIN shows s ON s.theater_id = t.id
            LEFT JOIN show_dates sd ON sd.show_id = s.id
                AND sd.date >= $2 AND sd.is_cancelled = FALSE
            WHERE up.user_id = $1
              AND up.type = 'favorite' AND up.ref_type = 'theater'
            GROUP BY t.id, t.name, t.slug, t.metro
            ORDER BY upcoming_shows DESC, t.name
            """,
            user_id, today,
        )
    return [dict(r) for r in rows]


async def get_user_watchlist(pool, user_id: int) -> list[dict]:
    """Интересные спектакли с ближайшими датами. Помечает last_chance если <= 2 даты."""
    today = date.today()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.id, s.title, s.slug,
                   t.name AS theater_name, t.slug AS theater_slug,
                   MIN(sd.date) AS next_date,
                   MIN(sd.time) AS next_time,
                   COUNT(sd.id) AS remaining_dates
            FROM user_preferences up
            JOIN shows s ON s.id = up.ref_id
            JOIN theaters t ON t.id = s.theater_id
            LEFT JOIN show_dates sd ON sd.show_id = s.id
                AND sd.date >= $2 AND sd.is_cancelled = FALSE
            WHERE up.user_id = $1
              AND up.type = 'watchlist' AND up.ref_type = 'show'
            GROUP BY s.id, s.title, s.slug, t.name, t.slug
            ORDER BY next_date NULLS LAST, s.title
            """,
            user_id, today,
        )
    result = []
    for r in rows:
        d = dict(r)
        d["last_chance"] = 0 < d["remaining_dates"] <= 2
        result.append(d)
    return result


async def get_watchlist_users_for_show(pool, show_id: int) -> list[int]:
    """Все user_id у которых спектакль в вишлисте."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id FROM user_preferences
            WHERE type = 'watchlist' AND ref_type = 'show' AND ref_id = $1
            """,
            show_id,
        )
    return [r["user_id"] for r in rows]


async def get_favorite_users_for_theater(pool, theater_id: int) -> list[int]:
    """Все user_id у которых театр в избранном."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id FROM user_preferences
            WHERE type = 'favorite' AND ref_type = 'theater' AND ref_id = $1
            """,
            theater_id,
        )
    return [r["user_id"] for r in rows]


async def remove_preference(pool, user_id: int, type_: str,
                             ref_id: int, ref_type: str) -> bool:
    """Удалить предпочтение. Возвращает True если было удалено."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM user_preferences
            WHERE user_id = $1 AND type = $2 AND ref_id = $3 AND ref_type = $4
            """,
            user_id, type_, ref_id, ref_type,
        )
    return result == "DELETE 1"
