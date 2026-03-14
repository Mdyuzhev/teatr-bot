"""
Тесты для src/scheduler/jobs.py.
Проверяем get_period_dates и generate_digests_job.
"""
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.scheduler.jobs import get_period_dates, generate_digests_job, PERIOD_LABELS


class TestGetPeriodDates:
    """Тесты вычисления дат периодов."""

    def test_today(self):
        d_from, d_to = get_period_dates("today")
        assert d_from == date.today()
        assert d_to == date.today()

    def test_tomorrow(self):
        d_from, d_to = get_period_dates("tomorrow")
        expected = date.today() + timedelta(days=1)
        assert d_from == expected
        assert d_to == expected

    def test_week(self):
        d_from, d_to = get_period_dates("week")
        assert d_from == date.today()
        assert d_to == date.today() + timedelta(days=6)

    def test_weekend_from_monday(self):
        """Из понедельника weekend = ближайшие сб-вс."""
        monday = date(2026, 3, 16)  # понедельник
        with patch("src.scheduler.jobs.date") as mock_date:
            mock_date.today.return_value = monday
            mock_date.fromisoformat = date.fromisoformat
            d_from, d_to = get_period_dates("weekend")
        assert d_from.weekday() == 5  # суббота
        assert d_to.weekday() == 6    # воскресенье
        assert d_to - d_from == timedelta(days=1)

    def test_weekend_from_saturday(self):
        """Из субботы weekend = текущие сб-вс."""
        saturday = date(2026, 3, 21)  # суббота
        with patch("src.scheduler.jobs.date") as mock_date:
            mock_date.today.return_value = saturday
            mock_date.fromisoformat = date.fromisoformat
            d_from, d_to = get_period_dates("weekend")
        assert d_from == saturday
        assert d_to == saturday + timedelta(days=1)

    def test_weekend_from_sunday(self):
        """Из воскресенья weekend = только воскресенье."""
        sunday = date(2026, 3, 22)  # воскресенье
        with patch("src.scheduler.jobs.date") as mock_date:
            mock_date.today.return_value = sunday
            mock_date.fromisoformat = date.fromisoformat
            d_from, d_to = get_period_dates("weekend")
        assert d_from == sunday
        assert d_to == sunday

    def test_custom_period(self):
        d_from, d_to = get_period_dates("2026-03-20:2026-03-25")
        assert d_from == date(2026, 3, 20)
        assert d_to == date(2026, 3, 25)

    def test_unknown_key_defaults_to_today(self):
        d_from, d_to = get_period_dates("unknown")
        assert d_from == date.today()
        assert d_to == date.today()


class TestGenerateDigestsJob:
    """Тесты generate_digests_job."""

    @pytest.mark.asyncio
    async def test_generates_four_digests(self):
        """Должен сгенерировать 4 стандартных дайджеста."""
        pool = AsyncMock()
        with patch("src.scheduler.jobs.get_digest_data") as mock_data, \
             patch("src.scheduler.jobs.build_digest") as mock_build, \
             patch("src.scheduler.jobs.save_digest") as mock_save, \
             patch("src.scheduler.jobs.get_recent_news") as mock_rss:

            mock_data.return_value = {
                "shows": [{"title": "Тест"}],
                "premieres": [],
                "stats": {"theaters_count": 1, "shows_count": 1, "dates_count": 1},
            }
            mock_build.return_value = "<b>Дайджест</b>"
            mock_rss.return_value = []

            stats = await generate_digests_job(pool)

        assert stats["generated"] == 4
        assert stats["errors"] == 0
        assert mock_save.call_count == 4
        assert mock_build.call_count == 4

    @pytest.mark.asyncio
    async def test_empty_shows_still_saves(self):
        """Пустой список спектаклей — дайджест всё равно сохраняется."""
        pool = AsyncMock()
        with patch("src.scheduler.jobs.get_digest_data") as mock_data, \
             patch("src.scheduler.jobs.build_digest") as mock_build, \
             patch("src.scheduler.jobs.save_digest") as mock_save, \
             patch("src.scheduler.jobs.get_recent_news") as mock_rss:

            mock_data.return_value = {
                "shows": [],
                "premieres": [],
                "stats": {"theaters_count": 0, "shows_count": 0, "dates_count": 0},
            }
            mock_build.return_value = "Спектаклей не найдено."
            mock_rss.return_value = []

            stats = await generate_digests_job(pool)

        assert stats["generated"] == 4
        assert mock_save.call_count == 4

    @pytest.mark.asyncio
    async def test_error_in_one_period_continues(self):
        """Ошибка в одном периоде не останавливает остальные."""
        pool = AsyncMock()
        call_count = 0

        async def failing_build(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API Error")
            return "<b>ОК</b>"

        with patch("src.scheduler.jobs.get_digest_data") as mock_data, \
             patch("src.scheduler.jobs.build_digest", side_effect=failing_build), \
             patch("src.scheduler.jobs.save_digest") as mock_save, \
             patch("src.scheduler.jobs.get_recent_news") as mock_rss:

            mock_data.return_value = {
                "shows": [{"title": "Тест"}],
                "premieres": [],
                "stats": {},
            }
            mock_rss.return_value = []

            stats = await generate_digests_job(pool)

        assert stats["generated"] == 3
        assert stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_rss_only_for_today(self):
        """RSS-новости передаются только для дайджеста 'today'."""
        pool = AsyncMock()
        build_calls = []

        async def capture_build(*args, **kwargs):
            build_calls.append(kwargs)
            return "<b>OK</b>"

        with patch("src.scheduler.jobs.get_digest_data") as mock_data, \
             patch("src.scheduler.jobs.build_digest", side_effect=capture_build), \
             patch("src.scheduler.jobs.save_digest"), \
             patch("src.scheduler.jobs.get_recent_news") as mock_rss:

            mock_data.return_value = {
                "shows": [{"title": "Тест"}],
                "premieres": [],
                "stats": {},
            }
            mock_rss.return_value = [{"title": "Новость"}]

            await generate_digests_job(pool)

        # Проверяем что rss_news != None только для today (первый вызов)
        rss_values = [c.get("rss_news") for c in build_calls]
        assert rss_values[0] is not None  # today
        for v in rss_values[1:]:
            assert v is None  # остальные без RSS


class TestPeriodLabels:
    """Тесты констант."""

    def test_all_standard_periods_have_labels(self):
        for key in ["today", "tomorrow", "weekend", "week"]:
            assert key in PERIOD_LABELS
