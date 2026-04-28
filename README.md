# Stock Project — Full-stack + AI

ระบบจัดการสต็อกสินค้า + AI Chat ที่คุยกับ DB จริงผ่าน tool-calling agent

```
stock-project/
├── README.md                ← ไฟล์นี้ (overview)
├── .gitignore
├── database/
│   └── schema.sql           ← PostgreSQL schema + seed
├── backend/                 ← Express + pg  (port 4000)
│   └── README.md            ← วิธี setup + run
├── frontend/                ← React + Vite (port 5173)
│   └── README.md            ← วิธี setup + run
└── ai-service/              ← FastAPI tool-calling agent (port 8000)
    └── README.md            ← วิธี setup + run
```

---

## 📚 เอกสารแยกตามระบบ

| ระบบ | Port | คู่มือ |
|---|---|---|
| **Database** (Postgres) | 5432 | ดู [database/schema.sql](database/schema.sql) |
| **Backend** (Express + pg) | 4000 | [backend/README.md](backend/README.md) |
| **Frontend** (React + Vite) | 5173 | [frontend/README.md](frontend/README.md) |
| **AI Service** (FastAPI + Ollama) | 8000 | [ai-service/README.md](ai-service/README.md) |

---

## ▶️ Quick Start (รันทั้ง 4 ระบบ)

ใช้ 4 terminal แยกกัน — แต่ละ service ปล่อยรันค้างไว้

### 0. Database (ครั้งแรกเท่านั้น)
```bash
createdb -U postgres cms_stock
psql -U postgres -d cms_stock -f database/schema.sql
```

### 1. Backend (terminal 1)
```bash
cd backend
npm install         # ครั้งแรก
cp .env.example .env  # ครั้งแรก
npm start
# → http://localhost:4000
```

### 2. Frontend (terminal 2)
```bash
cd frontend
npm install         # ครั้งแรก
cp .env.example .env  # ครั้งแรก
npm run dev
# → http://localhost:5173
```

### 3. AI Service (terminal 3)
```bash
cd ai-service
python -m venv .venv               # ครั้งแรก
.venv\Scripts\activate             # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt    # ครั้งแรก
cp .env.example .env               # ครั้งแรก
uvicorn main:app --port 8000
# → http://localhost:8000
```

### 4. Ollama (terminal 4 — ครั้งแรกเท่านั้น)
```bash
ollama pull qwen2.5:14b
# Ollama daemon รันเป็น service อยู่แล้วหลังติดตั้ง — port 11434
```

จากนั้นเปิด browser → http://localhost:5173 → ใช้งานได้เลย

---

## 🏗 Architecture

```
┌──────────────┐      HTTP        ┌─────────────────┐      SQL        ┌──────────────┐
│              ├─────────────────▶│                 ├────────────────▶│              │
│   Frontend   │                  │     Backend     │                 │  PostgreSQL  │
│  (React 5173)│                  │  (Express 4000) │                 │  (cms_stock) │
│              │◀─────────────────│                 │◀────────────────│              │
└──────┬───────┘                  └─────────────────┘                 └──────┬───────┘
       │                                                                    ▲
       │  HTTP                                                              │ SQL
       ▼                                                                    │
┌──────────────┐  HTTP   ┌─────────────────┐                                │
│              ├────────▶│                 │────────────────────────────────┘
│  AI Service  │         │     Ollama      │
│ (FastAPI     │◀────────│  (qwen2.5:14b)  │
│  8000)       │         │                 │
└──────────────┘         └─────────────────┘
```

---

## 📋 ความสามารถหลัก

| Feature | ผ่านระบบไหน |
|---|---|
| ดูรายการสินค้า + ราคา + สี + qty + ขายแล้ว | Frontend → Backend → DB |
| เพิ่ม / แก้ไข / ขาย สินค้า | Frontend → Backend → DB |
| Filter ตามสี | Frontend (client-side) |
| Highlight ใกล้หมด | Frontend |
| มูลค่าสต็อก (SUM(qty×price)) | Frontend |
| 💬 ถาม AI (ภาษาธรรมชาติ) | Frontend → AI Service → Ollama + DB |
| AI เข้าใจคำพิมพ์ผิด (fuzzy) | AI Service ใช้ pg_trgm |
| AI เลือก tool เอง 15 ตัว | AI Service (tool-calling agent) |
| AI ปฏิเสธคำถามนอกเรื่อง | AI Service (system prompt) |

---

## 🔄 ย้าย AI Service ไป project อื่น

ดูรายละเอียดใน [ai-service/README.md](ai-service/README.md)

สรุปสั้น — แค่ 2 ไฟล์เท่านั้นที่ต้องแก้ไข:
- `tools/sql_tool.py` (queries ของ DB ใหม่)
- `tools/stock_tools.py` → rename เป็น `<your_domain>_tools.py`

---

## 📦 Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 14+ + `pg_trgm` extension |
| Backend | Node.js 18+ / Express 4 / `pg` |
| Frontend | React 18 / Vite 5 / axios |
| AI Service | Python 3.10+ / FastAPI / `psycopg[binary]` / `httpx` |
| LLM | Ollama (`qwen2.5:14b`) — สลับเป็น Claude API ได้ |

---

## 🐛 Troubleshooting

ดูในแต่ละ README ของระบบนั้น ๆ:
- DB issues → [backend/README.md](backend/README.md#-troubleshooting)
- Frontend issues → [frontend/README.md](frontend/README.md#-troubleshooting)
- AI issues → [ai-service/README.md](ai-service/README.md#-troubleshooting)
