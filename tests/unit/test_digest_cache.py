"""
Тесты для src/db/queries/digests.py.
Проверяем кэш-логику дайджестов с моками asyncpg.
"""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.queries.digests import get_fresh_digest, save_digest, get_all_digests_status


def _make_pool():
    """Создать мок asyncpg pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


class TestGetFreshDigest:
    """Тесты get_fresh_digest."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cache(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None
        result = await get_fresh_digest(pool, "today", date(2026, 3, 14), date(2026, 3, 14))
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_expired(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None  # SQL фильтрует expires_at > NOW()
        result = await get_fresh_digest(pool, "today", date(2026, 3, 14), date(2026, 3, 14))
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dict_when_fresh(self):
        pool, conn = _make_pool()
        now = datetime.now(timezone.utc)
        row = MagicMock()
        row.__iter__ = MagicMock(return_value=iter([
            ("id", 1), ("period_key", "today"),
            ("date_from", date(2026, 3, 14)), ("date_to", date(2026, 3, 14)),
            ("content", "<b>Дайджест</b>"), ("shows_count", 5),
            ("model", "claude-haiku-4-5-20251001"),
            ("generated_at", now), ("expires_at", now + timedelta(hours=24)),
        ]))
        row.keys.return_value = ["id", "period_key", "date_from", "date_to",
                                  "content", "shows_count", "model",
                                  "generated_at", "expires_at"]
        row.__getitem__ = lambda self, key: dict(self)[key]
        # Проще — пусть fetchrow вернёт dict-like Record
        fake_record = {
            "id": 1, "period_key": "today",
            "date_from": date(2026, 3, 14), "date_to": date(2026, 3, 14),
            "content": "<b>Дайджест</b>", "shows_count": 5,
            "model": "claude-haiku-4-5-20251001",
            "generated_at": now, "expires_at": now + timedelta(hours=24),
        }
        conn.fetchrow.return_value = fake_record
        result = await get_fresh_digest(pool, "today", date(2026, 3, 14), date(2026, 3, 14))
        assert result is not None
        assert result["content"] == "<b>Дайджест</b>"
        assert result["shows_count"] == 5

    @pytest.mark.asyncio
    async def test_sql_contains_expires_check(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None
        await get_fresh_digest(pool, "today", date(2026, 3, 14), date(2026, 3, 14))
        sql = conn.fetchrow.call_args[0][0]
        assert "expires_at > NOW()" in sql


class TestSaveDigest:
    """Тесты save_digest."""

    @pytest.mark.asyncio
    async def test_executes_upsert(self):
        pool, conn = _make_pool()
        await save_digest(pool, "today", date(2026, 3, 14), date(2026, 3, 14),
                          "<b>Тест</b>", 5, "claude-haiku-4-5-20251001")
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO digests" in sql
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql

    @pytest.mark.asyncio
    async def test_passes_correct_params(self):
        pool, conn = _make_pool()
        await save_digest(pool, "weekend", date(2026, 3, 15), date(2026, 3, 16),
                          "Контент", 10, "model-x")
        args = conn.execute.call_args[0]
        assert args[1] == "weekend"
        assert args[2] == date(2026, 3, 15)
        assert args[3] == date(2026, 3, 16)
        assert args[4] == "Контент"
        assert args[5] == 10
        assert args[6] == "model-x"


class TestGetAllDigestsStatus:
    """Тесты get_all_digests_status."""

    @pytest.mark.asyncio
    async def test_returns_list(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        result = await get_all_digests_status(pool)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_dicts(self):
        pool, conn = _make_pool()
        now = datetime.now(timezone.utc)
        conn.fetch.return_value = [
            {"period_key": "today", "date_from": date(2026, 3, 14),
             "date_to": date(2026, 3, 14), "shows_count": 5,
             "generated_at": now, "expires_at": now + timedelta(hours=24),
             "status": "fresh"},
        ]
        result = await get_all_digests_status(pool)
        assert len(result) == 1
        assert result[0]["period_key"] == "today"
        assert result[0]["status"] == "fresh"

    @pytest.mark.asyncio
    async def test_sql_has_status_case(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        await get_all_digests_status(pool)
        sql = conn.fetch.call_args[0][0]
        assert "CASE WHEN expires_at > NOW()" in sql
