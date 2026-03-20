Перезапустить бота на сервере.

Через нативные MCP-инструменты:

1. Остановить:
`mcp__homelab__run_shell_command` — `pgrep -f "src.main" | xargs kill 2>/dev/null; sleep 2; echo stopped`

2. Запустить:
`mcp__homelab__run_shell_command` — `cd /home/YOUR_SSH_USER/teatr-bot && . venv/bin/activate && nohup python -m src.main > logs/bot.log 2>&1 & echo PID=$!`

3. Проверить (через 3 сек):
`mcp__homelab__run_shell_command` — `sleep 3 && tail -15 /home/YOUR_SSH_USER/teatr-bot/logs/bot.log`

Убедиться: нет traceback, pool создан, планировщик запущен.
