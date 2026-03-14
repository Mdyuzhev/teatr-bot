"""
Тесты для вспомогательных функций telegram_commands.py.
Логика дат переехала в scheduler/jobs.py — тестируем через get_period_dates.
"""
from datetime import date, timedelta
from unittest.mock import patch

from src.scheduler.jobs import get_period_dates, _next_weekend_dates


class TestNextWeekendDates:
    """Тесты вычисления ближайших выходных."""

    def test_monday_returns_saturday(self):
        # 2026-03-16 — понедельник
        sat, sun = _next_weekend_dates(date(2026, 3, 16))
        assert sat == date(2026, 3, 21)
        assert sun == date(2026, 3, 22)

    def test_friday_returns_saturday(self):
        # 2026-03-20 — пятница
        sat, sun = _next_weekend_dates(date(2026, 3, 20))
        assert sat == date(2026, 3, 21)
        assert sun == date(2026, 3, 22)

    def test_saturday_returns_same(self):
        # 2026-03-21 — суббота
        sat, sun = _next_weekend_dates(date(2026, 3, 21))
        assert sat == date(2026, 3, 21)
        assert sun == date(2026, 3, 22)

    def test_sunday_returns_same(self):
        # 2026-03-22 — воскресенье
        d_from, d_to = _next_weekend_dates(date(2026, 3, 22))
        assert d_from == date(2026, 3, 22)
        assert d_to == date(2026, 3, 22)
