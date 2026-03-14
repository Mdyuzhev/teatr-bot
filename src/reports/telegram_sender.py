"""
Отправка сообщений в Telegram.
Обёртка над python-telegram-bot для удобного использования из других модулей.
"""
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

TELEGRAM_MSG_LIMIT = 4096
PAGE_SIZE = 5
THEATERS_PAGE_SIZE = 10


async def send_message(bot: Bot, chat_id: str | int, text: str,
                       parse_mode: str = "HTML") -> None:
    """Отправить сообщение, при необходимости разбив на части."""
    if len(text) <= TELEGRAM_MSG_LIMIT:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return

    await send_message_chunks(bot, chat_id, text, parse_mode=parse_mode)


async def send_message_chunks(bot: Bot, chat_id: str | int, text: str,
                              chunk_size: int = 4000,
                              parse_mode: str = "HTML") -> None:
    """Разбить длинное сообщение на части и отправить последовательно."""
    chunks = _split_text(text, chunk_size)
    for i, chunk in enumerate(chunks, 1):
        logger.debug("Отправка части {}/{} ({} символов)", i, len(chunks), len(chunk))
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)


def _split_text(text: str, chunk_size: int) -> list[str]:
    """Разбить текст по переносам строк, не ломая HTML-теги."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break

        # Ищем последний перенос строки в пределах chunk_size
        split_pos = text.rfind("\n", 0, chunk_size)
        if split_pos == -1:
            split_pos = chunk_size

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks


def format_show_card(show: dict) -> str:
    """Формирует HTML-текст одной карточки спектакля."""
    title = show.get("title", "Без названия")
    theater = show.get("theater_name", "")
    premiere = "🌟 " if show.get("is_premiere") else ""

    lines = [f"{premiere}🎭 <b>{title}</b>"]
    if theater:
        metro = f" · {show['metro']}" if show.get("metro") else ""
        lines.append(f"{theater}{metro}")

    if show.get("date"):
        d = show["date"]
        date_str = d.strftime("%a %d.%m") if hasattr(d, "strftime") else str(d)
        time_str = ""
        if show.get("time"):
            t = show["time"]
            time_str = f", {t.strftime('%H:%M')}" if hasattr(t, "strftime") else f", {t}"
        lines.append(f"📅 {date_str}{time_str}")

    parts = []
    if show.get("price_min"):
        parts.append(f"от {show['price_min']} ₽")
    if show.get("age_rating"):
        parts.append(show["age_rating"])
    if parts:
        lines.append("💰 " + "  |  ".join(parts))

    return "\n".join(lines)


def build_show_card_keyboard(show: dict, has_fav: bool = False,
                              has_wl: bool = False) -> InlineKeyboardMarkup:
    """Inline-кнопки для карточки спектакля."""
    theater_id = show.get("theater_id")
    show_id = show.get("show_id") or show.get("id")

    row1 = []  # Билеты + Рецензия
    row2 = []  # Избранное + Интересно

    if show.get("tickets_url"):
        row1.append(InlineKeyboardButton("🎟 Билеты", url=show["tickets_url"]))

    if show_id:
        row1.append(InlineKeyboardButton("📝 Рецензия", callback_data=f"review:{show_id}"))

    if theater_id:
        fav_text = "✅ Сохранён" if has_fav else "⭐ В избранное"
        row2.append(InlineKeyboardButton(fav_text, callback_data=f"fav:theater:{theater_id}"))

    if show_id:
        wl_text = "📌 В списке" if has_wl else "🔖 Интересно"
        row2.append(InlineKeyboardButton(wl_text, callback_data=f"wl:show:{show_id}"))

    rows = [r for r in [row1, row2] if r]
    return InlineKeyboardMarkup(rows) if rows else None


async def send_shows_as_cards(
    bot: Bot,
    chat_id: int | str,
    shows: list[dict],
    header_text: str,
    pool=None,
    user_id: int | None = None,
    page: int = 0,
    page_size: int = PAGE_SIZE,
    period_key: str = "",
) -> None:
    """Отправить спектакли как серию карточек с inline-кнопками.

    1. Первое сообщение — header_text (шапка)
    2. Карточки по page_size штук
    3. Навигация если > page_size
    """
    if not shows:
        await send_message(bot, chat_id, header_text or "Спектаклей не найдено.")
        return

    total_pages = (len(shows) + page_size - 1) // page_size
    page = min(page, total_pages - 1)
    start = page * page_size
    page_shows = shows[start:start + page_size]

    # Шапка — только на первой странице
    if page == 0 and header_text:
        await send_message(bot, chat_id, header_text)

    # Проверяем preferences пользователя для каждого show
    has_prefs = {}
    if pool and user_id:
        try:
            from src.db.queries.preferences import has_preference
            for s in page_shows:
                tid = s.get("theater_id")
                sid = s.get("show_id") or s.get("id")
                fav = await has_preference(pool, user_id, "favorite", tid, "theater") if tid else False
                wl = await has_preference(pool, user_id, "watchlist", sid, "show") if sid else False
                key = f"{tid}:{sid}"
                has_prefs[key] = (fav, wl)
        except Exception as e:
            logger.warning("Ошибка проверки preferences: {}", e)

    # Карточки
    for s in page_shows:
        text = format_show_card(s)
        tid = s.get("theater_id")
        sid = s.get("show_id") or s.get("id")
        key = f"{tid}:{sid}"
        fav, wl = has_prefs.get(key, (False, False))
        markup = build_show_card_keyboard(s, has_fav=fav, has_wl=wl)
        try:
            await bot.send_message(chat_id=chat_id, text=text,
                                   parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            logger.error("Ошибка отправки карточки: {}", e)

    # Навигация
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                "← Назад", callback_data=f"page:{period_key}:{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(
            f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(
                "Вперёд →", callback_data=f"page:{period_key}:{page + 1}"))

        nav_rows = [nav_buttons]
        nav_rows.append([InlineKeyboardButton(
            "📋 Показать текстом", callback_data=f"show_all:{period_key}")])

        await bot.send_message(
            chat_id=chat_id,
            text=f"Страница {page + 1} из {total_pages}",
            reply_markup=InlineKeyboardMarkup(nav_rows),
        )


def build_theaters_page_content(
    theaters: list[dict],
    fav_ids: set[int],
    page: int = 0,
    page_size: int = THEATERS_PAGE_SIZE,
    title: str = "🏛 Театры",
    search_query: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Собирает текст и клавиатуру для страницы списка театров."""
    total_pages = max(1, (len(theaters) + page_size - 1) // page_size)
    page = min(page, total_pages - 1)
    start = page * page_size
    page_theaters = theaters[start:start + page_size]

    lines = [f"<b>{title}</b>  (стр. {page + 1}/{total_pages})\n"]
    keyboard = []

    for i, t in enumerate(page_theaters, start + 1):
        count = t.get("upcoming_shows", 0)
        metro = f" · {t['metro']}" if t.get("metro") else ""
        lines.append(f"{i}. {t['name']}{metro} — {count} показов")

        fav_text = "✅" if t["id"] in fav_ids else "⭐"
        row = [
            InlineKeyboardButton(f"🎭 {t['name'][:25]}", callback_data=f"theater_shows:{t['slug']}"),
            InlineKeyboardButton(fav_text, callback_data=f"fav:theater:{t['id']}"),
        ]
        keyboard.append(row)

    # Навигация
    nav = []
    cb_prefix = f"theaters_search_page:{search_query}:" if search_query else "theaters_page:"
    if page > 0:
        nav.append(InlineKeyboardButton("←", callback_data=f"{cb_prefix}{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("→", callback_data=f"{cb_prefix}{page + 1}"))
    if len(nav) > 1 or total_pages > 1:
        keyboard.append(nav)

    # Нижние кнопки
    bottom = []
    if not search_query:
        bottom.append(InlineKeyboardButton("🔍 Найти театр", callback_data="theater_search_input"))
        bottom.append(InlineKeyboardButton("🚇 По метро", callback_data="metro_search"))
    keyboard.append(bottom) if bottom else None

    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(keyboard)
    return text, markup


async def send_theaters_page(
    bot: Bot,
    chat_id: int | str,
    theaters: list[dict],
    fav_ids: set[int],
    page: int = 0,
    page_size: int = THEATERS_PAGE_SIZE,
    title: str = "🏛 Театры",
    search_query: str | None = None,
) -> None:
    """Отправить страницу списка театров."""
    if not theaters:
        await send_message(bot, chat_id, "Театров не найдено.")
        return

    text, markup = build_theaters_page_content(
        theaters, fav_ids, page, page_size, title, search_query,
    )
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=markup)
