import express from 'express';
import cors from 'cors';
import 'dotenv/config';
import { pool } from './db.js';

const app = express();
app.use(cors());
app.use(express.json());

const PROD_COLS = `
    p.id, p.sku, p.name, p.description, p.qty, p.sold_count,
    p.price, p.discount_percent, p.color, p.weight_kg,
    p.rating, p.review_count, p.tags, p.is_active, p.created_at,
    b.name AS brand,
    c.name AS category,
    s.name AS supplier
`;

const PROD_JOINS = `
    FROM products p
    LEFT JOIN brands     b ON b.id = p.brand_id
    LEFT JOIN categories c ON c.id = p.category_id
    LEFT JOIN suppliers  s ON s.id = p.supplier_id
`;

app.get('/health', (_req, res) => res.json({ ok: true }));

// ============ PRODUCTS ============

// GET /products?brand=Apple&category=Phone&warehouse=BKK-SLM&search=iphone&page=1&page_size=50
app.get('/products', async (req, res) => {
    const { brand, category, warehouse, search, on_sale } = req.query;
    const page = Math.max(1, parseInt(req.query.page, 10) || 1);
    const pageSize = Math.min(200, Math.max(1, parseInt(req.query.page_size, 10) || 50));

    const where = [];
    const params = [];
    let n = 1;

    if (brand) { where.push(`b.name = $${n++}`); params.push(brand); }
    if (category) { where.push(`c.name = $${n++}`); params.push(category); }
    if (search) { where.push(`(p.name ILIKE $${n} OR p.sku ILIKE $${n})`); params.push(`%${search}%`); n++; }
    if (on_sale === '1' || on_sale === 'true') where.push(`p.discount_percent > 0`);

    let baseFrom = PROD_JOINS;
    if (warehouse) {
        baseFrom += ` JOIN product_locations pl ON pl.product_id = p.id
                      JOIN warehouses w ON w.id = pl.warehouse_id AND w.code = $${n++}`;
        params.push(warehouse);
    }

    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';
    const offset = (page - 1) * pageSize;

    try {
        const countRes = await pool.query(`SELECT COUNT(DISTINCT p.id) ${baseFrom} ${whereSql}`, params);
        const dataRes = await pool.query(
            `SELECT DISTINCT ${PROD_COLS} ${baseFrom} ${whereSql}
             ORDER BY p.id LIMIT $${n++} OFFSET $${n}`,
            [...params, pageSize, offset]
        );
        res.json({
            total: parseInt(countRes.rows[0].count, 10),
            page,
            page_size: pageSize,
            items: dataRes.rows,
        });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// GET /products/low-stock
app.get('/products/low-stock', async (_req, res) => {
    try {
        const { rows } = await pool.query(
            `SELECT ${PROD_COLS} ${PROD_JOINS} WHERE p.qty < 5 ORDER BY p.qty ASC LIMIT 100`
        );
        res.json(rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// GET /products/:id  (full detail incl. per-warehouse breakdown)
app.get('/products/:id', async (req, res) => {
    const id = parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) return res.status(400).json({ error: 'invalid_id' });
    try {
        const prod = await pool.query(
            `SELECT ${PROD_COLS} ${PROD_JOINS} WHERE p.id = $1`, [id]
        );
        if (prod.rows.length === 0) return res.status(404).json({ error: 'not_found' });
        const locs = await pool.query(
            `SELECT w.id, w.code, w.name, w.city, pl.qty
             FROM product_locations pl JOIN warehouses w ON w.id = pl.warehouse_id
             WHERE pl.product_id = $1 ORDER BY pl.qty DESC`, [id]
        );
        res.json({ ...prod.rows[0], locations: locs.rows });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// POST /products  → add
app.post('/products', async (req, res) => {
    const {
        sku, name, qty = 0, price = 0, discount_percent = 0,
        color, brand_id, category_id, supplier_id,
        weight_kg, description,
    } = req.body || {};
    if (!name || typeof name !== 'string') return res.status(400).json({ error: 'name_required' });
    if (!sku || typeof sku !== 'string') return res.status(400).json({ error: 'sku_required' });
    try {
        const { rows } = await pool.query(
            `INSERT INTO products
                (sku, name, qty, price, discount_percent, color, brand_id, category_id,
                 supplier_id, weight_kg, description)
             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id`,
            [sku, name.trim(), parseInt(qty, 10) || 0, parseFloat(price) || 0,
             parseFloat(discount_percent) || 0,
             color || null, brand_id || null, category_id || null,
             supplier_id || null, parseFloat(weight_kg) || null, description || null]
        );
        res.status(201).json({ id: rows[0].id });
    } catch (err) {
        if (String(err.message).includes('unique')) {
            return res.status(400).json({ error: 'sku_duplicate' });
        }
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// PUT /products/:id
app.put('/products/:id', async (req, res) => {
    const id = parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) return res.status(400).json({ error: 'invalid_id' });
    const allowed = ['name', 'qty', 'price', 'discount_percent', 'color',
                     'brand_id', 'category_id', 'supplier_id', 'weight_kg', 'description', 'is_active'];
    const fields = [], values = [];
    let n = 1;
    for (const key of allowed) {
        if (req.body && req.body[key] !== undefined) {
            fields.push(`${key} = $${n++}`);
            values.push(req.body[key]);
        }
    }
    if (fields.length === 0) return res.status(400).json({ error: 'no_fields' });
    values.push(id);
    try {
        const { rowCount } = await pool.query(
            `UPDATE products SET ${fields.join(', ')} WHERE id = $${n}`, values
        );
        if (rowCount === 0) return res.status(404).json({ error: 'not_found' });
        res.json({ ok: true });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// POST /products/:id/sell  (still atomic at total qty)
app.post('/products/:id/sell', async (req, res) => {
    const id = parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) return res.status(400).json({ error: 'invalid_id' });
    const amount = parseInt(req.body?.amount, 10) || 1;
    if (amount <= 0) return res.status(400).json({ error: 'amount_invalid' });
    try {
        const { rows } = await pool.query(
            `UPDATE products SET qty = qty - $1, sold_count = sold_count + $1
             WHERE id = $2 AND qty >= $1 RETURNING id, qty, sold_count`,
            [amount, id]
        );
        if (rows.length === 0) {
            const exists = await pool.query('SELECT qty FROM products WHERE id = $1', [id]);
            if (exists.rows.length === 0) return res.status(404).json({ error: 'not_found' });
            return res.status(400).json({ error: 'insufficient_qty', available: exists.rows[0].qty });
        }
        res.json(rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// ============ LOOKUP ENDPOINTS ============

app.get('/categories', async (_req, res) => {
    const { rows } = await pool.query('SELECT id, name, slug FROM categories ORDER BY name');
    res.json(rows);
});

app.get('/brands', async (_req, res) => {
    const { rows } = await pool.query('SELECT id, name, country FROM brands ORDER BY name');
    res.json(rows);
});

app.get('/warehouses', async (_req, res) => {
    const { rows } = await pool.query(
        `SELECT w.id, w.code, w.name, w.city, w.capacity,
                COALESCE(SUM(pl.qty),0)::int AS total_qty
         FROM warehouses w
         LEFT JOIN product_locations pl ON pl.warehouse_id = w.id
         GROUP BY w.id ORDER BY w.code`
    );
    res.json(rows);
});

app.get('/suppliers', async (_req, res) => {
    const { rows } = await pool.query(
        'SELECT id, name, lead_time_days, country FROM suppliers ORDER BY name'
    );
    res.json(rows);
});

// ============ DASHBOARD STATS ============

app.get('/stats', async (_req, res) => {
    try {
        const { rows } = await pool.query(`
            SELECT
              (SELECT COUNT(*) FROM products WHERE is_active) AS product_count,
              (SELECT COALESCE(SUM(qty),0) FROM products) AS total_qty,
              (SELECT COALESCE(SUM(sold_count),0) FROM products) AS total_sold,
              (SELECT COUNT(*) FROM products WHERE qty < 5)::int AS low_stock_count,
              (SELECT COUNT(*) FROM products WHERE discount_percent > 0)::int AS on_sale_count,
              (SELECT COALESCE(SUM(qty * price * (1 - discount_percent/100)),0)::float
                 FROM products) AS stock_value,
              (SELECT COUNT(*) FROM customers) AS customer_count,
              (SELECT COUNT(*) FROM orders) AS order_count,
              (SELECT COALESCE(SUM(total_amount),0)::float FROM orders
                 WHERE ordered_at >= NOW() - INTERVAL '30 days'
                   AND status <> 'cancelled') AS revenue_30d
        `);
        res.json(rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// ============ ORDERS ============

app.get('/orders', async (req, res) => {
    const limit = Math.min(100, parseInt(req.query.limit, 10) || 20);
    const { rows } = await pool.query(
        `SELECT o.id, o.status, o.total_amount, o.ordered_at, c.name AS customer_name
         FROM orders o JOIN customers c ON c.id = o.customer_id
         ORDER BY o.ordered_at DESC LIMIT $1`, [limit]
    );
    res.json(rows);
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
    console.log(`Stock backend running on http://localhost:${PORT}`);
});
