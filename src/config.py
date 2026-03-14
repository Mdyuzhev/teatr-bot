"""
Конфигурация театрального бота.
Читает переменные окружения из .env, валидирует при старте.
"""
import os
from pathlib import Path
from dotenv import load_dotenv


# Загружаем .env из корня проекта
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


class Config:
    """Настройки проекта из переменных окружения."""

    # PostgreSQL
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5435"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "teatr_bot")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "teatr_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")

    # Anthropic (только для digest_builder.py)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # KudaGo
    KUDAGO_DAYS_AHEAD: int = int(os.getenv("KUDAGO_DAYS_AHEAD", "30"))
    KUDAGO_PAGE_SIZE: int = int(os.getenv("KUDAGO_PAGE_SIZE", "100"))
    COLLECTION_HOUR: int = int(os.getenv("COLLECTION_HOUR", "6"))

    # Дайджест
    MAX_DIGEST_SHOWS: int = int(os.getenv("MAX_DIGEST_SHOWS", "20"))
    DIGEST_MAX_TOKENS: int = int(os.getenv("DIGEST_MAX_TOKENS", "1500"))

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def validate(self) -> list[str]:
        """Проверить обязательные переменные. Возвращает список ошибок."""
        errors = []
        required = {
            "POSTGRES_PASSWORD": self.POSTGRES_PASSWORD,
            "TELEGRAM_BOT_TOKEN": self.TELEGRAM_BOT_TOKEN,
            "TELEGRAM_CHAT_ID": self.TELEGRAM_CHAT_ID,
        }
        for name, value in required.items():
            if not value:
                errors.append(f"Не задана переменная {name}")
        return errors


config = Config()
