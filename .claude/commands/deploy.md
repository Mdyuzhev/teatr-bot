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
mcp__homelab__run_shell_command: cd /home/flomaster/teatr-bot && git pull origin main
```

## Шаг 3: Перезапуск бота

```
# Убить все процессы бота
mcp__homelab__run_shell_command: pkill -9 -f "python.*src.main" 2>/dev/null; sleep 2

# Запустить заново
mcp__homelab__run_shell_command: cd /home/flomaster/teatr-bot && nohup venv/bin/python -m src.main > /tmp/teatr-bot.log 2>&1 & echo "PID: $!"

# Подождать и проверить лог
mcp__homelab__run_shell_command: sleep 3 && tail -5 /tmp/teatr-bot.log
```

Бот должен показать:
- "Запуск театрального бота"
- "Бот запущен, ожидаю команды..."
- "Планировщик: KudaGo 06:00..."

Если в логе ошибка — сообщить пользователю, НЕ продолжать.

## Шаг 4: Тесты на сервере

```
mcp__homelab__run_shell_command: cd /home/flomaster/teatr-bot && venv/bin/python -m pytest tests/ -v
```

## Шаг 5: Отчёт

```
══════════════════════════════
  Деплой — $DATE
══════════════════════════════
Коммит:  [hash] [message]
Pull:    ✅ / ❌
Бот:     ✅ PID XXXX / ❌ [ошибка]
Тесты:   XX passed, XX failed
══════════════════════════════
```

## ВАЖНО

- **НЕ** использовать GitHub Actions, CI/CD пайплайны — их нет
- **НЕ** использовать `gh run` — нет CI
- Деплой ТОЛЬКО через MCP shell-команды на сервер
- Бот запускается через `venv/bin/python -m src.main`
- Путь на сервере: `/home/flomaster/teatr-bot`
