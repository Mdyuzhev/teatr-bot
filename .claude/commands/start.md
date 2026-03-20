# /start — Полная актуализация контекста

Выполни все шаги последовательно. Не меняй код. Только читай и отчитывайся.

## Шаг 1: Контекст проекта
Прочитай `.claude/CLAUDE.md`. Запомни архитектуру, стек, источники данных, ограничения.

## Шаг 2: Очередь задач
```bash
for f in Tasks/backlog/*.md; do echo "=== $f ==="; head -5 "$f"; done
```

## Шаг 3: Git состояние
```bash
git status
git log --oneline -10
```

## Шаг 4: Состояние сервера
Через нативные MCP-инструменты:
1. `mcp__homelab__run_shell_command` — `pgrep -fa "src.main" || echo "BOT:stopped"`
2. `mcp__homelab__run_shell_command` — `docker ps --filter name=teatr-postgres --format "{{.Names}} {{.Status}}"`

## Шаг 5: Логи бота
`mcp__homelab__run_shell_command` — `tail -30 /home/YOUR_SSH_USER/teatr-bot/logs/bot.log 2>/dev/null || tail -30 /home/YOUR_SSH_USER/teatr-bot/logs/stdout.log 2>/dev/null || echo "Логи не найдены"`

## Шаг 6: БД
`mcp__homelab__exec_in_container` (teatr-postgres) — `psql -U teatr_user -d teatr_bot -c "SELECT (SELECT count(*) FROM theaters) as theaters, (SELECT count(*) FROM shows) as shows, (SELECT count(*) FROM show_dates WHERE date >= CURRENT_DATE) as upcoming;"`

## Итоговый отчёт
```
Театральный бот — актуальный статус
════════════════════════════════════════
Git:         ветка / последний коммит
Бот:         running / stopped (PID)
PostgreSQL:  healthy / down
Данные:      X театров / X спектаклей / X предстоящих показов
Задачи:      X в очереди
Готов к работе. Следующая задача: [ID]
════════════════════════════════════════
```
