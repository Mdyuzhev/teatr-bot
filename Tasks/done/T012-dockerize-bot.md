# T012 — Контейнеризация бота: Dockerfile + docker-compose

**Статус**: TODO
**Приоритет**: высокий — необходимо для стабильного деплоя и передачи проекта
**Зависимости**: T001 ✅ T002 ✅
**Оценка**: ~1 рабочий день

---

## Цель

Упаковать Python-приложение бота в Docker-контейнер с явно заданным именем
`teatr-bot`. Объединить бота и PostgreSQL в один `docker-compose.yml` на
уровне проекта, чтобы весь стек поднимался одной командой:
`docker compose -f docker/docker-compose.yml up -d`.

Сейчас бот запускается как голый `python -m src.main` в venv на сервере —
это хрупко: зависит от версии Python, пакетов, переменных окружения.
Контейнер решает всё это разом.

---

## 1. Dockerfile — образ бота

Создать `Dockerfile` в корне проекта:

```dockerfile
# ── Стадия 1: сборка зависимостей ─────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app

# gcc нужен для компиляции asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Отдельный слой для requirements — кэшируется пока файл не меняется
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Стадия 2: финальный образ (без build-tools) ────────────────────
FROM python:3.11-slim

WORKDIR /app

# Копируем только установленные пакеты — без gcc и компиляторов
COPY --from=deps /usr/local/lib/python3.11/site-packages \
                 /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Исходный код
COPY src/ ./src/
COPY scripts/ ./scripts/

# Директория для логов (volume монтируется снаружи)
RUN mkdir -p /app/logs

# Не запускаем под root
RUN useradd -m -u 1000 teatr && chown -R teatr:teatr /app
USER teatr

CMD ["python", "-m", "src.main"]
```

---

## 2. .dockerignore — что НЕ копировать в образ

Создать `.dockerignore` в корне проекта.

**ВАЖНО**: `requirements.txt` должен присутствовать в образе на стадии `deps`
(`COPY requirements.txt .`), поэтому его нельзя исключать из `.dockerignore`.

```dockerignore
# Секреты — никогда не должны попасть в образ
.env
.env.*

# Служебные директории — не нужны в runtime
.git/
.claude/
.pytest_cache/
tests/
Tasks/
.mcp.json*
start-claude.bat

# Кэш Python
__pycache__/
*.pyc
*.pyo

# Docker-файлы (не нужны внутри контейнера)
docker/
Dockerfile

# Документация
*.md

# НЕ исключаем requirements.txt — Dockerfile делает COPY requirements.txt . на стадии deps
```

---

## 3. Разобраться с volume перед созданием нового compose-файла

Это самый критичный пункт. При запуске PostgreSQL из `docker/postgres/docker-compose.yml`
Docker автоматически добавляет префикс из имени директории к именам volumes.
Если запуск был из папки `postgres`, volume называется `postgres_teatr_pg_data`.
Если из другой папки — имя будет другим.

**Шаг 1** — выяснить точное имя существующего volume на сервере:

```bash
# Через MCP:
mcp__homelab__run_shell_command: docker volume ls --filter name=teatr
```

Ожидаемый вывод вида: `local   postgres_teatr_pg_data` (или другой префикс).

**Шаг 2** — в новом `docker-compose.yml` объявить этот volume как `external`
с точным именем, чтобы не создавать новый пустой:

```yaml
volumes:
  teatr_pg_data:
    external: true
    name: postgres_teatr_pg_data   # ← точное имя из шага 1, подставить реальное
```

Если имя окажется другим — подставить его. Принцип: `external: true` + `name`
говорит Docker «не создавай новый volume, используй вот этот существующий».

**Шаг 3** — в секции сервиса `teatr-postgres` ссылаться на этот volume:

```yaml
volumes:
  - teatr_pg_data:/var/lib/postgresql/data
```

---

## 4. docker-compose.yml — единый файл стека

Создать `docker/docker-compose.yml`:

```yaml
# version: убран — deprecated в современном Docker Compose V2

services:

  # ── Telegram-бот ──────────────────────────────────────────────────
  teatr-bot:
    build:
      context: ../
      dockerfile: Dockerfile
    image: teatr-bot:latest
    container_name: teatr-bot        # фиксированное имя, не рандомное
    restart: unless-stopped
    env_file:
      - ../.env
    environment:
      TZ: Europe/Moscow
      # POSTGRES_HOST не задаём здесь — читается из .env или дефолт из config.py
    volumes:
      - ../logs:/app/logs
    depends_on:
      teatr-postgres:
        condition: service_healthy   # ждём healthcheck PostgreSQL
    networks:
      - teatr-network
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  # ── PostgreSQL ────────────────────────────────────────────────────
  teatr-postgres:
    image: postgres:16-alpine
    container_name: teatr-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: teatr_bot
      POSTGRES_USER: teatr_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8"
      TZ: Europe/Moscow
    ports:
      - "5435:5432"
    volumes:
      - teatr_pg_data:/var/lib/postgresql/data
      - ./postgres/init:/docker-entrypoint-initdb.d
      - ./postgres/postgresql.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U teatr_user -d teatr_bot"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - teatr-network
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

networks:
  teatr-network:
    name: teatr-network              # фиксированное имя сети

volumes:
  teatr_pg_data:
    external: true
    name: REPLACE_WITH_REAL_VOLUME_NAME   # ← заменить по результату шага 3
```

---

## 5. Решить проблему прокси для Anthropic API

Бот использует `ANTHROPIC_PROXY=http://localhost:8888` (vpn-proxy контейнер
на сервере). Внутри Docker-контейнера `localhost` — это сам контейнер,
а не хост-машина. Без решения этой проблемы все вызовы Claude API
(дайджесты, рецензии) перестанут работать после перехода на Docker.

Есть три варианта. Нужно выяснить на сервере через MCP как именно
называется и подключён контейнер `vpn-proxy`:

```bash
mcp__homelab__run_shell_command: docker ps --filter name=vpn-proxy
mcp__homelab__run_shell_command: docker inspect vpn-proxy | grep -A5 Networks
```

**Вариант А** (рекомендуется если vpn-proxy — отдельный контейнер):
Подключить `teatr-bot` и `vpn-proxy` к одной сети и обращаться по имени:

```yaml
# В docker-compose.yml добавить внешнюю сеть:
networks:
  teatr-network:
    name: teatr-network
  vpn-network:
    external: true
    name: РЕАЛЬНОЕ_ИМЯ_СЕТИ_VPN_PROXY   # узнать из docker inspect

# В сервисе teatr-bot добавить сеть:
services:
  teatr-bot:
    networks:
      - teatr-network
      - vpn-network
```

В `.env` изменить:
```
ANTHROPIC_PROXY=http://vpn-proxy:8888
```

**Вариант Б** (если vpn-proxy работает как системный сервис, не контейнер):
Использовать `host-gateway` — специальный DNS-псевдоним который Docker
разрешает в IP хост-машины:

```yaml
services:
  teatr-bot:
    extra_hosts:
      - "host-gateway:host-gateway"
```

В `.env`:
```
ANTHROPIC_PROXY=http://host-gateway:8888
```

**Вариант В** (самый простой, но менее изолированный):
Запускать бота в `network_mode: host` — контейнер разделяет сетевой
стек с хостом, `localhost` становится хостом:

```yaml
services:
  teatr-bot:
    network_mode: host   # нельзя одновременно с networks: teatr-network
```

Тогда бот достучится до `localhost:8888` как обычно. Минус — потеря
сетевой изоляции контейнера и несовместимость с `depends_on` по healthcheck
(нужно будет добавить `healthcheck` retry в самом боте).

Выбрать вариант по результату `docker inspect vpn-proxy` и зафиксировать
в CLAUDE.md как работает прокси на этом сервере.

---

## 6. Обновить `.env` на сервере

При переходе на Docker нужно убедиться что `.env` на сервере содержит
правильный `POSTGRES_HOST`. Сейчас там вероятно `localhost` — это сломает
подключение к БД изнутри контейнера:

```bash
# Проверить текущее значение:
mcp__homelab__run_shell_command: grep POSTGRES_HOST /home/YOUR_SSH_USER/teatr-bot/.env
```

Если `POSTGRES_HOST=localhost` или `POSTGRES_HOST=192.168.1.74` — заменить на:
```
POSTGRES_HOST=teatr-postgres
```

Внутри Docker-сети `teatr-network` контейнеры видят друг друга по именам
сервисов из compose-файла. Имя сервиса PostgreSQL — `teatr-postgres`.

---

## 7. Обновить `src/config.py` — дефолт для POSTGRES_HOST

```python
# Было: localhost — не работает внутри Docker
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")

# Стало: teatr-postgres — имя сервиса в docker-compose
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "teatr-postgres")
```

---

## 8. Обновить `.env.example`

```bash
# При запуске через docker compose — имя сервиса в compose-файле
# При локальном запуске без Docker — IP сервера
POSTGRES_HOST=teatr-postgres

# URL MCP-сервера для скриптов
MCP_SERVER_URL=http://YOUR_SERVER_IP:8765

# Прокси для Anthropic API (опционально)
# Внутри Docker: http://vpn-proxy:8888 или http://host-gateway:8888
# Без Docker:    http://localhost:8888
ANTHROPIC_PROXY=
```

---

## 9. Обновить `.claude/commands/deploy.md`

Заменить venv-команды на Docker:

```markdown
## Шаг 3: Пересборка и рестарт

# Узнать имя volume (только при первом деплое)
mcp__homelab__run_shell_command: docker volume ls --filter name=teatr

# Пересобрать образ бота после изменений кода
mcp__homelab__run_shell_command:
  cd /home/YOUR_SSH_USER/teatr-bot && docker compose -f docker/docker-compose.yml build teatr-bot

# Перезапустить только бота (БД не трогаем)
mcp__homelab__run_shell_command:
  docker compose -f /home/YOUR_SSH_USER/teatr-bot/docker/docker-compose.yml up -d --no-deps teatr-bot

# Статус контейнеров
mcp__homelab__run_shell_command:
  docker ps --filter name=teatr --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Логи бота
mcp__homelab__run_shell_command: docker logs teatr-bot --tail=30 -f
```

---

## 10. Порядок первого деплоя на сервере

Выполнять строго по порядку — каждый шаг зависит от результата предыдущего.

```bash
# Шаг 1: узнать точное имя существующего volume
docker volume ls --filter name=teatr
# Записать имя, подставить в docker-compose.yml в секцию volumes.external.name

# Шаг 2: узнать сеть/имя vpn-proxy и выбрать вариант прокси (А/Б/В)
docker inspect vpn-proxy | grep -A5 Networks

# Шаг 3: обновить .env на сервере
# - POSTGRES_HOST=teatr-postgres
# - ANTHROPIC_PROXY=<выбранный вариант>

# Шаг 4: остановить старый способ запуска
pkill -f "python -m src.main" || true

# Шаг 5: остановить старый PostgreSQL-контейнер (запущенный из postgres/docker-compose.yml)
cd /home/YOUR_SSH_USER/teatr-bot/docker/postgres && docker compose down
# ВАЖНО: volume НЕ удаляется при down (только при down -v)

# Шаг 6: поднять новый стек
cd /home/YOUR_SSH_USER/teatr-bot
docker compose -f docker/docker-compose.yml up -d

# Шаг 7: проверить что оба контейнера healthy
docker ps --filter name=teatr

# Шаг 8: проверить логи бота
docker logs teatr-bot --tail=50
# Ожидать: "Бот запущен, ожидаю команды..."

# Шаг 9: проверить что данные на месте (БД не пустая)
docker exec teatr-postgres psql -U teatr_user -d teatr_bot \
  -c "SELECT count(*) FROM theaters;"
```

---

## Тесты

Новых unit-тестов не добавляем — это инфраструктура. Проверка — живая:
бот запустился, подключился к БД, отвечает на `/status`, дайджест
генерируется (проверяет прокси).

---

## Критерии готовности

- [ ] `Dockerfile` создан, `requirements.txt` НЕ в `.dockerignore`
- [ ] `docker build -t teatr-bot:test .` проходит без ошибок
- [ ] Точное имя существующего volume выяснено и прописано в compose как `external`
- [ ] Выбран и настроен вариант прокси (А/Б/В), дайджесты работают
- [ ] `docker compose -f docker/docker-compose.yml up -d` поднимает оба контейнера
- [ ] `docker ps` показывает `teatr-bot` и `teatr-postgres` со статусом `healthy`
- [ ] `docker logs teatr-bot` — нет traceback, есть `Бот запущен`
- [ ] `docker exec teatr-postgres psql ... -c "SELECT count(*) FROM theaters"` — данные на месте
- [ ] Команда `/status` в Telegram отвечает корректно
- [ ] `src/config.py` — дефолт `POSTGRES_HOST=teatr-postgres`
- [ ] `.env` на сервере обновлён (POSTGRES_HOST, ANTHROPIC_PROXY)
- [ ] `.claude/commands/deploy.md` обновлён на Docker-команды
- [ ] CLAUDE.md обновлён: T012 ✅, секция деплоя переписана
