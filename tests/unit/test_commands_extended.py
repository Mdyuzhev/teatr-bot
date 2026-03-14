"""
Расширенные тесты команд Telegram-бота.
Тестируем digest_callback, cmd_theater, cmd_status — с mock БД и Telegram.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_pool():
    """Мок asyncpg pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_update():
    """Мок Telegram Update."""
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = MagicMock()
    return update


@pytest.fixture
def mock_context():
    """Мок Telegram Context."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.args = []
    return context


class TestDigestCallback:
    """Тесты callback-обработчика inline-кнопок дайджеста."""

    @pytest.mark.asyncio
    async def test_digest_today_from_cache(self, mock_context):
        """digest_today с кэшем → отдаёт из кэша без вызова LLM."""
        from src.reports.telegram_commands import digest_callback

        update = MagicMock()
        query = AsyncMock()
        query.data = "digest_today"
        query.message.chat_id = 12345
        update.callback_query = query

        with patch("src.reports.telegram_commands.get_pool") as mock_gp, \
             patch("src.reports.telegram_commands.get_fresh_digest") as mock_cache, \
             patch("src.reports.telegram_commands.build_digest") as mock_bd, \
             patch("src.reports.telegram_commands.send_message") as mock_sm:

            mock_gp.return_value = AsyncMock()
            mock_cache.return_value = {"content": "Кэшированный дайджест"}

            await digest_callback(update, mock_context)

            query.answer.assert_awaited_once()
            mock_bd.assert_not_awaited()  # LLM не вызывался
            mock_sm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_digest_today_no_cache(self, mock_context):
        """digest_today без кэша → генерирует через LLM."""
        from src.reports.telegram_commands import digest_callback

        update = MagicMock()
        query = AsyncMock()
        query.data = "digest_today"
        query.message.chat_id = 12345
        update.callback_query = query

        with patch("src.reports.telegram_commands.get_pool") as mock_gp, \
             patch("src.reports.telegram_commands.get_fresh_digest") as mock_cache, \
             patch("src.reports.telegram_commands.get_digest_data") as mock_dd, \
             patch("src.reports.telegram_commands.get_recent_news") as mock_rn, \
             patch("src.reports.telegram_commands.build_digest") as mock_bd, \
             patch("src.reports.telegram_commands.save_digest") as mock_save, \
             patch("src.reports.telegram_commands.send_message") as mock_sm:

            mock_gp.return_value = AsyncMock()
            mock_cache.return_value = None  # нет кэша
            mock_dd.return_value = {"shows": [], "premieres": [], "stats": {}}
            mock_rn.return_value = []
            mock_bd.return_value = "Дайджест"

            await digest_callback(update, mock_context)

            query.answer.assert_awaited_once()
            query.edit_message_text.assert_awaited_with("Генерирую дайджест...")
            mock_bd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_digest_unknown_data_ignored(self, mock_context):
        """Неизвестный callback_data → ничего не происходит."""
        from src.reports.telegram_commands import digest_callback

        update = MagicMock()
        query = AsyncMock()
        query.data = "digest_unknown"
        update.callback_query = query

        with patch("src.reports.telegram_commands.send_message") as mock_sm:
            await digest_callback(update, mock_context)
            mock_sm.assert_not_awaited()


class TestCmdTheater:
    """Тесты команды /theater."""

    @pytest.mark.asyncio
    async def test_no_args_shows_help(self, mock_update, mock_context):
        """Без аргументов → подсказка."""
        from src.reports.telegram_commands import cmd_theater

        mock_context.args = []

        with patch("src.reports.telegram_commands.send_message") as mock_sm:
            await cmd_theater(mock_update, mock_context)
            mock_sm.assert_awaited_once()
            call_text = mock_sm.call_args[0][2]
            assert "Укажите название" in call_text

    @pytest.mark.asyncio
    async def test_theater_not_found(self, mock_update, mock_context):
        """Театр не найден → сообщение."""
        from src.reports.telegram_commands import cmd_theater
        from contextlib import asynccontextmanager

        mock_context.args = ["несуществующий"]

        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        mock_pool = MagicMock()

        @asynccontextmanager
        async def fake_acquire():
            yield mock_conn

        mock_pool.acquire = fake_acquire

        with patch("src.reports.telegram_commands.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("src.reports.telegram_commands.send_message") as mock_sm:
            await cmd_theater(mock_update, mock_context)
            call_text = mock_sm.call_args[0][2]
            assert "не найден" in call_text


class TestCmdStatus:
    """Тесты команды /status."""

    @pytest.mark.asyncio
    async def test_status_format(self, mock_update, mock_context):
        """Проверяем формат ответа /status."""
        from src.reports.telegram_commands import cmd_status
        from datetime import datetime

        with patch("src.reports.telegram_commands.get_pool") as mock_gp, \
             patch("src.reports.telegram_commands.get_bot_stats") as mock_bs, \
             patch("src.reports.telegram_commands.get_news_count") as mock_nc, \
             patch("src.reports.telegram_commands.get_all_digests_status") as mock_ds, \
             patch("src.reports.telegram_commands.send_message") as mock_sm:

            mock_gp.return_value = AsyncMock()
            mock_bs.return_value = {
                "theaters": 80,
                "shows": 500,
                "active_dates": 1200,
                "last_collected": datetime(2026, 3, 14, 6, 0),
            }
            mock_nc.return_value = 15
            mock_ds.return_value = [
                {"period_key": "today", "shows_count": 5,
                 "generated_at": datetime(2026, 3, 14, 7, 0), "status": "fresh"},
            ]

            await cmd_status(mock_update, mock_context)

            call_text = mock_sm.call_args[0][2]
            assert "80" in call_text
            assert "500" in call_text
            assert "1200" in call_text
            assert "15" in call_text
            assert "14.03.2026" in call_text
            assert "today" in call_text


class TestCmdNews:
    """Тесты команды /news."""

    @pytest.mark.asyncio
    async def test_no_news(self, mock_update, mock_context):
        """Нет новостей → сообщение."""
        from src.reports.telegram_commands import cmd_news

        with patch("src.reports.telegram_commands.get_pool") as mock_gp, \
             patch("src.reports.telegram_commands.get_recent_news") as mock_rn, \
             patch("src.reports.telegram_commands.send_message") as mock_sm:

            mock_gp.return_value = AsyncMock()
            mock_rn.return_value = []

            await cmd_news(mock_update, mock_context)

            call_text = mock_sm.call_args[0][2]
            assert "нет" in call_text.lower() or "Новостей" in call_text
