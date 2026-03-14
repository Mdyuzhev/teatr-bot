"""Тесты для db/queries/reviews.py (T008)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.db.queries.reviews import get_review, save_review, get_show_for_review


def _make_pool(fetchrow_result=None, fetch_result=None):
    """Создать mock asyncpg pool."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.fetch = AsyncMock(return_value=fetch_result or [])
    conn.execute = AsyncMock()

    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx
    return pool, conn


class TestGetReview:
    """Тесты get_review."""

    @pytest.mark.asyncio
    async def test_returns_none_if_no_review(self):
        pool, _ = _make_pool(fetchrow_result=None)
        result = await get_review(pool, show_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dict_if_found(self):
        row = MagicMock()
        row.__iter__ = MagicMock(return_value=iter([
            ("content", "<b>Рецензия</b>"),
            ("model", "claude-haiku-4-5-20251001"),
            ("created_at", "2026-03-14"),
        ]))
        row.keys = MagicMock(return_value=["content", "model", "created_at"])
        row.__getitem__ = lambda self, key: {"content": "<b>Рецензия</b>", "model": "claude-haiku-4-5-20251001", "created_at": "2026-03-14"}[key]

        pool, _ = _make_pool(fetchrow_result=row)
        result = await get_review(pool, show_id=1)
        assert result is not None


class TestSaveReview:
    """Тесты save_review."""

    @pytest.mark.asyncio
    async def test_calls_execute(self):
        pool, conn = _make_pool()
        await save_review(pool, show_id=1, content="<b>Текст</b>", model="haiku")
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO show_reviews" in sql
        assert "ON CONFLICT" in sql

    @pytest.mark.asyncio
    async def test_upsert_params(self):
        pool, conn = _make_pool()
        await save_review(pool, show_id=42, content="Рецензия", model="haiku-test")
        args = conn.execute.call_args[0]
        assert args[1] == 42
        assert args[2] == "Рецензия"
        assert args[3] == "haiku-test"


class TestGetShowForReview:
    """Тесты get_show_for_review."""

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        pool, _ = _make_pool(fetchrow_result=None)
        result = await get_show_for_review(pool, show_id=999)
        assert result is None

    @pytest.mark.asyncio
    async def test_sql_joins_theaters(self):
        pool, conn = _make_pool(fetchrow_result=None)
        await get_show_for_review(pool, show_id=1)
        sql = conn.fetchrow.call_args[0][0]
        assert "JOIN theaters" in sql
        assert "theater_name" in sql
