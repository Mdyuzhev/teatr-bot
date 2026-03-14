Показать логи бота.

- `/logs` — последние 50 строк
- `/logs errors` — только ошибки
- `/logs pg` — логи PostgreSQL

Через нативные MCP-инструменты:

### По умолчанию
`mcp__homelab__run_shell_command` — `tail -50 /home/flomaster/teatr-bot/logs/bot.log 2>/dev/null || tail -50 /home/flomaster/teatr-bot/logs/stdout.log 2>/dev/null`

### errors
`mcp__homelab__run_shell_command` — `grep -i "error\|warning\|traceback" /home/flomaster/teatr-bot/logs/bot.log 2>/dev/null | tail -30`

### pg
`mcp__homelab__get_service_logs` (service: teatr-postgres, lines: 30)
