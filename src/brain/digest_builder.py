"""
Генерация текстового дайджеста через Claude API.

Получает отфильтрованный список спектаклей из БД,
возвращает готовый текст для отправки в Telegram.

ВАЖНО: этот модуль — единственное место в проекте,
где разрешён вызов Anthropic API. Вся логика выборки
и фильтрации остаётся в db/queries/.
"""
from datetime import date

import anthropic
import httpx
from loguru import logger

from src.config import config


async def build_digest(shows: list[dict], period_label: str,
                       premieres: list[dict] | None = None,
                       stats: dict | None = None,
                       rss_news: list[dict] | None = None) -> str:
    """Сгенерировать дайджест через Claude. При ошибке — raw-список."""
    if not shows:
        return f"На период «{period_label}» спектаклей не найдено."

    raw_text = _format_raw_list(shows, period_label, premieres, stats)

    # Добавляем RSS-контекст для Claude
    rss_context = _format_rss_context(rss_news) if rss_news else ""

    if not config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY не задан — отдаю raw-список")
        result = raw_text
        if rss_news:
            result += "\n\n" + _format_rss_for_raw(rss_news)
        return result

    try:
        return await _call_claude(raw_text, period_label, rss_context)
    except Exception as e:
        logger.warning("Claude API недоступен ({}), отдаю raw-список", e)
        result = raw_text
        if rss_news:
            result += "\n\n" + _format_rss_for_raw(rss_news)
        return result


async def _call_claude(raw_text: str, period_label: str,
                       rss_context: str = "") -> str:
    """Вызов Claude API для генерации дайджеста."""
    http_client = None
    if config.ANTHROPIC_PROXY:
        http_client = httpx.Client(proxy=config.ANTHROPIC_PROXY)
    client = anthropic.Anthropic(
        api_key=config.ANTHROPIC_API_KEY,
        http_client=http_client,
    )

    rss_block = ""
    if rss_context:
        rss_block = f"""

Свежие новости театров (используй для обогащения дайджеста — упомяни если релевантно):
{rss_context}"""

    prompt = f"""Ты — театральный обозреватель Москвы. Составь краткий дайджест спектаклей
за период «{period_label}» на основе данных ниже.

Правила:
- Формат: HTML (теги <b>, <i>, <a> — для Telegram)
- Выдели премьеры, если есть
- Укажи цены, если известны
- Группируй по дням
- Будь лаконичен, не больше 3-4 строк на спектакль
- Если есть свежие новости театров — упомяни кратко в конце
- В конце — краткая сводка (сколько театров, спектаклей)

Данные:
{raw_text}{rss_block}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=config.DIGEST_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text  # type: ignore[union-attr]


def _format_raw_list(shows: list[dict], period_label: str,
                     premieres: list[dict] | None = None,
                     stats: dict | None = None) -> str:
    """Форматирование списка без AI — fallback."""
    lines = [f"<b>Афиша: {period_label}</b>\n"]

    if stats:
        lines.append(
            f"Театров: {stats.get('theaters_count', '?')}, "
            f"спектаклей: {stats.get('shows_count', '?')}, "
            f"показов: {stats.get('dates_count', '?')}\n"
        )

    if premieres:
        lines.append("<b>Премьеры:</b>")
        for p in premieres:
            lines.append(f"  {p['title']} — {p['theater_name']}")
        lines.append("")

    current_date = None
    for show in shows:
        show_date = show.get("date")
        if show_date != current_date:
            current_date = show_date
            if isinstance(show_date, date):
                lines.append(f"\n<b>{show_date.strftime('%d.%m (%a)')}</b>")
            else:
                lines.append(f"\n<b>{show_date}</b>")

        time_str = show["time"].strftime("%H:%M") if show.get("time") else ""
        premiere_mark = " [ПРЕМЬЕРА]" if show.get("is_premiere") else ""
        price = ""
        if show.get("price_min"):
            if show.get("price_max"):
                price = f" | {show['price_min']}-{show['price_max']} руб"
            else:
                price = f" | от {show['price_min']} руб"

        lines.append(
            f"  {time_str} <b>{show['title']}</b>{premiere_mark}\n"
            f"    {show.get('theater_name', '')}{price}"
        )

    return "\n".join(lines)


def _format_rss_context(news: list[dict]) -> str:
    """Форматировать RSS-новости для контекста Claude."""
    lines = []
    for item in news[:10]:
        theater = item.get("theater_name", "")
        title = item.get("title", "")
        lines.append(f"- [{theater}] {title}")
    return "\n".join(lines)


def _format_rss_for_raw(news: list[dict]) -> str:
    """Форматировать RSS-новости для raw-списка (fallback без Claude)."""
    lines = ["<b>Новости театров:</b>"]
    for item in news[:5]:
        theater = item.get("theater_name", "")
        title = item.get("title", "")
        url = item.get("url", "")
        if url:
            lines.append(f"  {theater}: <a href=\"{url}\">{title}</a>")
        else:
            lines.append(f"  {theater}: {title}")
    return "\n".join(lines)
