# T008 — Рецензии: кнопка в карточке, Haiku, кэш в БД

**Статус**: TODO
**Приоритет**: средний
**Зависимости**: T001 ✅ T002 ✅ T006 ✅ T007 ⬜
**Оценка**: ~1 рабочий день

---

## Цель

Добавить в карточку каждого спектакля кнопку **«📝 Рецензия»**.
По нажатию бот генерирует короткую рецензию через Haiku и возвращает её
вместе со ссылкой на страницу спектакля в афише.

Рецензии накапливаются в БД — повторный запрос любого пользователя на тот же
спектакль возвращает уже готовый текст без вызова LLM.

---

## 1. Схема БД — новая таблица `show_reviews`

Создать файл `docker/postgres/init/003_show_reviews.sql`:

```sql
CREATE TABLE IF NOT EXISTS show_reviews (
    id           SERIAL PRIMARY KEY,
    show_id      INTEGER NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    content      TEXT NOT NULL,            -- готовый HTML-текст рецензии
    model        VARCHAR(100) NOT NULL,    -- 'claude-haiku-4-5-20251001'
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(show_id)                        -- одна рецензия на спектакль
);

CREATE INDEX IF NOT EXISTS idx_show_reviews_show_id ON show_reviews(show_id);
```

Применить миграцию на сервере:

```bash
python scripts/mcp_call.py exec_in_container \
  '{"container": "teatr-postgres", "command": "psql -U teatr_user -d teatr_bot -f /docker-entrypoint-initdb.d/003_show_reviews.sql"}'
```

---

## 2. src/db/queries/reviews.py — новый модуль

```python
"""
SQL-запросы для рецензий на спектакли.
Одна рецензия на спектакль, генерируется один раз и кэшируется навсегда.
"""

async def get_review(pool, show_id: int) -> dict | None:
    """Получить рецензию из кэша. None если не было запроса."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content, model, created_at FROM show_reviews WHERE show_id = $1",
            show_id,
        )
    return dict(row) if row else None


async def save_review(pool, show_id: int, content: str, model: str) -> None:
    """Сохранить рецензию. ON CONFLICT DO UPDATE — перезаписать если уже есть."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO show_reviews (show_id, content, model)
            VALUES ($1, $2, $3)
            ON CONFLICT (show_id) DO UPDATE
                SET content = EXCLUDED.content,
                    model = EXCLUDED.model,
                    created_at = NOW()
            """,
            show_id, content, model,
        )


async def get_show_for_review(pool, show_id: int) -> dict | None:
    """Получить данные спектакля для генерации рецензии."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.id, s.title, s.slug, s.genre, s.age_rating,
                   s.description, s.is_premiere,
                   t.name AS theater_name, t.url AS theater_url
            FROM shows s
            JOIN theaters t ON t.id = s.theater_id
            WHERE s.id = $1
            """,
            show_id,
        )
    return dict(row) if row else None
```

---

## 3. src/brain/review_builder.py — генерация рецензии через Haiku

```python
"""
Генерация краткой рецензии на спектакль через Claude Haiku.

ВАЖНО: единственное место где вызывается Haiku для рецензий.
При ошибке API — возвращает описание из БД (graceful degradation).
"""

REVIEW_MODEL = "claude-haiku-4-5-20251001"
REVIEW_MAX_TOKENS = 400   # короткая рецензия — не больше 400 токенов


async def build_review(show: dict) -> str:
    """
    Сгенерировать рецензию через Haiku. При ошибке — fallback на описание.

    show: dict с полями title, theater_name, genre, age_rating,
          description, is_premiere, slug, theater_url
    """
```

### Промпт для Haiku

```python
prompt = f"""Ты — театральный критик. Напиши короткую рецензию на спектакль
для Telegram-бота (2-3 абзаца, HTML-разметка).

Спектакль: {show['title']}
Театр: {show['theater_name']}
Жанр: {show.get('genre') or 'не указан'}
Возрастной рейтинг: {show.get('age_rating') or 'не указан'}
{"🌟 ПРЕМЬЕРА" if show.get('is_premiere') else ""}

Описание от театра:
{show.get('description') or 'Описание отсутствует.'}

Правила:
- HTML: <b>жирный</b>, <i>курсив</i> — только для Telegram
- 2-3 абзаца: о чём спектакль, особенности постановки, кому рекомендовать
- Тон: живой, не сухой; пиши как для живого читателя
- Не придумывай факты которых нет в описании
- Если описание пустое — напиши нейтральный текст на основе названия и театра
- В конце — одна строка «Рекомендуем: [кому стоит сходить]»"""
```

### Fallback при пустом description или ошибке API

```python
def _fallback_review(show: dict) -> str:
    """Заглушка если API недоступен или description пустой."""
    premiere = "🌟 Премьера сезона. " if show.get("is_premiere") else ""
    genre = f"Жанр: {show['genre']}. " if show.get("genre") else ""
    return (
        f"{premiere}<b>{show['title']}</b>\n"
        f"{show['theater_name']}\n\n"
        f"{genre}"
        f"{show.get('description') or 'Описание спектакля уточняйте на сайте театра.'}"
    )
```

---

## 4. Обновить `build_show_card_keyboard()` в `telegram_sender.py`

Добавить кнопку «📝 Рецензия» четвёртой в ряд карточки:

```python
def build_show_card_keyboard(show: dict, has_fav: bool = False,
                              has_wl: bool = False) -> InlineKeyboardMarkup:
    theater_id = show.get("theater_id")
    show_id = show.get("show_id") or show.get("id")

    row1 = []  # Билеты + Рецензия
    row2 = []  # Избранное + Интересно

    if show.get("tickets_url"):
        row1.append(InlineKeyboardButton("🎟 Билеты", url=show["tickets_url"]))

    if show_id:
        row1.append(InlineKeyboardButton("📝 Рецензия", callback_data=f"review:{show_id}"))

    if theater_id:
        fav_text = "✅ Сохранён" if has_fav else "⭐ В избранное"
        row2.append(InlineKeyboardButton(fav_text, callback_data=f"fav:theater:{theater_id}"))

    if show_id:
        wl_text = "📌 В списке" if has_wl else "🔖 Интересно"
        row2.append(InlineKeyboardButton(wl_text, callback_data=f"wl:show:{show_id}"))

    rows = [r for r in [row1, row2] if r]
    return InlineKeyboardMarkup(rows) if rows else None
```

Раскладка по двум рядам чище: в первом — действия (купить, почитать),
во втором — сохранить (театр, спектакль).

---

## 5. Обновить `preference_callback()` в `telegram_commands.py`

Добавить обработку `review:{show_id}`:

```python
elif data.startswith("review:"):
    show_id = int(data.split(":")[1])
    await _handle_review_callback(query, context, pool, show_id)
```

### Функция `_handle_review_callback()`

```python
async def _handle_review_callback(query, context, pool, show_id: int) -> None:
    """
    Обработка кнопки «📝 Рецензия».
    1. Проверяем кэш в show_reviews
    2. Если есть — отправляем из кэша
    3. Если нет — генерируем через Haiku, сохраняем, отправляем
    """
    from src.db.queries.reviews import get_review, save_review, get_show_for_review
    from src.brain.review_builder import build_review, REVIEW_MODEL

    # Шаг 1: проверяем кэш
    cached = await get_review(pool, show_id)
    if cached:
        await _send_review(query, context.bot, cached["content"],
                           show_id, pool, from_cache=True)
        return

    # Шаг 2: генерируем
    await query.answer("Генерирую рецензию...")

    show = await get_show_for_review(pool, show_id)
    if not show:
        await query.answer("Спектакль не найден", show_alert=True)
        return

    content = await build_review(show)

    # Шаг 3: сохраняем и отправляем
    await save_review(pool, show_id, content, REVIEW_MODEL)
    await _send_review(query, context.bot, content,
                       show_id, pool, from_cache=False)
```

### Функция `_send_review()`

Рецензия отправляется отдельным сообщением в тот же чат.
Включает ссылку на спектакль и пометку если из кэша:

```python
async def _send_review(query, bot, content: str,
                        show_id: int, pool, from_cache: bool) -> None:
    """Отправить рецензию в чат."""
    from src.db.queries.reviews import get_show_for_review

    show = await get_show_for_review(pool, show_id)
    chat_id = query.message.chat_id

    # Строим ссылку — KudaGo если есть slug, иначе театральный сайт
    link = ""
    if show:
        if show.get("slug"):
            link = f'\n\n<a href="https://kudago.com/msk/event/{show["slug"]}/">📍 Страница в афише</a>'
        elif show.get("theater_url"):
            link = f'\n\n<a href="{show["theater_url"]}">🏛 Сайт театра</a>'

    cache_note = "\n<i>📦 из кэша</i>" if from_cache else ""

    text = f"{content}{link}{cache_note}"
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML",
                           disable_web_page_preview=False)
```

---

## 6. Обновить pattern в `main.py`

В `CallbackQueryHandler` для `preference_callback` добавить `review:` в pattern:

```python
app.add_handler(CallbackQueryHandler(
    preference_callback,
    pattern="^(fav:|wl:|rm_fav:|rm_wl:|goto_|theaters_page:|theaters_search_page:|theater_shows:|theater_search_input|metro_search|review:)"
))
```

---

## 7. Тесты

### tests/unit/test_review_builder.py

```python
# Тест: build_review возвращает непустую строку с HTML
# Тест: при пустом description — возвращает fallback, не падает
# Тест: при недоступном API — возвращает fallback (mock anthropic.Anthropic)
# Тест: промпт содержит название спектакля и театра

```

### tests/unit/test_reviews_queries.py

```python
# Тест get_review: возвращает None если рецензии нет
# Тест save_review + get_review: сохранили → нашли
# Тест save_review дважды: ON CONFLICT DO UPDATE, не дублирует
```

### tests/unit/test_card_keyboard.py

```python
# Тест: build_show_card_keyboard с show_id → кнопка «📝 Рецензия» есть
# Тест: без show_id → кнопки рецензии нет
# Тест: раскладка — первый ряд Билеты+Рецензия, второй Избранное+Интересно
```

---

## Критерии готовности

- [ ] Миграция `003_show_reviews.sql` применена на сервере
- [ ] В карточке спектакля появилась кнопка «📝 Рецензия»
- [ ] Первый запрос → генерация через Haiku → рецензия приходит в чат
- [ ] Повторный запрос любого пользователя → ответ из БД, без вызова LLM
- [ ] Рецензия содержит ссылку на страницу спектакля в афише KudaGo
- [ ] При пустом `description` и при недоступном API — graceful fallback,
      бот не падает
- [ ] `pytest tests/ -v` — все тесты зелёные
- [ ] CLAUDE.md обновлён: T008 ✅
