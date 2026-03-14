"""Тесты для пагинации списка театров (T007)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.reports.telegram_sender import build_theaters_page_content, THEATERS_PAGE_SIZE


def _make_theaters(n: int) -> list[dict]:
    """Генерация N театров для тестов."""
    return [
        {
            "id": i,
            "name": f"Театр-{i}",
            "slug": f"teatr-{i}",
            "address": f"Адрес {i}",
            "metro": f"Метро-{i}" if i % 2 == 0 else None,
            "url": f"https://teatr-{i}.ru",
            "upcoming_shows": max(0, 30 - i),
        }
        for i in range(1, n + 1)
    ]


class TestBuildTheatersPageContent:
    """Тесты build_theaters_page_content."""

    def test_single_page(self):
        """5 театров → 1 страница, нет кнопок навигации ← →."""
        theaters = _make_theaters(5)
        text, markup = build_theaters_page_content(theaters, set(), page=0)
        assert "стр. 1/1" in text
        assert "Театр-1" in text
        assert "Театр-5" in text

    def test_pagination_three_pages(self):
        """25 театров, page_size=10 → 3 страницы."""
        theaters = _make_theaters(25)
        text, markup = build_theaters_page_content(theaters, set(), page=0, page_size=10)
        assert "стр. 1/3" in text
        assert "Театр-1" in text
        assert "Театр-10" in text
        assert "Театр-11" not in text

    def test_last_page_partial(self):
        """25 театров, стр. 3 → театры 21..25."""
        theaters = _make_theaters(25)
        text, markup = build_theaters_page_content(theaters, set(), page=2, page_size=10)
        assert "стр. 3/3" in text
        assert "Театр-21" in text
        assert "Театр-25" in text

    def test_page_out_of_range_clamped(self):
        """Страница > max → показывается последняя."""
        theaters = _make_theaters(5)
        text, markup = build_theaters_page_content(theaters, set(), page=99, page_size=10)
        assert "стр. 1/1" in text

    def test_fav_star_shown(self):
        """Театр в избранном → кнопка ✅, не в избранном → ⭐."""
        theaters = _make_theaters(3)
        fav_ids = {1, 3}
        text, markup = build_theaters_page_content(theaters, fav_ids, page=0)
        buttons = markup.inline_keyboard
        # Первый театр (id=1) → ✅
        fav_btn_1 = buttons[0][1]
        assert fav_btn_1.text == "✅"
        assert fav_btn_1.callback_data == "fav:theater:1"
        # Второй театр (id=2) → ⭐
        fav_btn_2 = buttons[1][1]
        assert fav_btn_2.text == "⭐"
        assert fav_btn_2.callback_data == "fav:theater:2"

    def test_theater_shows_button(self):
        """Кнопка 🎭 ведёт на theater_shows:{slug}."""
        theaters = _make_theaters(1)
        text, markup = build_theaters_page_content(theaters, set(), page=0)
        show_btn = markup.inline_keyboard[0][0]
        assert show_btn.callback_data == "theater_shows:teatr-1"

    def test_search_query_in_callback(self):
        """При search_query навигация использует theaters_search_page."""
        theaters = _make_theaters(15)
        text, markup = build_theaters_page_content(
            theaters, set(), page=0, page_size=10, search_query="мхт",
        )
        # Ищем кнопку навигации →
        nav_row = markup.inline_keyboard[-1]  # может быть последний ряд
        # Проверяем что где-то есть theaters_search_page
        all_data = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert any("theaters_search_page:мхт:" in d for d in all_data if d)

    def test_metro_info_displayed(self):
        """Метро отображается рядом с названием."""
        theaters = _make_theaters(2)
        text, markup = build_theaters_page_content(theaters, set(), page=0)
        # Театр-2 имеет metro (чётный id)
        assert "Метро-2" in text

    def test_empty_theaters_list(self):
        """Пустой список — функция не падает."""
        text, markup = build_theaters_page_content([], set(), page=0)
        assert "стр. 1/1" in text

    def test_bottom_buttons_no_search(self):
        """Без search_query — есть кнопки 🔍 и 🚇."""
        theaters = _make_theaters(3)
        text, markup = build_theaters_page_content(theaters, set(), page=0)
        all_data = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "theater_search_input" in all_data
        assert "metro_search" in all_data

    def test_bottom_buttons_with_search(self):
        """С search_query — нет кнопок 🔍 и 🚇."""
        theaters = _make_theaters(3)
        text, markup = build_theaters_page_content(
            theaters, set(), page=0, search_query="тест",
        )
        all_data = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "theater_search_input" not in all_data


class TestSendTheatersPage:
    """Тесты send_theaters_page — проверяем вызов bot.send_message."""

    @pytest.mark.asyncio
    async def test_sends_message(self):
        from src.reports.telegram_sender import send_theaters_page
        bot = AsyncMock()
        theaters = _make_theaters(3)
        await send_theaters_page(bot, 123, theaters, set(), page=0)
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 123
        assert "Театр-1" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_empty_list(self):
        from src.reports.telegram_sender import send_theaters_page
        bot = AsyncMock()
        await send_theaters_page(bot, 123, [], set(), page=0)
        bot.send_message.assert_called_once()
        assert "не найдено" in bot.send_message.call_args[1]["text"]
