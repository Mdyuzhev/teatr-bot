"""
Тесты для telegram_sender.py.
"""
from src.reports.telegram_sender import _split_text


class TestSplitText:
    """Тесты разбиения текста на чанки."""

    def test_short_text_no_split(self):
        result = _split_text("hello", 100)
        assert result == ["hello"]

    def test_split_on_newline(self):
        text = "line1\nline2\nline3\nline4"
        result = _split_text(text, 12)
        assert len(result) >= 2
        assert "line1" in result[0]

    def test_no_newline_splits_at_limit(self):
        text = "a" * 100
        result = _split_text(text, 30)
        assert len(result) >= 3
        for chunk in result:
            assert len(chunk) <= 30

    def test_exact_size(self):
        text = "12345"
        result = _split_text(text, 5)
        assert result == ["12345"]
