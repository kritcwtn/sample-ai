# Frontend — Stock Manager (React + Vite)

UI สำหรับดู/เพิ่ม/แก้ไข/ขายสินค้า + Chat กับ AI assistant

---

## ⚙️ Requirements

| Tool | Version |
|---|---|
| Node.js | 18+ (แนะนำ 20+) |
| Backend | http://localhost:4000 (ต้องรันก่อน) |
| AI Service | http://localhost:8000 (optional — ใช้ปุ่ม chat) |

---

## 📦 Installation (ครั้งแรก)

### 1. ติดตั้ง dependencies
```bash
cd frontend
npm install
```

### 2. ตั้งค่า environment
```bash
cp .env.example .env
```

แก้ `.env` ตามที่ backend / ai-service รันอยู่:
```ini
VITE_BACKEND_URL=http://localhost:4000
VITE_AI_URL=http://localhost:8000
```

> ⚠️ ตัวแปรต้องขึ้นด้วย `VITE_` ไม่งั้น Vite จะไม่ส่งให้ browser

---

## ▶️ Run (Dev mode)

```bash
cd frontend
npm run dev
```

ถ้าเห็นบรรทัดนี้ = สำเร็จ:
```
  VITE v5.x  ready in 250 ms

  ➜  Local:   http://localhost:5173/
```

→ เปิด browser ที่ http://localhost:5173

⚠️ ห้ามปิด terminal — Vite จะหยุดทันที
หยุด: `Ctrl + C`

### Production build
```bash
npm run build         # สร้าง dist/
npm run preview       # ดู preview ก่อน deploy
```

---

## 🎨 Features

| Feature | คำอธิบาย |
|---|---|
| **Stats card** 5 ใบ | จำนวนสินค้า, รวมสต็อก, ขายไปแล้ว, มูลค่าสต็อก, ใกล้หมด |
| **ตารางสินค้า** | ID, ชื่อ, สี (มี swatch), ราคา (THB), คงเหลือ, ขายแล้ว, สถานะ |
| **Filter สี** | dropdown กรองสินค้าตามสี |
| **Highlight ใกล้หมด** | แถวสีเหลือง เมื่อ qty < 5 |
| **🛒 ปุ่มขาย** | popup ถามจำนวน → ลด qty + เพิ่ม sold_count |
| **✏️ ปุ่มแก้ไข** | modal แก้ name / สี / ราคา / qty |
| **+ เพิ่มสินค้า** | form 4 ช่อง (ชื่อ/สี/ราคา/จำนวน) |
| **💬 Floating chat** | ปุ่มมุมขวาล่าง → popup คุยกับ AI |

---

## 🗂 โครงสร้างไฟล์

```
frontend/
├── README.md            ← ไฟล์นี้
├── index.html           ← Vite entry
├── vite.config.js       ← config (port, plugin)
├── package.json
├── .env.example
└── src/
    ├── main.jsx         ← React mount + import CSS
    ├── App.jsx          ← UI หลัก + EditModal + ColorTag
    ├── App.css          ← styles ทั้งหมด
    └── api.js           ← axios wrappers (listProducts, addProduct, ...)
```

---

## 🔗 ติดต่อ Backend / AI Service

`src/api.js` ใช้ `axios` เรียก:

```js
// Backend
listProducts()                            // GET /products
addProduct({name, qty, price, color})     // POST /products
updateProduct(id, patch)                  // PUT /products/:id
sellProduct(id, amount)                   // POST /products/:id/sell

// AI Service
askAI(question)                           // POST /chat
```

URL อ่านจาก env:
- `VITE_BACKEND_URL` → backend
- `VITE_AI_URL` → AI service

---

## 🐛 Troubleshooting

### `Network Error` ตอนกดปุ่มอะไร
- **Backend ไม่ได้เปิด** — ตรวจที่ port 4000:
  ```bash
  curl http://localhost:4000/health
  ```
  ถ้าไม่ตอบ → ไปเปิด backend ก่อน (ดู backend/README.md)

### ปุ่ม "ถาม AI" ขึ้น Network Error
- **AI service ไม่ได้เปิด** — port 8000 ดู ai-service/README.md
- ปุ่มอื่น (list/เพิ่ม/แก้/ขาย) ไม่ได้ใช้ AI service จึงทำงานได้แม้ AI ดับ

### หน้าเว็บแสดง qty เก่า ทั้งที่กดเพิ่ม/ขายแล้ว
- โค้ดเรียก `refresh()` หลังทุก mutation อัตโนมัติ
- ถ้ายัง stale → กด F5 ล้าง cache

### `Error: Cannot find module '@vitejs/plugin-react'`
- รัน `npm install` ใหม่อีกครั้ง

### `Error: listen EADDRINUSE 5173`
- มี Vite อื่นรันอยู่ — kill หรือเปลี่ยน port:
  ```bash
  npm run dev -- --port 5174
  ```

### Browser cache เก่าหลัง update
- กด `Ctrl + Shift + R` (hard refresh) ใน browser
