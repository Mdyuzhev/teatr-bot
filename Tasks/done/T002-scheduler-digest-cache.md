# T002 — Планировщик + генерация дайджестов по расписанию

**Статус**: TODO
**Зависит от**: T001 (БД + KudaGo-коллектор)
**Оценка**: ~1 рабочий день

---

## Цель

Реализовать планировщик задач и логику генерации дайджестов через Haiku.
Главный принцип: LLM вызывается ТОЛЬКО планировщиком (07:00 МСК),
результат хранится в таблице `digests`. Telegram-команды читают из кэша.

---

## Архитектура потока данных

```
[APScheduler 06:00] → kudago.collect() → show_dates в БД
[APScheduler 07:00] → generate_digests_job():
    для каждого из ['today','tomorrow','weekend','week']:
        1. get_shows_by_period(pool, date_from, date_to)   ← SQL запрос
        2. digest_builder.build(shows, period_label)        ← вызов Haiku
        3. save_digest(pool, period_key, ...)               ← INSERT/UPDATE в digests

[Пользователь /today] → get_fresh_digest(pool, 'today', ...) ← SELECT из digests
                       → отправить content в Telegram
```

---

## Что нужно реализовать

### 1. src/db/queries/digests.py

Три функции (заглушки уже созданы, нужно реализовать):

```python
async def get_fresh_digest(pool, period_key, date_from, date_to) -> dict | None:
    """
    SELECT * FROM digests
    WHERE period_key=$1 AND date_from=$2 AND date_to=$3
      AND expires_at > NOW()
    LIMIT 1
    Вернуть None если нет актуального кэша.
    """

async def save_digest(pool, period_key, date_from, date_to,
                      content, shows_count, model) -> None:
    """
    INSERT INTO digests (period_key, date_from, date_to, content,
                         shows_count, model, expires_at)
    VALUES ($1,$2,$3,$4,$5,$6, NOW() + INTERVAL '24 hours')
    ON CONFLICT (period_key, date_from, date_to)
    DO UPDATE SET content=EXCLUDED.content,
                  shows_count=EXCLUDED.shows_count,
                  model=EXCLUDED.model,
                  generated_at=NOW(),
                  expires_at=NOW() + INTERVAL '24 hours'
    """

async def get_all_digests_status(pool) -> list[dict]:
    """
    SELECT period_key, date_from, date_to, shows_count,
           generated_at, expires_at,
           CASE WHEN expires_at > NOW() THEN 'fresh' ELSE 'stale' END as status
    FROM digests ORDER BY generated_at DESC
    """
```

### 2. src/brain/digest_builder.py

Класс `DigestBuilder`:

```python
class DigestBuilder:
    def __init__(self, config: Config):
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.model = "claude-haiku-4-5-20251001"
        self.max_tokens = 1500

    async def build(self, shows: list[dict], period_label: str) -> str:
        """
        Принимает список спектаклей из БД, возвращает готовый текст для Telegram.

        Формат shows[i]:
          {'title': str, 'theater': str, 'date': date, 'time': time,
           'genre': str, 'age_rating': str, 'price_min': int, 'price_max': int,
           'is_premiere': bool, 'stage': str}

        Graceful degradation: если Anthropic API недоступен —
        вернуть raw-список в простом текстовом формате (без LLM).
        """

    def _build_prompt(self, shows: list[dict], period_label: str) -> str:
        """
        Системный промпт + пользовательский запрос для Haiku.

        Системный промпт:
          Ты — редактор театральной афиши Москвы. Составь лаконичный
          дайджест спектаклей для Telegram. Используй HTML-разметку
          (<b>, <i>, эмодзи). Выдели премьеры. Укажи цены и театры.
          Не более 1500 символов.

        Пользовательский запрос:
          Период: {period_label}
          Спектаклей: {len(shows)}
          Данные: {json.dumps(shows_formatted, ensure_ascii=False)}
        """

    def _format_raw(self, shows: list[dict], period_label: str) -> str:
        """
        Fallback без LLM: простой текстовый список спектаклей.
        Используется если Anthropic API недоступен.
        """
```

### 3. src/scheduler/jobs.py

Две функции-задачи для APScheduler:

```python
async def collect_job(pool, config):
    """
    Задача 06:00: сбор данных KudaGo.
    Запускает KudaGoCollector.fetch_events() + save_to_db().
    Логирует статистику в bot_events.
    """

async def generate_digests_job(pool, config):
    """
    Задача 07:00: генерация стандартных дайджестов.

    Стандартные периоды для генерации:
      today    = date.today()
      tomorrow = date.today() + timedelta(days=1)
      weekend  = ближайшие Сб-Вс (если сегодня Сб или Вс — текущие)
      week     = Пн-Вс текущей недели

    Для каждого периода:
      1. shows = await get_shows_by_period(pool, date_from, date_to)
      2. content = await digest_builder.build(shows, label)
      3. await save_digest(pool, key, date_from, date_to, content, len(shows), model)

    Логировать: сколько дайджестов сгенерировано, сколько токенов потрачено.
    Если Haiku недоступен — сохранить raw-список, не падать.
    """
```

### 4. src/main.py

Планировщик APScheduler + запуск Telegram-бота:

```python
async def main():
    config = Config()
    pool = await get_pool(config)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(collect_job,          'cron', hour=6,  minute=0,  args=[pool, config])
    scheduler.add_job(generate_digests_job, 'cron', hour=7,  minute=0,  args=[pool, config])
    scheduler.start()

    # Запуск Telegram Application (polling)
    app = build_telegram_app(config, pool)
    await app.run_polling()
```

### 5. src/reports/telegram_commands.py

Все команды читают из кэша, не вызывают LLM:

```python
async def cmd_today(update, context):
    """Команда /today — читает из digests WHERE period_key='today'."""
    date_from = date.today()
    digest = await get_fresh_digest(pool, 'today', date_from, date_from)
    if digest:
        await update.message.reply_text(digest['content'], parse_mode='HTML')
    else:
        await update.message.reply_text(
            "⏳ Дайджест обновляется, попробуйте через несколько минут."
        )

async def cmd_digest(update, context):
    """
    Команда /digest — inline-кнопки для выбора периода.

    Кнопки: [Сегодня] [Завтра] [Выходные] [Эта неделя] [Свой период]

    При выборе 'Свой период' — бот просит ввести даты.
    Кастомный период: проверяем кэш → если нет → вызываем Haiku (единственный
    on-demand вызов LLM) → сохраняем → отправляем.
    """
```

---

## Вспомогательная логика дат

```python
def get_period_dates(period_key: str) -> tuple[date, date]:
    """
    'today'    → (today, today)
    'tomorrow' → (today+1, today+1)
    'weekend'  → (ближайшая Сб, ближайшее Вс)
    'week'     → (Пн текущей недели, Вс текущей недели)
    '2026-03-20:2026-03-25' → (date(2026,3,20), date(2026,3,25))
    """

PERIOD_LABELS = {
    'today':    'Сегодня',
    'tomorrow': 'Завтра',
    'weekend':  'Ближайшие выходные',
    'week':     'Эта неделя',
}
```

---

## Тесты

### tests/unit/test_digest_builder.py

```python
# Тест 1: build() с mock Anthropic API возвращает строку
# Тест 2: graceful degradation — если API недоступен → _format_raw()
# Тест 3: _build_prompt() корректно формирует промпт для 0, 1, N спектаклей
# Тест 4: премьеры выделяются в промпте отдельно
```

### tests/unit/test_digest_cache.py

```python
# Тест 1: get_fresh_digest → None если digest.expires_at < NOW()
# Тест 2: get_fresh_digest → dict если digest свежий
# Тест 3: save_digest → ON CONFLICT DO UPDATE (повторный вызов обновляет запись)
```

### tests/unit/test_scheduler_jobs.py

```python
# Тест 1: generate_digests_job генерирует 4 дайджеста (today/tomorrow/weekend/week)
# Тест 2: если shows пустой список → дайджест всё равно сохраняется (с текстом "нет спектаклей")
# Тест 3: get_period_dates('weekend') → корректные даты для любого дня недели
```

---

## Критерии готовности

- [ ] `generate_digests_job()` генерирует 4 дайджеста и сохраняет в БД
- [ ] `/today` в Telegram читает из `digests`, не вызывает LLM
- [ ] `/refresh` принудительно перезапускает `generate_digests_job()`
- [ ] При недоступном Haiku — в `digests` сохраняется raw-список, бот не падает
- [ ] `pytest tests/ -v` — все тесты зелёные
- [ ] Логи планировщика: видно время генерации и количество токенов
- [ ] CLAUDE.md обновлён: T002 ✅
