"""
Unit-тесты для KudaGoCollector.
Все тесты используют моки — реальных HTTP-запросов нет.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.collectors.kudago import KudaGoCollector


@pytest.fixture
def collector():
    return KudaGoCollector(config=MagicMock())


class TestParseTheater:

    def test_parse_theater_from_event(self, collector, kudago_event_fixture):
        """Поля театра правильно извлекаются из event['place']."""
        theater = collector._parse_theater(kudago_event_fixture["place"])
        assert theater["name"] == "МХТ им. Чехова"
        assert theater["slug"] == "mkhat-chekhova"
        assert theater["metro"] == "Охотный Ряд"
        assert theater["address"] == "Камергерский пер., 3"
        assert theater["url"] == "https://mxat.ru"


class TestParseShow:

    def test_parse_show_from_event(self, collector, kudago_event_fixture):
        """Поля спектакля правильно извлекаются из event."""
        show = collector._parse_show(kudago_event_fixture)
        assert show["title"] == "Вишнёвый сад"
        assert show["slug"] == "vishnyovyi-sad-mkhat"
        assert show["age_rating"] == "12+"
        assert show["is_premiere"] is False

    def test_premiere_detected_from_tags(self, collector, kudago_premiere_fixture):
        """Спектакль с тегом 'premera' должен иметь is_premiere=True."""
        show = collector._parse_show(kudago_premiere_fixture)
        assert show["is_premiere"] is True


class TestParsePrice:

    @pytest.mark.parametrize("price_str,expected_min,expected_max", [
        ("1000-5000 руб", 1000, 5000),
        ("500 — 3500 руб", 500, 3500),
        ("от 500 руб", 500, None),
        ("бесплатно", 0, 0),
        ("", None, None),
        ("300", 300, None),
    ])
    def test_parse_price(self, collector, price_str, expected_min, expected_max):
        """Парсинг строки цены в числовые min/max."""
        price_min, price_max = collector._parse_price(price_str)
        assert price_min == expected_min
        assert price_max == expected_max


class TestGracefulDegradation:

    def test_api_failure_returns_empty(self, collector):
        """При недоступности API должен вернуть пустой список, не упасть."""
        with patch("src.collectors.kudago.requests.get", side_effect=ConnectionError("timeout")):
            result = collector.fetch_events(days_ahead=7)
        assert result == []

    def test_api_timeout_returns_empty(self, collector):
        """При таймауте API должен вернуть пустой список."""
        with patch("src.collectors.kudago.requests.get", side_effect=requests.exceptions.Timeout("timeout")):
            result = collector.fetch_events(days_ahead=7)
        assert result == []


class TestFetchEvents:

    def test_fetch_events_pagination(self, collector):
        """Проверяем что пагинация работает корректно."""
        page1 = {
            "count": 2,
            "results": [{
                "id": 1, "title": "Test", "slug": "test",
                "body_text": "", "tags": [], "age_restriction": None,
                "price": "", "place": {"id": 1, "title": "T", "slug": "t"},
                "dates": [{"start": 1742400000}],
            }],
        }
        page2 = {"count": 2, "results": []}

        with patch("src.collectors.kudago.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(side_effect=[page1, page2])
            mock_get.return_value = mock_resp

            collector.config.KUDAGO_PAGE_SIZE = 1
            result = collector.fetch_events(days_ahead=7)

        assert len(result) == 1
        assert result[0]["title"] == "Test"


# Нужен import для теста таймаута
import requests
