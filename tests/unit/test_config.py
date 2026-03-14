"""
Тесты конфигурации.
"""
import pytest


class TestConfigDsn:
    """Проверка формирования DSN строки."""

    def test_dsn_format(self):
        from src.config import Config
        c = Config()
        c.POSTGRES_HOST = "localhost"
        c.POSTGRES_PORT = 5435
        c.POSTGRES_DB = "testdb"
        c.POSTGRES_USER = "testuser"
        c.POSTGRES_PASSWORD = "secret"
        assert c.dsn == "postgresql://testuser:secret@localhost:5435/testdb"

    def test_dsn_special_chars_in_password(self):
        from src.config import Config
        c = Config()
        c.POSTGRES_PASSWORD = "p@ss:word"
        c.POSTGRES_HOST = "host"
        c.POSTGRES_PORT = 5435
        c.POSTGRES_DB = "db"
        c.POSTGRES_USER = "user"
        assert "p@ss:word" in c.dsn


class TestConfigValidation:
    """Проверка валидации обязательных полей."""

    def test_all_set_no_errors(self):
        from src.config import Config
        c = Config()
        c.POSTGRES_PASSWORD = "secret"
        c.TELEGRAM_BOT_TOKEN = "123:abc"
        c.TELEGRAM_CHAT_ID = "-100123"
        errors = c.validate()
        assert errors == []

    def test_missing_password(self):
        from src.config import Config
        c = Config()
        c.POSTGRES_PASSWORD = ""
        c.TELEGRAM_BOT_TOKEN = "123:abc"
        c.TELEGRAM_CHAT_ID = "-100123"
        errors = c.validate()
        assert any("POSTGRES_PASSWORD" in e for e in errors)

    def test_missing_bot_token(self):
        from src.config import Config
        c = Config()
        c.POSTGRES_PASSWORD = "secret"
        c.TELEGRAM_BOT_TOKEN = ""
        c.TELEGRAM_CHAT_ID = "-100123"
        errors = c.validate()
        assert any("TELEGRAM_BOT_TOKEN" in e for e in errors)

    def test_missing_chat_id(self):
        from src.config import Config
        c = Config()
        c.POSTGRES_PASSWORD = "secret"
        c.TELEGRAM_BOT_TOKEN = "123:abc"
        c.TELEGRAM_CHAT_ID = ""
        errors = c.validate()
        assert any("TELEGRAM_CHAT_ID" in e for e in errors)

    def test_all_missing(self):
        from src.config import Config
        c = Config()
        c.POSTGRES_PASSWORD = ""
        c.TELEGRAM_BOT_TOKEN = ""
        c.TELEGRAM_CHAT_ID = ""
        errors = c.validate()
        assert len(errors) == 3


class TestConfigDefaults:
    """Проверка значений по умолчанию."""

    def test_default_days_ahead(self):
        from src.config import Config
        c = Config()
        assert c.KUDAGO_DAYS_AHEAD == 30

    def test_default_page_size(self):
        from src.config import Config
        c = Config()
        assert c.KUDAGO_PAGE_SIZE == 100

    def test_default_collection_hour(self):
        from src.config import Config
        c = Config()
        assert c.COLLECTION_HOUR == 6

    def test_default_max_digest_shows(self):
        from src.config import Config
        c = Config()
        assert c.MAX_DIGEST_SHOWS == 20
