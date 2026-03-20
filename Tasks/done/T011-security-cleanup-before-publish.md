# T011 — Очистка проекта от личных данных перед публикацией

**Статус**: TODO
**Приоритет**: КРИТИЧЕСКИЙ — выполнить до передачи ссылки на репозиторий коллегам
**Зависимости**: нет (не требует выполненных предыдущих задач)
**Оценка**: ~2-3 часа

---

## Контекст

Проект готовится к передаче коллегам. Аудит выявил файлы с личными данными
и данными инфраструктуры, которые не должны попасть в публичный репозиторий.

---

## Проблемы и что делать с каждой

### 1. `.mcp.json` — реальный IP сервера → добавить в .gitignore

Файл содержит `192.168.1.74:8765` и `127.0.0.1:8766`.
Это конфигурация локальной инфраструктуры, не часть кода проекта.

**Действие**: добавить `.mcp.json` в `.gitignore`. Рядом создать `.mcp.json.example`:

```json
{
  "mcpServers": {
    "homelab": {
      "type": "http",
      "url": "http://YOUR_SERVER_IP:8765/mcp"
    },
    "agent-context": {
      "type": "http",
      "url": "http://127.0.0.1:8766/mcp"
    }
  }
}
```

---

### 2. `.claude/settings.json` — реальный IP, Tailscale, username, пути

Файл содержит:
- `"host": "192.168.1.74"` — локальный IP сервера
- `"tailscale_host": "100.81.243.12"` — Tailscale-адрес
- `"ssh_user": "flomaster"` — имя пользователя
- `"project_path": "/home/flomaster/teatr-bot"` — путь на сервере
- `"mcp_server": "http://192.168.1.74:8765"` — IP в task_workflow

**Действие**: заменить все конкретные значения на плейсхолдеры. Итоговый файл:

```json
{
  "permissions": { ... },
  "autonomy": { ... },
  "server": {
    "host": "YOUR_SERVER_IP",
    "tailscale_host": "YOUR_TAILSCALE_IP",
    "ssh_user": "YOUR_SSH_USER",
    "project_path": "/home/YOUR_SSH_USER/teatr-bot"
  },
  "database": {
    "host": "YOUR_SERVER_IP",
    "port": 5435,
    "name": "teatr_bot",
    "user": "teatr_user",
    "pool_min": 2,
    "pool_max": 10,
    "driver": "asyncpg"
  },
  "task_workflow": {
    ...
    "mcp_server": "http://YOUR_SERVER_IP:8765"
  }
}
```

---

### 3. `.claude/CLAUDE.md` — реальный IP и пути в секции «Инфраструктура»

Секция «Инфраструктура» содержит `192.168.1.74`, `100.81.243.12`,
`flomaster`, `/home/flomaster/teatr-bot`.

**Действие**: заменить на плейсхолдеры в тех же местах:

```markdown
### Сервер
- **Хост**: `YOUR_SERVER_IP` (YOUR_SSH_USER@YOUR_SERVER_IP)
- **Tailscale**: `YOUR_TAILSCALE_IP`
- **ОС**: Ubuntu 24.04
- **Путь проекта**: `/home/YOUR_SSH_USER/teatr-bot`
```

---

### 4. `.claude/proxy-setup.md` — детали VPN-прокси → добавить в .gitignore

Файл раскрывает детали личной инфраструктуры: IP прокси-сервера,
схему обхода геоблокировки, порт 8888. Это не часть кода проекта.

**Действие**: добавить `.claude/proxy-setup.md` в `.gitignore`.

---

### 5. `.claude/commands/register.md` — путь C:/Users/Михаил/

Файл содержит `C:/Users/Михаил/.agent-context/registry.json` — реальный
путь на машине разработчика с именем пользователя.

**Действие**: заменить на плейсхолдер:

```javascript
const path = 'C:/Users/YOUR_WINDOWS_USER/.agent-context/registry.json';
```

---

### 6. `.claude/commands/` — пути `/home/flomaster/` во всех файлах

Файлы `start.md`, `status.md`, `restart.md`, `deploy.md`, `logs.md` содержат
`/home/flomaster/teatr-bot` и другие конкретные пути.

**Действие**: заменить `flomaster` на `YOUR_SSH_USER` во всех вхождениях.

Команда для поиска всех вхождений:
```bash
grep -r "flomaster" .claude/commands/
```

---

### 7. `scripts/mcp_call.py` — захардкоженный IP

```python
MCP_SERVER = "http://192.168.1.74:8765"
```

**Действие**: читать из переменной окружения с fallback-значением:

```python
import os

MCP_SERVER = os.getenv("MCP_SERVER_URL", "http://localhost:8765")
```

Добавить `MCP_SERVER_URL` в `.env.example`:
```
MCP_SERVER_URL=http://YOUR_SERVER_IP:8765
```

---

### 8. `.env` — заменить реальный API ключ на плейсхолдер

Файл `.env` в `.gitignore` и не попадёт в репозиторий, но хорошая
практика — хранить в нём только плейсхолдер, а реальный ключ вводить
каждый раз руками или через менеджер секретов.

**Действие**: заменить значение `ANTHROPIC_API_KEY`:

```
ANTHROPIC_API_KEY=sk-ant-...  # вставить реальный ключ
```

---

### 9. Проверить git-историю на случайно закоммиченные секреты

```bash
# Искать паттерны API ключей в истории
git log --all --full-history --oneline -- .env
git log --all -p --follow -- .env | grep -i "sk-ant"

# Искать IP в истории
git log --all -p | grep "192.168.1" | head -20
```

Если `.env` когда-либо был в коммите — нужно удалить его из истории
через `git filter-branch` или BFG Repo Cleaner (и затем force-push).

---

### 10. Обновить `.gitignore` — добавить все найденные файлы

Итоговый `.gitignore` должен содержать:

```gitignore
# Секреты и окружение
.env
*.env.local

# Личная конфигурация инфраструктуры (не часть кода)
.mcp.json
.claude/proxy-setup.md

# Прокси-лаунчер
start-claude.bat
```

---

## Проверка результата

После выполнения всех пунктов — запустить:

```bash
# Убедиться что чувствительные файлы не в git
git status
git ls-files .mcp.json .env .claude/proxy-setup.md
# Должно вернуть пустой вывод

# Убедиться что плейсхолдеры на месте
grep -r "192.168.1" .claude/ scripts/
grep -r "flomaster" .claude/ scripts/
grep -r "100.81.243" .claude/ scripts/
grep -r "Михаил" .claude/
# Все команды должны вернуть пустой вывод
```

---

## Что НЕ нужно скрывать

- GitHub username `Mdyuzhev` — публичная информация
- Репозиторий `https://github.com/Mdyuzhev/teatr-bot` — это и есть ссылка для коллег
- IP `192.168.1.74` только в `.gitignore`-d файлах (`.env`, `.mcp.json`) — окей
- Технические детали архитектуры в `CLAUDE.md` — полезны для коллег

---

## Критерии готовности

- [ ] `.mcp.json` в `.gitignore`, рядом `.mcp.json.example` с плейсхолдерами
- [ ] `.claude/settings.json` — все реальные IP, username, пути заменены на `YOUR_*`
- [ ] `.claude/CLAUDE.md` — секция «Инфраструктура» sanitized
- [ ] `.claude/proxy-setup.md` в `.gitignore`
- [ ] `.claude/commands/register.md` — путь C:/Users/Михаил/ заменён
- [ ] Все файлы в `.claude/commands/` — `flomaster` заменён на `YOUR_SSH_USER`
- [ ] `scripts/mcp_call.py` — IP читается из `os.getenv("MCP_SERVER_URL")`
- [ ] `.env.example` обновлён (добавлен `MCP_SERVER_URL`)
- [ ] Git-история проверена на секреты
- [ ] `git status` и `git ls-files` подтверждают что секретные файлы не отслеживаются
- [ ] `grep -r "192.168.1" .claude/ scripts/` возвращает пустой вывод
