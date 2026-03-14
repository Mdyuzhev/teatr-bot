# Инструкция для агента — Театральный бот Москвы

> Этот файл читается один раз при первом запуске. После выполнения всех шагов
> дальнейшая работа ведётся через команды `/init` и `/task`.

---

## Кто ты и что делаешь

Ты — автономный агент-разработчик. Твоя задача: реализовать Telegram-бота,
который собирает афишу московских театров и формирует дайджест по запросу.

Проект называется **teatr-bot**. Он живёт в папке `E:/teatr` на машине
разработчика и деплоится на сервер `192.168.1.74` по пути
`/home/flomaster/teatr-bot`.

На этом же сервере уже работает другой бот (`moex-bot`) — не трогай его файлы.

---

## Шаг 1 — Прочитай контекст проекта

Прежде чем делать что-либо ещё, прочитай главный файл контекста:

```
.claude/CLAUDE.md
```

Там описана архитектура, стек, источники данных, структура БД, список команд
бота и критические ограничения. Это твоя конституция — возвращайся к ней
в начале каждой новой сессии.

---

## Шаг 2 — Зарегистрируй проект в agent-context

Выполни команду `/register` — она прописывает проект `E:/teatr` в реестр
MCP-сервера `agent-context`, чтобы между сессиями сохранялась память о
проделанной работе. Команда идемпотентна: если уже зарегистрирован — ничего
не изменится.

```bash
# Команда описана подробно в .claude/commands/register.md
```

---

## Шаг 3 — Создай GitHub-репозиторий

Репозиторий должен называться `teatr-bot` под аккаунтом `Mdyuzhev`.
Выполни инициализацию локально и первый push:

```bash
cd E:/teatr
git init
git add .
git commit -m "[INIT] Инициализация проекта teatr-bot"
git branch -M main
git remote add origin https://github.com/Mdyuzhev/teatr-bot.git
git push -u origin main
```

После этого защити ветку `main` в настройках репозитория на GitHub
(Settings → Branches → Add rule → требовать Pull Request).

---

## Шаг 4 — Скопируй проект на сервер

Создай папку на сервере и перенеси туда все файлы через MCP:

```bash
python scripts/mcp_call.py run_shell_command \
  '{"command": "mkdir -p /home/flomaster/teatr-bot/logs"}'

# Затем выполни git clone с сервера (после того как репо создано на GitHub):
python scripts/mcp_call.py run_shell_command \
  '{"command": "cd /home/flomaster && git clone https://github.com/Mdyuzhev/teatr-bot.git"}'
```

---

## Шаг 5 — Создай .env на сервере

Файл `.env` не хранится в git (он в `.gitignore`). Создай его на сервере
на основе `.env.example`. Тебе нужны реальные значения:

- `POSTGRES_PASSWORD` — придумай надёжный пароль для нового контейнера
- `ANTHROPIC_API_KEY` — тот же ключ что используется в moex-боте
  (найди его в `/home/flomaster/moex-bot/.env`)
- `TELEGRAM_BOT_TOKEN` — **новый** токен от @BotFather (не используй токен
  moex-бота — это два разных бота)
- `TELEGRAM_CHAT_ID` — твой chat_id (тот же что в moex-боте)

```bash
# Проверить ANTHROPIC_API_KEY и TELEGRAM_CHAT_ID из moex-бота:
python scripts/mcp_call.py run_shell_command \
  '{"command": "grep -E \"ANTHROPIC|CHAT_ID\" /home/flomaster/moex-bot/.env"}'
```

---

## Шаг 6 — Подними PostgreSQL-контейнер

База данных для teatr-бота живёт в **отдельном контейнере** на порту `5435`
(moex-postgres занимает `5434` — конфликта нет).

```bash
python scripts/mcp_call.py run_shell_command \
  '{"command": "cd /home/flomaster/teatr-bot/docker/postgres && docker-compose up -d"}'

# Проверить статус через 15 секунд:
python scripts/mcp_call.py run_shell_command \
  '{"command": "docker ps --filter name=teatr-postgres --format \"{{.Names}} {{.Status}}\""}'
```

Ожидаемый результат: `teatr-postgres Up X seconds (healthy)`.

---

## Шаг 7 — Установи зависимости на сервере

```bash
python scripts/mcp_call.py run_shell_command \
  '{"command": "cd /home/flomaster/teatr-bot && pip3 install -r requirements.txt --break-system-packages"}'
```

---

## Шаг 8 — Выполни первую задачу

Теперь инфраструктура готова. Прочитай задачу:

```
Tasks/backlog/T001-db-kudago-collector.md
```

Задача описывает что нужно реализовать, какой должен быть маппинг полей
KudaGo API, какие тесты написать и по каким критериям считать задачу
выполненной. Работай строго по этому файлу.

Общий ритм работы над каждой задачей такой: читаешь файл задачи →
составляешь план → реализуешь шаг за шагом → прогоняешь тесты →
деплоишь на сервер через MCP → обновляешь `CLAUDE.md` (меняешь ⬜ на ✅) →
перемещаешь файл задачи из `Tasks/backlog/` в `Tasks/done/` → делаешь
Pull Request в `main`.

---

## Как работать дальше (после первого запуска)

В начале каждой новой сессии выполняй `/init` — это откроет сессию в
agent-context, покажет состояние сервера и напомнит что было в прошлый раз.

Затем `/start` — для полной актуализации: читает `CLAUDE.md`, проверяет
очередь задач, логи, состояние БД.

Когда готов работать — `/task T001` (или следующий номер из backlog).

---

## Ключевые правила, которые нельзя нарушать

Все ограничения подробно описаны в `CLAUDE.md`, но вот самые важные:

**Claude API** вызывается только из `src/brain/digest_builder.py`. Ни коллекторы, ни модули БД не должны обращаться к Anthropic API — это нарушило бы принцип детерминизма в критическом пути.

**KudaGo** запрашивается не чаще одного раза в 6 часов. Данные кэшируются в БД — именно поэтому у нас вообще есть PostgreSQL, а не просто прямые запросы к API.

**Docker-образы** не строятся локально на сервере — там 24 ГБ RAM и риск OOM. Используй только готовые образы из DockerHub (`postgres:16-alpine`).

**ORM не используется** — только raw SQL через asyncpg, как в moex-боте.

**Порт 5435** для PostgreSQL — не менять, чтобы не конфликтовать с moex-postgres на 5434.

---

*Удачи. Дорожная карта — в `Tasks/ROADMAP.md`. Начинай с T001.*
