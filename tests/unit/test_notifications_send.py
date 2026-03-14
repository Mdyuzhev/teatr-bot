"""
Тесты реальной отправки уведомлений через bot.send_message.
"""
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scheduler.jobs import notifications_job


@pytest.mark.asyncio
@patch("src.scheduler.jobs.get_new_show_dates")
@patch("src.scheduler.jobs.get_last_chance_shows")
@patch("src.scheduler.jobs.get_favorite_users_for_theater")
@patch("src.scheduler.jobs.get_watchlist_users_for_show")
@patch("src.scheduler.jobs.is_notification_sent")
@patch("src.scheduler.jobs.log_notification")
async def test_bot_send_message_called(
    mock_log, mock_is_sent, mock_wl_users,
    mock_fav_users, mock_last_chance, mock_new_dates,
):
    """notifications_job вызывает bot.send_message для каждого подписчика."""
    pool = MagicMock()
    bot = AsyncMock()

    mock_new_dates.return_value = [
        {"show_date_id": 10, "date": date(2026, 3, 20), "time": time(19, 0),
         "show_id": 5, "title": "Гамлет",
         "theater_id": 1, "theater_name": "Ленком"},
    ]
    mock_last_chance.return_value = []
    mock_fav_users.return_value = [111, 222]
    mock_wl_users.return_value = [333]
    mock_is_sent.return_value = False

    stats = await notifications_job(pool, bot=bot)

    assert stats["sent"] == 3
    assert bot.send_message.call_count == 3

    # Проверяем что сообщения с HTML
    for call in bot.send_message.call_args_list:
        assert call[1]["parse_mode"] == "HTML"


@pytest.mark.asyncio
@patch("src.scheduler.jobs.get_new_show_dates")
@patch("src.scheduler.jobs.get_last_chance_shows")
@patch("src.scheduler.jobs.get_favorite_users_for_theater")
@patch("src.scheduler.jobs.get_watchlist_users_for_show")
@patch("src.scheduler.jobs.is_notification_sent")
@patch("src.scheduler.jobs.log_notification")
async def test_skip_already_sent_no_bot_call(
    mock_log, mock_is_sent, mock_wl_users,
    mock_fav_users, mock_last_chance, mock_new_dates,
):
    """Повторный вызов не отправляет уведомление (notification_log)."""
    pool = MagicMock()
    bot = AsyncMock()

    mock_new_dates.return_value = [
        {"show_date_id": 10, "date": date(2026, 3, 20), "time": time(19, 0),
         "show_id": 5, "title": "Гамлет",
         "theater_id": 1, "theater_name": "Ленком"},
    ]
    mock_last_chance.return_value = []
    mock_fav_users.return_value = [111]
    mock_wl_users.return_value = []
    mock_is_sent.return_value = True

    stats = await notifications_job(pool, bot=bot)

    assert stats["sent"] == 0
    assert stats["skipped"] == 1
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
@patch("src.scheduler.jobs.get_new_show_dates")
@patch("src.scheduler.jobs.get_last_chance_shows")
@patch("src.scheduler.jobs.get_favorite_users_for_theater")
@patch("src.scheduler.jobs.get_watchlist_users_for_show")
@patch("src.scheduler.jobs.is_notification_sent")
@patch("src.scheduler.jobs.log_notification")
async def test_send_error_does_not_crash(
    mock_log, mock_is_sent, mock_wl_users,
    mock_fav_users, mock_last_chance, mock_new_dates,
):
    """Exception при send_message не роняет весь job."""
    pool = MagicMock()
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("User blocked bot")

    mock_new_dates.return_value = [
        {"show_date_id": 10, "date": date(2026, 3, 20), "time": time(19, 0),
         "show_id": 5, "title": "Гамлет",
         "theater_id": 1, "theater_name": "Ленком"},
    ]
    mock_last_chance.return_value = []
    mock_fav_users.return_value = [111]
    mock_wl_users.return_value = []
    mock_is_sent.return_value = False

    stats = await notifications_job(pool, bot=bot)

    # Ошибка отправки, но job не упал
    assert stats["errors"] >= 1
    assert stats["sent"] == 0


@pytest.mark.asyncio
@patch("src.scheduler.jobs.get_new_show_dates")
@patch("src.scheduler.jobs.get_last_chance_shows")
@patch("src.scheduler.jobs.get_favorite_users_for_theater")
@patch("src.scheduler.jobs.get_watchlist_users_for_show")
@patch("src.scheduler.jobs.is_notification_sent")
@patch("src.scheduler.jobs.log_notification")
async def test_last_chance_sends_message(
    mock_log, mock_is_sent, mock_wl_users,
    mock_fav_users, mock_last_chance, mock_new_dates,
):
    """Last chance уведомление реально отправляется."""
    pool = MagicMock()
    bot = AsyncMock()

    mock_new_dates.return_value = []
    mock_last_chance.return_value = [
        {"show_id": 5, "title": "Три сестры",
         "theater_id": 2, "theater_name": "МХАТ", "remaining": 2},
    ]
    mock_fav_users.return_value = []
    mock_wl_users.return_value = [444]
    mock_is_sent.return_value = False

    stats = await notifications_job(pool, bot=bot)

    assert stats["sent"] == 1
    assert bot.send_message.call_count == 1
    msg = bot.send_message.call_args[1]["text"]
    assert "Последний шанс" in msg
    assert "Три сестры" in msg


@pytest.mark.asyncio
@patch("src.scheduler.jobs.get_new_show_dates")
@patch("src.scheduler.jobs.get_last_chance_shows")
async def test_no_bot_backward_compat(mock_last_chance, mock_new_dates):
    """Без bot (backward compat) — job работает, но не отправляет."""
    pool = MagicMock()
    mock_new_dates.return_value = []
    mock_last_chance.return_value = []

    stats = await notifications_job(pool)  # no bot
    assert stats["sent"] == 0
    assert stats["errors"] == 0
