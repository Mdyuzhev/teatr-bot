"""
Тесты главного модуля — валидация, регистрация команд.
"""
import pytest
from unittest.mock import patch


class TestMainValidation:
    """Проверка валидации конфигурации при старте."""

    def test_main_exits_on_invalid_config(self):
        """Если конфиг невалидный → SystemExit."""
        from src.main import main

        with patch("src.main.config") as mock_cfg:
            mock_cfg.validate.return_value = ["Не задана переменная TELEGRAM_BOT_TOKEN"]
            with pytest.raises(SystemExit):
                main()


class TestScheduledCollection:
    """Тесты плановых сборов данных."""

    @pytest.mark.asyncio
    async def test_scheduled_collection_no_events(self):
        """Сбор без событий → warning, не падает."""
        from src.main import scheduled_collection

        with patch("src.main.KudaGoCollector") as MockCollector:
            instance = MockCollector.return_value
            instance.fetch_events.return_value = []

            await scheduled_collection()

            instance.fetch_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduled_collection_exception(self):
        """Исключение при сборе → логируется, не падает."""
        from src.main import scheduled_collection

        with patch("src.main.KudaGoCollector") as MockCollector:
            instance = MockCollector.return_value
            instance.fetch_events.side_effect = Exception("API down")

            # Не должно бросить исключение
            await scheduled_collection()

    @pytest.mark.asyncio
    async def test_scheduled_rss_collection_no_news(self):
        """RSS сбор без новостей → info, не падает."""
        from src.main import scheduled_rss_collection

        with patch("src.main.RssCollector") as MockCollector:
            instance = MockCollector.return_value
            instance.collect_all.return_value = []

            await scheduled_rss_collection()

            instance.collect_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduled_rss_collection_exception(self):
        """Исключение при сборе RSS → логируется, не падает."""
        from src.main import scheduled_rss_collection

        with patch("src.main.RssCollector") as MockCollector:
            instance = MockCollector.return_value
            instance.collect_all.side_effect = Exception("Network error")

            await scheduled_rss_collection()
