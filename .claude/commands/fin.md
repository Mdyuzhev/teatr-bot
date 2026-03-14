# /fin — Фиксация контекста и завершение сессии

Выполни все шаги последовательно. Это команда завершения рабочей сессии.

## Шаг 1: Git — зафиксировать незакоммиченные изменения
```bash
git status
git diff --stat
```
Если есть незакоммиченные изменения — предложи коммит с описанием. Если нет — пропусти.

## Шаг 2: Синхронизация с сервером
Через нативные MCP-инструменты (НЕ через mcp_call.py):
1. `mcp__homelab__run_shell_command` — `cd /home/flomaster/teatr-bot && git fetch origin && git reset --hard origin/main`
2. `mcp__homelab__run_shell_command` — `cd /home/flomaster/teatr-bot && . venv/bin/activate && pip install -r requirements.txt 2>&1 | tail -5`

## Шаг 3: Тесты на сервере
`mcp__homelab__run_shell_command` — `cd /home/flomaster/teatr-bot && . venv/bin/activate && python -m pytest tests/ -v 2>&1`

## Шаг 4: Состояние бота и БД
1. `mcp__homelab__run_shell_command` — `pgrep -fa "src.main" || echo "BOT:stopped"`
2. `mcp__homelab__exec_in_container` (teatr-postgres) — `psql -U teatr_user -d teatr_bot -c "SELECT (SELECT count(*) FROM theaters) as theaters, (SELECT count(*) FROM shows) as shows, (SELECT count(*) FROM show_dates WHERE date >= CURRENT_DATE) as upcoming;"`

## Шаг 5: Сохранение контекста в память
Обнови или создай файл `C:/Users/Михаил/.claude/projects/e--teatr/memory/project_session_log.md` с:
- Дата сессии
- Что было сделано (коммиты)
- Текущий статус задач (T001-T004)
- Открытые проблемы / блокеры
- Что делать в следующей сессии

## Шаг 6: Обновить CLAUDE.md
Обнови статусы задач в `.claude/CLAUDE.md` если они изменились за сессию.

## Шаг 7: Итоговый отчёт
```
══════════════════════════════════════════
  Сессия завершена — $DATE
══════════════════════════════════════════
Git:          ветка / последний коммит / push статус
Сервер:       код синхронизирован / нет
Тесты:       X passed / X failed / X skipped
Бот:          running (PID) / stopped
БД:           X театров / X спектаклей / X предстоящих
Задачи:       T001 ✅ T002 ✅ T003 ⬜ T004 ⬜
Следующее:    [что делать дальше]
══════════════════════════════════════════
```
