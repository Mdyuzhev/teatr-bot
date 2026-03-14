# T006 — UX: Карточки спектаклей, кнопки и реальные уведомления

**Статус**: ✅ DONE
**Приоритет**: критический — без этого Избранное и Интересное (T005) не работают
**Зависимости**: T001 ✅ T002 ✅ T003 ✅ T004 ✅
**Оценка**: ~1-2 рабочих дня

---

## Проблемы которые нужно исправить

### Баг 1 — Карточки с кнопками не показываются (КРИТИЧНО)

`build_show_card_keyboard()` реализована в `telegram_commands.py`, но нигде
не вызывается при выводе дайджестов. Пользователь получает один текстовый блок
без inline-кнопок — добавить в избранное/интересное невозможно.

**Нужно**: переделать вывод дайджеста — вместо одного текста отправлять
серию карточек, каждая с кнопками `[🎟 Билеты] [⭐ В избранное] [🔖 Интересно]`.

### Баг 2 — Уведомления не доставляются (КРИТИЧНО)

В `scheduler/jobs.py` функция `notifications_job(pool)` вызывает
`log_notification()` и `is_notification_sent()`, но **ни разу не вызывает**
`bot.send_message()`. Уведомления только считаются — пользователи ничего
не получают. Bot instance не передаётся в планировщик.

**Нужно**: передать `bot` в `notifications_job` и добавить реальную отправку.

### Отсутствующий функционал

- Навигация `← 2/7 →` между карточками при многих спектаклях
- Свободный текстовый поиск (пользователь пишет «Дядя Ваня» — бот ищет)
- Группировка театров: ⭐ Мои избранные / 🔥 Популярные / 📍 По метро
- `🎲 Случайный спектакль`

---

## 1. Переделать вывод дайджеста — карточки вместо текста

### Новая функция `send_shows_as_cards()` в `telegram_sender.py`

```python
async def send_shows_as_cards(
    bot,
    chat_id: int,
    shows: list[dict],
    period_label: str,
    digest_text: str,          # текст от Claude — шапка дайджеста
    user_id: int | None = None,
    pool=None,
    page_size: int = 5,        # карточек на страницу
    page: int = 0,
) -> None:
    """
    Отправить дайджест как серию карточек с inline-кнопками.

    Схема:
    1. Первое сообщение — шапка от Claude (без кнопок)
    2. Далее по page_size карточек спектаклей с кнопками
    3. Последнее сообщение — навигация ← страница N/M →
    """
```

### Формат одной карточки

```
🎭 <b>Вишнёвый сад</b>
МХТ им. Чехова · Основная сцена
📅 Сб 22 марта, 19:00
💰 от 1 500 ₽  |  12+

[ 🎟 Билеты ]  [ ⭐ В избранное ]  [ 🔖 Интересно ]
```

- `theater_id` и `show_id` должны быть в данных из `get_digest_data()`
  (добавить в SQL если не хватает)
- Проверять `has_preference()` при рендере и показывать актуальный статус
  кнопок (`✅ Сохранён` / `📌 В списке` если уже добавлено)
- `🎟 Билеты` — url-кнопка если есть `tickets_url`, иначе не показывать

### Навигация между страницами

Если спектаклей больше `page_size` — добавить под последней карточкой:

```
[ ← Назад ]   Страница 1 / 3   [ Вперёд → ]
[ 📋 Показать все одним текстом ]
```

Callback data:
```
page:today:1          — страница 1 периода 'today'
page:weekend:2        — страница 2 периода 'weekend'
show_all:today        — отправить весь дайджест текстом
```

### Изменения в `telegram_commands.py`

Все команды `/today`, `/weekend`, `/week`, команды через inline (digest_callback)
должны вызывать `send_shows_as_cards()` вместо `send_message()` с текстом.

Шапку (текст от Claude) отправить первым сообщением, затем карточки.

---

## 2. Починить реальную отправку уведомлений

### Передача bot в планировщик

В `main.py` в функции `post_init(application)`:

```python
bot = application.bot   # получаем bot instance

async def scheduled_notifications_wrapper():
    pool = await get_pool()
    await notifications_job(pool, bot)   # передаём bot

scheduler.add_job(scheduled_notifications_wrapper, ...)
```

### Обновить `notifications_job(pool, bot)` в `scheduler/jobs.py`

Добавить реальную отправку после `log_notification()`:

```python
from src.reports.telegram_sender import send_message

# Уведомление: новые показы в избранных театрах
msg = (
    f"⭐ <b>{theater_name}</b>\n"
    f"Новые даты: <b>{show_title}</b> — {date_str}\n"
    f"Используй /today чтобы увидеть полную афишу"
)
await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")

# Уведомление: новая дата в вишлисте
msg = (
    f"🔖 Появилась новая дата!\n"
    f"<b>{show_title}</b> · {theater_name}\n"
    f"📅 {date_str}"
)
await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")

# Уведомление: последний шанс
msg = (
    f"⚠️ <b>Последний шанс!</b>\n"
    f"<b>{show_title}</b> · {theater_name}\n"
    f"Осталось всего 2 показа в сезоне.\n"
    f"Успей купить билет!"
)
await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
```

Оборачивать каждую отправку в try/except — если пользователь заблокировал бота,
не падать, только логировать.

---

## 3. Свободный текстовый поиск

В `reply_keyboard_handler()` — если текст не совпал ни с одной кнопкой,
трактовать как поисковый запрос:

```python
async def reply_keyboard_handler(update, context):
    text = update.message.text
    handlers = { ... }  # существующие кнопки
    handler = handlers.get(text)
    if handler:
        await handler(update, context)
    elif text == "🏛 Театры":
        await _cmd_theaters_list(update, context)
    else:
        # Свободный поиск
        await _search_shows(update, context, query=text)
```

### Функция `_search_shows()`

```python
async def _search_shows(update, context, query: str) -> None:
    """Поиск спектаклей и театров по тексту запроса."""
    pool = await get_pool()
    today = date.today()
    date_to = today + timedelta(days=30)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sd.date, sd.time, sd.price_min, sd.price_max, sd.tickets_url,
                   s.id AS show_id, s.title, s.is_premiere, s.age_rating,
                   t.id AS theater_id, t.name AS theater_name, t.metro
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE sd.date BETWEEN $1 AND $2
              AND sd.is_cancelled = FALSE
              AND (
                  LOWER(s.title) LIKE $3
                  OR LOWER(t.name) LIKE $3
              )
            ORDER BY sd.date, sd.time
            LIMIT 20
            """,
            today, date_to, f"%{query.lower()}%",
        )

    if not rows:
        await send_message(context.bot, update.effective_chat.id,
                           f"По запросу «{query}» ничего не найдено.")
        return

    shows = [dict(r) for r in rows]
    await send_shows_as_cards(
        context.bot, update.effective_chat.id, shows,
        f"Поиск: {query}", f"Найдено {len(shows)} показов",
        user_id=update.effective_user.id, pool=pool,
    )
```

---

## 4. Группировка театров

Обновить `_cmd_theaters_list()` — вместо плоского списка:

```
<b>Театры</b>

⭐ Мои избранные
[ МХТ им. Чехова ]  [ Вахтангова ]

🔥 Популярные (больше всего показов)
[ Большой ]  [ Ленком ]  [ Et Cetera ]

📍 Найти по метро:
[ 🚇 Выбрать станцию ]
```

Кнопки театров → callback `theater:{slug}` → показывает карточки спектаклей театра.
Кнопка «Выбрать станцию» → бот просит написать название станции.

Популярные — TOP-6 театров по количеству предстоящих показов (SQL уже есть в `get_all_theaters`).

### Поиск по метро

```python
# callback: metro_search
# бот: «Введите название станции:»
# пользователь: «Охотный Ряд»
# бот: показывает театры WHERE metro ILIKE '%Охотный%'
```

Для хранения state («ожидаем ввод станции») использовать `context.user_data["awaiting"] = "metro_input"`.

---

## 5. 🎲 Случайный спектакль

Добавить в ReplyKeyboard или в меню «⚙️ Настройки»:

```
[ 🎲 Удивить меня ]
```

Callback / команда `/random`:

```python
async def cmd_random(update, context) -> None:
    """Случайный спектакль из ближайших 14 дней."""
    pool = await get_pool()
    today = date.today()
    date_to = today + timedelta(days=14)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT sd.date, sd.time, sd.price_min, sd.price_max, sd.tickets_url,
                   s.id AS show_id, s.title, s.is_premiere, s.age_rating,
                   t.id AS theater_id, t.name AS theater_name, t.metro
            FROM show_dates sd
            JOIN shows s ON s.id = sd.show_id
            JOIN theaters t ON t.id = s.theater_id
            WHERE sd.date BETWEEN $1 AND $2
              AND sd.is_cancelled = FALSE
            ORDER BY RANDOM()
            LIMIT 1
            """,
            today, date_to,
        )

    if not row:
        await send_message(context.bot, update.effective_chat.id,
                           "Не удалось найти спектакль.")
        return

    show = dict(row)
    await send_shows_as_cards(
        context.bot, update.effective_chat.id, [show],
        "Случайный спектакль", "🎲",
        user_id=update.effective_user.id, pool=pool,
    )
```

---

## 6. Обновить SQL в `get_digest_data()` и `get_shows_by_period()`

Убедиться что в возвращаемых строках присутствуют `show_id` и `theater_id`
(они нужны для формирования callback_data кнопок карточек).

Проверить `src/db/queries/reports.py` и `src/db/queries/shows.py` — добавить
поля если отсутствуют.

---

## 7. Тесты

### tests/unit/test_cards.py

```python
# Тест build_show_card_keyboard: возвращает корректный InlineKeyboardMarkup
# Тест: has_fav=True → кнопка «✅ Сохранён», has_fav=False → «⭐ В избранное»
# Тест: нет tickets_url → кнопки Билеты нет
```

### tests/unit/test_notifications_send.py

```python
# Тест: notifications_job вызывает bot.send_message для каждого подписчика
# Тест: повторный вызов не отправляет (notification_log)
# Тест: exception при send_message не роняет весь job
```

---

## Критерии готовности

- [ ] `/today`, `/weekend`, `/week` отдают серию карточек с кнопками,
      а не один текстовый блок
- [ ] Кнопки «⭐ В избранное» и «🔖 Интересно» работают из карточки дайджеста,
      иконка меняется после нажатия
- [ ] При > 5 спектаклей появляется навигация `← 1/3 →`
- [ ] Уведомления реально приходят в Telegram (проверить вручную)
- [ ] Свободный текст «Гамлет» → поиск по спектаклям
- [ ] `/random` или кнопка «🎲» выдаёт случайный спектакль с кнопками
- [ ] «🏛 Театры» показывает группировку: Мои / Популярные / По метро
- [ ] `pytest tests/ -v` — все тесты зелёные
- [ ] CLAUDE.md обновлён: T006 ✅
