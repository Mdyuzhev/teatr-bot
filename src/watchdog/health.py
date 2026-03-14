"""
Circuit breaker для внешних API (KudaGo, Culture.ru).

Логика: если API недоступен более N часов — переключаться
на кэшированные данные из БД и отправлять предупреждение в Telegram.
"""
# TODO T004: реализовать HealthWatchdog
#
# Интерфейс:
#   class ApiHealth:
#     is_healthy: bool
#     last_success: datetime | None
#     failure_count: int
#
#   def record_success(source: str) -> None
#   def record_failure(source: str) -> None
#   def is_stale(source: str, max_hours: int = 24) -> bool
