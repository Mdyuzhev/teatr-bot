"""
Ручной запуск сбора данных из KudaGo.
Запуск: python -m scripts.collect_now
или:    python scripts/collect_now.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from src.config import config
from src.collectors.kudago import KudaGoCollector
from src.db.connection import get_pool, close_pool


async def main():
    logger.info("=== Ручной сбор данных KudaGo ===")

    collector = KudaGoCollector(config)
    events = collector.fetch_events()

    if not events:
        logger.warning("Нет событий для сохранения")
        return

    logger.info("Получено {} событий, сохраняю в БД...", len(events))

    pool = await get_pool()
    try:
        stats = await collector.save_to_db(events, pool)
        logger.info("Готово! Театров: {}, спектаклей: {}, дат: {}",
                     stats["theaters"], stats["shows"], stats["dates"])
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
