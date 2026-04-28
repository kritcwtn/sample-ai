# Backend — Stock API (Express + PostgreSQL)

REST API สำหรับจัดการสินค้า — ใช้ Express + node-postgres (`pg`)

---

## ⚙️ Requirements

| Tool | Version |
|---|---|
| Node.js | 18+ (แนะนำ 20+) |
| PostgreSQL | 14+ |

---

## 📦 Installation (ครั้งแรก)

### 1. ตรวจ Node version
```bash
node -v
# ต้อง >= 18
```

ถ้ายังไม่มี → ดาวน์โหลด https://nodejs.org/

### 2. เตรียม Database
สมมติเรามี PostgreSQL พร้อม user `postgres` password `root`:

```bash
# สร้าง DB
createdb -U postgres cms_stock

# โหลด schema + seed
psql -U postgres -d cms_stock -f ../database/schema.sql
```

ตรวจ:
```bash
psql -U postgres -d cms_stock -c "SELECT id, name, qty, price FROM products;"
```

### 3. ติดตั้ง dependencies
```bash
cd backend
npm install
```

### 4. ตั้งค่า environment
```bash
cp .env.example .env
```

แก้ `.env` ให้ตรง:
```ini
PORT=4000
DATABASE_URL=postgres://postgres:root@localhost:5432/cms_stock
```

---

## ▶️ Run

```bash
cd backend
npm start
```

ถ้าเห็นบรรทัดนี้ = สำเร็จ:
```
Stock backend running on http://localhost:4000
```

⚠️ ห้ามปิด terminal — เปิดอันใหม่ถ้าต้องใช้ shell อื่น
หยุด service: `Ctrl + C`

### Dev mode (auto-reload)
```bash
npm run dev
```

---

## 🧪 ทดสอบ API

```bash
# Health
curl http://localhost:4000/health

# List ทุกสินค้า
curl http://localhost:4000/products

# สินค้าใกล้หมด (qty < 5)
curl http://localhost:4000/products/low-stock

# เพิ่มสินค้าใหม่
curl -X POST http://localhost:4000/products \
     -H "Content-Type: application/json" \
     -d "{\"name\":\"Apple Watch\",\"qty\":7,\"price\":13900,\"color\":\"Midnight\"}"

# แก้ไข
curl -X PUT http://localhost:4000/products/6 \
     -H "Content-Type: application/json" \
     -d "{\"qty\":10,\"price\":12900}"

# ขาย 2 ชิ้น (qty -= 2, sold_count += 2 atomic)
curl -X POST http://localhost:4000/products/1/sell \
     -H "Content-Type: application/json" \
     -d "{\"amount\":2}"
```

---

## 🔌 API Reference

| Method | Path | Body | คืน |
|---|---|---|---|
| `GET` | `/health` | — | `{ok: true}` |
| `GET` | `/products` | — | `[product...]` |
| `GET` | `/products/low-stock` | — | `[product...]` (qty < 5) |
| `POST` | `/products` | `{name, qty, price?, color?}` | `product` ใหม่ |
| `PUT` | `/products/:id` | `{name?, qty?, price?, color?}` | `product` ที่อัปเดต |
| `POST` | `/products/:id/sell` | `{amount}` | `product` (qty -= amount) |

### Product shape
```json
{
  "id": 1,
  "name": "iPhone 15 Pro",
  "qty": 8,
  "sold_count": 51,
  "price": "39900.00",
  "color": "Natural Titanium",
  "created_at": "2026-04-27T14:44:44.690Z"
}
```

### Error responses
| Status | Body | เกิดเมื่อ |
|---|---|---|
| `400` | `{error: "name_required"}` | name ว่าง |
| `400` | `{error: "qty_invalid"}` | qty ไม่ใช่ int >= 0 |
| `400` | `{error: "price_invalid"}` | price < 0 |
| `400` | `{error: "insufficient_qty", available: N}` | สั่งขายเกินสต็อก |
| `404` | `{error: "not_found"}` | ไม่เจอ id |
| `500` | `{error: "db_error"}` | DB ดับ |

---

## 🗂 โครงสร้างไฟล์

```
backend/
├── README.md            ← ไฟล์นี้
├── server.js            ← Express app + routes
├── db.js                ← pg.Pool config
├── package.json
└── .env.example
```

---

## 🐛 Troubleshooting

### `Error: connect ECONNREFUSED 127.0.0.1:5432`
PostgreSQL ไม่ได้เปิด — เช็ค service:
```bash
# Windows
sc query postgresql-x64-18
# Linux
sudo systemctl status postgresql
```

### `Error: password authentication failed`
แก้ `DATABASE_URL` ใน `.env` ให้ user/password ตรงกับที่ตั้งไว้

### `Error: relation "products" does not exist`
ยังไม่ได้รัน schema — กลับไปทำ Step 2 (โหลด schema)

### `Error: listen EADDRINUSE: address already in use 4000`
มี service อื่นครอง port 4000 — หา + kill:
```powershell
# Windows PowerShell
$p = (Get-NetTCPConnection -LocalPort 4000 -State Listen).OwningProcess
Stop-Process -Id $p -Force
```
หรือเปลี่ยน `PORT` ใน `.env`
