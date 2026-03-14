"""Тесты для build_show_card_keyboard (T008)."""
import pytest
from src.reports.telegram_sender import build_show_card_keyboard


def _make_show(**overrides) -> dict:
    base = {
        "show_id": 1,
        "theater_id": 10,
        "tickets_url": "https://tickets.ru/1",
    }
    base.update(overrides)
    return base


class TestBuildShowCardKeyboard:
    """Тесты кнопок карточки спектакля."""

    def test_review_button_present(self):
        """Кнопка 📝 Рецензия есть когда есть show_id."""
        show = _make_show()
        markup = build_show_card_keyboard(show)
        all_buttons = [btn for row in markup.inline_keyboard for btn in row]
        review_btns = [b for b in all_buttons if "Рецензия" in b.text]
        assert len(review_btns) == 1
        assert review_btns[0].callback_data == "review:1"

    def test_no_review_without_show_id(self):
        """Без show_id кнопки рецензии нет."""
        show = _make_show(show_id=None, id=None)
        markup = build_show_card_keyboard(show)
        if markup:
            all_buttons = [btn for row in markup.inline_keyboard for btn in row]
            review_btns = [b for b in all_buttons if "Рецензия" in (b.text or "")]
            assert len(review_btns) == 0

    def test_two_rows_layout(self):
        """Первый ряд: Билеты+Рецензия, второй: Избранное+Интересно."""
        show = _make_show()
        markup = build_show_card_keyboard(show)
        rows = markup.inline_keyboard
        assert len(rows) == 2
        # Первый ряд — Билеты + Рецензия
        row1_texts = [b.text for b in rows[0]]
        assert any("Билеты" in t for t in row1_texts)
        assert any("Рецензия" in t for t in row1_texts)
        # Второй ряд — Избранное + Интересно
        row2_texts = [b.text for b in rows[1]]
        assert any("избранное" in t.lower() or "Сохранён" in t for t in row2_texts)
        assert any("Интересно" in t or "В списке" in t for t in row2_texts)

    def test_no_tickets_still_has_review(self):
        """Без билетов рецензия всё равно в первом ряду."""
        show = _make_show(tickets_url=None)
        markup = build_show_card_keyboard(show)
        row1 = markup.inline_keyboard[0]
        assert any("Рецензия" in b.text for b in row1)

    def test_fav_and_wl_flags(self):
        """has_fav и has_wl меняют текст кнопок."""
        show = _make_show()
        markup = build_show_card_keyboard(show, has_fav=True, has_wl=True)
        all_texts = [b.text for row in markup.inline_keyboard for b in row]
        assert "✅ Сохранён" in all_texts
        assert "📌 В списке" in all_texts
