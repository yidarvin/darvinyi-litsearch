---
name: litsearch
description: Launch or resume a topic-driven literature search for Paper Atlas — seeds a survey's queue with high-priority core papers via multi-angle Semantic Scholar + web search, then (once milestone M4 lands) processes them one at a time with a sonnet-builder/opus-critic loop, tagging discovered core papers into the survey as it goes. Use whenever the user says "run a lit search on <topic>", "start a literature search", "search the literature for <topic>", "keep working on <survey>", "continue the lit search", "resume <survey>", or names a topic they want covered as a new or existing survey — even without the words "lit search", e.g. "let's build out an agent-benchmarks survey" or "find papers on <topic> and add them". Do NOT use for Procedure A's plain "run the next one" — the ~1,000-entry general queue has no survey attached, that's ordinary queue processing unrelated to this pipeline — for read-only status (use `/surveys`), or for building the survey's site/PDF once its corpus is tagged (use `/survey`).
---

# /litsearch — topic-driven literature search

Orchestrates a survey's pipeline through `data/litsearch/<id>.state.json`,
owned exclusively by `python3 scripts/litsearch.py`. Read
[CLAUDE.md](../../../CLAUDE.md)'s data-shapes section for that file's schema
before your first run. Every step here is meant to checkpoint to disk so a
kill mid-run (token exhaustion, Ctrl-C, a crash) loses at most the
in-flight step — see **Resume protocol** below; that property is the reason
this skill exists rather than just running Procedures A/B by hand.

**Current build status (2026-07-18, milestone M4 of PIPELINE_PLAN.md):**
this skill implements survey resolution (Step 0), seeding (Phase S), and
the per-paper builder/critic loop (Phase P) end to end, including the
resume-after-kill path (verified with a real interrupt-and-resume run —
see the worked examples).

## Invocation

`/litsearch <topic-or-survey-id> [N]` — `N` (optional) caps how many papers
to process in *this* run; omit it for unbounded (safe, because every step
checkpoints — an unbounded run just means "keep going until the queue's
core entries are drained or something needs your attention").

## Step 0 — resolve the survey

1. Read `data/surveys.json`. Match the argument against every `id` and
   `label`, case-insensitively, allowing partial/fuzzy word overlap (e.g.
   "agent benchmarks" should match a `label: "Agent Benchmarks"` or an
   `id: "agent-benchmarks"`).
   - **Exactly one plausible match** → that's the target survey. If the
     match wasn't exact (fuzzy), say which survey you resolved to in one
     line before continuing — cheap enough to not need a full pause, but
     worth stating since silently guessing wrong wastes a whole seeding
     pass.
   - **More than one plausible match** → ask one short question (the
     `AskUserQuestion` tool) listing the candidates plus a "this is a new
     topic" option.
   - **No match** → this is a new topic. Do not create the survey silently:
     a. Derive a survey id — lowercase, hyphenated, from the topic (drop
        filler words if a tighter id reads better, but keep it
        recognizable; never reuse or lightly vary an existing id).
     b. Pick a `color` distinct from every existing survey's `color` in
        `data/surveys.json` **and** from the teal selection accent
        (`#2dd4bf`, `src/style.css`'s `--accent`) — read the current
        palette before choosing, don't guess from memory.
     c. Draft a sharp `description`: the membership rubric — what makes a
        paper a *core* member, phrased like the existing two ("primary/
        headline contribution is X", not "uses/reports X"). This
        description is what Phase S's ranking and the future per-paper
        tagging step both apply, so vague wording here compounds.
     d. Present id + color + description in one message; get a one-shot
        confirm or edits before writing anything. This is the one piece of
        durable taxonomy the pipeline creates unprompted — worth a check
        even though the rest of the run is otherwise unattended.
     e. On confirm: append the entry to `data/surveys.json` (preserve
        existing entries' order and formatting exactly — this file has no
        canonicalizing script yet, so hand-edit carefully, matching the
        existing indentation), then `python3 scripts/litsearch.py init <id>
        --topic "<topic>"`.
   - **Existing survey with no state file** (both `benchmarks` and
     `evaluations` are in this state today — built by hand via Procedure D
     before this pipeline existed): ask the user whether to (i) treat the
     corpus as already complete — `init --seeding-done` it, landing `idle`,
     ready for `/survey` later — or (ii) gap-fill it, running seeding to
     find papers the manual pass missed (expect most hits to dedupe away
     against the 137/66 already-tagged papers). These are very different
     amounts of work; don't assume either.
2. Read the resulting state file and route on `phase`:
   `seeding` (and `seeding.done` false) → **Phase S**. `processing` →
   **Phase P**. `survey` → tell the user this is `/survey` territory and
   stop. `idle` → this survey has nothing to resume; report its
   `/surveys`-style status and ask what to do next.

## Phase S — seeding (skipped if `seeding.done` is already `true`)

Multi-angle search. Every Semantic Scholar call carries the API key header
(CLAUDE.md doctrine): `curl -s -H "x-api-key: $S2_API_KEY" "..."` — back off
and retry on 429, never drop the key even after a failure. Note the bulk
endpoint is keyword/phrase matching, not semantic search — expect noise in
raw results (a query like "agent benchmark" can surface loosely-related
high-citation papers); that's exactly why the rank + user-confirm steps
below exist, don't skip them because a query "looked" precise.

1. **S2 bulk search** — 3–5 phrasings of the topic (for "LLM and Agent
   benchmarks": "LLM agent benchmark", "language model agent evaluation
   environment", "agentic task benchmark", "tool-use benchmark language
   model", "web/computer-use agent benchmark" — adapt to the actual topic,
   this is an example set, not a fixed list) against:
   ```
   https://api.semanticscholar.org/graph/v1/paper/search/bulk
     ?query=<phrase>
     &fields=title,authors,year,venue,externalIds,citationCount,publicationDate,abstract
     &sort=citationCount:desc
   ```
   Run each phrasing once sorted by `citationCount:desc` and once by
   `publicationDate:desc` (drop `sort` for the API's relevance default) so
   both foundational and current papers surface — citation-sorted alone
   buries anything published in the last few months.
2. **Web search** (`WebSearch`) for 1–2 recent survey/review papers on the
   topic; pull candidates from their reference lists — the highest-
   precision source of "the named entries a survey would cite" (this is
   Procedure B's topic-search step, reused here).
3. **Snowball** — only on a gap-fill run (the survey already has tagged
   nodes): union the references + citations (from each tagged paper's S2
   record) of every already-tagged node, rank by how many are already
   in-corpus (in-degree among existing nodes is itself a relevance signal).
4. **Dedupe** every candidate against `data/papers.json` and
   `data/queue.json` — arxiv_id first (most reliable), then doi, then
   normalized title (lowercase, strip non-alphanumerics to spaces, collapse
   whitespace — the same normalization `scripts/tests/test_data_integrity.py`
   uses). **Trust arxiv_id matching over title matching**: the real M3 run
   below missed two duplicates on a manual title check because a title
   starting with a non-ASCII character (`τ-bench`) silently loses that
   character under naive lowercase+strip-non-alphanumeric normalization,
   collapsing to a near-empty, falsely-distinct string — arxiv_id comparison
   doesn't have that failure mode. Do the title check too (arxiv_id is
   sometimes missing or wrong), just don't rely on it alone for anything
   with a non-ASCII title.
5. **Rank** survivors: rubric-relevance first (does title+abstract read as
   a *core* member by the survey's `description`?), citation count as the
   tiebreaker.
6. **Cap at ~25** and present the list — title · authors · year ·
   citations · one-line why — for a single confirm/edit pass (the user may
   add, drop, or reprioritize freely). This is the pipeline's one
   interactive gate; once confirmed, everything through the rest of Phase S
   is mechanical.
7. On confirm, append each accepted paper to the **top** of
   `data/queue.json` (shift existing entries down; never reorder or touch
   anything already in the file) in that file's existing key style:
   ```json
   { "title": "…", "arxiv_id": "…", "doi": null, "authors": "…", "year": 2024,
     "venue": "…", "citation_count": 312, "topic": "…", "priority": "High",
     "source": "Lit search: <topic>", "why": "…", "survey": "<id>", "role": "core" }
   ```
   **Validate before checkpointing**: `python3 -m pytest
   scripts/tests/test_data_integrity.py -q` must pass — it catches
   duplicates (against the graph and within the queue) that a manual dedupe
   pass can miss (see the worked example below for a real instance). If it
   fails, fix the queue entries (remove/merge the flagged duplicates) and
   re-run before proceeding; do not checkpoint seeding as done over a
   failing integrity check. Then checkpoint: `python3 scripts/litsearch.py
   seed-done <id> --seeded <N> --query "<phrase-1>" --query "<phrase-2>"
   ...` (flips `phase` to `processing` and records what was searched, for
   anyone auditing later).

## Phase P — per-paper loop

Repeat while the survey has `core` queue entries (`survey == <id> && role
== "core"`, in file order — file order already reflects Phase S's ranking
and any manual reprioritization) and the run's `N` cap isn't reached.
Skip `foundational` entries entirely unless `config.process_foundational`
is `true` or the user explicitly asks for one this run. Every agent call
below uses the `Agent` tool with `run_in_background: false` — the loop is
inherently sequential (each step's output is the next step's input), so a
background/parallel invocation would just mean waiting anyway, and
synchronous execution keeps the state-file writes in a clean, unambiguous
order.

**pick.** Take the first eligible `core` entry. Generate its slug
(`firstauthor-year-keywords`, per CLAUDE.md — you don't yet know the exact
author/year until `resolve`, so a provisional slug from the queue entry's
`authors`/`year` is fine; the builder can correct it during `resolve` if
the confirmed metadata disagrees, as long as it tells you the final slug in
its report). Checkpoint: `python3 scripts/litsearch.py start-paper <id>
<slug> --title "<queue title>" --arxiv-id <arxiv_id or omit>`.

**resolve → fetch → figures → draft** (one `paper-builder` call). Prompt it
with exactly what its own contract (`.claude/agents/paper-builder.md`)
says it receives — don't paraphrase the queue entry, pass the real fields:
```
Build the explainer for survey <survey_id>, slug <slug>, resuming at step
<current.step>. Queue entry: <the full JSON object from data/queue.json>.
Work in work/<slug>/. Follow CLAUDE.md Procedure A and your own
instructions exactly.
```
The builder self-checkpoints through `resolve`/`fetch`/`figures`/`draft`
via its own `litsearch.py set-step` calls — you don't drive those
sub-steps individually, you just wait for its final message (a terse
step/report summary) or for the agent to report it couldn't resolve the
paper (→ treat as **unresolvable**, see Failure handling). When it reports
`draft` complete, read `work/<slug>/report.json` — you'll need
`queue_candidates` at `queue-ops` below.

**critique.** One `paper-critic` call:
```
Review survey <survey_id>, slug <slug>, round <current.round>. Read
public/papers/<slug>.html, work/<slug>/{paper.txt,meta.json,figures.json,
report.json}, the node+edges in data/papers.json, and data/surveys.json's
rubric for <survey_id>. Write work/<slug>/critique-r<round>.json.
```
On its final message, sync the state file — `python3 scripts/litsearch.py
set-blockers <survey_id> work/<slug>/critique-r<round>.json` — then branch
on the critique's `verdict`:
- `"approve"` → **verify** (below).
- `"revise"` **and** `current.round < config.max_rounds` → **revise**
  (below).
- `"revise"` **and** `current.round == config.max_rounds` → do not spawn
  another builder/critic round. This paper is done for this run: go
  straight to **queue-ops**, but call `complete-paper --verdict
  approved_with_notes` instead of `approved` (see queue-ops below) and
  make sure it's called out prominently in the end-of-run report. This is
  the round-cap escape hatch (PIPELINE_PLAN.md §4.5) — it exists so one
  stubborn paper can never wedge the whole run; don't loosen it by adding
  a 4th round "just this once".

**revise.** One `paper-builder` call in revise mode:
```
Revise survey <survey_id>, slug <slug>. Read
work/<slug>/critique-r<round>.json and address every blocking item;
write work/<slug>/response-r<round>.md.
```
On its final message, checkpoint the next round: `python3
scripts/litsearch.py set-step <survey_id> critique --round <round + 1>`.
Loop back to **critique**.

**verify** (you, not an agent). Three checks, in order, and fix what you
find rather than just reporting it — you own the site code, the builder
and critic don't touch it directly:
1. `npm run build` must succeed.
2. `python3 scripts/lint_pages.py <slug>` must exit 0.
3. **Render check** (Procedure A step 11's browser pass — the render is
   the source of truth, a clean JSON diff is not enough): load the site,
   confirm the new node appears in its correct publication-quarter column,
   hover it and confirm its citation edges brighten, open its explainer
   and confirm it's self-contained, and at ≈375px confirm
   `document.documentElement.scrollWidth <= clientWidth` (no sideways
   scroll) on the explainer. If anything's off despite the data looking
   right, it's a site bug — fix it, note the fix in the end-of-run report,
   then re-check.
Checkpoint: `python3 scripts/litsearch.py set-step <survey_id> verify`
(you may already be there from the critic's `approve`/round-cap branch
above — this call is idempotent, see Resume protocol).

**queue-ops** (you). From `work/<slug>/report.json`'s `queue_candidates`:
dedupe each candidate against `data/papers.json` + `data/queue.json`
(same arxiv_id-first rule as Phase S's dedupe step — don't relax it here),
then insert surviving `core` candidates at the **top** of the queue and
surviving `foundational` candidates at the **bottom**, both stamped
`survey: <id>`. Remove the just-processed entry from `data/queue.json` (an
exact match on title+arxiv_id — if it's already gone, that's fine, it
means a previous attempt at this same paper already removed it; see
Resume protocol). Validate: `python3 -m pytest
scripts/tests/test_data_integrity.py -q` must pass before you checkpoint —
same rule as Phase S, and for the same reason (a manual dedupe pass can
miss a non-ASCII-title or already-queued duplicate; let the test catch
it). Checkpoint: `python3 scripts/litsearch.py set-step <survey_id>
queue-ops` if not already there, then `python3 scripts/litsearch.py
complete-paper <survey_id> --verdict approved` (or `approved_with_notes`
per the round-cap branch above — pass `--notes` only if you want to
override the CLI's auto-fill-from-open-blockers default). This clears
`current` and appends to `completed[]` — the paper is done. Loop back to
**pick**.

**End of run** (N reached, no more `core` entries, or you're stopping for
another reason): report papers built this run (slug, rounds, verdict),
any `approved_with_notes` papers with their open notes highlighted for
human review, queue growth (X core inserted, Y foundational appended),
what got tagged and why, and the standing reminder to `npm run dev` and
review before committing. **Never auto-commit.**

## Resume protocol

Every invocation re-reads the state file first — never trust conversation
memory for what phase a survey is in or what paper is mid-flight; a
token-death or a fresh session/machine has none of that memory, only the
file does.

- `current == null` → announce "resuming `<survey>`: M done, K core
  queued" and enter Phase P at **pick**.
- `current != null` → announce "resuming `<slug>` at step `<step>`" (add
  ", round `<round>`" if the step is `critique`/`revise`) and re-enter
  Phase P's table **at that step** — not from `pick`, and not from
  `resolve`. Every step is safe to redo in place:
  - `resolve`/`fetch`/`figures`/`draft` → re-invoke `paper-builder` with
    that `step`; it overwrites the same `work/<slug>/` paths and
    `public/papers/<slug>.html`, so a partial previous attempt just gets
    replaced, not duplicated.
  - `critique` → check whether `work/<slug>/critique-r<round>.json`
    already exists on disk. If yes (the critic finished but the
    orchestrator died before branching on the verdict), read it and
    branch immediately — don't re-run the critic. If no, re-invoke
    `paper-critic`.
  - `revise` → check whether `work/<slug>/response-r<round>.md` already
    exists. If yes, checkpoint straight to `critique --round <round+1>`
    without re-invoking the builder. If no, re-invoke `paper-builder` in
    revise mode.
  - `verify`/`queue-ops` → re-run the checks/ops as written above; both
    are written to be no-ops on a second pass (the build/lint checks just
    re-pass, the dedupe means candidates already inserted won't
    double-insert, and removing an already-removed queue entry is a
    silent no-op by construction of "remove by exact match").
- **`work/<slug>/` missing while `current` says mid-paper** (new machine, a
  cleaned scratch dir): don't error — restart that paper from `resolve`.
  Only the in-flight scratch is lost; nothing in `data/papers.json`,
  `public/papers/`, or `data/queue.json` was touched yet at any step before
  `draft`, and `draft` overwrites deterministically anyway.

**Token exhaustion is just this**: the session ends mid-step; nothing else
is needed. When tokens refresh, run `/litsearch <topic-or-survey-id>` (or
just say "keep working on `<survey>`") and it picks the resume point back
up from the two lines above. The same protocol covers Esc, Ctrl-C,
crashes, and switching machines — none of them are special-cased, because
none of them are distinguishable from "the process just stopped" once
you're back reading the state file.

## Failure handling

- **S2 429s** (Phase S) → back off and retry with the key; never proceed
  keyless if a key is configured (CLAUDE.md doctrine).
- **No `$S2_API_KEY` configured** → seeding still works (the bulk endpoint
  is public) but expect heavier throttling and noisier ranking; say so in
  the seeding report rather than silently producing a worse list.
- **User rejects the whole seed list at the confirm step** → don't force
  it; ask what to adjust (different phrasings, a narrower rubric) and
  re-run the search rather than seeding zero papers and calling it done.
- **No PDF obtainable** (Phase P `resolve`/`fetch`) → the builder continues
  abstract-only per Procedure A; this is allowed, not a failure — just make
  sure the end-of-run report says which papers were abstract-only.
- **Paper unresolvable** (builder can't confirm identity against S2 + web)
  → `python3 scripts/litsearch.py skip-paper <survey_id> --reason "…"`,
  remove the entry from `data/queue.json`, continue to the next `pick`.
- **Builder or critic agent dies on a terminal API error** → re-spawn it
  once from the checkpointed step (the `Agent` tool already retries
  transient errors; this is for the case where it still comes back
  `null`/dead). A second death → `skip-paper --reason "agent failure at
  <step>"`, leave the queue entry in place, continue with the next paper,
  and say so plainly in the end-of-run report — don't silently drop a
  paper that failed for a systemic reason (e.g. a broken tool) rather than
  a paper-specific one.
- **A malformed `critique-r<N>.json`** (bad JSON, missing required keys) →
  re-invoke the critic once, telling it what was wrong. A second failure
  → treat the raw text as a single `"revise"` blocker yourself and
  continue the loop rather than crashing the run over a formatting slip.
- **`npm run build` breaks at `verify`** → you own the site code; fix it,
  note the fix in the end-of-run report, then re-verify. Don't checkpoint
  past `verify` with a broken build.

## `claude_loop.sh` for unattended runs

`claude_loop.sh --survey <id>` (once added to that script — see
PIPELINE_PLAN.md §5.4) drives Phase P unattended: prompt `"Continue the
lit search for <id> (process one paper)."` per iteration, progress gate
"queue shrank **or** `litsearch.py status <id> --json` shows `completed`
grew" (Phase P can legitimately grow the queue via `queue_candidates`
even while `completed` also grows, so queue-shrank-alone is the wrong
signal here — unlike Procedure A's plain queue, which only ever shrinks).
Everything else (build/lint/clean-tree gates, `--timeout`, the
confirmation prompt) is unchanged from that script's existing behavior.

## When NOT to use this skill

- **Status only, no action** — use `/surveys`; this skill mutates state
  (creates surveys, writes the queue), that one only reads.
- **Building/refreshing the survey's site page or PDF** once its corpus is
  tagged — use `/survey` (once M5/M6 land).
- **Procedure A's "run the next one"** — the general ~1,000-entry queue
  has no `survey`/`role` fields and predates this pipeline; that's still
  ordinary manual queue processing, untouched by `/litsearch`.

## Worked example

A real run against this repo, 2026-07-18 — "LLM and Agent benchmarks":

**Step 0.** The topic fuzzy-matched `benchmarks` (`data/surveys.json`), which
already had 137 tagged nodes but no state file. Asked the user: gap-fill the
existing survey, or split off a new `agent-benchmarks` survey? Answer:
gap-fill `benchmarks`. Ran `python3 scripts/litsearch.py init benchmarks
--topic "LLM and Agent benchmarks"` — `phase` started at `seeding`.

**Phase S.** Five S2 bulk-search phrasings plus one web search for a recent
survey paper (`arxiv.org/html/2507.21504v1`, "Evaluation and Benchmarking of
LLM Agents: A Survey") whose named-benchmark list caught four papers the
keyword search missed entirely (ToolLLM/ToolBench, MiniWoB++, AssistantBench,
τ-bench). Deduped ~1,400 raw hits down to 20 genuine candidates against the
existing 292 nodes + 1,043 queued entries; two (BOLAA, InfiGUIAgent) were
flagged borderline against the core-benchmark rubric and surfaced to the user
rather than silently included or excluded. User confirmed all 20. Writing
them surfaced two the manual dedup pass had actually missed — `ToolLLM` and
`τ-bench` were already graph nodes (`qin-2023-toolllm`, `yao-2024-tau-bench`;
the τ-bench miss was a Unicode normalization gap — the `τ` character silently
drops out of an ASCII-only dedup regex) — caught by
`scripts/tests/test_data_integrity.py`, not by the manual check, which is
exactly why that gate exists. Also found and merged one pre-existing untagged
queue duplicate (MiniWoB++, added by an earlier manual pass). Net: **18**
papers landed in `data/queue.json` at the top, each with `"survey":
"benchmarks", "role": "core", "priority": "High"`. Checkpointed with
`python3 scripts/litsearch.py seed-done benchmarks --seeded 18 --query "…"
...`; `status --json` afterward showed `"queue_core": 18, "phase":
"processing"`. `npm run build` and the full test suite stayed green
throughout.

One operational finding worth carrying forward: this run had no
`$S2_API_KEY` configured (`.claude/settings.local.json` doesn't exist in
this checkout) and unauthenticated Semantic Scholar calls got persistently
429'd — not just a transient blip, six retries with 30s backoff over three
minutes all failed. Four papers' `citation_count` were left `null` pending a
future refresh rather than guessed. **Set up the API key before a real
production run** — see CLAUDE.md's "Semantic Scholar API key" section.

**Phase P, real run, 2026-07-18** (milestone M4): processed the top two
seeded `core` entries end to end. Paper 1 (`maharana-2024-locomo`, LoCoMo)
took 2 critique rounds — round 1 found 5 real blockers (3 factual
mismatches against the paper's own text, 2 missed citation edges to
existing nodes), the builder fixed all 5, round 2 approved. Paper 2
(`xu-2022-msc`, the MSC dataset) approved in round 1 with zero blockers.
Both fully verified: `npm run build` and `lint_pages.py` clean, and the
render checked precisely via the map's own `window.cy` cytoscape instance
(not just pixel-hunting a screenshot) — each node's `connectedEdges()`
count and the exact edge-id list produced by a simulated `mouseover`
matched what the builder/critic reported, confirming hover-brightening
works for the specific edges each paper added. Total after both papers:
294 nodes, 3,165 edges (+14 from 3,151), `benchmarks` at 139 tagged
(+2), 8 new discovered-candidate papers inserted (5 core + 3
foundational, all found by reading each paper's own bibliography since S2
was unreachable) — `data/queue.json` net +10 despite processing 2 entries.

**The kill test.** Started a third paper, ran the builder for `resolve`
only, and stopped it there deliberately (`work/<slug>/meta.json` on disk,
`current.step: "fetch"`, nothing else touched — no PDF, no node). Then
treated the next turn as a fresh `/litsearch` invocation: re-read the
state file from disk, announced "resuming `xu-2022-msc` at step `fetch`",
and continued the builder from exactly that checkpoint. The state log
shows a single `-> fetch` transition with no duplicate `resolve` entry,
proving the resume didn't redo already-completed work. The paper finished
normally (round 1 approval); the full integrity test suite (`63/63`,
including the duplicate-slug/edge/queue checks) confirmed zero
duplicates resulted from the interruption.

**The round-cap escape hatch.** Both real papers converged before hitting
`max_rounds`, so this was verified with an isolated scratch harness (a
temp copy of `litsearch.py` + a throwaway survey, touching zero real repo
data — same pattern as `scripts/tests/test_litsearch_state.py`): walked a
synthetic paper through 3 real critique rounds with a blocker that
legitimately never got fixed, confirmed `complete-paper --verdict
approved` correctly refuses with an open blocker on record, confirmed
`--verdict approved_with_notes` succeeds and auto-fills the note from the
blocker's own `issue` text, and confirmed the pipeline immediately accepts
a `start-paper` for the next entry afterward — proving one stuck paper
cannot wedge the run.

## Provenance and maintenance

- **Authored and verified: 2026-07-18**, against a live (unauthenticated)
  call to `https://api.semanticscholar.org/graph/v1/paper/search/bulk`
  confirming the `fields`/`sort`/`limit` parameters used above return real
  data, and against `data/surveys.json`'s actual current colors
  (`benchmarks: #ffd166`, `evaluations: #c792ea`) and `src/style.css`'s
  `--accent: #2dd4bf`.
- **Re-verify with:**
  ```bash
  curl -s "https://api.semanticscholar.org/graph/v1/paper/search/bulk?query=test&fields=title,authors,year,venue,externalIds,citationCount,publicationDate,abstract&sort=citationCount:desc&limit=1" | python3 -m json.tool
  python3 scripts/litsearch.py status --json   # confirm the CLI surface this skill drives hasn't changed
  ```
- **Most likely to go stale:** the S2 bulk-search field list (S2 has
  changed field names before); the existing survey colors (grows as more
  surveys are added — always re-read `data/surveys.json`, never hardcode
  the two above as exhaustive); Phase P's "not yet implemented" status,
  which this file must lose the moment M4 ships.
