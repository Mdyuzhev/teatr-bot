"""
Тесты для notifications_job из src/scheduler/jobs.py
и src/db/queries/notifications.py.
"""
from contextlib import asynccontextmanager
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.queries.notifications import (
    is_notification_sent, log_notification,
    get_new_show_dates, get_last_chance_shows,
)
from src.scheduler.jobs import notifications_job


def _make_pool():
    conn = AsyncMock()
    pool = MagicMock()

    @asynccontextmanager
    async def fake_acquire():
        yield conn

    pool.acquire = fake_acquire
    return pool, conn


class TestIsNotificationSent:
    """Тесты is_notification_sent."""

    @pytest.mark.asyncio
    async def test_returns_true_when_exists(self):
        pool, conn = _make_pool()
        conn.fetchval.return_value = 1
        result = await is_notification_sent(pool, 111, "new_date", 5)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_exists(self):
        pool, conn = _make_pool()
        conn.fetchval.return_value = None
        result = await is_notification_sent(pool, 111, "new_date", 5)
        assert result is False


class TestLogNotification:
    """Тесты log_notification."""

    @pytest.mark.asyncio
    async def test_inserts_record(self):
        pool, conn = _make_pool()
        await log_notification(pool, 111, "new_date", 5)
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO notification_log" in sql
        assert "ON CONFLICT DO NOTHING" in sql


class TestGetNewShowDates:
    """Тесты get_new_show_dates."""

    @pytest.mark.asyncio
    async def test_returns_list(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            {"show_date_id": 10, "date": date(2026, 3, 20), "time": time(19, 0),
             "show_id": 5, "title": "Гамлет",
             "theater_id": 1, "theater_name": "Ленком"},
        ]
        result = await get_new_show_dates(pool, hours=24)
        assert len(result) == 1
        assert result[0]["show_id"] == 5

    @pytest.mark.asyncio
    async def test_returns_empty(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        result = await get_new_show_dates(pool, hours=24)
        assert result == []


class TestGetLastChanceShows:
    """Тесты get_last_chance_shows."""

    @pytest.mark.asyncio
    async def test_returns_shows_with_2_dates(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            {"show_id": 5, "title": "Три сестры",
             "theater_id": 2, "theater_name": "МХАТ", "remaining": 2},
        ]
        result = await get_last_chance_shows(pool)
        assert len(result) == 1
        assert result[0]["remaining"] == 2

    @pytest.mark.asyncio
    async def test_sql_has_having_count_2(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        await get_last_chance_shows(pool)
        sql = conn.fetch.call_args[0][0]
        assert "HAVING COUNT(sd.id) = 2" in sql


class TestNotificationsJob:
    """Тесты notifications_job — интеграция с моками."""

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.get_new_show_dates")
    @patch("src.scheduler.jobs.get_last_chance_shows")
    @patch("src.scheduler.jobs.get_favorite_users_for_theater")
    @patch("src.scheduler.jobs.get_watchlist_users_for_show")
    @patch("src.scheduler.jobs.is_notification_sent")
    @patch("src.scheduler.jobs.log_notification")
    async def test_sends_notifications_for_new_dates(
        self, mock_log, mock_is_sent, mock_wl_users,
        mock_fav_users, mock_last_chance, mock_new_dates,
    ):
        pool, conn = _make_pool()

        mock_new_dates.return_value = [
            {"show_date_id": 10, "date": date(2026, 3, 20), "time": time(19, 0),
             "show_id": 5, "title": "Гамлет",
             "theater_id": 1, "theater_name": "Ленком"},
        ]
        mock_last_chance.return_value = []
        mock_fav_users.return_value = [111, 222]
        mock_wl_users.return_value = [333]
        mock_is_sent.return_value = False

        stats = await notifications_job(pool)

        assert stats["sent"] == 3  # 2 fav + 1 watchlist
        assert stats["skipped"] == 0
        assert mock_log.call_count == 3

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.get_new_show_dates")
    @patch("src.scheduler.jobs.get_last_chance_shows")
    @patch("src.scheduler.jobs.get_favorite_users_for_theater")
    @patch("src.scheduler.jobs.get_watchlist_users_for_show")
    @patch("src.scheduler.jobs.is_notification_sent")
    @patch("src.scheduler.jobs.log_notification")
    async def test_skips_already_sent(
        self, mock_log, mock_is_sent, mock_wl_users,
        mock_fav_users, mock_last_chance, mock_new_dates,
    ):
        pool, conn = _make_pool()

        mock_new_dates.return_value = [
            {"show_date_id": 10, "date": date(2026, 3, 20), "time": time(19, 0),
             "show_id": 5, "title": "Гамлет",
             "theater_id": 1, "theater_name": "Ленком"},
        ]
        mock_last_chance.return_value = []
        mock_fav_users.return_value = [111]
        mock_wl_users.return_value = []
        mock_is_sent.return_value = True  # уже отправлено

        stats = await notifications_job(pool)

        assert stats["sent"] == 0
        assert stats["skipped"] == 1
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.get_new_show_dates")
    @patch("src.scheduler.jobs.get_last_chance_shows")
    @patch("src.scheduler.jobs.get_favorite_users_for_theater")
    @patch("src.scheduler.jobs.get_watchlist_users_for_show")
    @patch("src.scheduler.jobs.is_notification_sent")
    @patch("src.scheduler.jobs.log_notification")
    async def test_last_chance_notifications(
        self, mock_log, mock_is_sent, mock_wl_users,
        mock_fav_users, mock_last_chance, mock_new_dates,
    ):
        pool, conn = _make_pool()

        mock_new_dates.return_value = []
        mock_last_chance.return_value = [
            {"show_id": 5, "title": "Три сестры",
             "theater_id": 2, "theater_name": "МХАТ", "remaining": 2},
        ]
        mock_fav_users.return_value = []
        mock_wl_users.return_value = [444, 555]
        mock_is_sent.return_value = False

        stats = await notifications_job(pool)

        assert stats["sent"] == 2
        # Проверяем тип уведомления
        log_calls = mock_log.call_args_list
        for call in log_calls:
            assert call[0][2] == "last_chance"

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.get_new_show_dates")
    @patch("src.scheduler.jobs.get_last_chance_shows")
    async def test_handles_empty_data(self, mock_last_chance, mock_new_dates):
        pool, conn = _make_pool()
        mock_new_dates.return_value = []
        mock_last_chance.return_value = []

        stats = await notifications_job(pool)

        assert stats["sent"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
