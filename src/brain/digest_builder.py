"""
Генерация текстового дайджеста через Claude API.

Получает отфильтрованный список спектаклей из БД,
возвращает готовый текст для отправки в Telegram.

ВАЖНО: этот модуль — единственное место в проекте,
где разрешён вызов Anthropic API. Вся логика выборки
и фильтрации остаётся в db/queries/.
"""
# TODO T002: реализовать DigestBuilder с graceful degradation
#
# Интерфейс:
#   async def build_digest(shows: list[dict], period_label: str) -> str
#     - если Anthropic API недоступен — вернуть raw-список без AI-обработки
#     - max_tokens из конфига (DIGEST_MAX_TOKENS=1500)
