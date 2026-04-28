import { useEffect, useMemo, useRef, useState } from 'react';
import { listProducts, addProduct, updateProduct, sellProduct, askAI } from './api.js';

const SUGGESTIONS = [
    'สินค้าตัวไหนใกล้หมดบ้าง',
    'สินค้าขายดีที่สุด',
    'มูลค่าสต็อกรวมเท่าไร',
];

const fmtTHB = (n) =>
    new Intl.NumberFormat('th-TH', { style: 'currency', currency: 'THB' }).format(Number(n) || 0);

// Map a few common color names to swatches; unknown colors fall back to a label only.
const COLOR_HEX = {
    'natural titanium': '#8e8e93',
    midnight: '#1f1f1f',
    'space gray': '#3a3a3c',
    silver: '#c7c7cc',
    white: '#f5f5f7',
    black: '#000',
    starlight: '#f6f0e0',
    blue: '#0a84ff',
    pink: '#ff66c4',
    red: '#ff3b30',
    green: '#30d158',
    yellow: '#ffd60a',
    purple: '#bf5af2',
};

function ColorTag({ color }) {
    if (!color) return <span className="muted">—</span>;
    const hex = COLOR_HEX[color.toLowerCase()];
    return (
        <span className="color-tag">
            {hex && <span className="swatch" style={{ background: hex }} />}
            {color}
        </span>
    );
}

export default function App() {
    const [products, setProducts] = useState([]);
    const [form, setForm] = useState({ name: '', qty: '', price: '', color: '' });
    const [err, setErr] = useState('');
    const [editing, setEditing] = useState(null);
    const [filterColor, setFilterColor] = useState('');

    const [chatOpen, setChatOpen] = useState(false);
    const [messages, setMessages] = useState([
        { role: 'bot', text: 'สวัสดี! ผมเป็นผู้ช่วยจัดการสต็อก ถามได้เลยครับ 👋' },
    ]);
    const [question, setQuestion] = useState('');
    const [sending, setSending] = useState(false);
    const bodyRef = useRef(null);

    const refresh = async () => {
        try {
            setProducts(await listProducts());
        } catch (e) {
            setErr('โหลดสินค้าล้มเหลว: ' + e.message);
        }
    };

    useEffect(() => { refresh(); }, []);
    useEffect(() => {
        if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }, [messages, chatOpen]);

    const colors = useMemo(() => {
        const set = new Set();
        products.forEach((p) => p.color && set.add(p.color));
        return Array.from(set).sort();
    }, [products]);

    const visibleProducts = useMemo(
        () => (filterColor ? products.filter((p) => p.color === filterColor) : products),
        [products, filterColor]
    );

    const onAdd = async (e) => {
        e.preventDefault();
        setErr('');
        if (!form.name.trim()) return setErr('กรุณากรอกชื่อสินค้า');
        const q = parseInt(form.qty, 10);
        if (!Number.isFinite(q) || q < 0) return setErr('qty ต้องเป็นจำนวนเต็ม >= 0');
        const p = form.price === '' ? 0 : parseFloat(form.price);
        if (!Number.isFinite(p) || p < 0) return setErr('ราคาต้อง >= 0');
        try {
            await addProduct({
                name: form.name.trim(),
                qty: q,
                price: p,
                color: form.color.trim() || null,
            });
            setForm({ name: '', qty: '', price: '', color: '' });
            await refresh();
        } catch (e) {
            setErr('เพิ่มสินค้าล้มเหลว: ' + e.message);
        }
    };

    const onSell = async (p) => {
        const input = prompt(`ขาย "${p.name}" จำนวนเท่าไร? (เหลือ ${p.qty})`, '1');
        if (input === null) return;
        const n = parseInt(input, 10);
        if (!Number.isFinite(n) || n <= 0) return setErr('จำนวนไม่ถูกต้อง');
        try {
            await sellProduct(p.id, n);
            await refresh();
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

    const totalQty = products.reduce((s, p) => s + p.qty, 0);
    const totalSold = products.reduce((s, p) => s + (p.sold_count || 0), 0);
    const lowCount = products.filter((p) => p.qty < 5).length;
    const stockValue = products.reduce(
        (s, p) => s + Number(p.qty) * Number(p.price || 0),
        0
    );

    return (
        <div className="app">
            <header className="header">
                <h1>
                    <span className="logo">📦</span>
                    Stock Manager
                </h1>
            </header>

            {err && <div className="alert" onClick={() => setErr('')}>{err}</div>}

            <div className="stats">
                <div className="stat">
                    <div className="label">รายการสินค้า</div>
                    <div className="value">{products.length}</div>
                </div>
                <div className="stat">
                    <div className="label">รวมสต็อก</div>
                    <div className="value">{totalQty}</div>
                </div>
                <div className="stat">
                    <div className="label">ขายไปแล้ว</div>
                    <div className="value">{totalSold}</div>
                </div>
                <div className="stat">
                    <div className="label">มูลค่าสต็อก</div>
                    <div className="value money">{fmtTHB(stockValue)}</div>
                </div>
                <div className="stat">
                    <div className="label">ใกล้หมด (qty &lt; 5)</div>
                    <div className={'value' + (lowCount > 0 ? ' warn' : '')}>{lowCount}</div>
                </div>
            </div>

            <section className="card">
                <div className="card-head">
                    <h2 className="card-title">รายการสินค้า</h2>
                    {colors.length > 0 && (
                        <div className="filter">
                            <label>สี:</label>
                            <select
                                value={filterColor}
                                onChange={(e) => setFilterColor(e.target.value)}
                            >
                                <option value="">ทั้งหมด</option>
                                {colors.map((c) => (
                                    <option key={c} value={c}>{c}</option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>
                <div className="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>ชื่อ</th>
                                <th>สี</th>
                                <th className="num">ราคา</th>
                                <th className="num">คงเหลือ</th>
                                <th className="num">ขายไปแล้ว</th>
                                <th>สถานะ</th>
                                <th style={{ textAlign: 'right' }}>จัดการ</th>
                            </tr>
                        </thead>
                        <tbody>
                            {visibleProducts.map((p) => (
                                <tr key={p.id} className={p.qty < 5 ? 'low-stock' : ''}>
                                    <td>{p.id}</td>
                                    <td>{p.name}</td>
                                    <td><ColorTag color={p.color} /></td>
                                    <td className="num money">{fmtTHB(p.price)}</td>
                                    <td className="num">{p.qty}</td>
                                    <td className="num">{p.sold_count}</td>
                                    <td>
                                        {p.qty < 5
                                            ? <span className="badge warn">ใกล้หมด</span>
                                            : <span className="badge ok">ปกติ</span>}
                                    </td>
                                    <td className="actions">
                                        <button className="icon-btn" title="ขาย"
                                                onClick={() => onSell(p)} disabled={p.qty <= 0}>🛒</button>
                                        <button className="icon-btn" title="แก้ไข"
                                                onClick={() => setEditing(p)}>✏️</button>
                                    </td>
                                </tr>
                            ))}
                            {visibleProducts.length === 0 && (
                                <tr><td colSpan={8} className="empty">ไม่พบสินค้าที่ตรงกับตัวกรอง</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            <section className="card">
                <h2 className="card-title">เพิ่มสินค้า</h2>
                <form className="form-grid" onSubmit={onAdd}>
                    <input className="input" placeholder="ชื่อสินค้า"
                           value={form.name}
                           onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    <input className="input" placeholder="สี (เช่น Black, Silver)"
                           value={form.color}
                           onChange={(e) => setForm({ ...form, color: e.target.value })} />
                    <input className="input" type="number" min="0" step="0.01" placeholder="ราคา"
                           value={form.price}
                           onChange={(e) => setForm({ ...form, price: e.target.value })} />
                    <input className="input" type="number" min="0" placeholder="จำนวน"
                           value={form.qty}
                           onChange={(e) => setForm({ ...form, qty: e.target.value })} />
                    <button className="btn" type="submit">+ เพิ่ม</button>
                </form>
            </section>

            {editing && (
                <EditModal
                    product={editing}
                    onClose={() => setEditing(null)}
                    onSaved={async () => { setEditing(null); await refresh(); }}
                    onError={setErr}
                />
            )}

            {chatOpen && (
                <div className="chat-popup" role="dialog" aria-label="AI Chat">
                    <div className="chat-header">
                        <div>
                            <div className="title">🤖 AI Assistant</div>
                            <div className="subtitle">ผู้ช่วยตอบเรื่องสต็อกสินค้า</div>
                        </div>
                        <button className="chat-close" onClick={() => setChatOpen(false)} aria-label="ปิด">✕</button>
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
                        <input placeholder="พิมพ์คำถาม..."
                               value={question}
                               onChange={(e) => setQuestion(e.target.value)}
                               disabled={sending} />
                        <button className="chat-send" type="submit"
                                disabled={sending || !question.trim()} aria-label="ส่ง">➤</button>
                    </form>
                </div>
            )}

            <button
                className="chat-fab"
                onClick={() => setChatOpen((o) => !o)}
                aria-label={chatOpen ? 'ปิด chat' : 'เปิด chat'}
                title="ถาม AI"
            >
                {chatOpen ? '✕' : '💬'}
            </button>
        </div>
    );
}

function EditModal({ product, onClose, onSaved, onError }) {
    const [form, setForm] = useState({
        name: product.name,
        qty: String(product.qty),
        price: String(product.price ?? 0),
        color: product.color ?? '',
    });
    const [saving, setSaving] = useState(false);

    const onSave = async (e) => {
        e.preventDefault();
        const q = parseInt(form.qty, 10);
        const p = form.price === '' ? 0 : parseFloat(form.price);
        if (!form.name.trim()) return onError('กรุณากรอกชื่อสินค้า');
        if (!Number.isFinite(q) || q < 0) return onError('qty ต้องเป็นจำนวนเต็ม >= 0');
        if (!Number.isFinite(p) || p < 0) return onError('ราคาต้อง >= 0');
        setSaving(true);
        try {
            await updateProduct(product.id, {
                name: form.name.trim(),
                qty: q,
                price: p,
                color: form.color.trim() || null,
            });
            await onSaved();
        } catch (e) {
            onError('แก้ไขไม่สำเร็จ: ' + (e.response?.data?.error || e.message));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>แก้ไขสินค้า #{product.id}</h3>
                    <button className="chat-close" onClick={onClose} aria-label="ปิด">✕</button>
                </div>
                <form className="modal-body" onSubmit={onSave}>
                    <label className="field">
                        <span>ชื่อสินค้า</span>
                        <input className="input" value={form.name}
                               onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    </label>
                    <label className="field">
                        <span>สี</span>
                        <input className="input" placeholder="เช่น Black, Silver" value={form.color}
                               onChange={(e) => setForm({ ...form, color: e.target.value })} />
                    </label>
                    <label className="field">
                        <span>ราคา (บาท)</span>
                        <input className="input" type="number" min="0" step="0.01" value={form.price}
                               onChange={(e) => setForm({ ...form, price: e.target.value })} />
                    </label>
                    <label className="field">
                        <span>จำนวนคงเหลือ</span>
                        <input className="input" type="number" min="0" value={form.qty}
                               onChange={(e) => setForm({ ...form, qty: e.target.value })} />
                    </label>
                    <div className="modal-actions">
                        <button type="button" className="btn-secondary" onClick={onClose}>ยกเลิก</button>
                        <button type="submit" className="btn" disabled={saving}>
                            {saving ? 'กำลังบันทึก...' : 'บันทึก'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
