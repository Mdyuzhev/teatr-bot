# T009 — Фото афиши в карточке спектакля

**Статус**: TODO
**Приоритет**: средний — визуальное улучшение
**Зависимости**: T001 ✅ T006 ✅ T008 ⬜
**Оценка**: ~0.5 рабочего дня

---

## Цель

Показывать фото афиши перед карточкой спектакля. KudaGo возвращает
изображения в поле `images`, но сейчас оно не запрашивается и не хранится.

**Схема вывода — два сообщения подряд:**
1. `bot.send_photo(photo=image_url)` — фото без текста и кнопок
2. `bot.send_message(text=..., reply_markup=...)` — карточка с кнопками

Два отдельных сообщения дают полный текст карточки без ограничений caption
(caption ≤ 1024 символа). Telegram визуально группирует их вместе если
отправлены подряд без задержки.

Если у спектакля нет фото — graceful fallback: только текстовая карточка
как сейчас, поведение не меняется.

---

## 1. Схема БД — добавить `image_url` в `shows`

Создать `docker/postgres/init/004_shows_image_url.sql`:

```sql
ALTER TABLE shows ADD COLUMN IF NOT EXISTS image_url TEXT;
CREATE INDEX IF NOT EXISTS idx_shows_image_url ON shows(id) WHERE image_url IS NOT NULL;
```

Применить на сервере:

```bash
python scripts/mcp_call.py exec_in_container \
  '{"container": "teatr-postgres", "command": "psql -U teatr_user -d teatr_bot -f /docker-entrypoint-initdb.d/004_shows_image_url.sql"}'
```

---

## 2. Обновить KudaGo коллектор — запросить `images`

### `fetch_events()` — добавить `images` в `fields`

```python
"fields": "id,title,slug,body_text,tags,age_restriction,price,place,dates,images",
#                                                                           ^^^^^^ добавить
```

### `_parse_show()` — парсить первое изображение

```python
def _parse_show(self, event: dict) -> dict:
    # ... существующий код ...

    image_url = None
    images = event.get("images", [])
    if images and isinstance(images, list):
        first = images[0]
        if isinstance(first, dict):
            thumbnails = first.get("thumbnail", {})
            # Предпочитаем 640x384 — хорошее качество без лишнего веса
            image_url = (
                thumbnails.get("640x384")
                or thumbnails.get("144x96")
                or first.get("image")   # оригинал — последний fallback
            )

    return {
        "title": ...,
        "slug": ...,
        "description": ...,
        "age_rating": ...,
        "is_premiere": ...,
        "image_url": image_url,  # новое поле
    }
```

### `save_to_db()` — сохранять `image_url`

```python
show_id = await conn.fetchval(
    """
    INSERT INTO shows (theater_id, title, slug, age_rating, description,
                       is_premiere, image_url, source)
    VALUES ($1, $2, $3, $4, $5, $6, $7, 'kudago')
    ON CONFLICT (slug) DO UPDATE SET
        title        = EXCLUDED.title,
        description  = EXCLUDED.description,
        is_premiere  = EXCLUDED.is_premiere,
        image_url    = COALESCE(EXCLUDED.image_url, shows.image_url)
        -- COALESCE: не затираем сохранённое фото если новое пришло пустым
    RETURNING id
    """,
    theater_id, show["title"], show["slug"], show["age_rating"],
    show["description"], show["is_premiere"], show["image_url"],
)
```

---

## 3. Обновить SQL-запросы — добавить `s.image_url` в SELECT

Добавить `s.image_url` во все запросы которые возвращают данные спектаклей:

- `src/db/queries/reports.py` → `get_digest_data()`
- `src/db/queries/shows.py` → `get_shows_by_period()`, `get_shows_by_theater()`,
  `get_premieres()`
- `src/db/queries/reviews.py` → `get_show_for_review()`

---

## 4. Обновить `send_shows_as_cards()` в `telegram_sender.py`

Логика для каждой карточки в цикле:

```python
for s in page_shows:
    image_url = s.get("image_url")
    tid = s.get("theater_id")
    sid = s.get("show_id") or s.get("id")
    key = f"{tid}:{sid}"
    fav, wl = has_prefs.get(key, (False, False))
    markup = build_show_card_keyboard(s, has_fav=fav, has_wl=wl)
    card_text = format_show_card(s)

    try:
        if image_url:
            # Шаг 1: фото без текста и кнопок
            try:
                await bot.send_photo(chat_id=chat_id, photo=image_url)
            except Exception as photo_err:
                # Битый URL — тихо пропускаем фото, карточку всё равно покажем
                logger.warning("Не удалось загрузить фото для show {}: {}", sid, photo_err)

            # Шаг 2: карточка с полным текстом и кнопками
            await bot.send_message(
                chat_id=chat_id,
                text=card_text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        else:
            # Нет фото — просто карточка
            await bot.send_message(
                chat_id=chat_id,
                text=card_text,
                parse_mode="HTML",
                reply_markup=markup,
            )
    except Exception as e:
        logger.error("Ошибка отправки карточки show {}: {}", sid, e)
```

**Важно**: фото и карточка — отдельные try/except. Ошибка при загрузке фото
не должна скрывать карточку с кнопками — пользователь всегда получит
хотя бы текст.

`format_show_card()` остаётся без изменений — текст полный,
без ограничений caption.

---

## 5. Тесты

### tests/unit/test_kudago_images.py

```python
# Тест _parse_show: event с images → image_url = thumbnails['640x384']
# Тест _parse_show: предпочтение размеров: 640x384 > 144x96 > image
# Тест _parse_show: event без images → image_url = None
# Тест _parse_show: images = [] → image_url = None
# Тест _parse_show: images[0] без thumbnail → берёт images[0]['image']
```

### tests/unit/test_send_cards_with_photo.py

```python
# Тест: show с image_url → send_photo вызван, затем send_message (mock)
# Тест: show без image_url → только send_message, send_photo не вызван
# Тест: send_photo бросает исключение → send_message всё равно вызван
# Тест: send_message бросает исключение → логируется, не роняет цикл
```

---

## Критерии готовности

- [ ] Миграция `004_shows_image_url.sql` применена на сервере
- [ ] После `/refresh` фото появляются в БД:
      `SELECT count(*) FROM shows WHERE image_url IS NOT NULL` > 0
- [ ] В дайджесте спектакли с фото показывают сначала картинку, потом карточку
- [ ] Спектакли без фото показывают только текстовую карточку — без ошибок
- [ ] Битый URL фото не скрывает карточку с кнопками
- [ ] `pytest tests/ -v` — все тесты зелёные
- [ ] CLAUDE.md обновлён: T009 ✅
