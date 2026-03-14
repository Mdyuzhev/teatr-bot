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

-- Журнал событий бота
CREATE TABLE IF NOT EXISTS bot_events (
    id         SERIAL PRIMARY KEY,
    level      VARCHAR(20) NOT NULL,
    message    TEXT NOT NULL,
    details    JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_show_dates_date      ON show_dates(date);
CREATE INDEX IF NOT EXISTS idx_show_dates_show_id   ON show_dates(show_id);
CREATE INDEX IF NOT EXISTS idx_shows_theater_id     ON shows(theater_id);
CREATE INDEX IF NOT EXISTS idx_shows_is_premiere    ON shows(is_premiere) WHERE is_premiere = TRUE;
CREATE INDEX IF NOT EXISTS idx_rss_news_theater_id  ON rss_news(theater_id);
CREATE INDEX IF NOT EXISTS idx_rss_news_published   ON rss_news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_bot_events_level     ON bot_events(level);
CREATE INDEX IF NOT EXISTS idx_bot_events_created   ON bot_events(created_at DESC);

-- Автообновление updated_at
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
