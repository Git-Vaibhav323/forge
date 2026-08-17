# ForgeData — Backend plan (microservices)

Build the backend as **independent services**, not phase-sized vertical slices. Each service owns its domain, database schema, and test suite. Integrate services **one at a time** into the API gateway only after that service passes **unit tests** and **module tests** (contract + integration against real dependencies).

The UI stays on mock data until a service is merged and its routes match `lib/types.ts`. Flip only the matching functions in `lib/api.ts` — never the React components.

---

## Architecture shift

| Before (phase-wise) | Now (microservices) |
| --- | --- |
| One monolith filled tab-by-tab in 6 phases | Separate deployable services with clear boundaries |
| Later phases assume earlier code in the same process | Services communicate over HTTP and/or events; each can ship alone |
| No test gates | **Unit + module tests required before merge** |
| Shared in-process imports | Shared **contracts only** (`lib/types.ts`, events, OpenAPI) |

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)  →  lib/api.ts  →  API Gateway :8000   │
└───────────────────────────────┬─────────────────────────────┘
                                │ HTTP (internal)
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   project-svc  file-svc   question-svc  evidence-svc  review-svc
   :8001        :8002      :8003         :8004         :8005
        │           │           │           │           │
        └───────────┴───────────┴───────────┴───────────┘
                          PostgreSQL, MinIO, Redis
                    (schemas per service where possible)
```

The gateway preserves the **public API contract** (`/api/projects`, `/api/projects/{id}/files`, …). Internally it proxies or aggregates calls to the right service. The frontend never sees service boundaries.

---

## Current state

| Piece | Status |
| --- | --- |
| Frontend (all tabs) | UI complete; **Overview + create/upload + Questions live** when `NEXT_PUBLIC_API_BASE_URL` is set |
| **Gateway** | ✅ `gateway/` on `:8000` — public entrypoint |
| **project-service (M1)** | ✅ `services/project_service/` on `:8001` — Postgres CRUD |
| **file-service (M2)** | ✅ `services/file_service/` on `:8002` — MinIO uploads, SHA-256 dedup |
| **question-service (M3)** | ✅ `services/question_service/` on `:8003` — required fields, one-question loop |
| **evidence-service (M4)** | ✅ `services/evidence_service/` on `:8004` — cited attributes (PDF + web) |
| **review-service (M5)** | ✅ `services/review_service/` on `:8005` — conflict / high-risk holds, decisions, propagation |
| **relationship-service (M6)** | ✅ `services/relationship_service/` on `:8006` — variants, compatibility rules, BOM lines (internal, not proxied) |
| **vision-service (M7)** | ✅ `services/vision_service/` on `:8007` — nameplate OCR via `shared/ocr.py`; OCR defaults off (internal, not proxied) |
| **generation-service (M8)** | ✅ `services/generation_service/` on `:8008` — QA gate, markdown artifact, download |
| **shared/** | ✅ `shared/schemas.py` + `shared/db/` + `shared/completeness.py` + `shared/risk.py` + `shared/normalization.py` + `shared/review_sync.py` |
| Stub routers | ✅ **All removed.** Every public route is a gateway proxy. |
| Postgres | ✅ Docker on host port **5433**, or **Supabase Postgres** via `DATABASE_URL` |
| MinIO / S3 | ✅ Docker MinIO **or Supabase Storage (S3 API)** |
| Redis, LLM | Not wired |
| Automated tests | ✅ **181 passing** (`pytest` — unit + module) |

### Run the stack

See **`README.md`** (repo root) and **`backend/README.md`** for step-by-step instructions.

Quick version:

```bash
# Terminal 1 — backend
cd backend
docker compose up -d
source .venv/bin/activate   # Python 3.12 venv required
alembic upgrade head          # use .venv/bin/alembic, not system python
./scripts/run-dev.sh

# Terminal 2 — frontend (repo root)
cp .env.example .env.local    # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install && npm run dev
```

Health: http://localhost:8000/health  
Docs: http://localhost:8000/docs  
Frontend: http://localhost:3000

### Live frontend functions (`lib/api.ts`)

| Function | Merge | Status |
| --- | --- | --- |
| `listProjects`, `getProject`, `createProject`, `deleteProject` | M1 | ✅ live |
| `uploadDocument` | M2 | ✅ live (409 on duplicate; `intent` param for retry) |
| `listQuestions`, `answerQuestion` | M3 | ✅ live |
| All others | M4–M8 | mock only |

---

## Hard rules (every service)

1. **Wire shape is locked.** Field JSON is `{ attribute, value, unit, source, page, evidence, confidence, status }`. Change `lib/types.ts` and the shared Pydantic package together — never fork shapes per service.
2. **One frontend seam.** Only `lib/api.ts` talks to the gateway. Flip one function at a time when that route is live.
3. **Abstain, don’t invent.** A field may be `missing`, `conflicting`, or `needs_review`. Never fill a technical value from model knowledge.
4. **Human gate.** Conflicts, high-risk fields (voltage, pressure, temperature, chemical compatibility, safety certs), bulk edits, and published-data changes always pause for a person.
5. **Test before merge.** No service is wired into the gateway until its unit suite is green and its module suite passes against Postgres / MinIO / Redis as applicable.
6. **Service independence.** A service must boot, health-check, and run its tests without other application services running (use testcontainers or docker-compose profiles for deps).

---

## Target layout

Current structure (M1 + M2 merged):

```
backend/
├── gateway/                    # Public API (:8000) — proxies + stub routers
├── shared/                     # Cross-service contracts
│   ├── schemas.py              # Pydantic mirror of lib/types.ts
│   ├── db/models.py            # ProjectRow, DocumentRow
│   └── db/documents.py         # read helpers
├── services/
│   ├── project_service/        # :8001 ✅ M1
│   ├── file_service/           # :8002 ✅ M2
│   └── question_service/       # :8003 ✅ M3
├── alembic/                    # 001 projects, 002 documents, 003 questions
├── docker-compose.yml          # Postgres (:5433) + MinIO (:9000)
├── scripts/run-dev.sh          # start gateway + M1–M3 services
└── app/routers/                # stub routers (attributes, reviews, outputs)
```

Still to extract:

```
├── services/
│   ├── evidence_service/       # :8004  M4
│   ├── review_service/         # :8005  M5
│   ├── relationship_service/   # :8006  M6
│   ├── vision_service/         # :8007  M7
│   └── generation_service/     # :8008  M8
```

Each service follows the same internal shape:

```
services/<name>/
├── app/
│   ├── main.py           # FastAPI app, /health, domain routes
│   ├── config.py
│   ├── db/               # SQLAlchemy models + migrations (Alembic)
│   ├── domain/           # business logic (pure functions where possible)
│   └── api/              # route handlers (thin)
├── tests/
│   ├── unit/             # no network, no real DB
│   └── module/           # real Postgres/MinIO via testcontainers or compose
├── requirements.txt
└── Dockerfile
```

---

## Service catalog

| Service | Port | Owns | Public routes (via gateway) |
| --- | --- | --- | --- |
| **project-service** | 8001 | Job lifecycle, goal, category, status, completion metadata | `GET/POST /api/projects`, `GET/DELETE /api/projects/{id}` |
| **file-service** | 8002 | Upload bytes, hashes, document metadata, processing status | `POST /api/projects/{id}/files` |
| **question-service** | 8003 | Required-field schema, completeness, single next question, answers | `GET /api/projects/{id}/questions`, `POST …/questions/{qid}/answer` |
| **evidence-service** | 8004 | PDF/OCR extraction, chunks, pgvector, attribute mapping | `GET /api/projects/{id}/attributes` |
| **review-service** | 8005 | Unit normalize, conflicts, risk, decisions, bulk propagate, audit | `GET /api/projects/{id}/reviews`, `POST /api/reviews/{rid}/decision` |
| **relationship-service** | 8006 | Variants, accessories, compatibility, BOM tables | Internal APIs consumed by generation / review |
| **vision-service** | 8007 | Nameplate OCR, image-to-SKU, table reconstruction | Feeds evidence-service (same attribute contract) |
| **generation-service** | 8008 | Goal templates, QA gate, artifact storage | `GET/POST /api/projects/{id}/outputs` |

**Cross-cutting (later):** workflow-orchestrator (LangGraph interrupts), event bus (Redis Streams). Add only after review-service and evidence-service are merged and stable.

---

## Testing strategy

### Unit tests (`tests/unit/`)

- Pure domain logic: completeness scoring, conflict detection, risk classification, template rendering guards.
- Pydantic validation and serializers.
- HTTP handlers with dependencies mocked (no real DB or object storage).
- **Gate:** `pytest services/<name>/tests/unit` — 100% pass, no skipped critical paths.

### Module tests (`tests/module/`)

- Service boots against real dependencies (Postgres, MinIO, Redis) via **docker-compose test profile** or **testcontainers**.
- Repository round-trips, migrations apply cleanly, upload → metadata row → fetch.
- **Contract tests:** response JSON matches OpenAPI generated from shared schemas; snapshot or schema-assert against fixtures derived from `lib/types.ts`.
- **Gateway module tests:** gateway → service hop returns the same body the frontend expects (run with both processes or TestClient + httpx mock upstream).
- **Gate:** `pytest services/<name>/tests/module` — 100% pass in CI.

### CI merge checklist (per service)

Before opening a “merge service X into gateway” PR:

- [ ] Unit suite green locally and in CI
- [ ] Module suite green with docker-compose `test` profile
- [ ] Service `/health` and `/docs` (or internal OpenAPI) published
- [ ] Gateway proxy routes added; gateway module tests green
- [ ] Matching `lib/api.ts` functions flipped from mock to live
- [ ] Manual smoke: affected UI tab works against live stack

### Shared tooling to add (first extraction PR)

- `pytest`, `pytest-asyncio`, `httpx`, `testcontainers` (or compose-based fixtures)
- `ruff` for lint/format
- Root `Makefile` or scripts: `make test-unit`, `make test-module`, `make up`

---

## Merge order

Integrate in dependency order. Each row is one merge milestone — do not wire the gateway until both test gates pass.

### M1 — project-service ✅ DONE

**Unlocks:** Overview (project list + detail)  
**Service:** `services/project_service/` on `:8001`

| Work | Detail |
| --- | --- |
| Build | Postgres persistence, Alembic migrations, domain CRUD |
| Unit tests | Create/read/update rules, schema validation |
| Module tests | CRUD against SQLite (default) / Postgres (optional) |
| Gateway | Proxy project routes to `:8001` |
| Frontend | `listProjects`, `getProject`, `createProject` |

**Done when:** Projects persist across restarts; unit + module green; Overview uses live API. ✅

---

### M2 — file-service ✅ DONE

**Unlocks:** Overview (documents list), create-job file upload  
**Service:** `services/file_service/` on `:8002`  
**Depends on:** M1 (project IDs must exist)

| Work | Detail |
| --- | --- |
| Build | MinIO upload, SHA-256 hash, document row linked to `project_id` |
| Unit tests | Filename sanitization, doc type guessing |
| Module tests | Upload → metadata row → appears on project GET |
| Duplicate handling | 409 on same hash; `?intent=reupload` or `?intent=replace` |
| Gateway | Proxy `POST /api/projects/{id}/files` |
| Frontend | `uploadDocument` (with optional `intent`) |

**Done when:** Upload stores bytes and returns `documentId`; module tests prove round-trip. ✅

---

### M3 — question-service ✅ DONE

**Unlocks:** Overview (completion score), Questions tab  
**Calendar:** 1–2 weeks  
**Depends on:** M1, M2 (optional: file count for completeness)

| Work | Detail |
| --- | --- |
| Build | Required-field schema per goal+category, completeness engine, one-question-at-a-time loop |
| Unit tests | Scoring, blocking field count, question ranking, answer application |
| Module tests | End-to-end: create project → answer → score updates in Postgres |
| Gateway | Proxy question routes; optionally aggregate completion fields onto project GET |
| Frontend | `listQuestions`, `answerQuestion`; refresh project detail |

**Done when:** Answering the next missing field updates `completionScore` and `blockingFieldsCount` from real rules. ✅

---

### M4 — evidence-service ✅ DONE

**Unlocks:** Evidence tab  
**Depends on:** M2 (documents in object storage)

| Work | Detail |
| --- | --- |
| Build | `pypdf` per-page text + deterministic label→field rules → `Attribute` records with cited page + quote. **Key-free** (no embeddings/pgvector); same wire shape so semantic RAG is a drop-in later. |
| Unit tests | `test_evidence.py` — parse, missing-not-invented, agreement raises confidence, conflict flagged (two sources → `conflicting`). |
| Module tests | `test_evidence_api.py` — seeded PDFs → attribute rows with page + quoted evidence, conflict count, idempotent re-scan. |
| Gateway | Proxy `GET /api/projects/{id}/attributes` + `POST …/attributes/extract` → :8004. |
| Frontend | `listAttributes` live; `extractAttributes` (re-scan); Evidence tab auto-scans on first open. |

**Done when:** Evidence tab shows real cited fields; missing stays missing; conflicts not merged. ✅

**Deferred (drop-in upgrades):** OCR for scanned PDFs, pgvector + embeddings for semantic retrieval, unit normalization (Pint). **Web page sources (URL paste / fetch) are live** — optional Apify/custom fetch providers remain config stubs.

---

### M5 — review-service ✅ DONE

**Unlocks:** Review tab  
**Service:** `services/review_service/` on `:8005`  
**Depends on:** M4 (attributes to validate)

| Work | Detail |
| --- | --- |
| Build | Pint normalization (`shared/normalization.py`), conflict/risk detection + decision replay (`shared/review_sync.py`), canonical risk list (`shared/risk.py`), `review_items` + `review_decisions` audit table, bulk propagate |
| Unit tests | `test_normalization.py` — conversion vs value differences, AC≠DC, same-unit exactness, never raises |
| Module tests | `test_reviews_api.py` — derivation, counters, all four decisions, audit trail, **survival across a re-scan**, sibling propagation |
| Gateway | Proxies `GET /api/projects/{id}/reviews` + `POST /api/reviews/{rid}/decision` → :8005 |
| Frontend | `listReviewItems`, `submitReviewDecision` live (now cached + invalidated) |

**Done when:** Approve/edit/reject persists; print blocked while holds exist. ✅

**Key design decision:** review items are keyed on **(project_id, field)**, not
on the attribute id, because evidence-service deletes and recreates every
attribute row on each re-scan. `run_extraction` replays settled decisions, so
"Re-scan documents" no longer undoes human approvals.

**Deferred:** bulk propagation matches siblings by (category, field, value)
rather than a real relationship graph — upgrade in M6.

---

### M6 — relationship-service ✅ DONE

**Unlocks:** BOM / configuration jobs beyond flat fields  
**Service:** `services/relationship_service/` on `:8006`  
**Depends on:** M5 (mismatches become review items)

| Work | Detail |
| --- | --- |
| Build | `product_relationships`, `compatibility_findings`, `bom_lines`; pure rule modules `shared/compatibility.py` + `shared/bom.py`; persistence in `shared/relationship_sync.py` |
| Unit tests | `test_compatibility.py` (rules, cross-unit ordering, AC≠DC, abstention), `test_bom.py` (identity, named gaps, positions) |
| Module tests | `test_relationships_api.py` — findings, variants, BOM, idempotence, **fail → review hold**, override clears without changing the value |
| Gateway | **No public routes** — internal API, per the original plan |

**Done when:** Configuration/BOM jobs resolve compatible parts; mismatches are review items, not silent merges. ✅

**Key design decision:** the requirement side of every check is the user's
Questions answer and the rating side is the datasheet's own cited value — both
already on the record, so nothing new is invented to run a rule. A field still
`conflicting` has no trustworthy rating, so its rules abstain until the conflict
is resolved.

**Deliberate abstention:** `chemical_compatibility` always returns `unknown`.
Deciding whether a medium attacks a material needs a materials database this
project does not have.

**Also landed:** M5 bulk propagation now prefers the M6 variant graph and only
falls back to "same category" when no relationships have been resolved.

---

### M7 — vision-service ✅ DONE

**Unlocks:** Nameplate / image sources  
**Service:** `services/vision_service/` on `:8007`  
**Depends on:** M4 (same attribute contract)

| Work | Detail |
| --- | --- |
| Build | `shared/ocr.py` provider abstraction (off / tesseract / custom) + meaning-preserving post-processing; images join the existing extraction pipeline |
| Unit tests | `test_ocr.py` — cleanup, **never repairs misread characters**, provider selection, off reads nothing |
| Module tests | `test_vision_api.py` — photo fills a field citing the image, photo agreeing confirms, photo disagreeing conflicts, photo-only critical field becomes a hold, OCR-off contributes nothing |
| Gateway | **No public routes** — internal, as planned |

**Done when:** Nameplate photo can fill or conflict with datasheet fields, citing the image. ✅

**Key design decision:** M7 added **no new tables and no new attribute path**.
OCR just supplies text to the same `parse_page` rules a PDF goes through, so
conflict detection, review holds and M6 compatibility work on nameplate data
unchanged. evidence-service remains the only writer of attributes.

**Trust rule:** a photo alone yields `unverified` (0.60), never `known`. Since
`unverified` makes a safety-critical field a hold, a photo-only coil voltage
reaches the reviewer. A photo agreeing with a datasheet lifts the field to
`known` (0.95) like any other second source.

**OCR defaults to OFF** and that is a supported configuration — no system
binaries required to run the stack. Unread images are marked `pending`, not
`processed`.

---

### M8 — generation-service ✅ DONE

**Unlocks:** Outputs tab  
**Service:** `services/generation_service/` on `:8008`  
**Depends on:** M5 (approved facts only), M6 for BOM/configuration goals

| Work | Detail |
| --- | --- |
| Build | `outputs` table, `shared/qa.py` gate, `shared/output_render.py` markdown templates, artifact bytes to object storage, download route |
| Unit tests | `test_qa.py` (blockers vs warnings), `test_output_render.py` (sourcing, withheld table, table-injection safety) |
| Module tests | `test_outputs_api.py` — generate, download as attachment, regenerate replaces, conflict blocks, hold blocks, uncited value never stated, BOM goals pull in M6 |
| Gateway | Proxies `GET|POST /api/projects/{id}/outputs` + `GET /api/outputs/{id}/download` |
| Frontend | `listOutputs`, `generateOutput` live; `outputDownloadUrl` wires the Download button |

**Done when:** Print on Outputs tab writes a real file built only from approved, cited facts. ✅

**Key design decision:** a value is stated only when it is publishable **and
cited**. Status alone is not enough — an attribute claiming `known` with no
evidence behind it is withheld. Everything withheld appears in a **Not
established** table with its reason, so an incomplete document cannot read as a
complete one.

**Blocked ≠ silent:** a QA-blocked print writes a `qa_failed` row listing the
blockers, but no file (`/download` → 409).

**Format:** markdown, chosen so the artifact needs no rendering dependency.
Swapping in PDF later touches `shared/output_render.py` only.

**Cleanup landed with M8:** the deprecated `app/main.py`, `app/routers/`,
`app/db/` and `app/models/` are deleted. `app/config.py` stays — it is the
shared settings module every service imports.

---

## Frontend switch-over (per merge)

When a service is merged and module tests pass, change only the matching functions in `lib/api.ts` from the `USE_MOCK` branch to `http()`.

| Merge | `lib/api.ts` functions | Status |
| --- | --- | --- |
| M1 | `listProjects`, `getProject`, `createProject` | ✅ live |
| M2 | `uploadDocument` | ✅ live |
| M3 | `listQuestions`, `answerQuestion` | ✅ live |
| M4 | `listAttributes`, `extractAttributes` | ✅ live |
| M5 | `listReviewItems`, `submitReviewDecision` | ✅ live |
| M8 | `listOutputs`, `generateOutput`, `outputDownloadUrl` | ✅ live |

Set when M1 is live:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## Local stack

| Component | Role | Status |
| --- | --- | --- |
| **API gateway** | `:8000` — only public port the frontend uses | ✅ |
| **project-service** | `:8001` | ✅ |
| **file-service** | `:8002` | ✅ |
| **question-service** | `:8003` | ✅ |
| **evidence-service** | `:8004` | ✅ |
| **review-service** | `:8005` | ✅ |
| **relationship-service** | `:8006` (internal) | ✅ |
| **vision-service** | `:8007` (internal) | ✅ |
| **generation-service** | `:8008` | ✅ |
| **PostgreSQL** | Host port **5433** → container 5432 | ✅ |
| **MinIO** | `:9000` API, `:9001` console | ✅ |
| **pgvector** | evidence-service embeddings | deferred (M4 ships key-free) |
| **Redis** | Events, LangGraph interrupts | M5+ |

`backend/.env.example` has all required vars for M1–M3. Copy to `backend/.env`.

Postgres uses port **5433** on the host because **5432** is often taken by Colima or local Postgres installs.

```bash
cd backend
docker compose up -d    # starts postgres + minio
```

---

## Order of work next

**M1–M8 are merged.** The build plan is complete: every tab is live and every
public route is a gateway proxy.

Remaining verification (not new features):

1. Apply migrations `006`–`008` against real Postgres — they have only run
   against SQLite via the test suite
2. Manual end-to-end pass: create → upload → questions → evidence → resolve a
   hold → print → download
3. Environment: the repo documents Python **3.12+**; development has been on
   **3.11.9**

Deferred upgrades, none blocking:

- PDF/DOCX artifacts (swap the writer in `shared/output_render.py`)
- Real relationship graph for variants, replacing (category, field, value)
- pgvector/embeddings for semantic retrieval in evidence-service
- Apify provider for JS-heavy web pages (`_fetch_apify` is still a stub)
- Redis / LangGraph orchestration

---

## Migration note (monolith → services)

M1–M3 are extracted. `backend/app/routers/` still holds **stub routers** for attributes, reviews, outputs — wired into the gateway until their services merge. The old `backend/app/main.py` is deprecated; use `gateway.main:app` on port 8000.
