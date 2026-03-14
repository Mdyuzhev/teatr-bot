"""
Отправка сообщений в Telegram.
Обёртка над python-telegram-bot для удобного использования из других модулей.
"""
# TODO T002: реализовать TelegramSender
#
# Интерфейс:
#   async def send_message(text: str, parse_mode: str = "HTML") -> None
#   async def send_message_chunks(text: str, chunk_size: int = 4000) -> None
#     — Telegram ограничивает сообщения 4096 символами
