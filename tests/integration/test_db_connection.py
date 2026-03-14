"""
Интеграционные тесты подключения к БД.
Требуют запущенного teatr-postgres (пропускаются если .env не настроен).
"""
import os
import pytest
import asyncio


# Пропускаем интеграционные тесты если нет переменных окружения
pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_HOST"),
    reason="Требуется POSTGRES_HOST в окружении (интеграционные тесты)"
)


@pytest.mark.asyncio
async def test_db_connection():
    """Проверяем что asyncpg pool успешно подключается к БД."""
    # TODO T001: раскомментировать после реализации connection.py
    # from src.db.connection import get_pool, close_pool
    # pool = await get_pool()
    # assert pool is not None
    # result = await pool.fetchval("SELECT 1")
    # assert result == 1
    # await close_pool()
    pass


@pytest.mark.asyncio
async def test_show_dates_unique_constraint():
    """Проверяем UNIQUE(show_id, date, time, stage) — дубликат не создаётся."""
    # TODO T001: раскомментировать после реализации connection.py
    # from src.db.connection import get_pool, close_pool
    # pool = await get_pool()
    # async with pool.acquire() as conn:
    #     await conn.execute("BEGIN")
    #     try:
    #         # Вставляем тестовый театр и спектакль
    #         theater_id = await conn.fetchval(
    #             "INSERT INTO theaters(name, slug) VALUES($1,$2) RETURNING id",
    #             "Тест-Театр", "test-theater-unique"
    #         )
    #         show_id = await conn.fetchval(
    #             "INSERT INTO shows(theater_id, title, slug) VALUES($1,$2,$3) RETURNING id",
    #             theater_id, "Тест-Спектакль", "test-show-unique"
    #         )
    #         # Первая вставка — должна пройти
    #         await conn.execute(
    #             "INSERT INTO show_dates(show_id, date, time) VALUES($1,'2026-12-31','19:00')",
    #             show_id
    #         )
    #         # Вторая вставка того же — ON CONFLICT DO NOTHING
    #         await conn.execute(
    #             "INSERT INTO show_dates(show_id, date, time) VALUES($1,'2026-12-31','19:00') ON CONFLICT DO NOTHING",
    #             show_id
    #         )
    #         count = await conn.fetchval(
    #             "SELECT count(*) FROM show_dates WHERE show_id=$1", show_id
    #         )
    #         assert count == 1
    #     finally:
    #         await conn.execute("ROLLBACK")
    # await close_pool()
    pass
