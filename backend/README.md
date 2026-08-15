# ForgeData — Backend

Microservices behind a single **API gateway** on port **8000**. The frontend
only talks to the gateway; it proxies to internal services.

```
Frontend → gateway :8000 → project-service :8001  (jobs CRUD)
                         → file-service    :8002  (uploads + MinIO)
                         → stub routers              (attributes, questions, …)
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
```

If you only see `001` and not `002`, you are already up to date.

### Step 4 — Start all backend services

```bash
source .venv/bin/activate
./scripts/run-dev.sh
```

Or three separate terminals:

```bash
uvicorn services.project_service.main:app --reload --port 8001
uvicorn services.file_service.main:app --reload --port 8002
uvicorn gateway.main:app --reload --port 8000
```

### Step 5 — Verify backend

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
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

**Stack:** FastAPI, Pydantic, SQLAlchemy 2, PostgreSQL 16, Alembic, psycopg 3

---

## M2 — File uploads ✅ DONE

**Service:** `services/file_service/` on **:8002**

| Method | Path | Status |
| --- | --- | --- |
| `POST` | `/api/projects/{id}/files` | ✅ |

**Stack:** MinIO (S3-compatible), SHA-256 hash, PostgreSQL `documents` table

### Duplicate file handling

Same SHA-256 content on the same project:

| Request | Result |
| --- | --- |
| Default upload | **409** — message asks what you need differently |
| `?intent=reupload` | New document row (another copy) |
| `?intent=replace` | Swaps the existing stored file |

---

## Environment variables (`backend/.env`)

Copy from `.env.example`. Required for M1 + M2:

| Variable | Value | Used by |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://forgedata:forgedata@localhost:5433/forgedata` | project + file services |
| `PROJECT_SERVICE_URL` | `http://localhost:8001` | gateway, file-service |
| `FILE_SERVICE_URL` | `http://localhost:8002` | gateway |
| `OBJECT_STORAGE_ENDPOINT` | `localhost:9000` | file-service |
| `OBJECT_STORAGE_ACCESS_KEY` | `forgedata` | file-service |
| `OBJECT_STORAGE_SECRET_KEY` | `forgedata` | file-service |
| `OBJECT_STORAGE_BUCKET` | `forgedata` | file-service |
| `OBJECT_STORAGE_SECURE` | `false` | file-service |
| `CORS_ORIGINS` | `http://localhost:3000` | all services |

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

8 tests — unit + module. Module tests use SQLite in-memory by default (MinIO and HTTP mocked).

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
│   └── file_service/           :8002 — uploads, MinIO, SHA-256 dedup
├── alembic/                    001 projects, 002 documents
├── docker-compose.yml          Postgres (:5433) + MinIO (:9000)
├── scripts/run-dev.sh          start gateway + both services
└── app/routers/                stub routers wired into gateway
```

---

## API contract

| Method | Path | Status |
| --- | --- | --- |
| GET | `/api/projects` | ✅ M1 |
| POST | `/api/projects` | ✅ M1 |
| GET | `/api/projects/{id}` | ✅ M1 (+ documents M2) |
| POST | `/api/projects/{id}/files` | ✅ M2 |
| GET | `/api/projects/{id}/attributes` | ⏳ M4 |
| GET | `/api/projects/{id}/questions` | ⏳ M3 |
| POST | `/api/projects/{id}/questions/{qid}/answer` | ⏳ M3 |
| GET | `/api/projects/{id}/reviews` | ⏳ M5 |
| POST | `/api/reviews/{rid}/decision` | ⏳ M5 |
| GET | `/api/projects/{id}/outputs` | ⏳ M8 |
| POST | `/api/projects/{id}/outputs` | ⏳ M8 |

Next: **M3 — question-service**. See `plan.md`.
