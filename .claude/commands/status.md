Показать состояние проекта и бота.

```bash
python scripts/mcp_call.py run_shell_command '{"command": "pgrep -f src.main && echo BOT:running || echo BOT:stopped"}'
python scripts/mcp_call.py run_shell_command '{"command": "docker ps --filter name=teatr-postgres --format \"{{.Names}} {{.Status}}\""}'
python scripts/mcp_call.py run_shell_command '{"command": "tail -10 /home/flomaster/teatr-bot/logs/stdout.log 2>/dev/null"}'
python scripts/mcp_call.py exec_in_container '{"container": "teatr-postgres", "command": "psql -U teatr_user -d teatr_bot -c \"SELECT (SELECT count(*) FROM theaters) as theaters, (SELECT count(*) FROM shows) as shows, (SELECT count(*) FROM show_dates WHERE date >= CURRENT_DATE) as upcoming;\""}'
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
