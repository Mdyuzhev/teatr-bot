"""Тесты для review_builder (T008)."""
import pytest
from unittest.mock import patch, MagicMock

from src.brain.review_builder import build_review, _fallback_review, _call_haiku


def _make_show(**overrides) -> dict:
    """Тестовый спектакль."""
    base = {
        "id": 1,
        "title": "Чайка",
        "slug": "chaika",
        "genre": "драма",
        "age_rating": "16+",
        "description": "Классическая пьеса Чехова о любви и искусстве.",
        "is_premiere": False,
        "theater_name": "МХАТ",
        "theater_url": "https://mhat.ru",
    }
    base.update(overrides)
    return base


class TestFallbackReview:
    """Тесты fallback-рецензии."""

    def test_basic(self):
        show = _make_show()
        result = _fallback_review(show)
        assert "Чайка" in result
        assert "МХАТ" in result
        assert "драма" in result

    def test_empty_description(self):
        show = _make_show(description=None)
        result = _fallback_review(show)
        assert "уточняйте на сайте театра" in result

    def test_premiere(self):
        show = _make_show(is_premiere=True)
        result = _fallback_review(show)
        assert "Премьера" in result

    def test_no_genre(self):
        show = _make_show(genre=None)
        result = _fallback_review(show)
        assert "Жанр" not in result


class TestBuildReview:
    """Тесты build_review."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_fallback(self):
        """Без API-ключа — возвращает fallback."""
        show = _make_show()
        with patch("src.brain.review_builder.config") as mock_config:
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.ANTHROPIC_PROXY = None
            result = await build_review(show)
        assert "Чайка" in result
        assert "МХАТ" in result

    @pytest.mark.asyncio
    async def test_api_error_returns_fallback(self):
        """При ошибке API — возвращает fallback."""
        show = _make_show()
        with patch("src.brain.review_builder.config") as mock_config, \
             patch("src.brain.review_builder._call_haiku", side_effect=Exception("API down")):
            mock_config.ANTHROPIC_API_KEY = "test-key"
            result = await build_review(show)
        assert "Чайка" in result

    @pytest.mark.asyncio
    async def test_successful_api_call(self):
        """Успешный вызов API — возвращает текст от Haiku."""
        show = _make_show()
        with patch("src.brain.review_builder.config") as mock_config, \
             patch("src.brain.review_builder._call_haiku", return_value="<b>Отличный спектакль</b>"):
            mock_config.ANTHROPIC_API_KEY = "test-key"
            result = await build_review(show)
        assert "Отличный спектакль" in result


class TestCallHaikuPrompt:
    """Тесты промпта для Haiku."""

    def test_prompt_contains_show_info(self):
        """Промпт содержит название и театр."""
        show = _make_show()
        with patch("src.brain.review_builder.config") as mock_config, \
             patch("anthropic.Anthropic") as mock_cls:
            mock_config.ANTHROPIC_API_KEY = "test-key"
            mock_config.ANTHROPIC_PROXY = None
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Рецензия")]
            mock_client.messages.create.return_value = mock_response
            result = _call_haiku(show)
            call_args = mock_client.messages.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "Чайка" in prompt
            assert "МХАТ" in prompt
            assert "драма" in prompt

    def test_premiere_in_prompt(self):
        """Премьера отмечена в промпте."""
        show = _make_show(is_premiere=True)
        with patch("src.brain.review_builder.config") as mock_config, \
             patch("anthropic.Anthropic") as mock_cls:
            mock_config.ANTHROPIC_API_KEY = "test-key"
            mock_config.ANTHROPIC_PROXY = None
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Рецензия")]
            mock_client.messages.create.return_value = mock_response
            _call_haiku(show)
            call_args = mock_client.messages.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "ПРЕМЬЕРА" in prompt
