# ForgeData — Backend

Microservices behind a single **API gateway** on port **8000**. The frontend
only talks to the gateway; it proxies to internal services.

```
Frontend → gateway :8000 → project-service  :8001  (jobs CRUD)
                         → file-service     :8002  (uploads + MinIO)
                         → question-service :8003  (completeness loop)
                         → evidence-service :8004  (cited attributes / evidence)
                         → review-service   :8005  (conflict / high-risk holds)
                         → generation-service :8008 (outputs + QA gate + download)

relationship-service :8006  (variants, compatibility, BOM) — internal only,
                             not proxied; called by generation-service (M8)
vision-service       :8007  (nameplate OCR inspection) — internal only;
                             evidence-service reads images via shared/ocr.py
```

Every public route is a proxy. There are **no stub routers left** — the
deprecated `app/main.py` monolith and `app/routers/` were removed in M8.
`app/config.py` remains: it is the shared settings module every service imports.

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
uvicorn services.review_service.main:app --reload --port 8005
uvicorn services.relationship_service.main:app --reload --port 8006
uvicorn services.vision_service.main:app --reload --port 8007
uvicorn services.generation_service.main:app --reload --port 8008
uvicorn gateway.main:app --reload --port 8000
```

### Step 5 — Verify backend

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8004/health
curl http://127.0.0.1:8005/health
curl http://127.0.0.1:8006/health
curl http://127.0.0.1:8007/health
curl http://127.0.0.1:8008/health
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

## M3 — Completeness / questions ✅ DONE (hybrid engine)

**Service:** `services/question_service/` on **:8003**

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/projects/{id}/questions` | ✅ |
| `POST` | `/api/projects/{id}/questions/{qid}/answer` | ✅ |

**Hybrid question selection** (`shared/question_engine.py`):

1. **Goal + category schema** — base required fields (`shared/completeness.py`)
2. **Conditional rules** — extra fields when answers match (e.g. Hazardous area → area class)
3. **Evidence pre-fill** — `known`/`verified` attributes from M4 skip those questions
4. **Optional LLM ranker** — picks which gap to ask first (falls back to priority sort)

One open question at a time. `"Not applicable"` completes a field; `"I don't know"` / `"idk"` do not.
User answers override evidence. Answers persist in `questions`; `completionScore` updates on the job.

**Free LLM (optional)** — add to `backend/.env`:

| Provider | Get key | Env |
| --- | --- | --- |
| **Google Gemini** (recommended) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `LLM_PROVIDER=gemini`, `LLM_API_KEY=...`, `LLM_MODEL=gemini-2.0-flash` |
| **Groq** (alternative) | [console.groq.com](https://console.groq.com/) | `LLM_PROVIDER=groq`, `LLM_API_KEY=...`, `LLM_MODEL=llama-3.1-8b-instant` |
| **Off** (rules only) | — | `LLM_PROVIDER=off` |

Without a key, layers 1–3 still work; layer 4 uses critical → high priority ordering.

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

## M5 — review-service ✅ DONE

**Service:** `services/review_service/` on **:8005**. Powers the **Review** tab.

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/projects/{id}/reviews` | ✅ derives + returns the queue |
| `POST` | `/api/reviews/{rid}/decision` | ✅ approve / edit / reject / unresolved |

### What becomes a hold

| Condition | Issue type | Severity |
| --- | --- | --- |
| Two sources disagree on one field | `conflict` | field risk, min `high` |
| Safety-critical field with no evidence | `high_risk` | field risk, min `high` |
| Unit-only disagreement (285 PSI vs 19.65 bar) | **none** — normalized automatically | — |

Safety-critical fields are listed once in `shared/risk.py`: pressure, voltage,
temperature, connection standard, hazardous-area class, chemical compatibility.

### Decisions

| Action | Effect on the record |
| --- | --- |
| `approve` | Writes the shown value (or your typed one) → attribute `verified` |
| `approve` with nothing proposed | Explicit override — clears the hold **without inventing a value** |
| `edit` | Writes the value you typed → attribute `verified` |
| `reject` | Clears the value → attribute `missing`. Nothing is kept that nobody stands behind. On a safety-critical field this correctly reopens as a `high_risk` "no evidence" hold. |
| `unresolved` | Parks it; still counted as pending |

Every decision is appended to `review_decisions` (never updated, never deleted).

### Why decisions survive "Re-scan documents"

evidence-service rebuilds **every** attribute row on each extract, with fresh
ids. Review items are therefore keyed on **(project_id, field)**, not on the
attribute id, and `run_extraction` replays settled decisions through
`shared/review_sync.py`. A re-scan re-reads the PDFs, finds the same
disagreement, and still shows the field as approved.

A decided item only re-opens when the underlying disagreement actually changes
(tracked by `signature`), so a re-scan never nags about a settled question.

### Unit normalization (Pint)

`shared/normalization.py` decides whether two values are the same fact written
two ways. Rules that matter:

- Different units → converted, with 0.5% slack for published rounding.
- **Same** unit → exact match required (285 PSI ≠ 287 PSI).
- **24 VDC ≠ 24 VAC** — Pint sees only volts, so current type is compared
  separately. On a critical field that must stay a hold.
- Anything unparseable falls back to string comparison; nothing ever raises.

### Bulk propagation

When other jobs **in the same category** carry the same wrong value for the
same field, the item reports `affectedProducts`. Approving with
`propagate: true` applies your correction to those siblings too. Without the
flag they are untouched. This is a deliberate stand-in until M6 provides a real
relationship graph.

### Counters

`shared/review_sync.recompute_counts` is the **single writer** of
`conflictsCount` and `pendingApprovalsCount`. Both the Review tab badge and the
Outputs print gate read them, so they are derived in one place rather than by
each service that happens to touch attributes.

### How to test M5

```bash
python -m pytest tests/unit/test_normalization.py tests/module/test_reviews_api.py -q
```

---

## M6 — relationship-service ✅ DONE

**Service:** `services/relationship_service/` on **:8006**. **Internal** — the
gateway does not proxy it and no frontend tab calls it. generation-service (M8)
is the intended consumer.

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/projects/{id}/relationships` | ✅ returns stored state |
| `POST` | `/api/projects/{id}/relationships/resolve` | ✅ re-derives everything |

It is also re-run automatically inside `run_extraction`, so a document re-scan
refreshes variants, findings and BOM lines along with the attributes.

### Where the two sides of a compatibility check come from

Both already exist on the record, and both are cited:

| Side | Source | Stored as |
| --- | --- | --- |
| **Requirement** — what you asked for | Questions tab answer | the attribute value + a `user-answer` evidence row |
| **Rating** — what the datasheet says | extracted document | document evidence rows, each with its own `value` (M5) |

A field that is still `conflicting` has **no** trustworthy rating, so every rule
over it abstains. You cannot check a number nobody has agreed on yet — the
conflict is the hold, and the compatibility check runs once it clears.

### Rules (`shared/compatibility.py`)

| Rule | Field | Test | Severity |
| --- | --- | --- | --- |
| `pressure_rating` | `maximum_pressure` | rating ≥ requirement | critical |
| `temperature_rating` | `max_temperature` | rating ≥ requirement | high |
| `supply_voltage_match` | `supply_voltage` | exact (AC ≠ DC) | critical |
| `connection_match` | `connection_standard` | exact | high |
| `chemical_compatibility` | `operating_medium` | **always abstains** | critical |

Three outcomes: `pass`, `fail`, `unknown`. **`unknown` is a first-class result** —
it means the rule refused to guess (a side is missing, the quantities are not
comparable, or there is no knowledge base behind the question). Only `fail`
becomes a hold; `unknown` is recorded as a visible gap and never blocks.

`chemical_compatibility` abstains by design: deciding whether a medium attacks a
material needs a materials database this project does not have, and guessing it
would be exactly the invention the whole system exists to prevent.

### Failures become review holds

A `fail` finding is turned into a review item with issue type `incompatible`
("Does not meet requirement"). Approving one is an **explicit override** — it
clears the hold and does not change the value, because there is no new fact to
record. See `shared/review_sync.py`.

### Variants

Two jobs are linked when they share a manufacturer **and** a model family
(`MFC-GV-100` and `MFC-GV-150` → family `MFC-GV`). Every link records the
`basis` that produced it, so a propagated correction can be explained rather
than trusted. M5 bulk propagation now prefers these links and only falls back
to "same category" when no relationships have been resolved.

### BOM lines

Built only for `bom_generation` and `product_configuration` goals, from cited
attributes. Anything the goal wants but nothing supports becomes a `missing`
line rather than being dropped — a BOM that silently omits what it could not
resolve is worse than one that names the gap.

### How to test M6

```bash
python -m pytest tests/unit/test_compatibility.py tests/unit/test_bom.py \
  tests/module/test_relationships_api.py -q
```

---

## M7 — vision-service ✅ DONE

**Service:** `services/vision_service/` on **:8007**. **Internal** — not proxied.
Images are read during normal extraction; these routes exist to see what OCR saw,
which is the only practical way to debug a bad nameplate read.

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/vision/status` | ✅ which provider is active |
| `GET` | `/api/projects/{id}/images` | ✅ image documents on the job |
| `POST` | `/api/projects/{id}/images/{doc_id}/read` | ✅ OCR one image, returns text only |

### OCR is off by default — and that is a real answer

| `OCR_PROVIDER` | Needs | Behaviour |
| --- | --- | --- |
| `off` (**default**) | nothing | Images are stored and listed, and read **no facts**. |
| `tesseract` | tesseract binary + `pip install pytesseract pillow` | Local OCR |
| `custom` | `OCR_API_URL` (+ optional `OCR_API_KEY`) | POSTs the image; expects `{"text"}` or `{"pages"}` |

Running with no OCR is a **supported configuration, not a failure**. The stack
boots on a clean machine with no system binaries; an unread image produces
silence, and silence produces `missing` — never a guess. Unread images are
marked `pending`, not `processed`, so the UI does not claim they were read.

### A photo is not a datasheet

| Evidence for a field | Status | Confidence |
| --- | --- | --- |
| Image only | **`unverified`** | 0.60 |
| Image + document that agree | `known` | 0.95 |
| Image + document that disagree | `conflicting` | 0.50 |

A single OCR read is a *reading*, not an established fact — so it never lands as
`known`. Because `unverified` is one of the statuses that makes a safety-critical
field a hold (M5), a photo-only coil voltage reaches the reviewer instead of the
record. A photo that **agrees** with a datasheet is a genuine second source and
lifts the field like any other agreement.

### Why post-processing never repairs characters

OCR confuses `O`/`0`, `I`/`1`, `S`/`5`. "Correcting" those inside a value would
fabricate a rating nobody can cite — turning a blurry `28S PSI` into `285 PSI`
invents a pressure. `shared/ocr.clean_text` therefore only makes changes that
**cannot alter meaning**: whitespace, control characters, unicode punctuation,
and hyphen-broken line joins. A misread stays misread, shown next to the photo
it came from.

One subtlety worth keeping: punctuation is mapped **before** NFKC normalization,
because NFKC decomposes `″` into two apostrophes and would destroy the inch
symbol that the `nominal_size` rule matches on.

### Architecture note

Images join the **existing** pipeline rather than getting their own. OCR simply
supplies text to the same `parse_page` label→field rules a PDF goes through, so
conflict detection, review holds, and M6 compatibility all work on nameplate
data with no changes. Attributes are still written by exactly one service
(evidence-service), which is what stops a photo taking a different path onto the
record than a datasheet does.

### How to test M7

```bash
python -m pytest tests/unit/test_ocr.py tests/module/test_vision_api.py -q
```

---

## M8 — generation-service ✅ DONE

**Service:** `services/generation_service/` on **:8008**. Powers the **Outputs** tab.

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/api/projects/{id}/outputs` | ✅ |
| `POST` | `/api/projects/{id}/outputs` | ✅ runs the QA gate, then prints |
| `GET` | `/api/outputs/{id}/download` | ✅ serves the artifact as an attachment |

### The QA gate

`shared/qa.py` separates two questions, and the split is the whole design:

| | Meaning | Effect |
| --- | --- | --- |
| **Blocker** | Two sources still disagree, or a hold is unanswered | **Nothing is printed.** No file is written. |
| **Warning** | A gap, an abstained rule, a photo-only value, an unresolved BOM line | Printed, and the caveat is **written into the document** |

A blocked print still records a row with `status=qa_failed` and the blocking
reasons, so the Outputs tab says exactly what to fix — but `storage_key` stays
null and `/download` returns **409**. There is no file because there was nothing
legitimate to write.

Resulting status: `qa_failed` (blocked) → `generated` (printed with caveats) →
`qa_passed` (printed clean).

### What actually reaches the page

A value is stated as fact only when it is **publishable AND cited**:

```
status in {known, verified, derived}  AND  raw_value non-empty  AND  has evidence
```

Status alone is not enough — an attribute claiming `known` with nothing behind
it is withheld. Everything withheld appears in a **Not established** table with
the reason. That table is the point: a datasheet that silently omits the field
it could not source reads as complete when it is not.

### The artifact

Markdown (`text/markdown`), rendered by `shared/output_render.py`. Chosen so a
cited document is readable, diffable, and needs **no rendering dependency** —
no reportlab, no python-docx. Swapping the writer for PDF later touches that one
module; everything above it works in `RenderContext`.

Sections: header → **Established** (value + confidence + document/page) →
**Not established** (field + status + why) → **Bill of materials** (BOM goals,
via M6) → **Compatibility** (M6, with `unknown` explicitly marked *not a pass*)
→ **QA notes**.

Artifacts are stored in object storage under `{project}/outputs/{id}/{filename}`,
reusing `file_service/storage.py`. One artifact per `(job, type)` — regenerating
replaces the previous file rather than piling up copies.

### How to test M8

```bash
python -m pytest tests/unit/test_qa.py tests/unit/test_output_render.py \
  tests/module/test_outputs_api.py -q
```

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

181 tests — unit + module. Module tests use SQLite in-memory by default (object storage and OCR mocked).

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
│   ├── evidence_service/       :8004 — cited attributes (PDF + web)
│   ├── review_service/         :8005 — conflict / high-risk approval queue
│   ├── relationship_service/   :8006 — variants, compatibility, BOM (internal)
│   ├── vision_service/         :8007 — nameplate OCR inspection (internal)
│   └── generation_service/     :8008 — outputs, QA gate, download
├── alembic/                    001–008 (projects, documents+source_url, questions,
│                               attributes, reviews, relationships, outputs)
│                               M7 added no tables — images reuse `documents`
├── docker-compose.yml          Postgres (:5433) + MinIO (:9000)
├── scripts/run-dev.sh          start gateway + all services (:8001–:8008)
├── scripts/run-dev.ps1         same on Windows PowerShell
└── app/config.py               shared settings (all that remains of the monolith)
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
| GET | `/api/projects/{id}/reviews` | ✅ M5 |
| POST | `/api/reviews/{rid}/decision` | ✅ M5 |
| GET | `/api/projects/{id}/outputs` | ✅ M8 |
| POST | `/api/projects/{id}/outputs` | ✅ M8 |
| GET | `/api/outputs/{id}/download` | ✅ M8 |

Internal (not proxied):
- `GET|POST /api/projects/{id}/relationships[/resolve]` on :8006 — ✅ M6
- `GET /api/vision/status`, `GET /api/projects/{id}/images`, `POST /api/projects/{id}/images/{doc}/read` on :8007 — ✅ M7

**M1–M8 are complete.** The public contract in `context.md` is fully live.
