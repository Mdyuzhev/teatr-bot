"""
SQL-запросы для рецензий на спектакли.
Одна рецензия на спектакль, генерируется один раз и кэшируется навсегда.
"""


async def get_review(pool, show_id: int) -> dict | None:
    """Получить рецензию из кэша. None если не было запроса."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content, model, created_at FROM show_reviews WHERE show_id = $1",
            show_id,
        )
    return dict(row) if row else None


async def save_review(pool, show_id: int, content: str, model: str) -> None:
    """Сохранить рецензию. ON CONFLICT DO UPDATE — перезаписать если уже есть."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO show_reviews (show_id, content, model)
            VALUES ($1, $2, $3)
            ON CONFLICT (show_id) DO UPDATE
                SET content = EXCLUDED.content,
                    model = EXCLUDED.model,
                    created_at = NOW()
            """,
            show_id, content, model,
        )


async def get_show_for_review(pool, show_id: int) -> dict | None:
    """Получить данные спектакля для генерации рецензии."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.id, s.title, s.slug, s.genre, s.age_rating,
                   s.description, s.is_premiere, s.image_url,
                   t.name AS theater_name, t.url AS theater_url
            FROM shows s
            JOIN theaters t ON t.id = s.theater_id
            WHERE s.id = $1
            """,
            show_id,
        )
    return dict(row) if row else None
