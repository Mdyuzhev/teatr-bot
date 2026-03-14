"""
Главный модуль театрального бота.
Планировщик ежедневного сбора данных + Telegram-бот.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from src.config import config
from src.db.connection import get_pool
from src.collectors.kudago import KudaGoCollector
from src.collectors.rss_feeds import RssCollector
from src.scheduler.jobs import generate_digests_job, notifications_job
from src.reports.telegram_commands import (
    cmd_start, cmd_digest, cmd_today, cmd_weekend, cmd_week,
    cmd_premieres, cmd_theater, cmd_status, cmd_refresh,
    cmd_news, cmd_rss_refresh, cmd_favorites, cmd_watchlist, cmd_settings,
    cmd_random,
    digest_callback, preference_callback, reply_keyboard_handler,
    page_callback, metro_callback,
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


async def scheduled_digest_generation():
    """Генерация стандартных дайджестов (запускается планировщиком)."""
    logger.info("=== Плановая генерация дайджестов ===")
    try:
        pool = await get_pool()
        stats = await generate_digests_job(pool)
        logger.info("Генерация дайджестов завершена: {}", stats)
    except Exception as e:
        logger.error("Ошибка генерации дайджестов: {}", e)


async def post_init(application):
    """Запуск планировщика после старта event loop."""
    bot = application.bot

    async def scheduled_notifications():
        """Рассылка уведомлений с реальной отправкой через bot."""
        logger.info("=== Плановая рассылка уведомлений ===")
        try:
            pool = await get_pool()
            stats = await notifications_job(pool, bot=bot)
            logger.info("Уведомления: {}", stats)
        except Exception as e:
            logger.error("Ошибка рассылки уведомлений: {}", e)

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
    scheduler.add_job(
        scheduled_digest_generation,
        "cron",
        hour=config.COLLECTION_HOUR + 1,
        minute=0,
        id="digest_daily",
    )
    scheduler.add_job(
        scheduled_notifications,
        "cron",
        hour=config.COLLECTION_HOUR + 3,
        minute=0,
        id="notifications_daily",
    )
    scheduler.start()
    logger.info(
        "Планировщик: KudaGo {:02d}:00, RSS {:02d}:30, дайджесты {:02d}:00, уведомления {:02d}:00 МСК",
        config.COLLECTION_HOUR, config.COLLECTION_HOUR,
        config.COLLECTION_HOUR + 1, config.COLLECTION_HOUR + 3,
    )


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
    app.add_handler(CommandHandler("favorites", cmd_favorites))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("random", cmd_random))
    app.add_handler(CallbackQueryHandler(digest_callback, pattern="^digest_"))
    app.add_handler(CallbackQueryHandler(preference_callback, pattern="^(fav:|wl:|rm_fav:|rm_wl:|goto_)"))
    app.add_handler(CallbackQueryHandler(page_callback, pattern="^(page:|show_all:|noop)"))
    app.add_handler(CallbackQueryHandler(metro_callback, pattern="^metro_search$"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, reply_keyboard_handler
    ))

    # Запуск polling
    logger.info("Бот запущен, ожидаю команды...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
