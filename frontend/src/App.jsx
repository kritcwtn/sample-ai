import { useEffect, useMemo, useRef, useState } from 'react';
import {
    listProducts, sellProduct, askAI,
    getStats, listBrands, listCategories, listWarehouses,
} from './api.js';
import {
    IconBag, IconBox, IconCart, IconChart, IconUsers, IconWallet,
    IconTag, IconAlert, IconSearch, IconCartSm, IconChat, IconClose, IconArrowUp,
} from './icons.jsx';

const SUGGESTIONS = [
    'สินค้าขายดีตอนนี้',
    'แบรนด์ Apple มีอะไร',
    'ลูกค้ารายใหญ่ 5 อันดับ',
    'รายได้เดือนนี้',
];

const fmtTHB = (n) =>
    new Intl.NumberFormat('th-TH', { style: 'currency', currency: 'THB' }).format(Number(n) || 0);

// Map common color names to swatches.
const COLOR_HEX = {
    'natural titanium': '#8e8e93', midnight: '#1f1f1f', 'space gray': '#3a3a3c',
    silver: '#c7c7cc', white: '#f5f5f7', black: '#000', starlight: '#f6f0e0',
    blue: '#0a84ff', pink: '#ff66c4', red: '#ff3b30', green: '#30d158',
    yellow: '#ffd60a', purple: '#bf5af2', graphite: '#5e5e5e', gold: '#d4af37',
};

function ColorTag({ color }) {
    if (!color) return <span className="muted">—</span>;
    const hex = COLOR_HEX[color.toLowerCase()] || '#94a3b8';
    return (
        <span className="color-tag">
            <span className="swatch" style={{ background: hex }} />
            {color}
        </span>
    );
}

function PriceCell({ price, discount }) {
    const original = Number(price) || 0;
    const d = Number(discount) || 0;
    if (d <= 0) return <span className="money">{fmtTHB(original)}</span>;
    const eff = original * (1 - d / 100);
    return (
        <span className="price-with-discount">
            <span className="price-original">{fmtTHB(original)}</span>
            <span className="price-now">
                <span className="money">{fmtTHB(eff)}</span>
                <span className="discount-pill">−{Math.round(d)}%</span>
            </span>
        </span>
    );
}

function RatingCell({ rating, count }) {
    if (!rating) return <span className="muted">—</span>;
    const r = Number(rating);
    const stars = '★'.repeat(Math.round(r)) + '☆'.repeat(5 - Math.round(r));
    return (
        <span className="rating">
            <span className="stars">{stars}</span>
            <span className="rating-num">{r.toFixed(1)}</span>
            <span className="muted">({count})</span>
        </span>
    );
}

const PAGE_SIZES = [10, 20, 50, 100];

export default function App() {
    const [products, setProducts] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);

    const [stats, setStats] = useState(null);
    const [brands, setBrands] = useState([]);
    const [categories, setCategories] = useState([]);
    const [warehouses, setWarehouses] = useState([]);

    const [filter, setFilter] = useState({
        brand: '', category: '', warehouse: '', search: '', on_sale: false,
    });
    const [err, setErr] = useState('');

    const [sellTarget, setSellTarget] = useState(null);
    const [chatOpen, setChatOpen] = useState(false);
    const [messages, setMessages] = useState([
        { role: 'bot', text: 'สวัสดีครับ! ผมคือ AI Assistant ถามผมได้เกี่ยวกับสต็อก ลูกค้า และยอดขาย 👋' },
    ]);
    const [question, setQuestion] = useState('');
    const [sending, setSending] = useState(false);
    const bodyRef = useRef(null);

    const refresh = async (toPage = page, toSize = pageSize) => {
        try {
            const params = { page: toPage, page_size: toSize };
            if (filter.brand) params.brand = filter.brand;
            if (filter.category) params.category = filter.category;
            if (filter.warehouse) params.warehouse = filter.warehouse;
            if (filter.search) params.search = filter.search;
            if (filter.on_sale) params.on_sale = 1;
            const data = await listProducts(params);
            setProducts(data.items);
            setTotal(data.total);
            setPage(data.page);
            setPageSize(data.page_size);
        } catch (e) {
            setErr('โหลดสินค้าล้มเหลว: ' + e.message);
        }
    };

    const refreshStats = async () => {
        try { setStats(await getStats()); } catch { /* ignore */ }
    };

    useEffect(() => {
        Promise.all([
            listBrands().then(setBrands).catch(() => {}),
            listCategories().then(setCategories).catch(() => {}),
            listWarehouses().then(setWarehouses).catch(() => {}),
        ]);
        refresh(1, pageSize);
        refreshStats();
    }, []);

    useEffect(() => { refresh(1, pageSize); }, [filter.brand, filter.category, filter.warehouse, filter.on_sale]);

    useEffect(() => {
        if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }, [messages, chatOpen]);

    const confirmSell = async (product, amount) => {
        const n = parseInt(amount, 10);
        if (!Number.isFinite(n) || n <= 0) {
            setErr('จำนวนไม่ถูกต้อง');
            return;
        }
        try {
            await sellProduct(product.id, n);
            setSellTarget(null);
            await refresh();
            await refreshStats();
        } catch (e) {
            const detail = e.response?.data?.error || e.message;
            const avail = e.response?.data?.available;
            setErr(`ขายไม่สำเร็จ: ${detail}${avail !== undefined ? ` (เหลือ ${avail})` : ''}`);
        }
    };

    const send = async (text) => {
        const q = (text ?? question).trim();
        if (!q || sending) return;
        setMessages((m) => [...m, { role: 'user', text: q }]);
        setQuestion('');
        setSending(true);
        try {
            const res = await askAI(q);
            setMessages((m) => [...m, { role: 'bot', text: res.answer || JSON.stringify(res) }]);
        } catch (e) {
            const detail = e.response?.data?.detail || e.message;
            setMessages((m) => [...m, { role: 'bot', text: 'เกิดข้อผิดพลาด: ' + detail, error: true }]);
        } finally {
            setSending(false);
        }
    };

    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const onSearchKey = (e) => { if (e.key === 'Enter') refresh(1, pageSize); };

    return (
        <div className="app">
            <div className="shell">
                <header className="header">
                    <h1>
                        <span className="logo">📦</span>
                        Stock Manager
                    </h1>
                    <span className="header-meta">
                        {warehouses.length} warehouses · {brands.length} brands · {categories.length} categories
                    </span>
                </header>

                {err && <div className="alert" onClick={() => setErr('')}>{err}</div>}

                {stats && (
                    <div className="stats">
                        <div className="stat t-blue">
                            <span className="icon-wrap"><IconBag /></span>
                            <div className="label">Products</div>
                            <div className="value">{Number(stats.product_count).toLocaleString()}</div>
                            <div className="sublabel">Total items</div>
                        </div>
                        <div className="stat t-cyan">
                            <span className="icon-wrap"><IconBox /></span>
                            <div className="label">In stock</div>
                            <div className="value">{Number(stats.total_qty).toLocaleString()}</div>
                            <div className="sublabel">Total units</div>
                        </div>
                        <div className="stat t-green">
                            <span className="icon-wrap"><IconCart /></span>
                            <div className="label">Sold</div>
                            <div className="value">{Number(stats.total_sold).toLocaleString()}</div>
                            <div className="sublabel">Total units</div>
                        </div>
                        <div className="stat t-navy">
                            <span className="icon-wrap"><IconChart /></span>
                            <div className="label">Stock value</div>
                            <div className="value money">{fmtTHB(stats.stock_value)}</div>
                            <div className="sublabel">Total value</div>
                        </div>
                        <div className="stat t-peach">
                            <span className="icon-wrap"><IconUsers /></span>
                            <div className="label">Customers</div>
                            <div className="value">{Number(stats.customer_count).toLocaleString()}</div>
                            <div className="sublabel">Total customers</div>
                        </div>
                        <div className="stat t-indigo">
                            <span className="icon-wrap"><IconWallet /></span>
                            <div className="label">Revenue 30d</div>
                            <div className="value money">{fmtTHB(stats.revenue_30d)}</div>
                            <div className="sublabel">Total revenue</div>
                        </div>
                        <div className="stat t-orange">
                            <span className="icon-wrap"><IconTag /></span>
                            <div className="label">On sale</div>
                            <div className="value">{stats.on_sale_count}</div>
                            <div className="sublabel">Products</div>
                        </div>
                        <div className="stat t-rose">
                            <span className="icon-wrap"><IconAlert /></span>
                            <div className="label">Low stock</div>
                            <div className="value">{stats.low_stock_count}</div>
                            <div className="sublabel">Products</div>
                        </div>
                    </div>
                )}
            </div>

            <div className="shell">
                <section className="section">
                    <div className="section-head">
                        <h2 className="section-title">Products</h2>
                        <span className="muted">{total.toLocaleString()} items</span>
                    </div>

                    <div className="filters">
                        <div className="search-wrap">
                            <span className="icon-search"><IconSearch size={16} /></span>
                            <input
                                className="input"
                                placeholder="ค้นชื่อ / SKU"
                                value={filter.search}
                                onChange={(e) => setFilter({ ...filter, search: e.target.value })}
                                onKeyDown={onSearchKey}
                            />
                        </div>
                        <select value={filter.brand} onChange={(e) => setFilter({ ...filter, brand: e.target.value })}>
                            <option value="">All brands</option>
                            {brands.map((b) => <option key={b.id} value={b.name}>{b.name}</option>)}
                        </select>
                        <select value={filter.category} onChange={(e) => setFilter({ ...filter, category: e.target.value })}>
                            <option value="">All categories</option>
                            {categories.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                        </select>
                        <select value={filter.warehouse} onChange={(e) => setFilter({ ...filter, warehouse: e.target.value })}>
                            <option value="">All warehouses</option>
                            {warehouses.map((w) => <option key={w.id} value={w.code}>{w.name}</option>)}
                        </select>
                        <label className="checkbox">
                            <input
                                type="checkbox"
                                checked={filter.on_sale}
                                onChange={(e) => setFilter({ ...filter, on_sale: e.target.checked })}
                            />
                            On sale
                        </label>
                    </div>

                    <div className="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>SKU</th>
                                    <th>Name</th>
                                    <th>Brand</th>
                                    <th>Category</th>
                                    <th>Color</th>
                                    <th className="num">Price</th>
                                    <th className="num">Stock</th>
                                    <th className="num">Sold</th>
                                    <th>Rating</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {products.map((p) => (
                                    <tr key={p.id} className={p.qty < 5 ? 'low-stock' : ''}>
                                        <td><span className="sku">{p.sku}</span></td>
                                        <td>{p.name}</td>
                                        <td>{p.brand || <span className="muted">—</span>}</td>
                                        <td>{p.category || <span className="muted">—</span>}</td>
                                        <td><ColorTag color={p.color} /></td>
                                        <td className="num">
                                            <PriceCell price={p.price} discount={p.discount_percent} />
                                        </td>
                                        <td className="num">
                                            {p.qty === 0
                                                ? <span className="stock-zero">0</span>
                                                : p.qty}
                                        </td>
                                        <td className="num">{p.sold_count}</td>
                                        <td><RatingCell rating={p.rating} count={p.review_count} /></td>
                                        <td className="actions">
                                            <button
                                                className="icon-btn"
                                                title="ขาย"
                                                onClick={() => setSellTarget(p)}
                                                disabled={p.qty <= 0}
                                            >
                                                <IconCartSm size={15} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {products.length === 0 && (
                                    <tr><td colSpan={10} className="empty">No products found · try adjusting filters</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    <div className="pagination">
                        <div className="pagination-left">
                            <span>Rows per page:</span>
                            <select
                                className="page-size-select"
                                value={pageSize}
                                onChange={(e) => {
                                    const newSize = parseInt(e.target.value, 10);
                                    setPageSize(newSize);
                                    refresh(1, newSize);
                                }}
                            >
                                {PAGE_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
                            </select>
                        </div>
                        <div className="pagination-right">
                            <button onClick={() => refresh(1, pageSize)} disabled={page === 1}>«</button>
                            <button onClick={() => refresh(page - 1, pageSize)} disabled={page === 1}>‹ Prev</button>
                            <span>Page {page} of {totalPages}</span>
                            <button onClick={() => refresh(page + 1, pageSize)} disabled={page >= totalPages}>Next ›</button>
                            <button onClick={() => refresh(totalPages, pageSize)} disabled={page >= totalPages}>»</button>
                        </div>
                    </div>
                </section>
            </div>

            {sellTarget && (
                <SellModal
                    product={sellTarget}
                    onClose={() => setSellTarget(null)}
                    onConfirm={(amount) => confirmSell(sellTarget, amount)}
                />
            )}

            {chatOpen && (
                <div className="chat-popup" role="dialog">
                    <div className="chat-header">
                        <div>
                            <div className="title">AI Assistant</div>
                            <div className="subtitle">ถามเรื่อง สต็อก · ลูกค้า · ยอดขาย</div>
                        </div>
                        <button className="chat-close" onClick={() => setChatOpen(false)}>
                            <IconClose size={16} />
                        </button>
                    </div>
                    <div className="chat-body" ref={bodyRef}>
                        {messages.map((m, i) => (
                            <div key={i} className={'msg ' + m.role + (m.error ? ' error' : '')}>{m.text}</div>
                        ))}
                        {sending && <div className="typing"><span /><span /><span /></div>}
                    </div>
                    {messages.length <= 1 && !sending && (
                        <div className="suggestions">
                            {SUGGESTIONS.map((s) => (
                                <button key={s} onClick={() => send(s)}>{s}</button>
                            ))}
                        </div>
                    )}
                    <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
                        <input
                            placeholder="ถาม AI..."
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            disabled={sending}
                        />
                        <button className="chat-send" type="submit" disabled={sending || !question.trim()}>
                            <IconArrowUp size={16} />
                        </button>
                    </form>
                </div>
            )}

            <button className="chat-fab" onClick={() => setChatOpen((o) => !o)}>
                {chatOpen ? <IconClose size={20} /> : <IconChat size={20} />}
            </button>
        </div>
    );
}

function SellModal({ product, onClose, onConfirm }) {
    const [amount, setAmount] = useState('1');
    const [submitting, setSubmitting] = useState(false);
    const eff = Number(product.price || 0) * (1 - Number(product.discount_percent || 0) / 100);
    const n = parseInt(amount, 10);
    const valid = Number.isFinite(n) && n > 0 && n <= product.qty;
    const lineTotal = valid ? eff * n : 0;

    const submit = async (e) => {
        e?.preventDefault();
        if (!valid || submitting) return;
        setSubmitting(true);
        try { await onConfirm(n); } finally { setSubmitting(false); }
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>ขายสินค้า</h3>
                    <button className="chat-close" onClick={onClose} aria-label="ปิด">
                        <IconClose size={16} />
                    </button>
                </div>
                <form className="modal-body" onSubmit={submit}>
                    <div className="sell-product">
                        <div className="sell-product-name">{product.name}</div>
                        <div className="sell-product-meta">
                            <span className="sku">{product.sku}</span>
                            {product.color && <ColorTag color={product.color} />}
                        </div>
                    </div>

                    <div className="sell-info">
                        <div>
                            <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>คงเหลือ</div>
                            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>{product.qty}</div>
                        </div>
                        <div>
                            <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>ราคา/ชิ้น</div>
                            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>{fmtTHB(eff)}</div>
                        </div>
                    </div>

                    <label className="field">
                        <span>จำนวนที่ต้องการขาย</span>
                        <input
                            className="input"
                            type="number"
                            min="1"
                            max={product.qty}
                            value={amount}
                            autoFocus
                            onChange={(e) => setAmount(e.target.value)}
                        />
                    </label>

                    <div className="sell-summary">
                        <span className="muted">ยอดรวม</span>
                        <span className="sell-total">{fmtTHB(lineTotal)}</span>
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="btn-secondary" onClick={onClose}>ยกเลิก</button>
                        <button type="submit" className="btn" disabled={!valid || submitting}>
                            {submitting ? 'กำลังขาย...' : `ขาย ${valid ? n : ''} ชิ้น`}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
