"""Тесты отправки карточек с фото (T009)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.reports.telegram_sender import send_shows_as_cards


def _make_show(**overrides) -> dict:
    base = {
        "show_id": 1,
        "title": "Чайка",
        "theater_name": "МХАТ",
        "theater_id": 10,
        "is_premiere": False,
        "image_url": None,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_with_image_sends_photo_then_message():
    """show с image_url → send_photo вызван, затем send_message."""
    bot = AsyncMock()
    show = _make_show(image_url="https://img.kudago.com/640x384.jpg")
    await send_shows_as_cards(bot, 123, [show], "Header")
    # Header + карточка = 2 send_message, 1 send_photo
    assert bot.send_photo.call_count == 1
    assert bot.send_photo.call_args.kwargs["photo"] == "https://img.kudago.com/640x384.jpg"
    assert bot.send_message.call_count >= 2  # header + card


@pytest.mark.asyncio
async def test_without_image_no_photo():
    """show без image_url → send_photo не вызван."""
    bot = AsyncMock()
    show = _make_show(image_url=None)
    await send_shows_as_cards(bot, 123, [show], "Header")
    assert bot.send_photo.call_count == 0
    assert bot.send_message.call_count >= 1


@pytest.mark.asyncio
async def test_photo_error_still_sends_card():
    """send_photo бросает исключение → send_message всё равно вызван."""
    bot = AsyncMock()
    bot.send_photo.side_effect = Exception("Bad photo URL")
    show = _make_show(image_url="https://broken.url/img.jpg")
    await send_shows_as_cards(bot, 123, [show], "Header")
    assert bot.send_photo.call_count == 1
    # Карточка должна быть отправлена несмотря на ошибку фото
    card_calls = [c for c in bot.send_message.call_args_list if "reply_markup" in c.kwargs]
    assert len(card_calls) >= 1


@pytest.mark.asyncio
async def test_message_error_does_not_crash():
    """send_message бросает исключение → не роняет цикл."""
    bot = AsyncMock()
    # Header отправляется нормально, карточка падает
    call_count = 0

    async def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 1:  # Вторая попытка — карточка
            raise Exception("Send failed")

    bot.send_message.side_effect = side_effect
    shows = [_make_show(), _make_show(show_id=2, title="Вишнёвый сад")]
    # Не должен упасть
    await send_shows_as_cards(bot, 123, shows, "Header")
