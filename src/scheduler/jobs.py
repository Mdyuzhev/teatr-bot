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
from src.db.queries.notifications import (
    get_new_show_dates, get_last_chance_shows,
    is_notification_sent, log_notification,
)
from src.db.queries.preferences import (
    get_favorite_users_for_theater, get_watchlist_users_for_show,
)
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


async def notifications_job(pool, bot=None) -> dict:
    """
    Задача 09:00: уведомления для подписчиков.

    1. Новые даты в избранных театрах → уведомление подписчикам
    2. Новые даты для спектаклей из вишлиста → уведомление
    3. Последний шанс (≤2 даты) → уведомление подписчикам вишлиста

    Возвращает статистику.
    """
    logger.info("=== Рассылка уведомлений ===")
    stats = {"sent": 0, "skipped": 0, "errors": 0}

    try:
        # 1. Новые даты за последние 24 часа
        new_dates = await get_new_show_dates(pool, hours=24)

        # Группируем по театру для уведомлений об избранных
        theater_dates: dict[int, list] = {}
        show_dates_map: dict[int, list] = {}
        for sd in new_dates:
            tid = sd["theater_id"]
            sid = sd["show_id"]
            theater_dates.setdefault(tid, []).append(sd)
            show_dates_map.setdefault(sid, []).append(sd)

        # Уведомления: новые показы в избранных театрах
        for theater_id, dates in theater_dates.items():
            users = await get_favorite_users_for_theater(pool, theater_id)
            theater_name = dates[0].get("theater_name", "")
            titles = list({d["title"] for d in dates})
            titles_str = ", ".join(titles[:3])
            date_str = dates[0]["date"].strftime("%d.%m") if dates[0].get("date") else ""

            for user_id in users:
                ref_id = dates[0]["show_date_id"]
                if await is_notification_sent(pool, user_id, "new_at_favorite", ref_id):
                    stats["skipped"] += 1
                    continue
                await log_notification(pool, user_id, "new_at_favorite", ref_id)
                if bot:
                    msg = (
                        f"⭐ <b>{theater_name}</b>\n"
                        f"Новые даты: <b>{titles_str}</b> — {date_str}\n"
                        f"Используй /today чтобы увидеть полную афишу"
                    )
                    try:
                        await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                    except Exception as e:
                        logger.warning("Не удалось отправить уведомление {}: {}", user_id, e)
                        stats["errors"] += 1
                        continue
                stats["sent"] += 1

        # Уведомления: новые даты для спектаклей в вишлисте
        for show_id, dates in show_dates_map.items():
            users = await get_watchlist_users_for_show(pool, show_id)
            show_title = dates[0].get("title", "")
            theater_name = dates[0].get("theater_name", "")
            date_str = dates[0]["date"].strftime("%d.%m") if dates[0].get("date") else ""

            for user_id in users:
                ref_id = dates[0]["show_date_id"]
                if await is_notification_sent(pool, user_id, "new_date", ref_id):
                    stats["skipped"] += 1
                    continue
                await log_notification(pool, user_id, "new_date", ref_id)
                if bot:
                    msg = (
                        f"🔖 Появилась новая дата!\n"
                        f"<b>{show_title}</b> · {theater_name}\n"
                        f"📅 {date_str}"
                    )
                    try:
                        await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                    except Exception as e:
                        logger.warning("Не удалось отправить уведомление {}: {}", user_id, e)
                        stats["errors"] += 1
                        continue
                stats["sent"] += 1

        # 2. Последний шанс — ровно 2 даты осталось
        last_chance = await get_last_chance_shows(pool)
        for show in last_chance:
            users = await get_watchlist_users_for_show(pool, show["show_id"])
            show_title = show.get("title", "")
            theater_name = show.get("theater_name", "")

            for user_id in users:
                if await is_notification_sent(pool, user_id, "last_chance", show["show_id"]):
                    stats["skipped"] += 1
                    continue
                await log_notification(pool, user_id, "last_chance", show["show_id"])
                if bot:
                    msg = (
                        f"⚠️ <b>Последний шанс!</b>\n"
                        f"<b>{show_title}</b> · {theater_name}\n"
                        f"Осталось всего 2 показа в сезоне.\n"
                        f"Успей купить билет!"
                    )
                    try:
                        await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                    except Exception as e:
                        logger.warning("Не удалось отправить уведомление {}: {}", user_id, e)
                        stats["errors"] += 1
                        continue
                stats["sent"] += 1

    except Exception as e:
        stats["errors"] += 1
        logger.error("Ошибка рассылки уведомлений: {}", e)

    logger.info(
        "Уведомления: {} отправлено, {} пропущено, {} ошибок",
        stats["sent"], stats["skipped"], stats["errors"],
    )
    return stats
