"""
Тесты для карточек спектаклей: format_show_card, build_show_card_keyboard, send_shows_as_cards.
"""
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reports.telegram_sender import (
    format_show_card, build_show_card_keyboard, send_shows_as_cards,
)


def _sample_show(**overrides):
    """Пример данных спектакля."""
    show = {
        "show_id": 5,
        "title": "Вишнёвый сад",
        "theater_id": 1,
        "theater_name": "МХТ им. Чехова",
        "metro": "Охотный Ряд",
        "date": date(2026, 3, 22),
        "time": time(19, 0),
        "price_min": 1500,
        "price_max": 5000,
        "age_rating": "12+",
        "is_premiere": False,
        "tickets_url": "https://mxat.ru/tickets",
    }
    show.update(overrides)
    return show


class TestFormatShowCard:
    """Тесты format_show_card."""

    def test_basic_card(self):
        card = format_show_card(_sample_show())
        assert "Вишнёвый сад" in card
        assert "МХТ им. Чехова" in card
        assert "от 1500 ₽" in card
        assert "12+" in card

    def test_premiere_marker(self):
        card = format_show_card(_sample_show(is_premiere=True))
        assert "🌟" in card

    def test_no_premiere_marker(self):
        card = format_show_card(_sample_show(is_premiere=False))
        assert "🌟" not in card

    def test_no_metro(self):
        card = format_show_card(_sample_show(metro=None))
        assert "Охотный Ряд" not in card

    def test_no_price(self):
        card = format_show_card(_sample_show(price_min=None))
        assert "₽" not in card


class TestBuildShowCardKeyboard:
    """Тесты build_show_card_keyboard."""

    def test_has_all_buttons(self):
        show = _sample_show()
        markup = build_show_card_keyboard(show)
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        texts = [b.text for b in buttons]
        assert "🎟 Билеты" in texts
        assert "⭐ В избранное" in texts
        assert "🔖 Интересно" in texts

    def test_fav_active(self):
        markup = build_show_card_keyboard(_sample_show(), has_fav=True)
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        texts = [b.text for b in buttons]
        assert "✅ Сохранён" in texts
        assert "⭐ В избранное" not in texts

    def test_wl_active(self):
        markup = build_show_card_keyboard(_sample_show(), has_wl=True)
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        texts = [b.text for b in buttons]
        assert "📌 В списке" in texts
        assert "🔖 Интересно" not in texts

    def test_no_tickets_url(self):
        markup = build_show_card_keyboard(_sample_show(tickets_url=None))
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        texts = [b.text for b in buttons]
        assert "🎟 Билеты" not in texts

    def test_no_theater_id(self):
        markup = build_show_card_keyboard(_sample_show(theater_id=None))
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        texts = [b.text for b in buttons]
        assert "⭐ В избранное" not in texts

    def test_callback_data_format(self):
        markup = build_show_card_keyboard(_sample_show())
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        callbacks = [b.callback_data for b in buttons if b.callback_data]
        assert "fav:theater:1" in callbacks
        assert "wl:show:5" in callbacks


class TestSendShowsAsCards:
    """Тесты send_shows_as_cards."""

    @pytest.mark.asyncio
    async def test_sends_header_and_cards(self):
        bot = AsyncMock()
        shows = [_sample_show(), _sample_show(show_id=6, title="Гамлет")]
        await send_shows_as_cards(bot, 123, shows, "Тест")
        # header + 2 cards = 3 вызова send_message
        assert bot.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_shows(self):
        bot = AsyncMock()
        await send_shows_as_cards(bot, 123, [], "Пусто")
        # 1 вызов с "Пусто"
        assert bot.send_message.call_count == 1

    @pytest.mark.asyncio
    async def test_pagination_nav(self):
        bot = AsyncMock()
        shows = [_sample_show(show_id=i) for i in range(12)]
        await send_shows_as_cards(bot, 123, shows, "Много", page_size=5)
        # header(1) + 5 cards + nav(1) = 7
        assert bot.send_message.call_count == 7

    @pytest.mark.asyncio
    async def test_second_page_no_header(self):
        bot = AsyncMock()
        shows = [_sample_show(show_id=i) for i in range(12)]
        await send_shows_as_cards(bot, 123, shows, "Много", page=1, page_size=5)
        # page 1: 5 cards + nav = 6 (no header)
        assert bot.send_message.call_count == 6
