# Demo data notes

The seed in `lib/mock-data.ts` is built to demonstrate the three
differentiators live, not just to fill screens. It follows the lessons in the
"where it bites" table from the original brief: seed a real conflict, seed a
repeated error, and don't leave the demo to chance.

## Project: SV-24 Outdoor Water Inlet Valve (`prj-1042`)

The main demo project. Status: **waiting for approval**.

### 1. A real conflict (evidence + review)

`maximum_pressure` has two disagreeing sources:

- datasheet rev B, p.3 → **16 bar**
- product web page → **10 bar**

This surfaces as:
- an attribute with status `conflicting` and lowered confidence in the
  **Evidence** tab (click it to see both quotes)
- a critical-severity conflict card in the **Review** tab, recommending 16 bar
  (newer, higher-authority source) but requiring human approval

### 2. A repeated error (bulk propagation)

A `connection_standard` correction (NPT → BSPP) is flagged as matching a
known extraction error for Acme datasheets using the same table template.
The Review tab shows it affects **62 sibling SKUs**, and the approve button
reads "Approve & propagate". This is the signature feature — one correction,
many products.

### 3. A missing high-risk field (abstention)

`chemical_compatibility` is `missing` with zero confidence and no evidence.
It shows as an unresolved high-risk review item that explicitly says it
cannot be inferred from general knowledge — demonstrating that the system
abstains instead of hallucinating a safety-critical value.

### The open question

`fail_safe_mode` ("close on power loss or stay open?") is the current open
completeness question — critical priority, blocks the actuator selection and
therefore the BOM. Answering it in the Questions tab persists in mock mode.

## Other projects

- `prj-1041` — Series X Ball Valve catalog cleanup, mid-collection (41%),
  one document still "processing" — shows an in-progress state.
- `prj-1039` — Sensor RFQ, completed (100%), with a QA-passed output — shows
  the finished end state and the Outputs tab populated.

## Editing

All of this lives in `lib/mock-data.ts`. Mutations in mock mode (answering a
question, approving a review) persist in memory for the session via the
in-memory clone in `lib/api.ts`, so the flows feel real during a demo.
