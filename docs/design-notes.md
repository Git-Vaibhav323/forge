# Design notes

The brief is an industrial data-verification console — engineers and product
managers cleaning up messy catalogs where a wrong pressure rating is a real
hazard. So the design is deliberately **instrument-like**: quiet, dense,
legible, with data typeset as data. Trust comes from precision, not polish.

## Tokens

Colors (see `tailwind.config.ts`):

- `paper` `#F7F6F2` — app background (warm, low-glare, not pure white)
- `panel` `#FFFFFF` — cards/surfaces
- `ink` `#15161A` — primary text + primary buttons
- `muted` `#6B6960`, `faint` `#9C998E` — secondary/tertiary text
- `line` `#DEDBD1`, `line-strong` `#C7C3B6` — hairline borders
- Status (each with a soft background variant):
  - `verified` `#2F6E4E` — confirmed, evidence-backed
  - `review` `#A75A0A` — needs a human
  - `conflict` `#9A2E2E` — sources disagree
  - `accent` `#1F5AA6` — derived / neutral highlight / selection
  - `missing` `#6B6960` — no value / N/A

Type:

- **IBM Plex Sans** — all UI copy
- **IBM Plex Mono** — values, IDs, units, confidence, micro-labels. Anything
  that is *data* is monospaced so it reads as data.
- Tabular numerals globally (`.num`) so columns of numbers align.

Structure:

- Small radii (2–4px). Hairline (1px) borders do the separating, not shadow.
- `.label-caps` — mono, uppercase, tracked — for structural signposting
  (section eyebrows, table headers). Used sparingly.
- Confidence is a **5-segment meter**, never a bare percentage — it reads at
  a glance and encodes the verified/review/conflict thresholds in color.
- The completeness gauge is a thin ring, not a big number — it's ambient
  context, not the hero.

## Why not the defaults

Avoided the three AI-design clichés: no cream-and-terracotta, no
black-with-acid-accent, no broadsheet columns. The one risk taken is
treating the whole app as a **spreadsheet-grade instrument** — mono values,
segment meters, hairline density — which suits catalog-cleanup work and
would look wrong on a consumer app. That restraint is the point: the
signature is the evidence panel sitting beside every value.

## Copy

Plain, active, specific. Buttons say what happens ("Approve", "Generate",
"Submit answer"). Empty states point at the next action. Errors (in the
backend stubs) say what's missing and where to implement it.
