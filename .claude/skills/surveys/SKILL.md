---
name: surveys
description: Report the status of every survey (literature-search topic) in the Paper Atlas /litsearch pipeline — tagged paper count, queue depth split by core/foundational, the paper currently in progress and its step/round, and whether the survey's site page and PDF exist. Use whenever the user asks "what surveys exist", "survey status", "what's the state of <survey>", "how far along is the <survey> survey", "list surveys", or wants an overview before deciding what to work on next — even a bare "status" while discussing Paper Atlas surveys. Read-only; makes no changes. Do NOT use to start or resume processing papers for a survey (that's /litsearch, in `.claude/skills/litsearch/`) or to build/refresh a survey's page and PDF (that's /survey). Also do NOT use for refsite-runner's chapter/paper build queue (repos with prompts/queue.md + content/registry.json) — this skill is specific to this repo's data/litsearch/*.state.json + data/queue.json.
---

# /surveys — Paper Atlas survey status

Read-only status report. Run from the repo root:

```bash
python3 scripts/litsearch.py status --json
```

This joins `data/surveys.json` (every defined survey), `data/litsearch/<id>.state.json`
(if the survey has ever been run through `/litsearch` — most haven't yet: a survey
tagged by hand via Procedure D, like the current `benchmarks`/`evaluations`, has no
state file and reports `"phase": "idle"`), `data/queue.json` (counted by `survey` +
`role`), and `data/papers.json` (tag counts). Nothing here mutates state — this skill
only reads and reports.

## Present it as a table

Turn the JSON array into a markdown table with these columns, in this order:

| survey | tagged | queue (core/found) | phase | current | page | pdf |
|---|---|---|---|---|---|---|

- `survey` — the `id` (use `label` in parens if it differs meaningfully from `id`).
- `tagged` — `tagged` field, the paper count in the graph carrying this survey's tag.
- `queue (core/found)` — `queue_core` / `queue_foundational`, e.g. `9 / 3`.
- `phase` — `phase` verbatim (`idle`, `seeding`, `processing`, `survey`).
- `current` — `-` if `current` is null; otherwise `<slug> (<step>, round <round>)`,
  omitting the round clause when `round` is null.
- `page` — `✓` if `page_exists`, else `—` if no `page` is set at all, else `missing`
  (a `page` key exists in `surveys.json` but the file isn't on disk — flag this, it's
  a bug, not a pending-work state).
- `pdf` — same three-way logic as `page`, using `pdf`/`pdf_exists`.

After the table, add `last_activity` as a one-line aside per survey that has one (it's
a log line like `"2026-07-18T13:28 completed foo-2024-bar (verdict=approved, rounds=2)"`
— just show it, don't reparse it).

## Suggest the next command

For every survey whose `phase` is not `idle`, add one line after the table:

- `phase: seeding` → `` `/litsearch <id>` to run/continue seeding. ``
- `phase: processing` with `current` set → `` `/litsearch <id>` to resume `<slug>` at
  step `<step>`` (mention the round if the step is `critique` or `revise`).
- `phase: processing` with `current` null → `` `/litsearch <id>` to continue — N core
  paper(s) queued.`` (use `queue_core`; if it's `0` and `queue_foundational > 0`, say so
  instead — foundational papers only process when the survey's state file has
  `process_foundational: true`).
- `phase: survey` → `` `/survey <id>` to continue building the survey artifact.``

If a survey is `idle` with a nonzero `queue_core`/`queue_foundational` (papers queued
but nothing in progress and no active phase), call that out explicitly — it usually
means a `/litsearch` run was interrupted before `seed-done`/`start-paper` ran, or the
queue was hand-edited; the fix is just running `/litsearch <id>` again, but it's worth
surfacing as unusual rather than silently folding into the normal "idle" case.

If `data/surveys.json` has no entries at all, say so plainly and suggest `/litsearch
<topic>` to create the first one — don't print an empty table.

## Worked example

Real output from this repo today (2026-07-18, before any `/litsearch` run has ever
happened — both existing surveys were built by hand via CLAUDE.md's Procedure D, so
neither has a state file):

```json
[
  {"id": "benchmarks", "label": "Benchmarks", "tagged": 137, "queue_core": 0,
   "queue_foundational": 0, "phase": "idle", "current": null,
   "page": "surveys/benchmarks.html", "page_exists": true, "pdf": null,
   "pdf_exists": false, "last_activity": null},
  {"id": "evaluations", "label": "Evaluations", "tagged": 66, "queue_core": 0,
   "queue_foundational": 0, "phase": "idle", "current": null,
   "page": "surveys/evaluations.html", "page_exists": true, "pdf": null,
   "pdf_exists": false, "last_activity": null}
]
```

renders as:

| survey | tagged | queue (core/found) | phase | current | page | pdf |
|---|---|---|---|---|---|---|
| benchmarks | 137 | 0 / 0 | idle | - | ✓ | — |
| evaluations | 66 | 0 / 0 | idle | - | ✓ | — |

Neither survey has a `state.json` yet and neither has a PDF; both idle rows get no
suggested-next-command line since `phase` is `idle` and `queue_core`/`queue_foundational`
are both `0`.

## When NOT to use this skill

- Starting or resuming a literature search (seeding, processing the queue,
  builder/critic loop) — that's `/litsearch`, once it exists in
  `.claude/skills/litsearch/`. This skill never calls `litsearch.py` subcommands other
  than `status`.
- Building or refreshing a survey's generated page/taxonomy/PDF — that's `/survey`.
- A chapter/paper build queue in a *different* repo that uses `prompts/queue.md` +
  `content/registry.json` — that's the `refsite-runner` skill's territory, not this
  one; this skill only understands Paper Atlas's `data/litsearch/` + `data/queue.json`.
- Editing `data/surveys.json` or tagging papers — that's Procedure D
  (`scripts/tag_papers.py`), unrelated to this read-only status report.

## Provenance and maintenance

- **Authored and verified: 2026-07-18**, against `scripts/litsearch.py`'s actual
  `compute_status()` output (the JSON shape above is a real command run, not a
  description from memory) and the current `data/surveys.json` (two surveys, both
  pageless-PDF, both idle).
- **Re-verify with:**

  ```bash
  python3 scripts/litsearch.py status --json
  ```

  If the JSON keys change (e.g. a new column is added to `compute_status()` in
  `scripts/litsearch.py`), update the column list and worked example above to match —
  this skill's table format is a direct read of that function's output shape.
- No other volatile facts — the state-machine step names (`resolve`, `fetch`, …) and
  phase names (`idle`, `seeding`, `processing`, `survey`) are defined in
  `scripts/litsearch.py` and change only when that file changes.
