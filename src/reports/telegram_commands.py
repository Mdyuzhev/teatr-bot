"""
Команды Telegram-бота.

Зарегистрированные команды:
  /start    — приветствие
  /digest   — дайджест с выбором периода (inline-кнопки)
  /today    — спектакли сегодня
  /weekend  — спектакли на ближайшие выходные
  /week     — спектакли на текущую неделю
  /theater  — афиша конкретного театра
  /premieres — только премьеры за 30 дней
  /status   — статус бота и БД
  /refresh  — принудительный сбор данных
"""
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from src.db.connection import get_pool
from src.db.queries.shows import get_shows_by_theater, get_premieres
from src.db.queries.reports import get_digest_data, get_bot_stats
from src.db.queries.digests import get_fresh_digest, save_digest, get_all_digests_status
from src.db.queries.rss import get_recent_news, get_news_count
from src.brain.digest_builder import build_digest
from src.scheduler.jobs import get_period_dates, PERIOD_LABELS, DIGEST_MODEL
from src.reports.telegram_sender import send_message
from src.collectors.kudago import KudaGoCollector
from src.collectors.rss_feeds import RssCollector
from src.config import config


# ── /start ──

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Театральный бот Москвы</b>\n\n"
        "Помогу найти спектакли и составить дайджест.\n\n"
        "/today — спектакли сегодня\n"
        "/weekend — на выходные\n"
        "/week — на неделю\n"
        "/digest — дайджест с выбором периода\n"
        "/premieres — премьеры\n"
        "/status — статус бота"
    )
    await send_message(context.bot, update.effective_chat.id, text)


# ── /digest ──

async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("Сегодня", callback_data="digest_today"),
            InlineKeyboardButton("Завтра", callback_data="digest_tomorrow"),
        ],
        [
            InlineKeyboardButton("Выходные", callback_data="digest_weekend"),
            InlineKeyboardButton("Неделя", callback_data="digest_week"),
        ],
    ]
    await update.message.reply_text(
        "Выберите период для дайджеста:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    period_map = {
        "digest_today": "today",
        "digest_tomorrow": "tomorrow",
        "digest_weekend": "weekend",
        "digest_week": "week",
    }
    period_key = period_map.get(data)
    if not period_key:
        return

    date_from, date_to = get_period_dates(period_key)
    label = PERIOD_LABELS[period_key]
    if period_key == "week":
        label = f"Неделя ({date_from.strftime('%d.%m')}–{date_to.strftime('%d.%m')})"

    pool = await get_pool()

    # Сначала проверяем кэш
    cached = await get_fresh_digest(pool, period_key, date_from, date_to)
    if cached:
        await send_message(context.bot, query.message.chat_id, cached["content"])
        return

    await query.edit_message_text("Генерирую дайджест...")
    text = await _generate_and_cache(pool, period_key, date_from, date_to, label)
    await send_message(context.bot, query.message.chat_id, text)


# ── /today ──

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool = await get_pool()
    date_from, date_to = get_period_dates("today")
    text = await _get_or_generate(pool, "today", date_from, date_to, "Сегодня")
    await send_message(context.bot, update.effective_chat.id, text)


# ── /weekend ──

async def cmd_weekend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool = await get_pool()
    date_from, date_to = get_period_dates("weekend")
    label = f"Выходные ({date_from.strftime('%d.%m')}–{date_to.strftime('%d.%m')})"
    text = await _get_or_generate(pool, "weekend", date_from, date_to, label)
    await send_message(context.bot, update.effective_chat.id, text)


# ── /week ──

async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool = await get_pool()
    date_from, date_to = get_period_dates("week")
    label = f"Неделя ({date_from.strftime('%d.%m')}–{date_to.strftime('%d.%m')})"
    text = await _get_or_generate(pool, "week", date_from, date_to, label)
    await send_message(context.bot, update.effective_chat.id, text)


# ── /premieres ──

async def cmd_premieres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool = await get_pool()
    shows = await get_premieres(pool, days=30)
    if not shows:
        await send_message(context.bot, update.effective_chat.id,
                           "Премьер в ближайшие 30 дней не найдено.")
        return
    text = await build_digest(shows, "Премьеры (30 дней)")
    await send_message(context.bot, update.effective_chat.id, text)


# ── /theater ──

async def cmd_theater(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await send_message(context.bot, update.effective_chat.id,
                           "Укажите название театра: /theater большой")
        return

    search = " ".join(context.args).lower()
    pool = await get_pool()

    # Поиск театра по подстроке
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT slug, name FROM theaters WHERE LOWER(name) LIKE $1 LIMIT 5",
            f"%{search}%",
        )

    if not rows:
        await send_message(context.bot, update.effective_chat.id,
                           f"Театр «{search}» не найден.")
        return

    if len(rows) == 1:
        slug = rows[0]["slug"]
        name = rows[0]["name"]
    else:
        # Несколько вариантов — показать список
        lines = ["Найдено несколько театров:"]
        for r in rows:
            lines.append(f"  /theater_{r['slug']}")
        await send_message(context.bot, update.effective_chat.id, "\n".join(lines))
        return

    today = date.today()
    date_to = today + timedelta(days=14)
    shows = await get_shows_by_theater(pool, slug, today, date_to)
    if not shows:
        await send_message(context.bot, update.effective_chat.id,
                           f"У «{name}» нет показов в ближайшие 2 недели.")
        return

    # Добавляем theater_name для форматирования
    for s in shows:
        s["theater_name"] = name

    text = await build_digest(shows, f"{name} (2 недели)")
    await send_message(context.bot, update.effective_chat.id, text)


# ── /status ──

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool = await get_pool()
    stats = await get_bot_stats(pool)
    rss_count = await get_news_count(pool)
    digests = await get_all_digests_status(pool)

    last = stats.get("last_collected")
    last_str = last.strftime("%d.%m.%Y %H:%M") if last else "никогда"

    lines = [
        "<b>Статус бота</b>\n",
        f"Театров: {stats.get('theaters', 0)}",
        f"Спектаклей: {stats.get('shows', 0)}",
        f"Предстоящих показов: {stats.get('active_dates', 0)}",
        f"RSS-новостей: {rss_count}",
        f"Последний сбор: {last_str}",
    ]

    if digests:
        lines.append("\n<b>Кэш дайджестов:</b>")
        for d in digests[:6]:
            status_icon = "🟢" if d["status"] == "fresh" else "🔴"
            gen = d["generated_at"].strftime("%H:%M") if d.get("generated_at") else "?"
            lines.append(f"  {status_icon} {d['period_key']} ({d['shows_count']} шт, {gen})")

    await send_message(context.bot, update.effective_chat.id, "\n".join(lines))


# ── /refresh ──

async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await send_message(context.bot, chat_id, "Запускаю сбор данных KudaGo...")

    collector = KudaGoCollector(config)
    events = collector.fetch_events()

    if not events:
        await send_message(context.bot, chat_id, "Не удалось загрузить события.")
        return

    pool = await get_pool()
    stats = await collector.save_to_db(events, pool)

    await send_message(context.bot, chat_id,
        f"Сбор завершён. Театров: {stats['theaters']}, "
        f"спектаклей: {stats['shows']}, дат: {stats['dates']}\n"
        "Перегенерирую дайджесты...")

    # Перегенерация дайджестов после обновления данных
    from src.scheduler.jobs import generate_digests_job
    digest_stats = await generate_digests_job(pool)
    await send_message(context.bot, chat_id,
        f"Дайджесты обновлены: {digest_stats['generated']} сгенерировано, "
        f"{digest_stats['errors']} ошибок")


# ── /news ──

async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pool = await get_pool()
    news = await get_recent_news(pool, days=7, limit=10)
    if not news:
        await send_message(context.bot, update.effective_chat.id,
                           "Новостей театров за последнюю неделю нет.")
        return

    lines = ["<b>Новости театров (7 дней)</b>\n"]
    for item in news:
        theater = item.get("theater_name", "")
        title = item.get("title", "")
        url = item.get("url", "")
        pub = item.get("published_at")
        date_str = pub.strftime("%d.%m") if pub else ""
        if url:
            lines.append(f"  {date_str} <b>{theater}</b>: <a href=\"{url}\">{title}</a>")
        else:
            lines.append(f"  {date_str} <b>{theater}</b>: {title}")

    await send_message(context.bot, update.effective_chat.id, "\n".join(lines))


# ── /rss_refresh ──

async def cmd_rss_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await send_message(context.bot, chat_id, "Собираю RSS-новости...")

    collector = RssCollector()
    news = collector.collect_all()

    if not news:
        await send_message(context.bot, chat_id, "Новых RSS-записей не найдено.")
        return

    pool = await get_pool()
    stats = await collector.save_to_db(news, pool)

    text = (
        f"RSS сбор завершён.\n"
        f"Новых: {stats['saved']}, дубликатов: {stats['skipped']}, "
        f"без театра: {stats['no_theater']}"
    )
    await send_message(context.bot, chat_id, text)


# ── helpers ──

async def _get_or_generate(pool, period_key: str, date_from, date_to, label: str) -> str:
    """Читаем из кэша, при отсутствии — генерируем и сохраняем."""
    cached = await get_fresh_digest(pool, period_key, date_from, date_to)
    if cached:
        return cached["content"]
    return await _generate_and_cache(pool, period_key, date_from, date_to, label)


async def _generate_and_cache(pool, period_key: str, date_from, date_to, label: str) -> str:
    """Генерация дайджеста через Claude + сохранение в кэш."""
    digest_data = await get_digest_data(pool, date_from, date_to, limit=config.MAX_DIGEST_SHOWS)
    rss_news = await get_recent_news(pool, days=7, limit=10) if period_key == "today" else None
    text = await build_digest(
        digest_data["shows"], label,
        premieres=digest_data["premieres"],
        stats=digest_data["stats"],
        rss_news=rss_news,
    )
    await save_digest(pool, period_key, date_from, date_to, text, len(digest_data["shows"]), DIGEST_MODEL)
    return text
