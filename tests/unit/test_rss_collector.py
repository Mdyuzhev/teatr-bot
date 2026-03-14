"""
Тесты RSS-коллектора.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.collectors.rss_feeds import RssCollector, _strip_html


# ── Фикстуры ──

@pytest.fixture
def rss_entry():
    """Пример записи из feedparser."""
    return {
        "title": "Премьера «Гамлета» в новой постановке",
        "link": "https://teatr-sats.ru/news/gamlet-premiera",
        "summary": "<p>В марте состоится <b>премьера</b> спектакля.</p>",
        "published_parsed": (2026, 3, 10, 12, 0, 0, 0, 69, 0),
    }


@pytest.fixture
def rss_feeds_config():
    return {
        "teatr-sats": {
            "url": "https://teatr-sats.ru/feed",
            "theater_name": "Театр им. Н.И. Сац",
        },
    }


# ── Тесты парсинга ──

class TestParseEntry:
    def test_parse_entry_basic(self, rss_entry, rss_feeds_config):
        collector = RssCollector(rss_feeds_config)
        result = collector._parse_entry(rss_entry, "teatr-sats", "Театр им. Н.И. Сац")

        assert result is not None
        assert result["title"] == "Премьера «Гамлета» в новой постановке"
        assert result["url"] == "https://teatr-sats.ru/news/gamlet-premiera"
        assert result["theater_slug"] == "teatr-sats"
        assert result["theater_name"] == "Театр им. Н.И. Сац"

    def test_parse_entry_strips_html(self, rss_entry, rss_feeds_config):
        collector = RssCollector(rss_feeds_config)
        result = collector._parse_entry(rss_entry, "teatr-sats", "Театр")

        assert "<p>" not in result["summary"]
        assert "<b>" not in result["summary"]
        assert "премьера" in result["summary"]

    def test_parse_entry_date(self, rss_entry, rss_feeds_config):
        collector = RssCollector(rss_feeds_config)
        result = collector._parse_entry(rss_entry, "teatr-sats", "Театр")

        assert result["published_at"] is not None
        assert result["published_at"].year == 2026
        assert result["published_at"].month == 3

    def test_parse_entry_no_title_returns_none(self, rss_feeds_config):
        collector = RssCollector(rss_feeds_config)
        entry = {"title": "", "link": "https://example.com"}
        result = collector._parse_entry(entry, "slug", "name")
        assert result is None

    def test_parse_entry_no_link_returns_none(self, rss_feeds_config):
        collector = RssCollector(rss_feeds_config)
        entry = {"title": "Заголовок", "link": ""}
        result = collector._parse_entry(entry, "slug", "name")
        assert result is None

    def test_parse_entry_no_date(self, rss_feeds_config):
        collector = RssCollector(rss_feeds_config)
        entry = {"title": "Заголовок", "link": "https://example.com"}
        result = collector._parse_entry(entry, "slug", "name")
        assert result is not None
        assert result["published_at"] is None


# ── Тесты strip_html ──

class TestStripHtml:
    def test_basic(self):
        assert _strip_html("<p>Текст</p>") == "Текст"

    def test_nested(self):
        assert _strip_html("<div><b>Жирный</b> текст</div>") == "Жирный текст"

    def test_no_html(self):
        assert _strip_html("Просто текст") == "Просто текст"


# ── Тесты collect_all ──

class TestCollectAll:
    @patch("src.collectors.rss_feeds.RssCollector._fetch_feed")
    def test_collect_all_success(self, mock_fetch, rss_entry, rss_feeds_config):
        mock_fetch.return_value = [rss_entry]
        collector = RssCollector(rss_feeds_config)
        result = collector.collect_all()

        assert len(result) == 1
        assert result[0]["title"] == "Премьера «Гамлета» в новой постановке"

    @patch("src.collectors.rss_feeds.RssCollector._fetch_feed")
    def test_collect_all_feed_error(self, mock_fetch, rss_feeds_config):
        """Ошибка фида — graceful degradation, пустой список."""
        mock_fetch.side_effect = Exception("Connection timeout")
        collector = RssCollector(rss_feeds_config)
        result = collector.collect_all()

        assert result == []

    @patch("src.collectors.rss_feeds.RssCollector._fetch_feed")
    def test_collect_all_empty_feed(self, mock_fetch, rss_feeds_config):
        mock_fetch.return_value = []
        collector = RssCollector(rss_feeds_config)
        result = collector.collect_all()

        assert result == []
