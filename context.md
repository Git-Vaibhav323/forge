# ForgeData — Project Context

> This file exists so an IDE / AI coding assistant has the full picture of
> what this project is, how it's structured, and what the rules are. Read it
> before generating or changing code.

## What this is

**ForgeData** is an evidence-grounded industrial product-intelligence
platform. It turns fragmented product data (PDF datasheets, product images,
incomplete CSV catalogs, RFQs, web pages) into a **complete, validated,
human-approved output** — a product configuration, bill of materials,
technical quote, datasheet, installation package, replacement
recommendation, or RFQ response.

It is **not** just an extractor and **not** just a data checker. The core
idea is a goal-driven loop:

```
Define goal → ingest documents (PDF upload, web URL, pasted HTML)
   → extract facts + evidence (never invent)
   → check completeness → ask the single most important missing question
   → validate answer → update model → repeat
   → pause for human approval on conflicts / high-risk fields
   → generate final output → QA → deliver
```

Three things make it distinct, and the UI is built around them:

1. **Evidence-first.** Every field carries its source (document or URL, page,
   quoted text, confidence, status). The UI never shows a bare value.
2. **Abstention over hallucination.** A field can be "missing",
   "conflicting", or "needs review" instead of being invented.
3. **Bulk-fix propagation.** One human correction can be applied across
   hundreds of sibling SKUs that share the same extraction error.

**Governance rule (non-negotiable):** conflicts, high-risk fields
(voltage, pressure, temperature, chemical compatibility, safety certs),
bulk corrections, and published-data changes ALWAYS pause for human
approval. Everything else (OCR, normalization, drafts, low-risk questions)
runs automatically.

## Repo layout

```
forgedata/
├── app/                      Next.js App Router pages
│   ├── page.tsx              dashboard (project list)
│   ├── projects/new/         create-project flow (goal, identity, upload)
│   ├── projects/[projectId]/ project workspace
│   │   ├── layout.tsx        header + tab nav (Overview/Evidence/Questions/Review/Outputs)
│   │   ├── page.tsx          Overview (next step, docs, at-a-glance)
│   │   ├── evidence/         attribute table + evidence panel
│   │   ├── questions/        completeness Q&A loop
│   │   ├── review/           conflict / high-risk / bulk-propagation approval
│   │   └── outputs/          generate + list final artifacts
│   └── settings/             backend connection info
├── components/
│   ├── ui/                   primitives (Button, Badge, Card, Progress, Tabs, Field)
│   ├── layout/               AppShell, Sidebar
│   ├── shared/               StatusBadge, Meters, EmptyState
│   ├── projects/             GoalSelector, UploadDropzone
│   ├── evidence/             AttributeTable, EvidencePanel, AddWebSourceCard
│   ├── questions/            QuestionCard, QuestionHistory
│   ├── review/               ReviewItemCard
│   └── outputs/              OutputCard
├── hooks/useProjectData.ts   data-fetching hooks (project, attributes, etc.)
├── lib/
│   ├── types.ts              ⭐ CANONICAL SCHEMA — the locked wire shape
│   ├── mock-data.ts          seeded demo data (has a real conflict + bulk case)
│   ├── api.ts                API client: mock mode by default, live if env set
│   └── utils.ts              cn(), formatters, simulateLatency()
├── backend/                  FastAPI microservices (see backend/README.md)
│   ├── gateway/              public API :8000
│   ├── services/
│   │   ├── project_service/  :8001 jobs
│   │   ├── file_service/     :8002 uploads + web sources
│   │   ├── question_service/ :8003 completeness loop
│   │   └── evidence_service/ :8004 cited attributes
│   └── shared/               schemas + SQLAlchemy models
└── docs/                     design + demo notes
```

## Tech stack

- **Frontend:** Next.js 14 (App Router), React 18, TypeScript (strict),
  Tailwind CSS, lucide-react icons, IBM Plex Sans/Mono.
- **Backend:** FastAPI microservices behind gateway :8000, PostgreSQL,
  object storage (MinIO or Supabase S3), `pypdf` for PDF text, deterministic
  label→field rules for extraction (no LLM required today). Optional later:
  pgvector/embeddings, OCR, Apify for JS-heavy web pages. Pint for units in M5.
  See `backend/requirements.txt` and `plan.md`.

## The data contract (READ THIS BEFORE CHANGING SCHEMAS)

The frontend and backend describe the **same wire shape**. The locked
field-level JSON is:

```
{ attribute, value, unit, source, page, evidence, confidence, status }
```

- Frontend source of truth: `lib/types.ts`
- Backend mirror: `backend/app/models/schemas.py`

If you change one, change the other. The Evidence panel, Attribute table,
Review console, and Question loop all render directly off these types — an
unmatched field breaks the review flow silently.

Key enums:
- `FieldStatus`: known | verified | derived | needs_review | conflicting |
  missing | unverified | not_applicable
- `Severity`: low | medium | high | critical
- `ProjectStatus`, `ProjectGoal` — see `lib/types.ts`

## Mock mode vs live mode

`lib/api.ts` is the single seam. If `NEXT_PUBLIC_API_BASE_URL` is set, every
function calls the real backend at the path in the contract table
(`backend/README.md`). If unset, it reads/writes an in-memory clone of
`lib/mock-data.ts`, so the whole app is clickable with no backend.

**When implementing a backend route, you only change the matching function
in `lib/api.ts` — never the components.**

## API contract

| Method | Path | Frontend fn (`lib/api.ts`) |
| --- | --- | --- |
| GET | `/api/projects` | `listProjects` |
| POST | `/api/projects` | `createProject` |
| GET | `/api/projects/{id}` | `getProject` |
| DELETE | `/api/projects/{id}` | `deleteProject` |
| POST | `/api/projects/{id}/files` | `uploadDocument` |
| POST | `/api/projects/{id}/sources` | `addWebSource` |
| GET | `/api/projects/{id}/attributes` | `listAttributes` |
| POST | `/api/projects/{id}/attributes/extract` | `extractAttributes` |
| GET | `/api/projects/{id}/questions` | `listQuestions` |
| POST | `/api/projects/{id}/questions/{qid}/answer` | `answerQuestion` |
| GET | `/api/projects/{id}/reviews` | `listReviewItems` |
| POST | `/api/reviews/{rid}/decision` | `submitReviewDecision` |
| GET | `/api/projects/{id}/outputs` | `listOutputs` |
| POST | `/api/projects/{id}/outputs` | `generateOutput` |

## Document ingest (what counts as a source)

ForgeData does **not** search the open web or invent facts from a URL alone.
A field only becomes `known` when extraction finds a **quoted line** in a
stored source on the job.

| Source type | How it arrives | Stored as |
| --- | --- | --- |
| PDF datasheet | Overview upload | `type=pdf` in object storage |
| Web catalog page | Evidence → **Add a web source** (URL) | `type=web`, `sourceUrl` set |
| Pasted HTML | Evidence → paste HTML + citation URL | `type=web` (no live fetch) |

**Web fetch today:** `WEB_FETCH_PROVIDER=direct` (default) — backend HTTP GET
of the URL you paste. Works for static HTML catalogs. No Apify token required.

**When direct fetch fails** (JavaScript-only page, bot wall): use **paste HTML**
on the Evidence tab, or wait for Apify integration (env placeholders exist;
not called yet).

After any new source, **Re-scan documents** on Evidence runs extraction.
PDF vs web disagreements on the same field → `conflicting` → M5 Review.

## Build order (backend)

The frontend is done and demoable on mock data. Backend milestones:

1. **M1–M3 ✅** — Projects, file upload, question loop (Overview + Questions live).
2. **M4 ✅** — evidence-service: PDF + web sources → cited attributes (Evidence live).
   Key-free extraction (`pypdf` + label rules). pgvector/LLM deferred.
   Web ingest via `POST /api/projects/{id}/sources`; **direct fetch only** for now.
3. **M5** — review-service: Pint normalization, conflict/high-risk queue, decisions,
   bulk propagate → Review tab live.
4. **M6** — relationship-service: variants, BOM, compatibility.
5. **M7** — vision-service: nameplate OCR, image sources.
6. **M8** — generation-service: outputs + QA gate.

Optional upgrades (not blocking M5): Apify actor for web fetch, pgvector RAG,
OCR for scanned PDFs.

## Design language (keep it consistent)

The look is a precise, evidence-driven data console — not a marketing page.

- **Palette:** warm paper `#F7F6F2`, white panels, near-black ink `#15161A`,
  hairline borders `#DEDBD1`. Status colors are muted and functional:
  verified green, review amber, conflict red, accent blue, missing grey.
- **Type:** IBM Plex Sans for UI, IBM Plex Mono for values, IDs, labels,
  and confidence — data reads as data. Tabular numerals everywhere numbers
  appear (`.num` utility).
- **Density:** compact rows, small radii (2–4px), one hairline between
  everything. No large shadows, no gradients, no rounded pills except
  status badges.
- **Rule:** monospace + uppercase micro-labels for structural signposting
  (`.label-caps`). Confidence is always a 5-segment meter, never a bare %.

Follow `docs/design-notes.md` for the full token list and `docs/demo-data-notes.md`
for what the seeded conflict/bulk-fix data is demonstrating.

## Quality floor

Responsive, visible keyboard focus (`:focus-visible` is styled globally),
`prefers-reduced-motion` respected (no essential animation), strict
TypeScript with `noUncheckedIndexedAccess`.
