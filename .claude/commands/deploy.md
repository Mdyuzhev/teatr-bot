# /deploy — Деплой бота на сервер

Полный пайплайн деплоя. Выполняй строго по шагам.

## Шаг 1: Коммит и пуш

1. `git status` — проверить что есть изменения
2. `git diff` — посмотреть что изменилось
3. `git add` — добавить нужные файлы (НЕ git add -A)
4. `git commit` — с осмысленным сообщением на русском
5. `git push origin main` — запушить

Если изменений нет — пропустить шаг.

## Шаг 2: Pull на сервере

```
mcp__homelab__run_shell_command: cd /home/YOUR_SSH_USER/teatr-bot && git pull origin main
```

## Шаг 3: Пересборка и рестарт (Docker)

```
# Пересобрать образ бота после изменений кода
mcp__homelab__run_shell_command: cd /home/YOUR_SSH_USER/teatr-bot && docker compose -f docker/docker-compose.yml build teatr-bot

# Перезапустить только бота (БД не трогаем)
mcp__homelab__run_shell_command: docker compose -f /home/YOUR_SSH_USER/teatr-bot/docker/docker-compose.yml up -d --no-deps teatr-bot

# Статус контейнеров
mcp__homelab__run_shell_command: docker ps --filter name=teatr --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Бот должен показать в логах:
- "Запуск театрального бота"
- "Бот запущен, ожидаю команды..."
- "Планировщик: KudaGo 06:00..."

Если в логе ошибка — сообщить пользователю, НЕ продолжать.

## Шаг 4: Проверка логов

```
mcp__homelab__run_shell_command: docker logs teatr-bot --tail=30
```

## Шаг 5: Отчёт

```
══════════════════════════════
  Деплой — $DATE
══════════════════════════════
Коммит:      [hash] [message]
Pull:        ✅ / ❌
Контейнеры:  ✅ teatr-bot + teatr-postgres / ❌ [ошибка]
Логи:        OK / traceback
══════════════════════════════
```

## ВАЖНО

- **НЕ** использовать GitHub Actions, CI/CD пайплайны — их нет
- **НЕ** использовать `gh run` — нет CI
- Деплой ТОЛЬКО через MCP shell-команды на сервер
- Бот запускается через Docker: `docker compose -f docker/docker-compose.yml up -d`
- Путь на сервере: `/home/YOUR_SSH_USER/teatr-bot`
