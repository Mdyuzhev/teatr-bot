"""
Генерация краткой рецензии на спектакль через Claude Haiku.

ВАЖНО: единственное место где вызывается Haiku для рецензий.
При ошибке API — возвращает описание из БД (graceful degradation).
"""
import anthropic
import httpx
from loguru import logger

from src.config import config

REVIEW_MODEL = "claude-haiku-4-5-20251001"
REVIEW_MAX_TOKENS = 400


async def build_review(show: dict) -> str:
    """Сгенерировать рецензию через Haiku. При ошибке — fallback на описание."""
    if not config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY не задан — отдаю fallback")
        return _fallback_review(show)

    try:
        return _call_haiku(show)
    except Exception as e:
        logger.warning("Haiku API недоступен ({}), отдаю fallback", e)
        return _fallback_review(show)


def _call_haiku(show: dict) -> str:
    """Вызов Claude Haiku для генерации рецензии."""
    http_client = None
    if config.ANTHROPIC_PROXY:
        http_client = httpx.Client(proxy=config.ANTHROPIC_PROXY)
    client = anthropic.Anthropic(
        api_key=config.ANTHROPIC_API_KEY,
        http_client=http_client,
    )

    premiere = "🌟 ПРЕМЬЕРА" if show.get("is_premiere") else ""
    prompt = f"""Ты — театральный критик. Напиши короткую рецензию на спектакль
для Telegram-бота (2-3 абзаца, HTML-разметка).

Спектакль: {show['title']}
Театр: {show['theater_name']}
Жанр: {show.get('genre') or 'не указан'}
Возрастной рейтинг: {show.get('age_rating') or 'не указан'}
{premiere}

Описание от театра:
{show.get('description') or 'Описание отсутствует.'}

Правила:
- HTML: <b>жирный</b>, <i>курсив</i> — только для Telegram
- 2-3 абзаца: о чём спектакль, особенности постановки, кому рекомендовать
- Тон: живой, не сухой; пиши как для живого читателя
- Не придумывай факты которых нет в описании
- Если описание пустое — напиши нейтральный текст на основе названия и театра
- В конце — одна строка «Рекомендуем: [кому стоит сходить]»"""

    response = client.messages.create(
        model=REVIEW_MODEL,
        max_tokens=REVIEW_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def _fallback_review(show: dict) -> str:
    """Заглушка если API недоступен или description пустой."""
    premiere = "🌟 Премьера сезона. " if show.get("is_premiere") else ""
    genre = f"Жанр: {show['genre']}. " if show.get("genre") else ""
    return (
        f"{premiere}<b>{show['title']}</b>\n"
        f"{show['theater_name']}\n\n"
        f"{genre}"
        f"{show.get('description') or 'Описание спектакля уточняйте на сайте театра.'}"
    )
