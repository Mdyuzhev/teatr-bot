Показать состояние проекта и бота.

Через нативные MCP-инструменты:

1. `mcp__homelab__run_shell_command` — `pgrep -fa "src.main" || echo "BOT:stopped"`
2. `mcp__homelab__run_shell_command` — `docker ps --filter name=teatr-postgres --format "{{.Names}} {{.Status}}"`
3. `mcp__homelab__run_shell_command` — `tail -10 /home/flomaster/teatr-bot/logs/bot.log 2>/dev/null || tail -10 /home/flomaster/teatr-bot/logs/stdout.log 2>/dev/null`
4. `mcp__homelab__exec_in_container` (teatr-postgres) — `psql -U teatr_user -d teatr_bot -c "SELECT (SELECT count(*) FROM theaters) as theaters, (SELECT count(*) FROM shows) as shows, (SELECT count(*) FROM show_dates WHERE date >= CURRENT_DATE) as upcoming;"`

Также локально:
```bash
git status --short
git log --oneline -5
for f in Tasks/backlog/*.md; do head -3 "$f"; done
```

Формат:
```
Театральный бот — Status
═══════════════════════════════════
Бот:         running / stopped
PostgreSQL:  healthy / down
Git:         ветка (clean/dirty)
Данные:      X театров / X спектаклей / X предстоящих показов
Последний лог: ...
Задачи:      X в очереди
═══════════════════════════════════
```
