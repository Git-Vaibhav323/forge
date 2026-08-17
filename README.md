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
| file-service | 8002 | File uploads + web sources + object storage |
| question-service | 8003 | Completeness + one-question loop |
| evidence-service | 8004 | PDF/web extraction → cited attributes |
| review-service | 8005 | Conflict / high-risk holds, decisions, propagation |
| relationship-service | 8006 | Variants, compatibility, BOM (internal — not proxied) |
| vision-service | 8007 | Nameplate OCR (internal — not proxied; OCR off by default) |
| generation-service | 8008 | Outputs, QA gate, artifact download |

Verify:

```bash
curl http://127.0.0.1:8000/health    # {"status":"ok","mode":"gateway"}
curl http://127.0.0.1:8004/health    # evidence-service
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

Open **http://localhost:3000**. Create a job with a file — it persists to Postgres (or Supabase) and object storage. Questions, **Evidence** (PDF + web sources), and **Review** (conflicts + high-risk holds) are live. Outputs is next (M8).

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

**M1–M8 are done.** Every tab is live against the real backend.

| Feature | Status |
| --- | --- |
| Dashboard — list/create/remove jobs | ✅ Live API (M1) |
| Open a job — upload files | ✅ Live API (M2) |
| Questions + completion score | ✅ Live API (M3) |
| Evidence tab — PDF + cited fields | ✅ Live API (M4) |
| Evidence tab — web page sources | ✅ Live API (**direct fetch** or paste HTML) |
| Review tab — conflicts, high-risk holds, approvals | ✅ Live API (M5) |
| Compatibility checks + BOM resolution | ✅ Live (M6 — internal, feeds Review) |
| Nameplate photos as a cited source | ✅ Live (M7 — needs `OCR_PROVIDER`, off by default) |
| Outputs tab — print + download, QA gate | ✅ Live API (M8) |

Every function in `lib/api.ts` is live: `listProjects`, `getProject`, `createProject`, `deleteProject`, `uploadDocument`, `addWebSource`, `listQuestions`, `answerQuestion`, `listAttributes`, `extractAttributes`, `listReviewItems`, `submitReviewDecision`, `listOutputs`, `generateOutput`, `outputDownloadUrl`.

### Review (M5)

Two sources disagreeing on a field, or a safety-critical field with no
evidence, becomes a **hold** on the Review tab. Nothing is auto-filled. A
unit-only difference (285 PSI vs 19.65 bar) is normalized instead of asked
about — but 285 PSI vs 287 PSI, and 24 VDC vs 24 VAC, stay holds.

Decisions survive **Re-scan documents**: review items are keyed on
(job, field), not on attribute ids, which evidence-service regenerates on every
scan. Details: `backend/README.md` → **M5 — review-service**.

### Compatibility and BOM (M6)

Your answers on the Questions tab are the **requirement**; the datasheet's cited
value is the **rating**. Deterministic rules compare them — a valve rated 285
PSI on a 300 PSI duty becomes a hold reading *"Does not meet requirement"*.
Rules that cannot be decided from the sources (chemical compatibility) abstain
instead of guessing. Jobs sharing a manufacturer and model family are linked as
variants, which is what bulk propagation now follows. No tab of its own — it
feeds Review today and Outputs in M8. Details: `backend/README.md` → **M6**.

### Nameplate photos (M7)

Upload a photo of a nameplate and it becomes a cited source like any datasheet —
**if** OCR is switched on. `OCR_PROVIDER` defaults to `off`, so the stack runs on
a clean machine with no extra binaries; images are stored and simply read no
facts rather than failing.

A photo alone never produces a `known` fact — it lands as `unverified`, which
makes a safety-critical field a hold. A photo that *agrees* with a datasheet
confirms it; one that *disagrees* becomes a conflict naming both sources. OCR
cleanup never repairs misread characters, because "fixing" `28S` to `285` would
invent a rating. Details: `backend/README.md` → **M7**.

### Printing (M8)

**Print** on the Outputs tab writes a real markdown file to object storage and
offers it for download. It is built only from values that are both publishable
**and cited** — an attribute claiming to be known with nothing behind it is
withheld.

Two kinds of QA result, and the difference matters:

- **Blocked** — sources still disagree, or a hold is unanswered. Nothing is
  printed; the tab shows exactly what to fix and there is no file to download.
- **Printed with caveats** — gaps, abstained checks, or photo-only values. The
  document is produced, and every caveat is written *into* it under **Not
  established** and **QA notes**, so the reader sees what the operator saw.

Details: `backend/README.md` → **M8**.

Hosted DB/files: set `POSTGRES_*` and `OBJECT_STORAGE_*` in `backend/.env` (see **Switch to Supabase** in `backend/README.md`). Local Docker Postgres/MinIO still works.

### Web sources (no Apify required)

On the **Evidence** tab you can add a manufacturer/catalog **URL**. ForgeData stores the page and cites labelled facts from it — same rules as PDFs (never invent; disagreements become `conflicting` for M5 Review).

| Mode | Config | When to use |
| --- | --- | --- |
| **Direct fetch** (default) | Nothing — `WEB_FETCH_PROVIDER` unset or `direct` | Public HTML catalog pages |
| **Paste HTML** | No API — expand “paste HTML” on Evidence | JS-heavy sites that block simple fetch |
| **Apify** | `WEB_FETCH_PROVIDER=apify` + token/actor | **Not wired yet** — env placeholders only |
| **Custom scraper** | `WEB_FETCH_PROVIDER=custom` + `WEB_FETCH_API_URL` | Your own fetch API |

You do **not** need Apify credentials for the current build. If you created an Apify account, keep the token for later — ForgeData does not call it until `_fetch_apify` is implemented.

Details: `backend/README.md` → **Web page sources**. Roadmap: `plan.md` → **M5 — review-service**.

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
│   ├── services/        project :8001, file :8002, question :8003,
│   │                    evidence :8004, review :8005, relationship :8006,
│   │                    vision :8007, generation :8008
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
