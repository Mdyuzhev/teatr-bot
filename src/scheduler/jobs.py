"""
Задачи планировщика APScheduler.

Расписание (МСК):
  06:00 — сбор данных KudaGo
  06:30 — сбор RSS новостей
  07:00 — генерация стандартных дайджестов через Haiku

ВАЖНО: вызов LLM происходит ТОЛЬКО здесь, не в Telegram-командах.
"""
from datetime import date, timedelta

from loguru import logger

from src.brain.digest_builder import build_digest
from src.db.queries.digests import save_digest
from src.db.queries.reports import get_digest_data
from src.db.queries.rss import get_recent_news
from src.config import config


# Метки периодов для дайджестов
PERIOD_LABELS = {
    "today": "Сегодня",
    "tomorrow": "Завтра",
    "weekend": "Ближайшие выходные",
    "week": "Эта неделя",
}

DIGEST_MODEL = "claude-haiku-4-5-20251001"


def get_period_dates(period_key: str) -> tuple[date, date]:
    """
    Вычислить date_from и date_to по ключу периода.

    'today'    → (today, today)
    'tomorrow' → (today+1, today+1)
    'weekend'  → (ближайшая Сб, ближайшее Вс)
    'week'     → (today, today+6)
    '2026-03-20:2026-03-25' → парсинг дат
    """
    today = date.today()

    if period_key == "today":
        return today, today
    elif period_key == "tomorrow":
        tmrw = today + timedelta(days=1)
        return tmrw, tmrw
    elif period_key == "weekend":
        return _next_weekend_dates(today)
    elif period_key == "week":
        return today, today + timedelta(days=6)
    elif ":" in period_key:
        # Кастомный период '2026-03-20:2026-03-25'
        parts = period_key.split(":")
        return date.fromisoformat(parts[0]), date.fromisoformat(parts[1])
    else:
        return today, today


def _next_weekend_dates(today: date) -> tuple[date, date]:
    """Даты ближайших выходных (сб-вс)."""
    weekday = today.weekday()  # 0=пн, 5=сб, 6=вс
    if weekday < 5:
        saturday = today + timedelta(days=5 - weekday)
    elif weekday == 5:
        saturday = today
    else:  # воскресенье
        return today, today

    sunday = saturday + timedelta(days=1)
    return saturday, sunday


async def generate_digests_job(pool) -> dict:
    """
    Задача 07:00: генерация стандартных дайджестов.
    Генерирует 4 дайджеста (today/tomorrow/weekend/week) и сохраняет в БД.
    Возвращает статистику.
    """
    logger.info("=== Генерация дайджестов ===")
    stats = {"generated": 0, "errors": 0}

    # RSS-новости для обогащения
    rss_news = await get_recent_news(pool, days=7, limit=10)

    for period_key, label in PERIOD_LABELS.items():
        try:
            date_from, date_to = get_period_dates(period_key)

            # Получаем данные из БД
            digest_data = await get_digest_data(
                pool, date_from, date_to, limit=config.MAX_DIGEST_SHOWS
            )
            shows = digest_data["shows"]

            # Генерируем дайджест через Claude (или raw-fallback)
            content = await build_digest(
                shows, label,
                premieres=digest_data["premieres"],
                stats=digest_data["stats"],
                rss_news=rss_news if period_key == "today" else None,
            )

            # Сохраняем в кэш
            await save_digest(
                pool, period_key, date_from, date_to,
                content, len(shows), DIGEST_MODEL,
            )

            stats["generated"] += 1
            logger.info(
                "Дайджест '{}': {} спектаклей, {}-{}",
                period_key, len(shows), date_from, date_to,
            )

        except Exception as e:
            stats["errors"] += 1
            logger.error("Ошибка генерации дайджеста '{}': {}", period_key, e)

    logger.info(
        "Генерация завершена: {} дайджестов, {} ошибок",
        stats["generated"], stats["errors"],
    )
    return stats
