# Команда /register — зарегистрировать проект в agent-context

Выполни следующий Bash-скрипт чтобы добавить проект teatr в реестр agent-context.
Скрипт идемпотентный — если запись уже есть, ничего не изменится.

```bash
node -e "
const fs = require('fs');
const path = process.env.HOME + '/.agent-context/registry.json';

let registry = {};
try {
  registry = JSON.parse(fs.readFileSync(path, 'utf8'));
} catch (e) {
  console.log('registry.json не найден, создаём новый');
}

if (!registry.projects) registry.projects = {};

const key = 'E:/teatr';
if (registry.projects[key]) {
  console.log('Проект уже зарегистрирован:', registry.projects[key]);
} else {
  registry.projects[key] = {
    name: 'teatr',
    description: 'Telegram-бот московской театральной афиши. Python 3.11, PostgreSQL, KudaGo API, RSS, Claude-дайджест.'
  };
  fs.writeFileSync(path, JSON.stringify(registry, null, 2), 'utf8');
  console.log('✅ Проект teatr зарегистрирован в agent-context');
}
"
```

После выполнения убедись что вывод содержит `✅ Проект teatr зарегистрирован`
или сообщение что запись уже существует. Ошибок быть не должно.
