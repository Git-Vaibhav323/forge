# ForgeData — Backend

Microservices behind a single **API gateway** on port **8000**. The frontend
only talks to the gateway; it proxies to internal services.

```
Frontend → gateway :8000 → project-service  :8001  (jobs CRUD)
                         → file-service     :8002  (uploads + MinIO)
                         → question-service :8003  (completeness loop)
                         → evidence-service :8004  (cited attributes / evidence)
                         → stub routers              (reviews, outputs, …)
```

---

## Prerequisites

- **Python 3.12+** (not 3.14 — pinned deps fail on 3.14)
- **Docker** (Colima or Docker Desktop) for Postgres + MinIO
- All commands below assume you are in **`backend/`** with the venv activated

---

## First-time setup (step by step)

### Step 1 — Docker infrastructure

```bash
cd backend
cp .env.example .env
docker compose up -d
```

Wait until both containers are up:

```bash
docker compose ps
```

Expected:

| Container | Port | Status |
| --- | --- | --- |
| `backend-postgres-1` | **5433** → 5432 | running (healthy) |
| `backend-minio-1` | **9000**, **9001** | running |

Verify Postgres:

```bash
docker port backend-postgres-1
# 5432/tcp -> 0.0.0.0:5433

docker exec backend-postgres-1 psql -U forgedata -d forgedata -c "SELECT 1;"
```

### Step 2 — Python virtualenv

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Always activate the venv** before running alembic, uvicorn, or pytest.

Confirm:

```bash
which python    # → .../backend/.venv/bin/python
which alembic   # → .../backend/.venv/bin/alembic
python --version # → Python 3.12.x
```

### Step 3 — Database migrations

```bash
source .venv/bin/activate
alembic upgrade head
```

Expected output includes:

```
Running upgrade  -> 001, create projects table
Running upgrade 001 -> 002, create documents table
Running upgrade 002 -> 003, create questions table
```

If you only see `001` and not `002`, you are already up to date.

### Step 4 — Start all backend services

```bash
source .venv/bin/activate
./scripts/run-dev.sh
```

Or separate terminals:

```bash
uvicorn services.project_service.main:app --reload --port 8001
uvicorn services.file_service.main:app --reload --port 8002
uvicorn services.question_service.main:app --reload --port 8003
uvicorn services.evidence_service.main:app --reload --port 8004
uvicorn gateway.main:app --reload --port 8000
```

### Step 5 — Verify backend

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8004/health
curl http://127.0.0.1:8000/api/projects
```

- API docs: http://127.0.0.1:8000/docs
- MinIO console: http://127.0.0.1:9001 (login `forgedata` / `forgedata`)

### Step 6 — Connect frontend

In repo root, create `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Restart Next.js (`npm run dev` from repo root).

---

## Daily startup

```bash
cd backend
docker compose up -d
source .venv/bin/activate
./scripts/run-dev.sh
```

In another terminal (repo root):

```bash
npm run dev
```

---

## M1 — Project persistence ✅ DONE

**Service:** `services/project_service/` on **:8001**

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/projects` | ✅ |
| `POST` | `/api/projects` | ✅ |
| `GET` | `/api/projects/{id}` | ✅ (includes `documents[]`) |
| `DELETE` | `/api/projects/{id}` | ✅ (job + questions + stored files) |

**Stack:** FastAPI, Pydantic, SQLAlchemy 2, PostgreSQL 16, Alembic, psycopg 3

---

## M2 — File uploads ✅ DONE

**Service:** `services/file_service/` on **:8002**

| Method | Path | Status |
| --- | --- | --- |
| `POST` | `/api/projects/{id}/files` | ✅ |

**Stack:** S3-compatible object storage (MinIO locally, or Supabase Storage), SHA-256 hash, PostgreSQL `documents` table

### Duplicate file handling

Same SHA-256 content on the same project:

| Request | Result |
| --- | --- |
| Default upload | **409** — message asks what you need differently |
| `?intent=reupload` | New document row (another copy) |
| `?intent=replace` | Swaps the existing stored file |

---

## Environment variables (`backend/.env`)

Copy from `.env.example`. Required for M1–M3:

| Variable | Value | Used by |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://forgedata:forgedata@localhost:5433/forgedata` | project + file services |
| `PROJECT_SERVICE_URL` | `http://localhost:8001` | gateway, file-service |
| `FILE_SERVICE_URL` | `http://localhost:8002` | gateway |
| `QUESTION_SERVICE_URL` | `http://localhost:8003` | gateway |
| `OBJECT_STORAGE_ENDPOINT` | `localhost:9000` | file-service |
| `OBJECT_STORAGE_ACCESS_KEY` | `forgedata` | file-service |
| `OBJECT_STORAGE_SECRET_KEY` | `forgedata` | file-service |
| `OBJECT_STORAGE_BUCKET` | `forgedata` | file-service |
| `OBJECT_STORAGE_SECURE` | `false` | file-service |
| `OBJECT_STORAGE_REGION` | `us-east-1` | file-service (Supabase: your project region) |
| `CORS_ORIGINS` | `http://localhost:3000` | all services |
| `POSTGRES_HOST` / `POSTGRES_PASSWORD` | (Supabase) | all DB services — preferred over a raw `DATABASE_URL` when the password contains `%` |

---

## M3 — Completeness / questions ✅ DONE

**Service:** `services/question_service/` on **:8003**

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/projects/{id}/questions` | ✅ |
| `POST` | `/api/projects/{id}/questions/{qid}/answer` | ✅ |

Required fields come from the job **goal + category**. One open question at a time. `"Not applicable"` completes a field; `"I don't know"` does not. Answers persist in `questions`; `completionScore` / `blockingFieldsCount` update on the job.

---

## M4 — evidence-service ✅ DONE

**Service:** `services/evidence_service/` on **:8004**. Powers the **Evidence** tab.

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/projects/{id}/attributes` | ✅ (stored, cited) |
| `POST` | `/api/projects/{id}/attributes/extract` | ✅ (re-scan PDFs + web) |

**File-service** also exposes web ingest (proxied through gateway):

| Method | Path | Status |
| --- | --- | --- |
| `POST` | `/api/projects/{id}/sources` | ✅ (URL fetch or pasted HTML) |

**How it works (key-free, no API key, no pgvector):** the service downloads each
PDF for the job from object storage, extracts text per page with `pypdf`, and
runs deterministic label→field rules (`extraction.py`). Every value it emits
carries the **document, page, and quoted line** it came from. Rules:

- A field with no supporting quote is reported `missing` — never invented.
- Two sources that disagree on the same field become `conflicting` (both quotes
  kept), not a silent merge. This drives `conflictsCount` on the job.
- Safety-critical fields (pressure, voltage, temperature, connection) carry a
  high/critical `riskLevel`.

The wire shape is the canonical `Attribute` + `Evidence`, identical to what a
semantic RAG pipeline would emit — so `parse_page` can later be swapped for
pgvector + embeddings **without touching the frontend or DB**.

### What you must configure

1. **Migrations:** `alembic upgrade head` (through revision `005` — `attributes`, `source_url`).
2. **Dependency:** `python -m pip install pypdf` (pinned in `requirements.txt`).
3. **`EVIDENCE_SERVICE_URL=http://localhost:8004`** in `backend/.env`.
4. Object storage + Postgres — **same as M1–M3**. **No API keys** for PDF or direct web fetch.

Not needed today: pgvector, embeddings key, Redis, Celery, OCR, **Apify**.

### Web page sources (direct fetch — live today)

Evidence tab → **Add a web source**, or `POST /api/projects/{id}/sources`:

```json
{ "url": "https://catalog.example.com/product/valve" }
```

The file-service fetches the page with **direct HTTP** (`WEB_FETCH_PROVIDER=direct`,
the default). HTML is stored in object storage as `type=web` with `sourceUrl`.
Evidence re-scan runs the same label→field rules as PDFs. Quotes show the URL
and **web** badge. PDF vs web disagreement → `conflicting` (feeds M5 Review).

**Paste HTML** (no network, no API):

```json
{
  "url": "https://catalog.example.com/product/valve",
  "html": "<html>…Model: ABC-100…</html>"
}
```

Use this when the site is JavaScript-heavy and direct fetch returns empty HTML.

### Web fetch providers (optional — not required now)

| `WEB_FETCH_PROVIDER` | Env vars | Status |
| --- | --- | --- |
| `direct` (default) | none | ✅ Live |
| `apify` | `APIFY_API_TOKEN`, `APIFY_ACTOR_ID` | ⏳ Placeholder — **not wired**; setting these does nothing yet |
| `custom` | `WEB_FETCH_API_URL`, optional `WEB_FETCH_API_KEY` | ✅ Live if you run your own fetch API |

If you created an Apify account and Actor, you can add credentials to `.env` for
later — ForgeData will not call Apify until `_fetch_apify` is implemented.
Until then, use **direct** or **paste HTML**.

Example `.env` for direct-only (recommended now):

```env
# WEB_FETCH_PROVIDER=direct   # omit or leave commented — same as direct
```

Do **not** set `WEB_FETCH_PROVIDER=apify` until the integration ships — you will
get HTTP 501 on URL-only ingest.

### How to test M4

- **Automated:** `python -m pytest tests/unit/test_evidence.py tests/module/test_evidence_api.py -q`
- **End to end:** start all services (`scripts/run-dev.ps1`), open a job, click **Evidence**.
  Upload a PDF or add a web URL, then re-scan. Seed PDF (`Meridian_MFC-GV-100`) shows
  `285 PSI`; `VB-220` datasheet + catalog pair shows **conflicting** pressure.

---

## Switch to Supabase (Postgres + Storage)

Local Docker Postgres/MinIO still works. To use a hosted Supabase project instead:

### 1. Create the project

1. Open [https://supabase.com/dashboard](https://supabase.com/dashboard) and create a project.
2. Save the **database password** you set at creation. You cannot see it again.

### 2. Database URL

**Project Settings → Database → Connection string → URI.**

Use the **Session pooler** (port **5432**). Do **not** use transaction pooler port **6543** — SQLAlchemy/Alembic need session mode.

Replace `[YOUR-PASSWORD]` and turn it into a SQLAlchemy URL:

```
postgresql+psycopg://postgres.PROJECT_REF:YOUR_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
```

If the password has `@`, `#`, `/`, or `%`, URL-encode it.

Paste that as `DATABASE_URL` in `backend/.env`. Then from `backend/`:

```bash
python -m alembic upgrade head
```

That creates `projects`, `documents`, and `questions` in the Supabase database.

### 3. Storage bucket (S3)

1. **Storage → New bucket** named `forgedata` (private).
2. **Storage → S3 Access Keys → New key.** Copy the access key and secret.
3. **Project Settings → General** — copy the **Reference ID**.
4. **Project Settings → General** (or Database) — note the **region** (example: `ap-south-1`).

Set in `backend/.env`:

```
OBJECT_STORAGE_ENDPOINT=https://PROJECT_REF.storage.supabase.co/storage/v1/s3
OBJECT_STORAGE_ACCESS_KEY=...
OBJECT_STORAGE_SECRET_KEY=...
OBJECT_STORAGE_BUCKET=forgedata
OBJECT_STORAGE_SECURE=true
OBJECT_STORAGE_REGION=ap-south-1
```

Comment out the local MinIO `OBJECT_STORAGE_*` lines so they do not override these.

Restart **file-service** (and the other services so they pick up `DATABASE_URL`). You can stop Docker Postgres/MinIO after this — they are unused.

### 4. Check it

Upload a PDF on a job. In Supabase: **Storage → forgedata** should show `prj-…/doc-…/filename.pdf`. **Table Editor → projects** should list the job. **Remove job** in the UI should delete the row and the object.

---

## Troubleshooting

### `alembic`: `No module named 'psycopg'`

System Python is being used instead of the venv.

```bash
source .venv/bin/activate
which alembic   # must be backend/.venv/bin/alembic
alembic upgrade head
```

### Postgres connection refused (port 5432)

Something else owns port 5432 on your Mac. **Use 5433** — already set in `.env.example`.

```bash
docker compose ps
docker port backend-postgres-1   # must show 0.0.0.0:5433
```

If `docker compose up` fails with "port already allocated", keep Postgres on **5433** (do not change back to 5432).

### Docker daemon not running

```bash
colima stop && colima start
# OR open Docker Desktop
docker info
docker compose up -d
```

### File upload fails (MinIO)

```bash
docker compose up -d
docker compose ps    # minio must be running
```

Check `backend/.env` has all `OBJECT_STORAGE_*` vars from `.env.example`.

### Gateway returns 502 on upload

project-service must be running on **8001** before file-service can verify projects.

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
```

---

## Tests

```bash
source .venv/bin/activate
pytest
```

21 tests — unit + module. Module tests use SQLite in-memory by default (object storage mocked).

Postgres-backed (optional):

```bash
TEST_DATABASE_URL=postgresql+psycopg://forgedata:forgedata@localhost:5433/forgedata pytest
```

---

## Layout

```
backend/
├── gateway/                    Public API :8000
├── shared/                     schemas + SQLAlchemy models
├── services/
│   ├── project_service/        :8001 — job CRUD
│   ├── file_service/           :8002 — uploads, web sources, S3/MinIO
│   ├── question_service/       :8003 — completeness loop
│   └── evidence_service/       :8004 — cited attributes (PDF + web)
├── alembic/                    001–005 (projects, documents+source_url, questions, attributes)
├── docker-compose.yml          Postgres (:5433) + MinIO (:9000)
├── scripts/run-dev.sh          start gateway + all services (:8001–:8004)
├── scripts/run-dev.ps1         same on Windows PowerShell
└── app/routers/                stub routers (attributes, reviews, outputs)
```

---

## API contract

| Method | Path | Status |
| --- | --- | --- |
| GET | `/api/projects` | ✅ M1 |
| POST | `/api/projects` | ✅ M1 |
| GET | `/api/projects/{id}` | ✅ M1 (+ documents M2) |
| DELETE | `/api/projects/{id}` | ✅ M1 |
| POST | `/api/projects/{id}/files` | ✅ M2 |
| POST | `/api/projects/{id}/sources` | ✅ M4 (web; direct fetch or paste HTML) |
| GET | `/api/projects/{id}/attributes` | ✅ M4 |
| POST | `/api/projects/{id}/attributes/extract` | ✅ M4 |
| GET | `/api/projects/{id}/questions` | ✅ M3 |
| POST | `/api/projects/{id}/questions/{qid}/answer` | ✅ M3 |
| GET | `/api/projects/{id}/reviews` | ⏳ M5 |
| POST | `/api/reviews/{rid}/decision` | ⏳ M5 |
| GET | `/api/projects/{id}/outputs` | ⏳ M8 |
| POST | `/api/projects/{id}/outputs` | ⏳ M8 |

Next: **M5 — review-service** (conflict/high-risk queue). See `plan.md`.
