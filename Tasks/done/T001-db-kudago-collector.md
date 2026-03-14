# T001 — PostgreSQL схема + KudaGo-коллектор

**Статус**: TODO
**Приоритет**: высокий (блокирует все остальные задачи)
**Оценка**: ~1 рабочий день

---

## Цель

Поднять PostgreSQL-контейнер, создать схему БД, написать коллектор KudaGo API,
который собирает афишу Москвы на 30 дней вперёд и сохраняет в БД.
Добавить скрипт ручного запуска и базовую конфигурацию проекта.

---

## Что нужно сделать

### 1. Docker + PostgreSQL

Файл `docker/postgres/docker-compose.yml` уже создан. Проверить и при необходимости адаптировать.
Файл `docker/postgres/init/001_create_tables.sql` уже создан — схема БД готова.

Запуск:
```bash
cd docker/postgres && docker-compose up -d
```

Проверка:
```bash
docker ps --filter name=teatr-postgres
```

### 2. src/config.py

Класс `Config` с валидацией через python-dotenv. Обязательные переменные:
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
Опциональные с defaults: `KUDAGO_DAYS_AHEAD=30`, `KUDAGO_PAGE_SIZE=100`, `COLLECTION_HOUR=6`, `MAX_DIGEST_SHOWS=20`.

### 3. src/db/connection.py

asyncpg pool (min=2, max=10). Функции `get_pool()`, `close_pool()`. По образцу moex-бота.

### 4. src/collectors/kudago.py

Класс `KudaGoCollector`:

**`fetch_events(days_ahead: int) -> list[dict]`**
- Постраничная загрузка: `GET https://kudago.com/public-api/v1.4/events/?location=msk&categories=theater&expand=place,dates&page_size=100&offset=N`
- Фильтр по дате: события у которых хотя бы одна дата попадает в диапазон [today, today+days_ahead]
- Продолжать пагинацию пока `results` не пустой
- Таймаут запроса: 30 сек, retry 3 раза с backoff

**`save_to_db(events: list[dict], pool) -> dict`**
- Возвращает `{"theaters": N, "shows": N, "dates": N}` — количество новых/обновлённых записей
- Маппинг полей KudaGo:
  ```
  event['place']['title']     → theaters.name
  event['place']['slug']      → theaters.slug  (UNIQUE KEY)
  event['place']['address']   → theaters.address
  event['place']['subway']    → theaters.metro  (поле subway в KudaGo)
  event['place']['site_url']  → theaters.url

  event['title']              → shows.title
  event['slug']               → shows.slug  (UNIQUE KEY)
  event['body_text']          → shows.description
  event['age_restriction']    → shows.age_rating  (число → строка "12+")
  'премьера' in event['tags'] → shows.is_premiere

  event['dates'][N]['start']  → show_dates.date + show_dates.time  (unix timestamp)
  event['dates'][N]['price']  → парсить "500-3500 руб" → price_min=500, price_max=3500
  ```
- INSERT theaters ON CONFLICT (slug) DO UPDATE SET name, address, metro, url, updated_at
- INSERT shows ON CONFLICT (slug) DO UPDATE SET title, description, is_premiere, updated_at
- INSERT show_dates ON CONFLICT (show_id, date, time, stage) DO NOTHING

**Graceful degradation**: если requests.get() выбрасывает исключение — логировать WARNING, вернуть пустой список, не падать.

### 5. src/db/queries/shows.py

```python
async def get_shows_by_period(pool, date_from: date, date_to: date) -> list[dict]:
    """Все показы в заданном периоде с инфой о театре."""

async def get_shows_by_theater(pool, theater_slug: str, date_from: date, date_to: date) -> list[dict]:
    """Показы конкретного театра в периоде."""

async def get_premieres(pool, days: int = 30) -> list[dict]:
    """Только спектакли с is_premiere=True в ближайшие N дней."""
```

### 6. src/db/queries/theaters.py

```python
async def get_all_theaters(pool) -> list[dict]:
    """Список всех театров с количеством предстоящих показов."""

async def get_theater_by_slug(pool, slug: str) -> dict | None:
    """Найти театр по slug."""
```

### 7. scripts/collect_now.py

```python
# Запуск: python scripts/collect_now.py
# Собирает данные и печатает статистику
```

### 8. scripts/mcp_call.py

Уже создан как заглушка — реализовать полностью (скопировать логику из moex-бота).

---

## Тесты

### tests/unit/test_kudago_collector.py

```python
# Тест 1: парсинг одного event с mock requests
# Fixture: kudago_event_fixture из conftest.py
# Проверить что theater/show/show_date правильно извлечены из fixture

# Тест 2: парсинг цены
# "500-3500 руб" → price_min=500, price_max=3500
# "от 1000 руб" → price_min=1000, price_max=None
# "" → price_min=None, price_max=None

# Тест 3: определение is_premiere
# tags=[{"slug": "premera"}] → is_premiere=True
# tags=[{"slug": "spektakl"}] → is_premiere=False

# Тест 4: graceful degradation
# requests.get() raises ConnectionError → возвращает [], не падает
```

### tests/integration/test_db_connection.py

```python
# Тест 1: подключение к БД (pytest.mark.skipif если нет POSTGRES_HOST в .env)
# Тест 2: INSERT + SELECT в show_dates, проверить UNIQUE constraint
```

---

## Критерии готовности

- [ ] `docker-compose up -d` поднимает `teatr-postgres` со статусом healthy
- [ ] `python scripts/collect_now.py` выводит статистику без ошибок
- [ ] В БД > 50 театров и > 500 предстоящих показов после первого запуска
- [ ] `pytest tests/ -v` — все тесты зелёные
- [ ] Код задеплоен на сервер через MCP (`/home/flomaster/teatr-bot`)
- [ ] CLAUDE.md обновлён: T001 ✅
