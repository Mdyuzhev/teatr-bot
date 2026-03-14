"""
Отправка сообщений в Telegram.
Обёртка над python-telegram-bot для удобного использования из других модулей.
"""
from telegram import Bot
from loguru import logger

TELEGRAM_MSG_LIMIT = 4096


async def send_message(bot: Bot, chat_id: str | int, text: str,
                       parse_mode: str = "HTML") -> None:
    """Отправить сообщение, при необходимости разбив на части."""
    if len(text) <= TELEGRAM_MSG_LIMIT:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return

    await send_message_chunks(bot, chat_id, text, parse_mode=parse_mode)


async def send_message_chunks(bot: Bot, chat_id: str | int, text: str,
                              chunk_size: int = 4000,
                              parse_mode: str = "HTML") -> None:
    """Разбить длинное сообщение на части и отправить последовательно."""
    chunks = _split_text(text, chunk_size)
    for i, chunk in enumerate(chunks, 1):
        logger.debug("Отправка части {}/{} ({} символов)", i, len(chunks), len(chunk))
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)


def _split_text(text: str, chunk_size: int) -> list[str]:
    """Разбить текст по переносам строк, не ломая HTML-теги."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break

        # Ищем последний перенос строки в пределах chunk_size
        split_pos = text.rfind("\n", 0, chunk_size)
        if split_pos == -1:
            split_pos = chunk_size

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks
