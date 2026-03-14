# Театральный бот Москвы — Контекст для агента

> Версия: 1.0 | Создано: 14 марта 2026
> T001 ✅ T002 ✅ T003 ⬜ T004 ⬜

---

## О проекте

Telegram-бот, который собирает афишу московских театров из открытых источников (KudaGo API, RSS, Culture.ru), хранит в PostgreSQL и по запросу пользователя формирует дайджест спектаклей за выбранный период. Claude используется для генерации текстового дайджеста — умной сводки с выделением премьер, последних показов и рекомендаций.

**Ключевой принцип**: данные о спектаклях собираются детерминированно (Python + API). Claude участвует только в финальной генерации дайджеста — не в логике сбора и фильтрации.

---

## Текущее состояние

### Что реализовано

| Файл | Статус | Примечание |
|------|--------|------------|
| `.claude/CLAUDE.md` | ✅ готов | Этот файл |
| `.env.example` | ✅ готов | Все переменные окружения |
| `requirements.txt` | ✅ готов | Зависимости проекта |
| `Tasks/ROADMAP.md` | ✅ готов | Дорожная карта |

### Что ещё не реализовано

| Задача | Статус | Описание |
|--------|--------|----------|
| T001 | ✅ DONE | PostgreSQL схема + KudaGo-коллектор |
| T002 | ✅ DONE | Telegram-бот + дайджест через Claude + планировщик |
| T003 | ⬜ TODO | RSS-слой + обогащение контекста |
| T004 | ⬜ TODO | Тесты + деплой |

---

## Архитектура

### Стек

```
Python 3.11
asyncpg>=0.29.0          — асинхронный PostgreSQL
apscheduler>=3.10.4      — планировщик ежедневного сбора
python-telegram-bot>=20.7
requests>=2.31.0         — KudaGo API, Culture.ru
feedparser>=6.0.10       — RSS новостей театров
python-dotenv>=1.0.0
loguru>=0.7.0            — структурированное логирование
anthropic>=0.40.0        — только для digest_builder.py
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

### Модули

```
teatr-bot/
├── src/
│   ├── config.py               — настройки, валидация при старте
│   ├── main.py                 — планировщик, graceful shutdown
│   ├── collectors/
│   │   ├── kudago.py           — основной источник (KudaGo API)
│   │   ├── rss_feeds.py        — RSS крупных театров
│   │   └── culture_ru.py       — Culture.ru API (гос. театры)
│   ├── db/
│   │   ├── connection.py       — asyncpg pool
│   │   └── queries/
│   │       ├── shows.py        — CRUD для спектаклей
│   │       ├── theaters.py     — CRUD для театров
│   │       └── reports.py      — SQL для дайджестов
│   ├── brain/
│   │   └── digest_builder.py   — Claude-powered дайджест
│   ├── reports/
│   │   ├── telegram_sender.py  — отправка сообщений
│   │   └── telegram_commands.py — команды бота
│   └── watchdog/
│       └── health.py           — circuit breaker для API
├── docker/postgres/
│   ├── docker-compose.yml
│   └── init/001_create_tables.sql
├── tests/
│   ├── unit/
│   └── integration/
└── scripts/
    └── mcp_call.py             — утилита вызова MCP-сервера
```

---

## Источники данных

### KudaGo API (главный)
- URL: `https://kudago.com/public-api/v1.4/events/`
- Параметры: `location=msk&categories=theater&expand=place,dates`
- Авторизация: не требуется
- Пагинация: `?offset=0&page_size=100`
- Обновление: 1 раз в сутки в 06:00 МСК
- Покрытие: ~80% московской театральной афиши

### RSS крупных театров (контекст)
- Большой театр: `https://www.bolshoi.ru/rss/`
- МХТ им. Чехова: `https://mxat.ru/rss/`
- Театр Вахтангова: `https://www.vakhtangov.ru/rss/news`
- Ленком: `https://lenkom.ru/rss`
- Современник: `https://sovremennik.ru/rss`
- Цель: новости о премьерах, гастролях, назначениях — обогащение дайджеста

### Culture.ru (дополнение)
- URL: `https://culture.ru/api/2.0/events`
- Параметры: `city=moskva&category=theater`
- Цель: государственные и муниципальные театры, которых нет в KudaGo

---

## Структура БД

### Таблицы

```sql
theaters          — театры (id, name, address, metro, url, source)
shows             — спектакли (id, theater_id, title, genre, age_rating, description, source_id)
show_dates        — даты показов (id, show_id, date, time, price_min, price_max, stage, url)
rss_news          — новости из RSS (id, theater_id, title, summary, published_at, url)
bot_events        — события бота (id, level, message, created_at)
```

---

## Telegram-команды

| Команда | Описание |
|---------|----------|
| `/digest` | Дайджест с выбором периода (inline-кнопки) |
| `/today` | Спектакли сегодня |
| `/weekend` | Спектакли на ближайшие выходные |
| `/week` | Спектакли на текущую неделю |
| `/theater [название]` | Афиша конкретного театра |
| `/premieres` | Только премьеры за 30 дней |
| `/status` | Статус бота и БД |
| `/refresh` | Принудительный сбор данных |

---

## Расписание работы (МСК)

| Время | Действие |
|-------|----------|
| 06:00 | Сбор данных KudaGo на 30 дней вперёд |
| 06:30 | Сбор RSS новостей театров |
| 07:00 | Проверка устаревших/отменённых событий |
| По запросу | Генерация дайджеста через Claude |

---

## Инфраструктура

### Сервер
- **Хост**: `192.168.1.74` (flomaster@192.168.1.74)
- **Tailscale**: `100.81.243.12`
- **ОС**: Ubuntu 24.04
- **Путь проекта**: `/home/flomaster/teatr-bot`

### PostgreSQL (отдельный контейнер)
- **Контейнер**: `teatr-postgres`
- **Порт**: `5435` (не конфликтует с moex-postgres на 5434)
- **База**: `teatr_bot` / **User**: `teatr_user`

### MCP-сервер
- URL: `http://192.168.1.74:8765/sse`
- Утилита: `scripts/mcp_call.py`

---

## Важные архитектурные решения (НЕ менять без обсуждения)

**1. Только один КудаГо запрос в сутки.** Не перегружать API — собирать ночью, кэшировать в БД.

**2. Claude только для дайджеста.** Вся логика выборки (по дате, по театру, по жанру) — Python/SQL. Claude получает уже отфильтрованный список и делает из него текст.

**3. Graceful degradation.** Если KudaGo недоступен — использовать данные из БД (пусть устаревшие на 1 день). Если Claude API недоступен — отдать raw список без дайджеста.

**4. asyncpg, raw SQL, без ORM.** Тот же подход что в moex-боте.

**5. Порт 5435 для PostgreSQL.** moex-postgres занимает 5434, не конфликтовать.

---

## Workflow агента

**Начало каждой задачи:**
1. Прочитать этот файл (`CLAUDE.md`)
2. Прочитать задачу из `Tasks/backlog/`
3. Изучить существующий код
4. Реализовать, написать тесты
5. Запустить `pytest tests/ -v`
6. Скопировать на сервер через MCP
7. Переместить задачу в `Tasks/done/`, обновить этот файл
8. Создать Pull Request в GitHub

**Git workflow:**
- Репозиторий: **https://github.com/Mdyuzhev/teatr-bot**
- Ветка `main` защищена
- Рабочая ветка: `feature/t00X-краткое-описание`
- Коммиты: `[T00X] краткое описание на русском`

---

## Критические ограничения

- **НЕ** строить Docker образы локально на сервере (риск OOM)
- **НЕ** вызывать Claude API из collectors/ или db/ — только из brain/
- **НЕ** использовать ORM — только raw SQL через asyncpg
- **НЕ** запрашивать KudaGo чаще 1 раза в 6 часов (rate limiting)
- **НЕ** хранить персональные данные пользователей Telegram
