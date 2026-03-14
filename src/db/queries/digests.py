"""
SQL-запросы для работы с кэшем дайджестов.

Логика кэширования:
  - Стандартные дайджесты генерируются планировщиком в 07:00 (4 вызова LLM в сутки)
  - Кастомные периоды кэшируются при первом запросе (1 вызов на период в 24ч)
  - Telegram-команды ВСЕГДА читают из этой таблицы, не вызывают LLM напрямую
"""


async def get_fresh_digest(pool, period_key: str, date_from, date_to) -> dict | None:
    """
    Вернуть актуальный дайджест из кэша или None если устарел/отсутствует.
    Проверка: expires_at > NOW()
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, period_key, date_from, date_to, content,
                   shows_count, model, generated_at, expires_at
            FROM digests
            WHERE period_key = $1 AND date_from = $2 AND date_to = $3
              AND expires_at > NOW()
            LIMIT 1
            """,
            period_key, date_from, date_to,
        )
    return dict(row) if row else None


async def save_digest(pool, period_key: str, date_from, date_to,
                      content: str, shows_count: int, model: str) -> None:
    """
    Сохранить или обновить дайджест в кэше.
    INSERT ... ON CONFLICT DO UPDATE, expires_at = NOW() + 24h.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO digests (period_key, date_from, date_to, content,
                                 shows_count, model, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '24 hours')
            ON CONFLICT (period_key, date_from, date_to)
            DO UPDATE SET content = EXCLUDED.content,
                          shows_count = EXCLUDED.shows_count,
                          model = EXCLUDED.model,
                          generated_at = NOW(),
                          expires_at = NOW() + INTERVAL '24 hours'
            """,
            period_key, date_from, date_to, content, shows_count, model,
        )


async def get_all_digests_status(pool) -> list[dict]:
    """
    Список всех дайджестов с их статусом (fresh/stale).
    Для команды /status.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT period_key, date_from, date_to, shows_count,
                   generated_at, expires_at,
                   CASE WHEN expires_at > NOW() THEN 'fresh' ELSE 'stale' END AS status
            FROM digests
            ORDER BY generated_at DESC
            """
        )
    return [dict(r) for r in rows]
