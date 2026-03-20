# T007 — Список театров: пагинация, поиск, кнопка ⭐ в списке

**Статус**: TODO
**Приоритет**: высокий
**Зависимости**: T001 ✅ T002 ✅ T005 ✅ T006 ✅
**Оценка**: ~1 рабочий день

---

## Что нужно сделать

Три взаимосвязанные доработки по разделу «🏛 Театры»:

1. **Список театров постранично** — по 10 за раз, кнопки `← / →`
2. **Кнопка ⭐ рядом с каждым театром** в списке — добавить/убрать из избранного
   прямо не выходя из списка
3. **Поиск театра по названию** — кнопка «🔍 Найти театр», пользователь вводит
   текст, бот показывает совпадения тоже с кнопками ⭐

---

## 1. SQL: добавить поиск по названию в `theaters.py`

```python
async def search_theaters_by_name(pool, query: str) -> list[dict]:
    """Поиск театров по подстроке в названии. Возвращает с upcoming_shows."""
    today = date.today()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.name, t.slug, t.address, t.metro, t.url,
                   COUNT(sd.id) AS upcoming_shows
            FROM theaters t
            LEFT JOIN shows s ON s.theater_id = t.id
            LEFT JOIN show_dates sd ON sd.show_id = s.id
                AND sd.date >= $1 AND sd.is_cancelled = FALSE
            WHERE LOWER(t.name) LIKE $2
            GROUP BY t.id
            ORDER BY upcoming_shows DESC, t.name
            """,
            today, f"%{query.lower()}%",
        )
    return [dict(r) for r in rows]
```

---

## 2. Новая функция `send_theaters_page()` в `telegram_sender.py`

```python
async def send_theaters_page(
    bot,
    chat_id: int,
    theaters: list[dict],
    fav_ids: set[int],
    page: int = 0,
    page_size: int = 10,
    title: str = "🏛 Театры",
    search_query: str | None = None,
) -> None:
    """
    Отправить страницу из списка театров.

    Каждый театр — отдельная строка в тексте + две inline-кнопки в ряду:
      [ 🎭 Афиша ]  [ ⭐ В избранное ] или [ ✅ Избранное ]

    Внизу навигация:
      [ ← ]  Страница 2 / 5  [ → ]
      [ 🔍 Найти театр ]  [ 🚇 По метро ]
    """
```

### Формат вывода одной страницы

```
🏛 Театры  (стр. 1 / 5)

1. МХТ им. Чехова · Охотный Ряд — 12 показов
2. Театр Вахтангова · Арбатская — 8 показов
3. Большой театр · Театральная — 6 показов
...
10. Ленком · Пушкинская — 4 показа

[ ← ]  1 / 5  [ → ]
[ 🔍 Найти театр ]  [ 🚇 По метро ]
```

Под текстом — inline-кнопки в два столбца для каждого театра:
```
[ 🎭 МХТ им. Чехова ]  [ ⭐ ]
[ 🎭 Вахтангова ]       [ ✅ ]   ← уже в избранном
...
[ ← ]  [ 1/5 ]  [ → ]
[ 🔍 Найти ]  [ 🚇 По метро ]
```

Кнопка `⭐` → `callback_data = fav:theater:{id}` (уже обрабатывается в `preference_callback`)
После toggle — обновить эту кнопку на `✅` или обратно (через `_update_card_button`).

Кнопка `🎭 Название` → `callback_data = theater_shows:{slug}` — показывает
карточки спектаклей этого театра.

### Callback data

```
theaters_page:{page}              — страница списка всех театров
theaters_search_page:{q}:{page}   — страница результатов поиска
theater_shows:{slug}              — афиша театра (замена /theater command)
```

---

## 3. Обновить `_cmd_theaters_list()` в `telegram_commands.py`

Убрать текущую логику (плоский список с "...и ещё N"). Заменить:

```python
async def _cmd_theaters_list(update, context) -> None:
    pool = await get_pool()
    user_id = update.effective_user.id
    theaters = await get_all_theaters(pool)
    favs = await get_user_favorites(pool, user_id)
    fav_ids = {f["id"] for f in favs}

    await send_theaters_page(
        context.bot, update.effective_chat.id,
        theaters, fav_ids, page=0,
    )
```

---

## 4. Обновить `preference_callback()` — добавить theater_shows

В существующем `preference_callback()` добавить обработку новых callback:

```python
elif data.startswith("theaters_page:"):
    page = int(data.split(":")[1])
    theaters = await get_all_theaters(pool)
    favs = await get_user_favorites(pool, user_id)
    fav_ids = {f["id"] for f in favs}
    # Редактировать текущее сообщение — новая страница
    await _edit_theaters_page(query, theaters, fav_ids, page)

elif data.startswith("theaters_search_page:"):
    parts = data.split(":", 3)
    search_q = parts[1]
    page = int(parts[2])
    from src.db.queries.theaters import search_theaters_by_name
    theaters = await search_theaters_by_name(pool, search_q)
    favs = await get_user_favorites(pool, user_id)
    fav_ids = {f["id"] for f in favs}
    await _edit_theaters_page(query, theaters, fav_ids, page,
                               title=f"🔍 Поиск: {search_q}", search_query=search_q)

elif data.startswith("theater_shows:"):
    slug = data.split(":", 1)[1]
    from src.db.queries.theaters import get_theater_by_slug
    theater = await get_theater_by_slug(pool, slug)
    if not theater:
        await query.answer("Театр не найден", show_alert=True)
        return
    today = date.today()
    date_to = today + timedelta(days=14)
    shows = await get_shows_by_theater(pool, slug, today, date_to)
    if not shows:
        await query.answer(f"У «{theater['name']}» нет показов в ближайшие 2 недели",
                           show_alert=True)
        return
    for s in shows:
        s["theater_name"] = theater["name"]
        s["theater_id"] = theater["id"]
    await send_shows_as_cards(
        context.bot, query.message.chat_id, shows,
        f"🏛 <b>{theater['name']}</b>",
        pool=pool, user_id=user_id,
    )

elif data == "theater_search_input":
    context.user_data["awaiting"] = "theater_search"
    await query.edit_message_text("🔍 Введите название театра (или часть названия):")
```

---

## 5. Обновить `reply_keyboard_handler()` — поиск театра

В `reply_keyboard_handler()` добавить ветку для ожидания ввода поиска театра:

```python
elif context.user_data.get("awaiting") == "theater_search":
    context.user_data.pop("awaiting", None)
    await _search_theaters_inline(update, context, text)
```

### Функция `_search_theaters_inline()`

```python
async def _search_theaters_inline(update, context, query_text: str) -> None:
    from src.db.queries.theaters import search_theaters_by_name
    pool = await get_pool()
    user_id = update.effective_user.id
    theaters = await search_theaters_by_name(pool, query_text)

    if not theaters:
        await send_message(context.bot, update.effective_chat.id,
                           f"Театров по запросу «{query_text}» не найдено.")
        return

    favs = await get_user_favorites(pool, user_id)
    fav_ids = {f["id"] for f in favs}

    await send_theaters_page(
        context.bot, update.effective_chat.id,
        theaters, fav_ids, page=0,
        title=f"🔍 Поиск: {query_text}",
        search_query=query_text,
    )
```

---

## 6. Добавить `theater_search_input` в маршруты `main.py`

```python
# В preference_callback уже обрабатывается через pattern
app.add_handler(CallbackQueryHandler(
    preference_callback,
    pattern="^(fav:|wl:|rm_fav:|rm_wl:|goto_|theaters_page:|theaters_search_page:|theater_shows:|theater_search_input|metro_search)"
))
```

---

## 7. Удалить/переработать старую команду `/theater`

Старая `cmd_theater()` при нескольких результатах выводила `  /theater_{slug}` —
это не работает как ссылка. Заменить на вывод через `send_theaters_page()`:

```python
async def cmd_theater(update, context) -> None:
    if not context.args:
        # Без аргументов — показать список с первой страницы
        await _cmd_theaters_list(update, context)
        return

    search = " ".join(context.args)
    from src.db.queries.theaters import search_theaters_by_name
    pool = await get_pool()
    theaters = await search_theaters_by_name(pool, search)

    if not theaters:
        await send_message(context.bot, update.effective_chat.id,
                           f"Театр «{search}» не найден.")
        return

    favs = await get_user_favorites(pool, user_id)
    fav_ids = {f["id"] for f in favs}

    if len(theaters) == 1:
        # Сразу показываем афишу единственного найденного театра
        t = theaters[0]
        today = date.today()
        shows = await get_shows_by_theater(pool, t["slug"], today, today + timedelta(days=14))
        if not shows:
            await send_message(context.bot, update.effective_chat.id,
                               f"У «{t['name']}» нет показов в ближайшие 2 недели.")
            return
        for s in shows:
            s["theater_name"] = t["name"]
            s["theater_id"] = t["id"]
        await send_shows_as_cards(context.bot, update.effective_chat.id, shows,
                                   f"🏛 <b>{t['name']}</b>",
                                   pool=pool, user_id=update.effective_user.id)
    else:
        # Несколько — страница результатов поиска с кнопками
        await send_theaters_page(
            context.bot, update.effective_chat.id,
            theaters, fav_ids, page=0,
            title=f"🔍 Поиск: {search}", search_query=search,
        )
```

---

## 8. Тесты

### tests/unit/test_theaters_list.py

```python
# Тест пагинации: 25 театров, page_size=10 → 3 страницы,
#   страница 0 → театры [0..9], страница 2 → театры [20..24]

# Тест send_theaters_page: кнопка ⭐ для театра в fav_ids → текст «✅»
# Тест send_theaters_page: театр не в fav_ids → текст «⭐»

# Тест search_theaters_by_name: «мхт» → находит «МХТ им. Чехова»
# Тест search_theaters_by_name: «xxxxxx» → пустой список
```

---

## Критерии готовности

- [ ] Кнопка «🏛 Театры» показывает список постранично по 10 штук
- [ ] Кнопки `← / →` переключают страницы, редактируя то же сообщение
- [ ] Рядом с каждым театром кнопка `⭐` / `✅` — добавляет/убирает из избранного
      не покидая список
- [ ] После toggle ⭐ кнопка меняет вид без перезагрузки всего списка
- [ ] Кнопка «🔍 Найти театр» → бот просит ввести текст → показывает
      результаты поиска тоже постранично с кнопками ⭐
- [ ] `/theater большой` — находит театр и показывает афишу карточками
- [ ] `/theater` без аргументов — показывает пагинированный список
- [ ] `pytest tests/ -v` — все тесты зелёные
- [ ] CLAUDE.md обновлён: T007 ✅
