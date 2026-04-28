# AI Service — Tool-Calling Agent

FastAPI ที่ฝัง LLM agent (Ollama หรือ Claude) เลือก tool จาก natural language เอง
ออกแบบให้ reuse ข้าม project ได้ — แค่เปลี่ยน `tools/sql_tool.py` + `tools/<project>_tools.py`

---

## ⚙️ Requirements

| Tool | Version | หมายเหตุ |
|---|---|---|
| Python | 3.10+ | venv |
| PostgreSQL | 14+ | ต้องเปิด extension `pg_trgm` ได้ |
| Ollama | latest | https://ollama.com/download |
| RAM | 8 GB ขั้นต่ำ | 16 GB แนะนำสำหรับ qwen2.5:14b |
| Disk | 10 GB | สำหรับ model file |

---

## 📦 Installation (ครั้งแรก)

### 1. ติดตั้ง Ollama
- ดาวน์โหลด installer: https://ollama.com/download/windows
- ติดตั้ง — Ollama จะรันเป็น service ที่ port `11434` อัตโนมัติ
- ตรวจสอบ:
  ```bash
  curl http://localhost:11434/api/tags
  ```

### 2. โหลด LLM model
แนะนำ `qwen2.5:14b` (tool calling ดี) — ใช้ disk ~9GB
```bash
ollama pull qwen2.5:14b
```

ถ้าเครื่องไม่แรง ใช้รุ่นเล็กลง:
```bash
ollama pull qwen2.5:7b      # 4.7GB
# หรือ
ollama pull llama3.1:8b     # 4.9GB
```

### 3. เปิด PostgreSQL extension `pg_trgm`
ใช้สำหรับ fuzzy search รองรับการพิมพ์ผิด
```bash
psql -U postgres -d <your_db_name> -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

### 4. สร้าง Python virtual environment
```bash
cd ai-service
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate
```

### 5. ติดตั้ง dependencies
```bash
pip install -r requirements.txt
```

### 6. ตั้งค่า environment
```bash
cp .env.example .env
```

แก้ไข `.env`:
```ini
# เลือก provider
LLM_PROVIDER=ollama          # หรือ claude

# ใช้ Ollama (local, ฟรี)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# ใช้ Claude (จ่ายเงิน, เร็ว/แม่นกว่า)
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6

# PostgreSQL connection
DATABASE_URL=postgres://postgres:root@localhost:5432/cms_stock
```

---

## ▶️ Run

```bash
cd ai-service
.venv\Scripts\activate     # Windows  (Linux/Mac: source .venv/bin/activate)
uvicorn main:app --port 8000
```

ถ้าเห็นบรรทัดนี้แสดงว่ารันสำเร็จ:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

⚠️ **ห้ามปิด terminal นี้** — เปิดอันใหม่หากต้องใช้ shell อื่น

หยุด service: กด `Ctrl + C`

---

## 🧪 ทดสอบ

### Health check
```bash
curl http://localhost:8000/health
```
ตอบ:
```json
{"ok": true, "provider": "ollama", "tools": ["list_products", "get_low_stock", ...]}
```

### ถาม chatbot
```bash
curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d "{\"question\":\"สินค้าไหนใกล้หมด\"}"
```

ตอบ:
```json
{
  "answer": "สินค้าที่ใกล้หมดคือ AirPods Pro 2 (1), iPad Air (2), MacBook Air M3 (3)",
  "tools_used": [{"name": "get_low_stock", "arguments": {"threshold": 5}, "result": [...]}]
}
```

---

## 🗂 โครงสร้างไฟล์

```
ai-service/
├── README.md            ← ไฟล์นี้
├── main.py              ← FastAPI endpoint
├── agent.py             ← Agent loop (LLM → tool → reply)
├── requirements.txt
├── .env.example
├── llm/
│   ├── base.py          ← LLMProvider interface + ChatTurn + ToolCall
│   ├── ollama.py        ← Ollama implementation
│   └── claude.py        ← Anthropic implementation
└── tools/
    ├── base.py          ← BaseTool + ToolRegistry (project-agnostic)
    ├── sql_tool.py      ← raw DB queries (project-specific)
    └── stock_tools.py   ← tool definitions (project-specific)
```

---

## 🔄 ย้ายไป project ใหม่

ดู section `Migration` ในไฟล์ `../README.md` ของ project root

สรุปสั้น:
1. Copy `ai-service/` ทั้งโฟลเดอร์
2. แทนที่ `tools/sql_tool.py` (queries ของ DB ใหม่)
3. แทนที่ `tools/stock_tools.py` ด้วย `tools/<your_domain>_tools.py`
4. แก้ `main.py` 2 บรรทัด (import + register)
5. แก้ `agent.py::SYSTEM_PROMPT` (เปลี่ยน domain)
6. แก้ `.env::DATABASE_URL`

ของที่ **ไม่ต้องแตะ** ตอนย้าย:
- `agent.py` (ยกเว้น SYSTEM_PROMPT 1 บรรทัด)
- `llm/*.py`
- `tools/base.py`

---

## 🐛 Troubleshooting

### `ollama is not recognized as a command`
- เปิด terminal ใหม่ (PATH ยังไม่โหลด) หรือใช้ full path:
  ```
  "C:\Users\<user>\AppData\Local\Programs\Ollama\ollama.exe"
  ```

### `[Errno 10048] address already in use`
- มี service ครองพอร์ต 8000 อยู่แล้ว — ปิดก่อน:
  ```powershell
  $p = (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
  Stop-Process -Id $p -Force
  ```

### `404 Not Found for /api/generate`
- Model ที่ตั้งใน `OLLAMA_MODEL` ไม่มีใน Ollama
  ```bash
  ollama list
  ollama pull <model>
  ```

### `ANTHROPIC_API_KEY is not set`
- เกิดเมื่อ `LLM_PROVIDER=claude` แต่ลืมใส่ key — ใส่ใน `.env`

### AI ตอบช้ามาก (>30s)
- Model ใหญ่เกิน VRAM → overflow มา CPU
- ตรวจ:
  ```bash
  ollama ps
  ```
  ถ้าเห็น `80%/20% CPU/GPU` แปลว่า model ไม่ลง VRAM
- ทางแก้: ใช้ model เล็กลง (`qwen2.5:7b`) หรือเปลี่ยนเป็น Claude API

### AI ตอบมีอักษรจีนปน
- มี post-processing strip CJK อยู่แล้วใน `agent.py::_strip_cjk()`
- ถ้ายังเจอ → ตั้ง `LLM_PROVIDER=claude` (ไม่มีปัญหานี้)

### AI ไม่เข้าใจคำพิมพ์ผิด
- ตรวจว่า `pg_trgm` extension เปิดแล้ว:
  ```sql
  SELECT * FROM pg_extension WHERE extname = 'pg_trgm';
  ```
- ถ้ายัง: รัน `CREATE EXTENSION pg_trgm;`

---

## 📝 รายการ tool ปัจจุบัน (stock domain) — 15 ตัว

### พื้นฐาน
| Tool | หน้าที่ |
|---|---|
| `list_products` | รายการสินค้าทั้งหมด |
| `get_low_stock(threshold=5)` | สินค้าที่ qty < threshold |
| `get_out_of_stock` | สินค้าที่ qty = 0 |
| `get_best_sellers(limit=5)` | สินค้าขายดีอันดับต้น |
| `get_bottom_sellers(limit=5)` | สินค้าขายไม่ดี |
| `search_products_by_name(keyword)` | ค้นชื่อ + fuzzy match (รองรับพิมพ์ผิด) |
| `get_total_stock` | รวมสต็อกคงเหลือ |
| `get_total_sold` | รวมยอดขายสะสม |
| `get_critical_alerts(threshold=5)` | composable: รวม out_of_stock + low_stock |

### ราคา + สี
| Tool | หน้าที่ |
|---|---|
| `get_total_stock_value` | มูลค่าสต็อก: SUM(qty × price) |
| `get_total_revenue` | รายได้สะสม: SUM(sold_count × price) |
| `get_products_by_color(color)` | filter ตามสี |
| `get_products_by_price_range(min, max)` | filter ตามช่วงราคา |
| `get_most_expensive(limit=5)` | สินค้าราคาแพงสุด |
| `get_cheapest(limit=5)` | สินค้าราคาถูกสุด |

### เพิ่ม tool ใหม่
1. สร้าง class ใน `tools/stock_tools.py` ที่สืบทอด `BaseTool` พร้อม description ที่มี:
   - `When to use` / `When NOT to use`
   - `Arguments` พร้อม range
   - `Examples`
2. เพิ่มใน `_ALL_TOOLS` tuple → `register_all()` จัดการให้
3. Restart service — LLM จะเริ่มใช้ tool ใหม่ทันที (ไม่ต้องแก้ logic)

> 💡 ที่สำคัญ: **description ดี = LLM เลือก tool ถูก** อ่าน existing tool ใน
> `tools/stock_tools.py` เป็น template

---

## 📊 Observability

ทุก request มี `request_id` 12 ตัวอักษร ตามไปถึง:
- HTTP middleware
- Agent loop
- ทุก SQL query
- Tool execution

ดูเฉพาะ 1 request:
```bash
tail -f ai-service.log | jq 'select(.request_id=="abc123def456")'
```

ดู query ที่ช้ากว่า 1s:
```bash
tail -f ai-service.log | jq 'select(.event=="sql.query" and .duration_ms>1000)'
```

ดู tool ที่ถูกเรียก:
```bash
tail -f ai-service.log | jq 'select(.event=="agent.tool")'
```

ตอนนี้ log ออก stdout เท่านั้น — ดู File logging ในส่วน Troubleshooting
