"""
Unit-тесты для KudaGoCollector.
Все тесты используют моки — реальных HTTP-запросов нет.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestKudaGoCollector:
    """Тесты парсинга и сохранения данных KudaGo."""

    def test_parse_theater_from_event(self, kudago_event_fixture):
        """Проверяем что поля театра правильно извлекаются из event['place']."""
        # TODO T001: раскомментировать после реализации KudaGoCollector
        # from src.collectors.kudago import KudaGoCollector
        # collector = KudaGoCollector(config=MagicMock())
        # theater = collector._parse_theater(kudago_event_fixture['place'])
        # assert theater['name'] == "МХТ им. Чехова"
        # assert theater['slug'] == "mkhat-chekhova"
        # assert theater['metro'] == "Охотный Ряд"
        pass

    def test_parse_show_from_event(self, kudago_event_fixture):
        """Проверяем что поля спектакля правильно извлекаются из event."""
        # TODO T001: раскомментировать после реализации KudaGoCollector
        # from src.collectors.kudago import KudaGoCollector
        # collector = KudaGoCollector(config=MagicMock())
        # show = collector._parse_show(kudago_event_fixture)
        # assert show['title'] == "Вишнёвый сад"
        # assert show['slug'] == "vishnyovyi-sad-mkhat"
        # assert show['age_rating'] == "12+"
        # assert show['is_premiere'] is False
        pass

    def test_premiere_detected_from_tags(self, kudago_premiere_fixture):
        """Спектакль с тегом 'premera' должен иметь is_premiere=True."""
        # TODO T001: раскомментировать после реализации KudaGoCollector
        # from src.collectors.kudago import KudaGoCollector
        # collector = KudaGoCollector(config=MagicMock())
        # show = collector._parse_show(kudago_premiere_fixture)
        # assert show['is_premiere'] is True
        pass

    @pytest.mark.parametrize("price_str,expected_min,expected_max", [
        ("1000-5000 руб", 1000, 5000),
        ("от 500 руб",    500,  None),
        ("бесплатно",     0,    0),
        ("",              None, None),
        ("300",           300,  None),
    ])
    def test_parse_price(self, price_str, expected_min, expected_max):
        """Парсинг строки цены в числовые min/max."""
        # TODO T001: раскомментировать после реализации KudaGoCollector
        # from src.collectors.kudago import KudaGoCollector
        # collector = KudaGoCollector(config=MagicMock())
        # price_min, price_max = collector._parse_price(price_str)
        # assert price_min == expected_min
        # assert price_max == expected_max
        pass

    def test_graceful_degradation_on_api_failure(self):
        """При недоступности API должен вернуть пустой список, не упасть."""
        # TODO T001: раскомментировать после реализации KudaGoCollector
        # from src.collectors.kudago import KudaGoCollector
        # collector = KudaGoCollector(config=MagicMock())
        # with patch('requests.get', side_effect=ConnectionError("timeout")):
        #     result = collector.fetch_events(days_ahead=7)
        # assert result == []
        pass
