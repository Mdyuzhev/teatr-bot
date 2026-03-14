"""
Главный модуль театрального бота.
Планировщик ежедневного сбора данных + Telegram-бот.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from src.config import config
from src.db.connection import get_pool
from src.collectors.kudago import KudaGoCollector
from src.collectors.rss_feeds import RssCollector
from src.reports.telegram_commands import (
    cmd_start, cmd_digest, cmd_today, cmd_weekend, cmd_week,
    cmd_premieres, cmd_theater, cmd_status, cmd_refresh,
    cmd_news, cmd_rss_refresh,
    digest_callback,
)


async def scheduled_collection():
    """Ежедневный сбор данных KudaGo (запускается планировщиком)."""
    logger.info("=== Плановый сбор данных KudaGo ===")
    try:
        collector = KudaGoCollector(config)
        events = collector.fetch_events()
        if not events:
            logger.warning("Плановый сбор: нет событий")
            return

        pool = await get_pool()
        stats = await collector.save_to_db(events, pool)
        logger.info("Плановый сбор завершён: {}", stats)
    except Exception as e:
        logger.error("Ошибка планового сбора: {}", e)


async def scheduled_rss_collection():
    """Ежедневный сбор RSS-новостей театров (06:30 МСК)."""
    logger.info("=== Плановый сбор RSS ===")
    try:
        collector = RssCollector()
        news = collector.collect_all()
        if not news:
            logger.info("RSS: новых записей нет")
            return

        pool = await get_pool()
        stats = await collector.save_to_db(news, pool)
        logger.info("RSS сбор завершён: {}", stats)
    except Exception as e:
        logger.error("Ошибка сбора RSS: {}", e)


async def post_init(application):
    """Запуск планировщика после старта event loop."""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        scheduled_collection,
        "cron",
        hour=config.COLLECTION_HOUR,
        minute=0,
        id="kudago_daily",
    )
    scheduler.add_job(
        scheduled_rss_collection,
        "cron",
        hour=config.COLLECTION_HOUR,
        minute=30,
        id="rss_daily",
    )
    scheduler.start()
    logger.info("Планировщик: KudaGo {:02d}:00, RSS {:02d}:30 МСК", config.COLLECTION_HOUR, config.COLLECTION_HOUR)


def main():
    """Запуск бота и планировщика."""
    # Валидация конфига
    errors = config.validate()
    if errors:
        for err in errors:
            logger.error(err)
        raise SystemExit(1)

    logger.info("Запуск театрального бота")

    # Telegram Application
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Регистрация команд
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("weekend", cmd_weekend))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("premieres", cmd_premieres))
    app.add_handler(CommandHandler("theater", cmd_theater))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("rss_refresh", cmd_rss_refresh))
    app.add_handler(CallbackQueryHandler(digest_callback, pattern="^digest_"))

    # Запуск polling
    logger.info("Бот запущен, ожидаю команды...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
