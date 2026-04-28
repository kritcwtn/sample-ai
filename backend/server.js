import express from 'express';
import cors from 'cors';
import 'dotenv/config';
import { pool } from './db.js';

const app = express();
app.use(cors());
app.use(express.json());

const COLS = 'id, name, qty, sold_count, price, discount_percent, color, created_at';

app.get('/health', (_req, res) => res.json({ ok: true }));

// GET /products  → list all
app.get('/products', async (_req, res) => {
    try {
        const { rows } = await pool.query(
            `SELECT ${COLS} FROM products ORDER BY id ASC`
        );
        res.json(rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// GET /products/low-stock  → qty < 5
app.get('/products/low-stock', async (_req, res) => {
    try {
        const { rows } = await pool.query(
            `SELECT ${COLS} FROM products WHERE qty < 5 ORDER BY qty ASC`
        );
        res.json(rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// POST /products  → add new
app.post('/products', async (req, res) => {
    const { name, qty, price, discount_percent, color } = req.body || {};
    if (!name || typeof name !== 'string') {
        return res.status(400).json({ error: 'name_required' });
    }
    const qtyNum = Number.isInteger(qty) ? qty : parseInt(qty, 10);
    if (!Number.isFinite(qtyNum) || qtyNum < 0) {
        return res.status(400).json({ error: 'qty_invalid' });
    }
    let priceNum = 0;
    if (price !== undefined && price !== '' && price !== null) {
        priceNum = typeof price === 'number' ? price : parseFloat(price);
        if (!Number.isFinite(priceNum) || priceNum < 0) {
            return res.status(400).json({ error: 'price_invalid' });
        }
    }
    let discountNum = 0;
    if (discount_percent !== undefined && discount_percent !== '' && discount_percent !== null) {
        discountNum = typeof discount_percent === 'number'
            ? discount_percent
            : parseFloat(discount_percent);
        if (!Number.isFinite(discountNum) || discountNum < 0 || discountNum > 100) {
            return res.status(400).json({ error: 'discount_invalid' });
        }
    }
    const colorVal =
        typeof color === 'string' && color.trim() !== '' ? color.trim() : null;

    try {
        const { rows } = await pool.query(
            `INSERT INTO products (name, qty, price, discount_percent, color)
             VALUES ($1, $2, $3, $4, $5) RETURNING ${COLS}`,
            [name.trim(), qtyNum, priceNum, discountNum, colorVal]
        );
        res.status(201).json(rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// PUT /products/:id  → update name and/or qty and/or price and/or color
app.put('/products/:id', async (req, res) => {
    const id = parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) return res.status(400).json({ error: 'invalid_id' });

    const { name, qty, price, discount_percent, color } = req.body || {};
    const fields = [];
    const values = [];
    let n = 1;

    if (name !== undefined) {
        if (typeof name !== 'string' || !name.trim()) {
            return res.status(400).json({ error: 'name_invalid' });
        }
        fields.push(`name = $${n++}`);
        values.push(name.trim());
    }
    if (qty !== undefined) {
        const qtyNum = Number.isInteger(qty) ? qty : parseInt(qty, 10);
        if (!Number.isFinite(qtyNum) || qtyNum < 0) {
            return res.status(400).json({ error: 'qty_invalid' });
        }
        fields.push(`qty = $${n++}`);
        values.push(qtyNum);
    }
    if (price !== undefined) {
        const priceNum =
            typeof price === 'number' ? price : parseFloat(price);
        if (!Number.isFinite(priceNum) || priceNum < 0) {
            return res.status(400).json({ error: 'price_invalid' });
        }
        fields.push(`price = $${n++}`);
        values.push(priceNum);
    }
    if (discount_percent !== undefined) {
        const dNum =
            typeof discount_percent === 'number'
                ? discount_percent
                : parseFloat(discount_percent);
        if (!Number.isFinite(dNum) || dNum < 0 || dNum > 100) {
            return res.status(400).json({ error: 'discount_invalid' });
        }
        fields.push(`discount_percent = $${n++}`);
        values.push(dNum);
    }
    if (color !== undefined) {
        const colorVal =
            color === null || (typeof color === 'string' && color.trim() === '')
                ? null
                : String(color).trim();
        fields.push(`color = $${n++}`);
        values.push(colorVal);
    }
    if (fields.length === 0) {
        return res.status(400).json({ error: 'no_fields' });
    }

    values.push(id);
    try {
        const { rows } = await pool.query(
            `UPDATE products SET ${fields.join(', ')} WHERE id = $${n} RETURNING ${COLS}`,
            values
        );
        if (rows.length === 0) return res.status(404).json({ error: 'not_found' });
        res.json(rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'db_error' });
    }
});

// POST /products/:id/sell  → decrement qty, increment sold_count (atomic)
app.post('/products/:id/sell', async (req, res) => {
    const id = parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) return res.status(400).json({ error: 'invalid_id' });

    const amount = req.body?.amount ?? 1;
    const n = Number.isInteger(amount) ? amount : parseInt(amount, 10);
    if (!Number.isFinite(n) || n <= 0) {
        return res.status(400).json({ error: 'amount_invalid' });
    }

    try {
        const { rows } = await pool.query(
            `UPDATE products
                SET qty = qty - $1,
                    sold_count = sold_count + $1
              WHERE id = $2 AND qty >= $1
              RETURNING ${COLS}`,
            [n, id]
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

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
    console.log(`Stock backend running on http://localhost:${PORT}`);
});
