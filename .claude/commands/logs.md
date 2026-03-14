Показать логи бота.

- `/logs` — последние 50 строк
- `/logs errors` — только ошибки
- `/logs pg` — логи PostgreSQL

### По умолчанию
```bash
python scripts/mcp_call.py run_shell_command '{"command": "tail -50 /home/flomaster/teatr-bot/logs/stdout.log"}'
```

### errors
```bash
python scripts/mcp_call.py run_shell_command '{"command": "grep -i \"error\\|warning\\|traceback\" /home/flomaster/teatr-bot/logs/stdout.log | tail -30"}'
```

### pg
```bash
python scripts/mcp_call.py run_shell_command '{"command": "docker logs teatr-postgres --tail=30 2>&1"}'
```
