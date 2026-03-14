-- ================================================
-- T005 — Персонализация: Избранное и Интересное
-- Создано: 14 марта 2026
-- ================================================

-- Пользовательские предпочтения (избранное / вишлист)
-- type: 'favorite' (театр) или 'watchlist' (спектакль)
CREATE TABLE IF NOT EXISTS user_preferences (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    type        VARCHAR(20) NOT NULL,
    ref_id      INTEGER NOT NULL,
    ref_type    VARCHAR(20) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, type, ref_id, ref_type)
);

CREATE INDEX IF NOT EXISTS idx_user_prefs_user_id ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_prefs_type    ON user_preferences(type, ref_id, ref_type);

-- Лог уведомлений (антиспам — одно уведомление не уходит дважды)
CREATE TABLE IF NOT EXISTS notification_log (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    type        VARCHAR(50) NOT NULL,
    ref_id      INTEGER NOT NULL,
    sent_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, type, ref_id)
);

CREATE INDEX IF NOT EXISTS idx_notification_log_user ON notification_log(user_id);
