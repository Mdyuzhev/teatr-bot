ALTER TABLE shows ADD COLUMN IF NOT EXISTS image_url TEXT;
CREATE INDEX IF NOT EXISTS idx_shows_image_url ON shows(id) WHERE image_url IS NOT NULL;
