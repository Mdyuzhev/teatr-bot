-- ================================================
-- Театральный бот — схема БД
-- Создано: 14 марта 2026
-- ================================================

-- Театры и театральные площадки
CREATE TABLE IF NOT EXISTS theaters (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(100) UNIQUE,
    address     TEXT,
    metro       VARCHAR(100),
    url         TEXT,
    source      VARCHAR(50) DEFAULT 'kudago',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Спектакли (уникальные постановки)
CREATE TABLE IF NOT EXISTS shows (
    id          SERIAL PRIMARY KEY,
    theater_id  INTEGER REFERENCES theaters(id),
    title       VARCHAR(300) NOT NULL,
    slug        VARCHAR(200) UNIQUE,
    genre       VARCHAR(100),
    age_rating  VARCHAR(20),
    description TEXT,
    is_premiere BOOLEAN DEFAULT FALSE,
    source      VARCHAR(50) DEFAULT 'kudago',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Конкретные даты показов
CREATE TABLE IF NOT EXISTS show_dates (
    id           SERIAL PRIMARY KEY,
    show_id      INTEGER REFERENCES shows(id) ON DELETE CASCADE,
    date         DATE NOT NULL,
    time         TIME,
    stage        VARCHAR(200),
    price_min    INTEGER,
    price_max    INTEGER,
    tickets_url  TEXT,
    is_cancelled BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(show_id, date, time, stage)
);

-- RSS-новости театров
CREATE TABLE IF NOT EXISTS rss_news (
    id           SERIAL PRIMARY KEY,
    theater_id   INTEGER REFERENCES theaters(id),
    title        VARCHAR(500) NOT NULL,
    summary      TEXT,
    url          TEXT UNIQUE,
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);

-- -------------------------------------------------------
-- Кэш дайджестов — главная таблица для экономии токенов
-- -------------------------------------------------------
-- Логика:
--   1. Планировщик 07:00 генерирует стандартные дайджесты
--      (today, tomorrow, weekend, week) через Haiku ОДИН РАЗ
--   2. Все запросы пользователей читают из этой таблицы
--   3. Нестандартный период — проверяем кэш, если нет/устарел → генерируем
--   4. TTL = 24 часа (expires_at = generated_at + INTERVAL '24 hours')
CREATE TABLE IF NOT EXISTS digests (
    id           SERIAL PRIMARY KEY,
    -- Ключ периода: 'today', 'tomorrow', 'weekend', 'week', 'next_week'
    -- или произвольный '2026-03-20:2026-03-25' для кастомных запросов
    period_key   VARCHAR(100) NOT NULL,
    date_from    DATE NOT NULL,
    date_to      DATE NOT NULL,
    -- Готовый текст дайджеста для Telegram (HTML-разметка)
    content      TEXT NOT NULL,
    shows_count  INTEGER DEFAULT 0,
    -- Какая модель использовалась (для отладки и мониторинга)
    model        VARCHAR(100) DEFAULT 'claude-haiku-4-5-20251001',
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Когда кэш устаревает — обычно generated_at + 24h
    expires_at   TIMESTAMPTZ NOT NULL,
    -- Один дайджест на период+даты (при перегенерации — UPDATE)
    UNIQUE(period_key, date_from, date_to)
);

-- Журнал событий бота
CREATE TABLE IF NOT EXISTS bot_events (
    id         SERIAL PRIMARY KEY,
    level      VARCHAR(20) NOT NULL,
    message    TEXT NOT NULL,
    details    JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- -------------------------------------------------------
-- Индексы
-- -------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_show_dates_date      ON show_dates(date);
CREATE INDEX IF NOT EXISTS idx_show_dates_show_id   ON show_dates(show_id);
CREATE INDEX IF NOT EXISTS idx_shows_theater_id     ON shows(theater_id);
CREATE INDEX IF NOT EXISTS idx_shows_is_premiere    ON shows(is_premiere) WHERE is_premiere = TRUE;
CREATE INDEX IF NOT EXISTS idx_rss_news_theater_id  ON rss_news(theater_id);
CREATE INDEX IF NOT EXISTS idx_rss_news_published   ON rss_news(published_at DESC);
-- Для быстрой проверки актуальности кэша по ключу периода
CREATE INDEX IF NOT EXISTS idx_digests_period_key   ON digests(period_key);
CREATE INDEX IF NOT EXISTS idx_digests_expires_at   ON digests(expires_at);
CREATE INDEX IF NOT EXISTS idx_bot_events_level     ON bot_events(level);
CREATE INDEX IF NOT EXISTS idx_bot_events_created   ON bot_events(created_at DESC);

-- -------------------------------------------------------
-- Автообновление updated_at
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER theaters_updated_at BEFORE UPDATE ON theaters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER shows_updated_at BEFORE UPDATE ON shows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
