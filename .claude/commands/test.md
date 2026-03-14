Запуск тестов на сервере.

```bash
python scripts/mcp_call.py run_shell_command '{"command": "cd /home/flomaster/teatr-bot && python3 -m pytest tests/ -v --tb=long 2>&1", "timeout_seconds": 120}'
```

Если есть падения — покажи причину, зафиксируй в отчёте.

Формат:
```
Театральный бот — Тесты
═══════════════════════
X passed / X failed
Падения: [список]
```
