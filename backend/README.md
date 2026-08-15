# ForgeData — Backend (placeholder)

FastAPI service that the frontend talks to. Right now it's a **scaffold**:
the Projects router has a working in-memory store, everything else returns
empty lists or `501 Not Implemented` with a pointer to the file to fill in.

The point of this package is to lock the **API contract** (paths + JSON
shapes) so the frontend can be built and demoed against mock data now, and
switched to the real backend later without touching any components.

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Point the frontend at it by setting `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
in the frontend's `.env.local`. With that unset, the frontend runs on mock
data and never calls this service.

## Layout

```
backend/app/
├── main.py              FastAPI app + CORS + router wiring
├── config.py            env-driven config (expand in Phase 2)
├── models/schemas.py    Pydantic models — MUST match frontend lib/types.ts
└── routers/
    ├── projects.py      ✅ working in-memory CRUD
    ├── files.py         ⏳ acknowledges uploads; TODO object storage
    ├── attributes.py    ⏳ returns []; TODO extraction pipeline
    ├── questions.py     ⏳ returns []; TODO completeness loop
    ├── reviews.py       ⏳ returns []; TODO approval + bulk propagation
    └── outputs.py       ⏳ returns []; TODO generation + QA
```

## API contract (what the frontend expects)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/projects` | list projects |
| POST | `/api/projects` | create a project |
| GET | `/api/projects/{id}` | get one project |
| POST | `/api/projects/{id}/files` | upload a document |
| GET | `/api/projects/{id}/attributes` | list extracted attributes + evidence |
| GET | `/api/projects/{id}/questions` | list questions (open + history) |
| POST | `/api/projects/{id}/questions/{qid}/answer` | answer a question |
| GET | `/api/projects/{id}/reviews` | list review tasks |
| POST | `/api/reviews/{rid}/decision` | approve / edit / reject / mark unresolved |
| GET | `/api/projects/{id}/outputs` | list generated outputs |
| POST | `/api/projects/{id}/outputs` | generate an output |

See `context.md` in the repo root for the full architecture and the phased
build order.
