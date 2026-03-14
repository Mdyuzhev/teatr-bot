"""Тесты парсинга изображений KudaGo (T009)."""
import pytest
from src.collectors.kudago import KudaGoCollector
from src.config import config


def _make_collector():
    return KudaGoCollector(config)


def _make_event(**overrides):
    """Минимальный event для _parse_show."""
    base = {
        "title": "Чайка",
        "slug": "chaika",
        "body_text": "Описание",
        "tags": [],
        "age_restriction": "16",
    }
    base.update(overrides)
    return base


class TestParseShowImages:
    """Тесты парсинга image_url из event."""

    def test_with_640x384_thumbnail(self):
        """Предпочитаем 640x384."""
        event = _make_event(images=[{
            "thumbnail": {
                "640x384": "https://img.kudago.com/640x384.jpg",
                "144x96": "https://img.kudago.com/144x96.jpg",
            },
            "image": "https://img.kudago.com/original.jpg",
        }])
        collector = _make_collector()
        result = collector._parse_show(event)
        assert result["image_url"] == "https://img.kudago.com/640x384.jpg"

    def test_fallback_to_144x96(self):
        """Если нет 640x384, берём 144x96."""
        event = _make_event(images=[{
            "thumbnail": {
                "144x96": "https://img.kudago.com/144x96.jpg",
            },
            "image": "https://img.kudago.com/original.jpg",
        }])
        collector = _make_collector()
        result = collector._parse_show(event)
        assert result["image_url"] == "https://img.kudago.com/144x96.jpg"

    def test_fallback_to_original(self):
        """Если нет thumbnail, берём оригинал."""
        event = _make_event(images=[{
            "thumbnail": {},
            "image": "https://img.kudago.com/original.jpg",
        }])
        collector = _make_collector()
        result = collector._parse_show(event)
        assert result["image_url"] == "https://img.kudago.com/original.jpg"

    def test_no_images(self):
        """Без images → None."""
        event = _make_event(images=[])
        collector = _make_collector()
        result = collector._parse_show(event)
        assert result["image_url"] is None

    def test_images_missing(self):
        """Поле images отсутствует → None."""
        event = _make_event()
        collector = _make_collector()
        result = collector._parse_show(event)
        assert result["image_url"] is None

    def test_images_not_dict(self):
        """images[0] не dict → None."""
        event = _make_event(images=["just_a_string"])
        collector = _make_collector()
        result = collector._parse_show(event)
        assert result["image_url"] is None

    def test_no_thumbnail_key(self):
        """images[0] без thumbnail → берём image."""
        event = _make_event(images=[{
            "image": "https://img.kudago.com/original.jpg",
        }])
        collector = _make_collector()
        result = collector._parse_show(event)
        assert result["image_url"] == "https://img.kudago.com/original.jpg"
