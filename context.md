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
Define goal → ingest documents → extract facts + evidence
   → check completeness → ask the single most important missing question
   → validate answer → update model → repeat
   → pause for human approval on conflicts / high-risk fields
   → generate final output → QA → deliver
```

Three things make it distinct, and the UI is built around them:

1. **Evidence-first.** Every field carries its source (document, page,
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
│   ├── evidence/             AttributeTable, EvidencePanel
│   ├── questions/            QuestionCard, QuestionHistory
│   ├── review/               ReviewItemCard
│   └── outputs/              OutputCard
├── hooks/useProjectData.ts   data-fetching hooks (project, attributes, etc.)
├── lib/
│   ├── types.ts              ⭐ CANONICAL SCHEMA — the locked wire shape
│   ├── mock-data.ts          seeded demo data (has a real conflict + bulk case)
│   ├── api.ts                API client: mock mode by default, live if env set
│   └── utils.ts              cn(), formatters, simulateLatency()
├── backend/                  FastAPI placeholder (see backend/README.md)
│   └── app/
│       ├── main.py           app + CORS + router wiring
│       ├── models/schemas.py ⭐ Pydantic mirror of lib/types.ts
│       └── routers/          projects (working) + stubs for the rest
└── docs/                     design + demo notes
```

## Tech stack

- **Frontend:** Next.js 14 (App Router), React 18, TypeScript (strict),
  Tailwind CSS, lucide-react icons, IBM Plex Sans/Mono.
- **Backend (planned):** FastAPI + Pydantic, PostgreSQL + pgvector,
  object storage (MinIO/S3), Redis + Celery, LangGraph for the workflow,
  PyMuPDF/OCRmyPDF/Tesseract for documents, Pint for units. See
  `backend/requirements.txt` for the phased dependency list.

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
| GET | `/api/projects/{id}/attributes` | `listAttributes` |
| GET | `/api/projects/{id}/questions` | `listQuestions` |
| POST | `/api/projects/{id}/questions/{qid}/answer` | `answerQuestion` |
| GET | `/api/projects/{id}/reviews` | `listReviewItems` |
| POST | `/api/reviews/{rid}/decision` | `submitReviewDecision` |
| GET | `/api/projects/{id}/outputs` | `listOutputs` |
| POST | `/api/projects/{id}/outputs` | `generateOutput` |

## Build order (backend)

The frontend is done and demoable now on mock data. Fill the backend in
this order — each phase makes one more tab real:

1. **Phase 1 — project loop:** Projects (done) + File upload + PostgreSQL +
   category schema + missing-field detection + Question loop → Overview,
   Questions tabs go live.
2. **Phase 2 — evidence & RAG:** document extraction (PyMuPDF/OCR), evidence
   chunks, embeddings (pgvector), attribute extraction → Evidence tab goes
   live.
3. **Phase 3 — validation & approval:** unit normalization, conflict
   detection, risk classification, LangGraph human-approval interrupts,
   audit log → Review tab goes live.
4. **Phase 4 — relationships:** variants, accessories, compatibility,
   knowledge-graph tables, BOM.
5. **Phase 5 — vision:** nameplate/label extraction, image-to-SKU matching,
   table reconstruction.
6. **Phase 6 — generation:** goal-specific output templates + QA gate →
   Outputs tab goes live.

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
