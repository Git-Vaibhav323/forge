# ForgeData — sample test data

Matches the current build state: **project-service (M1)** and **file-service
(M2) are live**; question/evidence/review/generation services are still
mock-only in the frontend. So this kit has two tiers:

- `datasheets/` + `fixtures/projects.json` + `seed.py` → real data you can
  push through the **live** API right now (create projects, upload files).
- `fixtures/attributes.json` + `fixtures/reviews.json` → data shaped like
  what evidence-service (M4) and review-service (M5) will eventually
  return, for wiring into frontend mocks or a DB seed script once those
  services exist.

## What's in the dataset

8 test products, deliberately not clean, on purpose:

- **5 Meridian gate valves** (`mfc-gv-100` … `mfc-gv-300`) all carry the
  *same wrong* `Max Working Pressure: 285 PSI` line — a seeded template
  error. Correcting the first one should be able to find and fix the other
  four. This is the case your bulk-fix propagation demo needs; without a
  planted repeated error, that screen has nothing to show on stage.
- **3 products with genuine two-source conflicts**: Vantage VB-220
  (600 PSI vs 720 PSI), Ironclad ICV-45 (180°C vs 210°C), Titan TBV-12
  (232 PSI vs 275 PSI).

11 one-page PDF "datasheets" back all of this — real files, generated with
reportlab, not placeholders — so file upload, OCR/extraction, and
evidence-linking all have something real to chew on.

## ⚠️ Before you run seed.py

The exact JSON your `POST /api/projects` and `POST /api/projects/{id}/files`
endpoints expect isn't something I have (I only have the plan doc, not
`shared/schemas.py`). `seed.py` guesses `{name, goal, category}` for
project creation and a `file` multipart field for upload — both are marked
`# ADJUST IF 422` in the script. Open **http://localhost:8000/docs** first,
check the real request shape against the guess, and edit those two spots
if they don't match. Two lines to fix, not a rewrite.

## How to run it

1. **Start the backend** (from your `backend/` folder):
   ```bash
   docker compose up -d          # Postgres :5433, MinIO :9000/9001
   source .venv/bin/activate     # Python 3.12 venv
   alembic upgrade head          # use .venv/bin/alembic
   ./scripts/run-dev.sh          # gateway :8000 + project-service + file-service
   ```
   Confirm it's up: http://localhost:8000/health and http://localhost:8000/docs

2. **Check the request schemas** at `/docs` and fix `seed.py` if needed
   (see the warning above).

3. **Generate the PDFs** (already done in this kit, but if you regenerate
   or add products):
   ```bash
   pip install reportlab --break-system-packages   # if not already installed
   python3 make_datasheets.py
   ```

4. **Seed the live services**:
   ```bash
   pip install requests --break-system-packages    # if not already installed
   python3 seed.py --base-url http://localhost:8000
   ```
   It health-checks the gateway first, creates all 8 projects, uploads
   their PDFs, and prints a slug → project_id summary at the end. Save
   that mapping — you'll want the project_ids for manual testing in
   `/docs` or in the frontend Overview tab.

5. **Start the frontend** (repo root):
   ```bash
   cp .env.example .env.local
   # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 in .env.local
   npm install && npm run dev
   ```
   Overview should now show your 8 seeded projects and their uploaded
   documents, live from Postgres/MinIO. Everything past that (Questions,
   Evidence, Review, Outputs tabs) is still on frontend mock data — that's
   expected until M3 onward are merged.

6. **Wire the mock tiers** for the screens that aren't live yet: swap the
   contents of `fixtures/attributes.json` and `fixtures/reviews.json` into
   wherever your frontend's mock data currently lives (e.g. the
   `USE_MOCK` branches in `lib/api.ts`), matching them up by `project_slug`
   to the real `project_id`s `seed.py` printed. This gets you a Review
   screen with real conflicts and a working bulk-fix propagation demo
   (4 products fixed at once) without waiting on M4/M5.

## Field-shape note

`attributes.json` uses `{ attribute, value, unit, source, page, evidence,
confidence, status }` — the locked shape from the plan. The `status` enum
(`extracted` / `needs_review` / `conflicting`) is my best reading of the
plan's rules (safety-critical fields always pause; two disagreeing sources
= conflicting) — the plan doc doesn't spell out the full enum, so check it
against `shared/schemas.py` and rename if it differs.
