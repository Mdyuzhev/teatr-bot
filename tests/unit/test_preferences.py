"""
Тесты для src/db/queries/preferences.py.
Проверяем toggle, has_preference, get_user_favorites/watchlist с моками asyncpg.
"""
from contextlib import asynccontextmanager
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.queries.preferences import (
    toggle_preference, has_preference,
    get_user_favorites, get_user_watchlist,
    get_watchlist_users_for_show, get_favorite_users_for_theater,
    remove_preference,
)


def _make_pool():
    """Создать мок asyncpg pool с корректным async context manager."""
    conn = AsyncMock()
    pool = MagicMock()

    @asynccontextmanager
    async def fake_acquire():
        yield conn

    pool.acquire = fake_acquire
    return pool, conn


class TestTogglePreference:
    """Тесты toggle_preference."""

    @pytest.mark.asyncio
    async def test_toggle_adds_when_not_exists(self):
        pool, conn = _make_pool()
        conn.fetchval.return_value = None  # не существует
        result = await toggle_preference(pool, 111, "favorite", 1, "theater")
        assert result is True
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO user_preferences" in sql

    @pytest.mark.asyncio
    async def test_toggle_removes_when_exists(self):
        pool, conn = _make_pool()
        conn.fetchval.return_value = 42  # существует, id=42
        result = await toggle_preference(pool, 111, "favorite", 1, "theater")
        assert result is False
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "DELETE FROM user_preferences" in sql


class TestHasPreference:
    """Тесты has_preference."""

    @pytest.mark.asyncio
    async def test_returns_true_when_exists(self):
        pool, conn = _make_pool()
        conn.fetchval.return_value = 1
        result = await has_preference(pool, 111, "watchlist", 5, "show")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_exists(self):
        pool, conn = _make_pool()
        conn.fetchval.return_value = None
        result = await has_preference(pool, 111, "watchlist", 5, "show")
        assert result is False


class TestGetUserFavorites:
    """Тесты get_user_favorites."""

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        result = await get_user_favorites(pool, 111)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_theater_list(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            {"id": 1, "name": "МХТ им. Чехова", "slug": "mkhat", "metro": "Охотный Ряд",
             "upcoming_shows": 7},
            {"id": 2, "name": "Театр Вахтангова", "slug": "vakhtangov", "metro": "Арбатская",
             "upcoming_shows": 3},
        ]
        result = await get_user_favorites(pool, 111)
        assert len(result) == 2
        assert result[0]["name"] == "МХТ им. Чехова"
        assert result[0]["upcoming_shows"] == 7

    @pytest.mark.asyncio
    async def test_sql_joins_user_preferences(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        await get_user_favorites(pool, 111)
        sql = conn.fetch.call_args[0][0]
        assert "user_preferences" in sql
        assert "favorite" in sql


class TestGetUserWatchlist:
    """Тесты get_user_watchlist."""

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        result = await get_user_watchlist(pool, 111)
        assert result == []

    @pytest.mark.asyncio
    async def test_marks_last_chance(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            {"id": 5, "title": "Вишнёвый сад", "slug": "vishneviy-sad",
             "theater_name": "МХТ", "theater_slug": "mkhat",
             "next_date": date(2026, 3, 22), "next_time": time(19, 0),
             "remaining_dates": 2},
        ]
        result = await get_user_watchlist(pool, 111)
        assert len(result) == 1
        assert result[0]["last_chance"] is True

    @pytest.mark.asyncio
    async def test_no_last_chance_when_many_dates(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            {"id": 5, "title": "Гамлет", "slug": "gamlet",
             "theater_name": "Ленком", "theater_slug": "lenkom",
             "next_date": date(2026, 3, 25), "next_time": time(19, 0),
             "remaining_dates": 5},
        ]
        result = await get_user_watchlist(pool, 111)
        assert result[0]["last_chance"] is False

    @pytest.mark.asyncio
    async def test_no_last_chance_when_zero_dates(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            {"id": 5, "title": "Три сестры", "slug": "tri-sestry",
             "theater_name": "МХАТ", "theater_slug": "mhat",
             "next_date": None, "next_time": None,
             "remaining_dates": 0},
        ]
        result = await get_user_watchlist(pool, 111)
        assert result[0]["last_chance"] is False


class TestGetUsersForNotifications:
    """Тесты get_watchlist_users_for_show / get_favorite_users_for_theater."""

    @pytest.mark.asyncio
    async def test_watchlist_users(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [{"user_id": 111}, {"user_id": 222}]
        result = await get_watchlist_users_for_show(pool, 5)
        assert result == [111, 222]

    @pytest.mark.asyncio
    async def test_favorite_users(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [{"user_id": 333}]
        result = await get_favorite_users_for_theater(pool, 1)
        assert result == [333]

    @pytest.mark.asyncio
    async def test_watchlist_users_empty(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        result = await get_watchlist_users_for_show(pool, 999)
        assert result == []


class TestRemovePreference:
    """Тесты remove_preference."""

    @pytest.mark.asyncio
    async def test_returns_true_when_deleted(self):
        pool, conn = _make_pool()
        conn.execute.return_value = "DELETE 1"
        result = await remove_preference(pool, 111, "favorite", 1, "theater")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        pool, conn = _make_pool()
        conn.execute.return_value = "DELETE 0"
        result = await remove_preference(pool, 111, "favorite", 999, "theater")
        assert result is False
