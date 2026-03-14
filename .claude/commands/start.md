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

## Шаг 4: Состояние сервера (через MCP)
```bash
python scripts/mcp_call.py run_shell_command '{"command": "pgrep -f src.main && echo BOT:running || echo BOT:stopped"}'
python scripts/mcp_call.py run_shell_command '{"command": "docker ps --filter name=teatr-postgres --format \"{{.Names}} {{.Status}}\""}'
```

## Шаг 5: Логи бота
```bash
python scripts/mcp_call.py run_shell_command '{"command": "tail -30 /home/flomaster/teatr-bot/logs/stdout.log 2>/dev/null"}'
```

## Шаг 6: БД
```bash
python scripts/mcp_call.py exec_in_container '{"container": "teatr-postgres", "command": "psql -U teatr_user -d teatr_bot -c \"SELECT (SELECT count(*) FROM theaters) as theaters, (SELECT count(*) FROM shows) as shows, (SELECT count(*) FROM show_dates WHERE date >= CURRENT_DATE) as upcoming;\""}'
```

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
