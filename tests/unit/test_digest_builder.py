"""
Тесты для digest_builder.py.
Проверяем raw-форматирование и graceful degradation.
"""
from datetime import date, time
from unittest.mock import patch

import pytest

from src.brain.digest_builder import build_digest, _format_raw_list


class TestFormatRawList:
    """Тесты форматирования raw-списка (fallback без Claude)."""

    def test_empty_shows(self):
        result = _format_raw_list([], "Сегодня")
        assert "Сегодня" in result

    def test_single_show(self):
        shows = [{
            "title": "Вишнёвый сад",
            "date": date(2026, 3, 15),
            "time": time(19, 0),
            "theater_name": "МХТ",
            "is_premiere": False,
            "price_min": 1000,
            "price_max": 5000,
        }]
        result = _format_raw_list(shows, "Сегодня")
        assert "Вишнёвый сад" in result
        assert "МХТ" in result
        assert "1000-5000" in result

    def test_premiere_marked(self):
        shows = [{
            "title": "Новый спектакль",
            "date": date(2026, 3, 15),
            "time": time(19, 0),
            "theater_name": "Большой",
            "is_premiere": True,
            "price_min": None,
            "price_max": None,
        }]
        result = _format_raw_list(shows, "Премьеры")
        assert "ПРЕМЬЕРА" in result

    def test_stats_included(self):
        shows = [{
            "title": "Тест",
            "date": date(2026, 3, 15),
            "time": time(19, 0),
            "theater_name": "Театр",
            "is_premiere": False,
            "price_min": None,
            "price_max": None,
        }]
        stats = {"theaters_count": 5, "shows_count": 10, "dates_count": 20}
        result = _format_raw_list(shows, "Неделя", stats=stats)
        assert "5" in result
        assert "10" in result

    def test_premieres_section(self):
        shows = [{
            "title": "Тест",
            "date": date(2026, 3, 15),
            "time": time(19, 0),
            "theater_name": "Театр",
            "is_premiere": False,
            "price_min": None,
            "price_max": None,
        }]
        premieres = [{"title": "Премьера1", "theater_name": "Большой"}]
        result = _format_raw_list(shows, "Неделя", premieres=premieres)
        assert "Премьера1" in result
        assert "Большой" in result


class TestBuildDigest:
    """Тесты build_digest с моками."""

    @pytest.mark.asyncio
    async def test_empty_shows_returns_message(self):
        result = await build_digest([], "Сегодня")
        assert "не найдено" in result

    @pytest.mark.asyncio
    async def test_no_api_key_returns_raw(self):
        shows = [{
            "title": "Тест",
            "date": date(2026, 3, 15),
            "time": time(19, 0),
            "theater_name": "Театр",
            "is_premiere": False,
            "price_min": None,
            "price_max": None,
        }]
        with patch("src.brain.digest_builder.config") as mock_config:
            mock_config.ANTHROPIC_API_KEY = ""
            result = await build_digest(shows, "Сегодня")
        assert "Тест" in result

    @pytest.mark.asyncio
    async def test_claude_failure_returns_raw(self):
        shows = [{
            "title": "Тест",
            "date": date(2026, 3, 15),
            "time": time(19, 0),
            "theater_name": "Театр",
            "is_premiere": False,
            "price_min": None,
            "price_max": None,
        }]
        with patch("src.brain.digest_builder.config") as mock_config, \
             patch("src.brain.digest_builder._call_claude", side_effect=Exception("API Error")):
            mock_config.ANTHROPIC_API_KEY = "sk-test"
            result = await build_digest(shows, "Сегодня")
        assert "Тест" in result
