# ForgeData

Evidence-grounded industrial product intelligence. Turns fragmented product
data (datasheets, images, incomplete catalogs, RFQs) into a complete,
validated, human-approved output — configuration, BOM, quote, datasheet,
installation package, or RFQ response.

Every field carries its source. Nothing gets invented. Conflicts and
high-risk fields always pause for human approval.

**→ Read `context.md`** for the full project brief.  
**→ Read `plan.md`** for the backend microservices roadmap.

---

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| **Node.js** | 18+ | Frontend |
| **Python** | **3.12+** | Backend venv — **do not use 3.14** (deps not supported yet) |
| **Docker** | Colima or Docker Desktop | Optional if you use **Supabase** for Postgres + Storage. Otherwise Postgres + MinIO. |

---

## Run the full stack (first time)

### 1. Start infrastructure (Postgres + MinIO)

```bash
cd backend
cp .env.example .env
docker compose up -d
docker compose ps    # postgres + minio should be running/healthy
```

Postgres is on host port **5433** (not 5432) to avoid conflicts with local Postgres or Colima.

### 2. Set up backend (Python venv)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head               # must use venv alembic, not system python
```

Verify:

```bash
which alembic    # → .../backend/.venv/bin/alembic
python --version # → Python 3.12.x
```

### 3. Start backend services (gateway + microservices)

**Terminal 1 — backend:**

```bash
cd backend
source .venv/bin/activate
./scripts/run-dev.sh
```

This starts:

| Process | Port | Role |
| --- | --- | --- |
| Gateway | **8000** | Public API (frontend connects here) |
| project-service | 8001 | Job CRUD |
| file-service | 8002 | File uploads + MinIO |
| question-service | 8003 | Completeness + one-question loop |

Verify:

```bash
curl http://127.0.0.1:8000/health    # {"status":"ok","mode":"gateway"}
open http://127.0.0.1:8000/docs
```

### 4. Set up frontend

**Terminal 2 — frontend:**

```bash
cd /path/to/forge          # repo root (where package.json lives)
cp .env.example .env.local
npm install
npm run dev
```

`.env.local` must contain:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Open **http://localhost:3000**. Create a job with a file — it persists to Postgres (or Supabase) and object storage. Questions are live. Evidence is next (M4).

---

## Run every day

**Terminal 1 — backend:**

```bash
cd backend
docker compose up -d
source .venv/bin/activate
./scripts/run-dev.sh
```

**Terminal 2 — frontend:**

```bash
npm run dev
```

After pulling new backend migrations:

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

---

## Mock mode (no backend)

Leave `NEXT_PUBLIC_API_BASE_URL` unset in `.env.local` (or delete the file).
Run `npm run dev` only — the UI uses seeded mock data from `lib/mock-data.ts`.

---

## What's live today

**M1–M3 are done.** The next build is **M4 — evidence-service** (PDF → cited attributes).

| Feature | Status |
| --- | --- |
| Dashboard — list/create/remove jobs | ✅ Live API (M1) |
| Open a job — upload files | ✅ Live API (M2) |
| Questions + completion score | ✅ Live API (M3) |
| Evidence tab | ⏳ Next — M4 |
| Review, Outputs tabs | Mock / stub (M5–M8) |

Live frontend functions in `lib/api.ts`: `listProjects`, `getProject`, `createProject`, `deleteProject`, `uploadDocument`, `listQuestions`, `answerQuestion`.

Hosted DB/files: set `POSTGRES_*` and `OBJECT_STORAGE_*` in `backend/.env` (see **Switch to Supabase** in `backend/README.md`). Local Docker Postgres/MinIO still works.

---

## Ready for M4 — prerequisites

M4 is **evidence-service** (`:8004`). It reads uploaded PDFs, extracts text, stores chunks with embeddings (**pgvector**), and fills the Evidence tab with cited fields (`attribute`, `value`, `source`, `page`, `evidence`, `confidence`). It must **not** invent values.

You already have everything for a first M4 slice if:

| Need | Why | You have it when… |
| --- | --- | --- |
| M1–M3 running | Jobs, files, questions exist | Gateway `:8000` healthy; Questions tab works |
| PDFs on a job | Extractor needs bytes in object storage | Overview shows documents; bucket `forgedata` has `prj-…/doc-…/*.pdf` |
| Postgres | New tables: chunks, embeddings, attributes | Same DB as M1–M3 (local **5433** or **Supabase**) |
| **pgvector** | Vector search over page quotes | **Supabase:** already enabled. **Local Docker:** enable the extension in M4 (`CREATE EXTENSION vector`) |
| Python packages (added in M4) | `pymupdf` (text), `pgvector`, later OCR (`ocrmypdf`) if the PDF is a scan | Not installed yet — M4 will pin them in `backend/requirements.txt` |
| Embeddings API key | Turn chunks into vectors | Optional at the start (can hash/embed later). Set `LLM_API_KEY` / provider when retrieval is wired |

Not required for M4: Redis, LangGraph, review-service, or a separate vector host.

**Do this before writing M4 code:** pick one PDF job that already uploaded (e.g. a seeded datasheet). M4’s first test is: that file → attributes with page + quote on the Evidence tab.

Details: `plan.md` → **M4 — evidence-service**. Backend notes: `backend/README.md`.

---

## Troubleshooting

### `alembic`: `ModuleNotFoundError: No module named 'psycopg'`

You are using **system Python**, not the venv.

```bash
cd backend
source .venv/bin/activate
which alembic   # must point to backend/.venv/bin/alembic
alembic upgrade head
```

### Postgres: `connection refused` or `password authentication failed`

- Start Docker first: `colima start` or open Docker Desktop
- Run from `backend/`: `docker compose up -d`
- Use port **5433** in `backend/.env`:
  ```
  DATABASE_URL=postgresql+psycopg://forgedata:forgedata@localhost:5433/forgedata
  ```
- If port 5432 is taken, that is expected — use 5433

### Frontend: `Internal Server Error` on localhost:3000

- Do **not** add a `.babelrc` — Next.js uses SWC
- If `node_modules` is corrupt: `rm -rf node_modules .next && npm install`
- If port 3000 is busy: `lsof -ti :3000 | xargs kill -9`

### Upload fails / MinIO errors

```bash
cd backend
docker compose up -d
docker compose ps
```

MinIO console: http://127.0.0.1:9001 — login `forgedata` / `forgedata`

### Duplicate file upload (409)

Same file content uploaded twice to one job returns **409** with a message.
Retry with `intent=reupload` or `intent=replace` via `uploadDocument()` in `lib/api.ts`.

---

## Project structure

```
forge/
├── app/                 Next.js pages
├── components/          UI + feature components
├── lib/
│   ├── types.ts         canonical schema (keep in sync with backend)
│   └── api.ts           mock/live seam
├── backend/
│   ├── gateway/         public API :8000
│   ├── services/        project :8001, file :8002, question :8003
│   ├── shared/          schemas + DB models
│   └── README.md        backend details
├── plan.md              microservices build plan
└── context.md           architecture + rules
```

---

## Scripts

```bash
npm run dev        # frontend dev server (:3000)
npm run build      # production build
npm run typecheck  # tsc --noEmit
npm run lint       # next lint
```

Backend tests:

```bash
cd backend && source .venv/bin/activate && pytest
```

See **`backend/README.md`** for backend architecture, env vars, and API contract.
