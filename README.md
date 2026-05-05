# Stock Project

ระบบจัดการสต็อก + AI Chat ที่คุย DB จริง — แบ่งเป็น 4 service

```
stock-project/
├── database/      ← PostgreSQL schema + seed
├── backend/       ← Express + pg          (port 4000)
├── frontend/      ← React + Vite          (port 5173)
└── ai-service/    ← FastAPI tool-calling  (port 8000)
```

| Service | Port | คู่มือ setup + run |
|---|---|---|
| Database | 5432 | [database/schema.sql](database/schema.sql) |
| Backend | 4000 | [backend/README.md](backend/README.md) |
| Frontend | 5173 | [frontend/README.md](frontend/README.md) |
| AI Service | 8000 | [ai-service/README.md](ai-service/README.md) |

---

## ⚙️ Prerequisites (ครั้งแรก)

| Tool | Version |
|---|---|
| Node.js | 18+ |
| Python | 3.10+ |
| PostgreSQL | 14+ |
| Ollama | latest (ถ้าใช้ LLM แบบ local) |

---

## 🚀 Quick Start

> รายละเอียดแต่ละ service ดูใน README ของ folder นั้น ๆ

### Step 0 — Database (ครั้งเดียว)

```bash
createdb -U postgres cms_stock
psql -U postgres -d cms_stock -f database/schema.sql
# (ถ้าต้องการ seed ตัวอย่าง 16k rows)
python ai-service/.venv/Scripts/python database/seed.py
```

### Step 1-3 — รัน 3 services (3 terminals แยก)

**Terminal 1 — Backend** (`http://localhost:4000`)
```bash
cd backend
npm install                      # ครั้งแรก
cp .env.example .env             # ครั้งแรก
npm start
```

**Terminal 2 — Frontend** (`http://localhost:5173`)
```bash
cd frontend
npm install                      # ครั้งแรก
cp .env.example .env             # ครั้งแรก
npm run dev
```

**Terminal 3 — AI Service** (`http://localhost:8000`)
```bash
cd ai-service
python -m venv .venv             # ครั้งแรก
.venv\Scripts\activate           # Windows
pip install -r requirements.txt  # ครั้งแรก
cp .env.example .env             # ครั้งแรก
uvicorn main:app --port 8000
```

### Step 4 — Ollama (ถ้าใช้ LLM local) ครั้งเดียว

```bash
ollama pull qwen2.5:7b
```

→ เปิด browser ที่ http://localhost:5173

---

## 📦 Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 14+ (+ `pg_trgm`) |
| Backend | Node.js / Express / `pg` |
| Frontend | React + Vite + axios |
| AI Service | Python / FastAPI / `psycopg` |
| LLM | Ollama (qwen2.5) หรือ Claude API |

---

## 🆘 Troubleshooting

แต่ละ service มี section troubleshooting เฉพาะใน README ของตัวเอง:
- [backend/README.md](backend/README.md#-troubleshooting)
- [frontend/README.md](frontend/README.md#-troubleshooting)
- [ai-service/README.md](ai-service/README.md#-troubleshooting)

---

## 📚 หัวข้ออื่น ๆ

- **AI Architecture / tool calling agent** → [ai-service/README.md](ai-service/README.md)
- **API endpoints** → [backend/README.md](backend/README.md)
- **UI features** → [frontend/README.md](frontend/README.md)
- **ย้าย AI ไป project อื่น** → [ai-service/README.md](ai-service/README.md#-ย้ายไป-project-ใหม่)
