Перезапустить бота на сервере.

1. Остановить:
```bash
python scripts/mcp_call.py run_shell_command '{"command": "pgrep -f src.main | xargs kill 2>/dev/null; sleep 2; echo stopped"}'
```

2. Запустить:
```bash
python scripts/mcp_call.py run_shell_command '{"command": "cd /home/flomaster/teatr-bot && nohup python3 -m src.main > logs/stdout.log 2>&1 & echo PID=$!"}'
```

3. Проверить (через 5 сек):
```bash
python scripts/mcp_call.py run_shell_command '{"command": "tail -10 /home/flomaster/teatr-bot/logs/stdout.log"}'
```

Убедиться: нет traceback, pool создан, планировщик запущен.
