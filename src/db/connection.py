"""
Управление asyncpg-пулом соединений с PostgreSQL.
Pool: min=2, max=10 — по образцу moex-бота.
"""
import asyncpg
from loguru import logger

from src.config import config

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Получить или создать пул соединений."""
    global _pool
    if _pool is None or _pool._closed:
        logger.info("Создаю asyncpg pool → {}:{}/{}", config.POSTGRES_HOST, config.POSTGRES_PORT, config.POSTGRES_DB)
        _pool = await asyncpg.create_pool(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            database=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    """Закрыть пул соединений."""
    global _pool
    if _pool is not None and not _pool._closed:
        await _pool.close()
        logger.info("asyncpg pool закрыт")
        _pool = None
