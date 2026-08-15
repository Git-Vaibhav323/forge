# ForgeData — Backend plan

Fill the FastAPI service in this order. Each phase turns one more frontend tab from mock data into a live API. Do not skip ahead: later phases assume the earlier store, files, and field model exist.

The UI is already demoable. Leave `NEXT_PUBLIC_API_BASE_URL` unset until a phase’s routes return the same JSON as `lib/types.ts`. Then flip only the matching function in `lib/api.ts` — never the React components.

---

## Current state

| Piece | Status |
| --- | --- |
| Frontend (all tabs) | Done on mock data (`lib/mock-data.ts`) |
| `GET/POST /api/projects`, `GET /api/projects/{id}` | Working, **in-memory only** |
| `POST /api/projects/{id}/files` | Acknowledges upload, **does not store bytes** |
| Attributes, questions, reviews, outputs | Empty list or `501 Not Implemented` |
| Postgres, MinIO, Redis, LLM | Not wired |

Run the stub:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health: `http://localhost:8000/health`  
Docs: `http://localhost:8000/docs`

---

## Hard rules (every phase)

1. **Wire shape is locked.** Field JSON is `{ attribute, value, unit, source, page, evidence, confidence, status }`. Change `lib/types.ts` and `backend/app/models/schemas.py` together.
2. **One seam.** Only `lib/api.ts` talks to the backend. Flip one function at a time when that route is real.
3. **Abstain, don’t invent.** A field may be `missing`, `conflicting`, or `needs_review`. Never fill a technical value from model knowledge.
4. **Human gate.** Conflicts, high-risk fields (voltage, pressure, temperature, chemical compatibility, safety certs), bulk edits, and published-data changes always pause for a person. OCR and drafts may run unattended.

---

## Phase 1 — Project loop

**Unlocks:** Overview tab, Questions tab  
**Calendar:** 2–3 weeks  
**Files:** `routers/projects.py`, `routers/files.py`, `routers/questions.py`, `config.py`

### Build

- Replace the in-memory `_projects` dict with PostgreSQL (SQLAlchemy + psycopg).
- Persist uploads to MinIO / S3-compatible storage. Store `documentId`, hash, filename, type, status.
- Load a **required-field schema** per `goal` + `category` (what must be known before the job can move).
- Completeness: classify each required field (`known` / `missing` / …). Compute `completionScore` and `blockingFieldsCount` from that, not a static number.
- Ask **one** open question at a time (highest impact ÷ effort). Record answers and re-run completeness.
- Process files inline for this cut. Redis/Celery can wait.

### Routes that must work

| Method | Path |
| --- | --- |
| GET | `/api/projects` |
| POST | `/api/projects` |
| GET | `/api/projects/{id}` |
| POST | `/api/projects/{id}/files` |
| GET | `/api/projects/{id}/questions` |
| POST | `/api/projects/{id}/questions/{qid}/answer` |

### Dependencies to add

`sqlalchemy`, `psycopg[binary]`, `pydantic-settings`. MinIO client when uploads persist.

### Done when

You can create a job against the live API, upload a PDF, and answer the next missing field. Overview and Questions stop using mock data. Then set:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## Phase 2 — Evidence and RAG

**Unlocks:** Evidence tab  
**Calendar:** 3–4 weeks  
**Files:** `routers/attributes.py`, new document-intelligence module

### Build

- Extract text from PDFs (PyMuPDF). OCR fallback for scans (OCRmyPDF / Tesseract).
- Chunk with **page + quoted text**. Store chunks; embed into **pgvector**.
- Map chunks onto `Attribute` records with `confidence` and `status`. Keep `rawValue` even after unit normalize.
- Two sources that disagree become `conflicting` — not a merged value.

### Routes

| Method | Path |
| --- | --- |
| GET | `/api/projects/{id}/attributes` |

Wire `listAttributes()` in `lib/api.ts` only.

### Dependencies to add

`pymupdf`, `ocrmypdf`, `pgvector`. Embedding model/API as chosen.

### Done when

The Evidence tab shows real fields with source, page, quoted text, and confidence. Missing stays missing.

---

## Phase 3 — Validation and approval

**Unlocks:** Review tab  
**Calendar:** 3–4 weeks  
**Files:** `routers/reviews.py`

### Build

- Normalize units with Pint; keep the raw string.
- Detect conflicts across sources.
- Classify risk. Voltage / pressure / temperature / chemistry / certs are always `needs_review` or a review task.
- Persist review tasks and decisions (`approve` / `edit` / `reject` / `unresolved`).
- **Bulk propagate:** one approved edit can stage the same correction across sibling SKUs that share the error fingerprint, with rollback.
- Audit log of every human decision.
- LangGraph interrupt is the workflow pause — not a chatbot.

### Routes

| Method | Path |
| --- | --- |
| GET | `/api/projects/{id}/reviews` |
| POST | `/api/reviews/{rid}/decision` |

### Dependencies to add

`langgraph`, Pint, Redis if the workflow needs a durable interrupt.

### Done when

Review lists real holds. Approve / edit / reject persist. Print stays blocked while holds exist.

---

## Phase 4 — Relationships

**Unlocks:** BOM / configuration jobs that are more than a flat field list  
**Calendar:** 2–3 weeks

### Build

- Variants, accessories, compatibility, BOM tables **in Postgres**. No graph database in this phase.
- A `product_configuration` or `bom_generation` job must resolve parts that actually fit.
- Mismatches become review items (Phase 3 contract), not silent merges.

### Done when

A configuration or BOM job resolves compatible parts and raises mismatches as holds.

---

## Phase 5 — Vision

**Unlocks:** Nameplate photos and scanned tables as first-class sources  
**Calendar:** 2–3 weeks

### Build

- Nameplate / label OCR.
- Image-to-SKU matching.
- Table reconstruction from scanned datasheets.
- Feed the **same** attribute + evidence contract. Do not add a parallel schema.

### Done when

A nameplate photo can fill or conflict with datasheet fields, citing the image as source.

---

## Phase 6 — Generation

**Unlocks:** Outputs tab  
**Calendar:** ~2 weeks  
**Files:** `routers/outputs.py`

### Build

- Goal-specific templates (configuration, BOM, quote, datasheet, installation pack, RFQ reply).
- QA gate: every emitted field is cited and approved. Unresolved conflicts block generation.
- Store the artifact; return it on list/create.

### Routes

| Method | Path |
| --- | --- |
| GET | `/api/projects/{id}/outputs` |
| POST | `/api/projects/{id}/outputs` |

### Done when

Print on the Outputs tab writes a real file built only from approved, cited facts.

---

## Frontend switch-over (per phase)

When a route is real, change only the matching function in `lib/api.ts` from the `USE_MOCK` branch to `http()`. Components stay untouched.

| Phase | `lib/api.ts` functions |
| --- | --- |
| 1 | `listProjects`, `getProject`, `createProject`, `uploadDocument`, `listQuestions`, `answerQuestion` |
| 2 | `listAttributes` |
| 3 | `listReviewItems`, `submitReviewDecision` |
| 6 | `listOutputs`, `generateOutput` |

---

## Suggested local stack (from Phase 1)

| Service | Role |
| --- | --- |
| PostgreSQL | Jobs, documents metadata, attributes, questions, reviews, audit |
| pgvector (Phase 2) | Evidence embeddings |
| MinIO | Uploaded PDFs / images / CSV |
| Redis + Celery (Phase 3+) | Extraction jobs, LangGraph interrupts |

`backend/.env.example` already lists `DATABASE_URL`, `REDIS_URL`, `OBJECT_STORAGE_ENDPOINT`, `LLM_API_KEY`. Fill them as each phase needs them — not all at once.

---

## Order of work this week

1. Postgres + project CRUD persistence (`projects.py`).
2. File upload to MinIO + document row (`files.py`).
3. Category/goal required-field schema + completeness score.
4. Question loop (`questions.py`) so Overview + Questions can go live.
5. Only then start Phase 2 extraction.
