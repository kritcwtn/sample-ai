-- ============================================
-- Stock Project: PostgreSQL schema v2 (full e-commerce)
-- ============================================
-- Drop in reverse FK order
DROP TABLE IF EXISTS stock_movements CASCADE;
DROP TABLE IF EXISTS order_items     CASCADE;
DROP TABLE IF EXISTS orders          CASCADE;
DROP TABLE IF EXISTS customers       CASCADE;
DROP TABLE IF EXISTS product_locations CASCADE;
DROP TABLE IF EXISTS products        CASCADE;
DROP TABLE IF EXISTS suppliers       CASCADE;
DROP TABLE IF EXISTS brands          CASCADE;
DROP TABLE IF EXISTS categories      CASCADE;
DROP TABLE IF EXISTS warehouses      CASCADE;

-- ===== reference / lookup tables =====
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE
);

CREATE TABLE brands (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    country     TEXT
);

CREATE TABLE suppliers (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    contact         TEXT,
    lead_time_days  INTEGER NOT NULL DEFAULT 7,
    country         TEXT
);

CREATE TABLE warehouses (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL,
    capacity    INTEGER NOT NULL DEFAULT 10000
);

-- ===== products (master) =====
CREATE TABLE products (
    id                SERIAL PRIMARY KEY,
    sku               TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    description       TEXT,
    brand_id          INTEGER REFERENCES brands(id),
    category_id       INTEGER REFERENCES categories(id),
    supplier_id       INTEGER REFERENCES suppliers(id),
    qty               INTEGER NOT NULL DEFAULT 0,        -- denormalized total
    sold_count        INTEGER NOT NULL DEFAULT 0,
    price             NUMERIC(10,2) NOT NULL DEFAULT 0,
    discount_percent  NUMERIC(5,2)  NOT NULL DEFAULT 0
        CHECK (discount_percent BETWEEN 0 AND 100),
    color             TEXT,
    weight_kg         NUMERIC(8,3),
    rating            NUMERIC(2,1) NOT NULL DEFAULT 0
        CHECK (rating BETWEEN 0 AND 5),
    review_count      INTEGER NOT NULL DEFAULT 0,
    tags              TEXT[],
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ===== per-warehouse stock breakdown =====
CREATE TABLE product_locations (
    product_id    INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id  INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    qty           INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, warehouse_id)
);

-- ===== customers + orders =====
CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE,
    phone       TEXT,
    city        TEXT,
    joined_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    id            SERIAL PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(id),
    status        TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','paid','shipped','delivered','cancelled')),
    total_amount  NUMERIC(12,2) NOT NULL DEFAULT 0,
    ordered_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    shipped_at    TIMESTAMP
);

CREATE TABLE order_items (
    id                  SERIAL PRIMARY KEY,
    order_id            INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id          INTEGER NOT NULL REFERENCES products(id),
    qty                 INTEGER NOT NULL,
    unit_price          NUMERIC(10,2) NOT NULL,
    discount_percent    NUMERIC(5,2) NOT NULL DEFAULT 0,
    line_total          NUMERIC(12,2) NOT NULL
);

-- ===== audit log =====
CREATE TABLE stock_movements (
    id            SERIAL PRIMARY KEY,
    product_id    INTEGER NOT NULL REFERENCES products(id),
    warehouse_id  INTEGER REFERENCES warehouses(id),
    type          TEXT NOT NULL
        CHECK (type IN ('restock','sale','transfer_in','transfer_out','adjust')),
    qty_delta     INTEGER NOT NULL,
    reason        TEXT,
    ref_id        INTEGER,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ===== indexes =====
CREATE INDEX idx_products_brand     ON products (brand_id);
CREATE INDEX idx_products_category  ON products (category_id);
CREATE INDEX idx_products_supplier  ON products (supplier_id);
CREATE INDEX idx_products_qty       ON products (qty);
CREATE INDEX idx_products_sold      ON products (sold_count DESC);
CREATE INDEX idx_products_price     ON products (price);
CREATE INDEX idx_products_rating    ON products (rating DESC);
CREATE INDEX idx_products_active    ON products (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_products_discount  ON products (discount_percent) WHERE discount_percent > 0;

CREATE INDEX idx_pl_warehouse       ON product_locations (warehouse_id);
CREATE INDEX idx_pl_qty             ON product_locations (qty);

CREATE INDEX idx_orders_customer    ON orders (customer_id);
CREATE INDEX idx_orders_date        ON orders (ordered_at DESC);
CREATE INDEX idx_orders_status      ON orders (status);

CREATE INDEX idx_oi_order           ON order_items (order_id);
CREATE INDEX idx_oi_product         ON order_items (product_id);

CREATE INDEX idx_sm_product         ON stock_movements (product_id);
CREATE INDEX idx_sm_warehouse       ON stock_movements (warehouse_id);
CREATE INDEX idx_sm_date            ON stock_movements (created_at DESC);
CREATE INDEX idx_sm_type            ON stock_movements (type);

-- pg_trgm fuzzy + GIN
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);
CREATE INDEX idx_products_tags      ON products USING gin (tags);
