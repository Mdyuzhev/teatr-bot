# T005 — Персонализация: Избранное и Интересное

**Статус**: ✅ DONE
**Приоритет**: высокий — core UX-функция, удерживает пользователей
**Зависимости**: T001 ✅, T002 ✅, T003 ✅, T004 ✅
**Оценка**: ~1 рабочий день

---

## Цель

Добавить два уровня персонализации:

- **Избранное** (`favorite`) — театры, за которыми пользователь следит.
  Уведомление когда в театре появляются новые показы.

- **Интересное** (`watchlist`) — конкретные спектакли, которые пользователь
  хочет посмотреть когда-нибудь. Уведомление когда появляются новые даты
  или остаются последние показы сезона.

Оба механизма хранятся в одной таблице `user_preferences` и управляются
через inline-кнопки прямо в карточке спектакля.

Плюс к этому — обновить закреплённую панель (ReplyKeyboard) на двухрядный
layout с кнопкой «⚙️ Настройки», которая открывает управление избранным
и вишлистом.

---

## 1. Схема БД

### Новая таблица `user_preferences`

```sql
CREATE TABLE IF NOT EXISTS user_preferences (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,          -- Telegram user_id
    type        VARCHAR(20) NOT NULL,     -- 'favorite' | 'watchlist'
    ref_id      INTEGER NOT NULL,         -- theater.id или show.id
    ref_type    VARCHAR(20) NOT NULL,     -- 'theater' | 'show'
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, type, ref_id, ref_type)
);

CREATE INDEX IF NOT EXISTS idx_user_prefs_user_id ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_prefs_type    ON user_preferences(type, ref_id, ref_type);
```

Почему одна таблица: в будущем можно добавить `type = 'blocked'`
(скрыть театр из дайджеста) тем же механизмом без изменения схемы.

### Таблица `notification_log` (антиспам)

```sql
CREATE TABLE IF NOT EXISTS notification_log (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    type        VARCHAR(50) NOT NULL,   -- 'new_date' | 'last_chance' | 'new_at_favorite'
    ref_id      INTEGER NOT NULL,       -- show_date.id
    sent_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, type, ref_id)
);
```

### Миграция

Создать файл `docker/postgres/init/002_personalization.sql` с обеими таблицами
и применить на сервере:

```bash
python scripts/mcp_call.py exec_in_container \
  '{"container": "teatr-postgres", "command": "psql -U teatr_user -d teatr_bot -f /docker-entrypoint-initdb.d/002_personalization.sql"}'
```

---

## 2. src/db/queries/preferences.py

```python
async def toggle_preference(pool, user_id, type_, ref_id, ref_type) -> bool:
    """Добавить если нет, удалить если есть. Возвращает True = сейчас активно."""

async def has_preference(pool, user_id, type_, ref_id, ref_type) -> bool:
    """Проверить наличие записи."""

async def get_user_favorites(pool, user_id) -> list[dict]:
    """Список избранных театров с количеством предстоящих показов."""

async def get_user_watchlist(pool, user_id) -> list[dict]:
    """Список интересных спектаклей с ближайшими датами.
    Выделять ⚠️ если осталось ≤ 2 будущих показа."""

async def get_watchlist_users_for_show(pool, show_id) -> list[int]:
    """Все user_id у которых этот спектакль в вишлисте. Для уведомлений."""

async def get_favorite_users_for_theater(pool, theater_id) -> list[int]:
    """Все user_id у которых этот театр в избранном. Для уведомлений."""
```

---

## 3. Обновить формат карточки спектакля

Каждый спектакль в выдаче бота должен отображаться карточкой с тремя
inline-кнопками снизу:

```
🎭 Вишнёвый сад
МХТ им. Чехова · Основная сцена
📅 Сб 22 марта, 19:00
💰 от 1 500 ₽  |  12+

[ 🎟 Билеты ]  [ ⭐ В избранное ]  [ 🔖 Интересно ]
```

### Toggle-логика

**«⭐ В избранное»** — сохраняет `theater_id` (подписка на весь театр).
После нажатия кнопка меняется на `«✅ Сохранён»` через `edit_message_reply_markup`.
Повторное нажатие — удаляет, возвращает исходный вид.

**«🔖 Интересно»** — сохраняет `show_id` (следим за конкретной постановкой).
После нажатия меняется на `«📌 В списке»`.
Повторное нажатие — удаляет.

При рендере карточки проверять `has_preference()` и сразу отображать
актуальный статус кнопок.

### Callback data формат

```
fav:theater:{theater_id}   — toggle избранного театра
wl:show:{show_id}          — toggle вишлиста спектакля
```

### Навигация при нескольких спектаклях

```
← 2 / 7 →        [ 📋 Показать все списком ]
```

---

## 4. Обновить закреплённую панель (ReplyKeyboard)

```
[ 🎭 Сегодня ]     [ 📅 Выходные ]
[ 📆 Вся неделя ]  [ 🌟 Премьеры ]
[ 🏛 Театры ]      [ ⚙️ Настройки ]
```

«⚙️ Настройки» открывает inline-меню:

```
⚙️ Настройки
──────────────────────────────
[ ⭐ Мои избранные театры (3) ]
[ 🔖 Моё интересное (4)       ]
[ 🔔 Уведомления: ВКЛ         ]
```

---

## 5. Новые команды

### /favorites

```
⭐ Ваши избранные театры (3)

🏛 МХТ им. Чехова
   7 показов в апреле  [ ❌ Удалить ]

🏛 Театр Вахтангова
   3 показа в апреле   [ ❌ Удалить ]

🏛 Ленком
   нет ближайших дат   [ ❌ Удалить ]
```

### /watchlist

```
🔖 Ваш список интересного (4)

🎭 Вишнёвый сад · МХТ
   Ближайший: Сб 22 марта, 19:00  [ 🎟 ] [ ❌ ]

🎭 Гамлет · Ленком
   ⚠️ Последний показ: 30 марта   [ 🎟 ] [ ❌ ]

🎭 Три сестры · МХАТ
   Дат нет — следим               [ ❌ ]
```

`⚠️ Последний показ` — выводить если в БД осталось ≤ 2 будущих даты.

---

## 6. Уведомления (новый job в планировщике)

Добавить `notifications_job` в `scheduler/jobs.py` — запуск **ежедневно
в 09:00 МСК** после обновления данных.

```python
async def notifications_job():
    # 1. Новые показы в избранных театрах
    #    show_dates.created_at за последние 24 часа
    #    → get_favorite_users_for_theater(theater_id)
    #    → отправить: «В МХТ им. Чехова появились новые даты — Вишнёвый сад, 15 апреля»

    # 2. Новые даты для спектаклей из вишлиста
    #    show_dates.created_at за последние 24 часа
    #    → get_watchlist_users_for_show(show_id)
    #    → отправить: «Появилась новая дата: Вишнёвый сад — Сб 5 апреля, 19:00»

    # 3. «Последний шанс» — осталось ровно 2 будущих даты
    #    → get_watchlist_users_for_show(show_id)
    #    → отправить: «⚠️ Последний шанс: Вишнёвый сад — осталось 2 показа в сезоне»
    #    Срабатывает ровно при 2 датах (не при 3 и не при 1) — чтобы не спамить
```

`notification_log` с UNIQUE(user_id, type, ref_id) гарантирует что одно
уведомление не уходит дважды.

---

## 7. Тесты

### tests/unit/test_preferences.py

```python
# toggle: добавить → есть → toggle → нет
# двойное добавление: UNIQUE constraint, не дубликат
# favorite и watchlist независимы для одного ref_id
```

### tests/unit/test_notifications_job.py

```python
# новая дата → правильные user_id получают уведомление
# антиспам: повторный вызов не отправляет то же уведомление (notification_log)
# last_chance: срабатывает при 2 датах, не при 3
```

---

## Критерии готовности

- [ ] Миграция `002_personalization.sql` применена на сервере
- [ ] Кнопки «⭐ В избранное» и «🔖 Интересно» работают в карточке, toggle меняет иконку
- [ ] `/favorites` и `/watchlist` показывают актуальные списки
- [ ] Закреплённая панель обновлена на двухрядный layout с «⚙️ Настройки»
- [ ] `notifications_job` запускается в 09:00 и рассылает уведомления
- [ ] `notification_log` защищает от повторных уведомлений
- [ ] `pytest tests/ -v` — все тесты зелёные
- [ ] CLAUDE.md обновлён: T005 ✅
