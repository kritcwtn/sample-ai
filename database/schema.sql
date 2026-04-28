-- ============================================
-- Stock Project: PostgreSQL schema + seed
-- ============================================

DROP TABLE IF EXISTS products;

CREATE TABLE products (
    id                SERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    qty               INTEGER NOT NULL DEFAULT 0,
    sold_count        INTEGER NOT NULL DEFAULT 0,
    price             NUMERIC(10,2) NOT NULL DEFAULT 0,
    discount_percent  NUMERIC(5,2)  NOT NULL DEFAULT 0
        CHECK (discount_percent BETWEEN 0 AND 100),
    color             TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_qty       ON products (qty);
CREATE INDEX IF NOT EXISTS idx_products_sold_desc ON products (sold_count DESC);
CREATE INDEX IF NOT EXISTS idx_products_price     ON products (price);
CREATE INDEX IF NOT EXISTS idx_products_color     ON products (color);
CREATE INDEX IF NOT EXISTS idx_products_discount  ON products (discount_percent)
    WHERE discount_percent > 0;

-- Optional: fuzzy search support (used by AI service for typo handling)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_products_name_trgm
    ON products USING gin (name gin_trgm_ops);

-- Seed data
INSERT INTO products (name, qty, sold_count, price, discount_percent, color) VALUES
    ('iPhone 15 Pro',  12,  47, 39900.00,  0, 'Natural Titanium'),
    ('MacBook Air M3',  3,  18, 41900.00, 10, 'Midnight'),
    ('AirPods Pro 2',  25, 130,  9990.00, 15, 'White'),
    ('iPad Air',        2,   9, 21900.00, 20, 'Space Gray'),
    ('Magic Keyboard',  8,  22,  3990.00,  5, 'Silver');
