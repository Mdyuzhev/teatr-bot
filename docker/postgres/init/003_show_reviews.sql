CREATE TABLE IF NOT EXISTS show_reviews (
    id           SERIAL PRIMARY KEY,
    show_id      INTEGER NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    content      TEXT NOT NULL,
    model        VARCHAR(100) NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(show_id)
);

CREATE INDEX IF NOT EXISTS idx_show_reviews_show_id ON show_reviews(show_id);
