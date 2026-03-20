Запуск тестов на сервере.

Через нативные MCP-инструменты:

`mcp__homelab__run_shell_command` (timeout_seconds: 120) — `cd /home/YOUR_SSH_USER/teatr-bot && . venv/bin/activate && python -m pytest tests/ -v --tb=long 2>&1`

Если есть падения — покажи причину, зафиксируй в отчёте.

Формат:
```
Театральный бот — Тесты
═══════════════════════
X passed / X failed
Падения: [список]
```
