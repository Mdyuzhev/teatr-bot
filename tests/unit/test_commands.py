"""
Тесты для вспомогательных функций telegram_commands.py.
"""
from datetime import date

from src.reports.telegram_commands import _next_weekend


class TestNextWeekend:
    """Тесты вычисления ближайших выходных."""

    def test_monday_returns_saturday(self):
        # 2026-03-16 — понедельник
        sat, sun, label = _next_weekend(date(2026, 3, 16))
        assert sat == date(2026, 3, 21)
        assert sun == date(2026, 3, 22)
        assert "21.03" in label

    def test_friday_returns_saturday(self):
        # 2026-03-20 — пятница
        sat, sun, label = _next_weekend(date(2026, 3, 20))
        assert sat == date(2026, 3, 21)
        assert sun == date(2026, 3, 22)

    def test_saturday_returns_same(self):
        # 2026-03-21 — суббота
        sat, sun, label = _next_weekend(date(2026, 3, 21))
        assert sat == date(2026, 3, 21)
        assert sun == date(2026, 3, 22)

    def test_sunday_returns_same(self):
        # 2026-03-22 — воскресенье
        result_date, _, label = _next_weekend(date(2026, 3, 22))
        assert result_date == date(2026, 3, 22)
        assert "Воскресенье" in label
