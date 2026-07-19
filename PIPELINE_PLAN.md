# PIPELINE_PLAN.md — Resumable literature-search & survey pipeline

Plan for turning Paper Atlas's manual Procedures A–D into a **topic-driven, stoppable/resumable
pipeline** runnable from Claude Code, with a builder/critic loop per paper, survey-paper
generation (site + LaTeX PDF), and map-declutter improvements. Written for implementation by
Sonnet 5 (xhigh); read alongside CLAUDE.md, which stays the source of truth for the per-paper
contract (Procedure A) and data shapes.

---

## 0. Goals (from the request)

1. **`/litsearch <topic>`** — launch a literature search on any topic, whether or not it has been
   searched before. Seed papers go to the queue at highest priority; then the queue is processed
   paper-by-paper (summary + node + explainer per Procedure A). Papers discovered while reading:
   *core* papers the seed search missed → highest priority; *foundational* high-citation papers →
   lower priority. Core papers get tagged with the topic's survey tag.
2. **Builder/critic loop per paper** — builder = Sonnet 5 @ high effort; critic = Opus 4.8 @ xhigh
   effort. Loop until the critic approves, with a **hard convergence guarantee** (bounded rounds +
   no-moving-goalposts rules).
3. **Stop/resume anywhere** — every step checkpoints to disk. Running out of tokens mid-paper
   loses at most the in-flight step; restarting the command resumes exactly where it stopped.
4. **`/surveys`** — ask what surveys exist and how far along each is; "keep working on X" resumes.
5. **`/survey <id>`** — create/refine the survey artifact for a topic: the generated site page
   (like benchmarks/evaluations today) **plus a LaTeX PDF** (common AI/CS preprint template,
   sole author *Darvin Yi*), linked from the survey page. Written and critiqued by Opus 4.8 @ xhigh.
6. **Visual recommendations** — declutter the map (opt-in toggles; current default look preserved).

## 1. Grounding — what exists today (verified 2026-07-18)

- `data/papers.json`: 292 nodes, 3,151 edges. `data/queue.json`: **1,043 entries** (shared, no
  per-survey attribution — the pipeline must filter, never drain the whole queue).
- Two surveys in `data/surveys.json` (`benchmarks` 137 tagged, `evaluations` 66 tagged), each with
  a **generated** page: `scripts/benchmarks_survey/` and `scripts/evaluations_survey/`
  (builder + `survey_template.html` + `stats_tokens.py` + `svgcharts.py`; shared lib in
  `scripts/survey_common/svgcharts.py`). All prose numbers come from stats tokens — keep this rule.
- `claude_loop.sh`: headless per-item driver (`claude -p "Run the next one."`) with build/lint/
  clean-tree/queue-progress gates. Reusable as the unattended runner for this pipeline (§7.6).
- `.claude/` is **entirely gitignored** (because `settings.local.json` holds the S2 key). The new
  skills/agents must be version-controlled → narrow the ignore (§3.4).
- **No LaTeX toolchain installed** (`pdflatex`/`tectonic`/`latexmk` absent) and **no "latex" skill
  exists** in the installed skill set — the PDF pipeline is implemented directly with `tectonic`
  (§8.4); the user must approve one `brew install tectonic`.
- Tests exist in `scripts/tests/` (backfill_dates, data_integrity, tag_papers) — extend, don't break.

## 2. Architecture overview

```
 /litsearch <topic>            /surveys              /survey <id>
      │ (skill)                  │ (skill)                │ (skill)
      ▼                          ▼                        ▼
 orchestrator (main session, Sonnet 5 xhigh)  ← reads/writes data/litsearch/<id>.state.json
      │
      ├─ Phase S: seed search  → queue entries (survey=<id>, role=core, top of queue)
      │
      └─ Per-paper loop (repeat until survey queue empty or N reached):
           pick → [paper-builder agent: resolve→fetch→figures→draft]     (sonnet, high)
                → [paper-critic agent: verdict JSON]                      (opus, xhigh)
                → [paper-builder agent: revise] → critic … (≤ max_rounds) 
                → orchestrator: verify (build+lint+browser) → queue-ops → checkpoint done
      
 /survey <id>: corpus → taxonomy → site (scaffolded builder) → LaTeX/PDF
               → [survey-author agent] ↔ [survey-critic agent] (both opus, xhigh, ≤ max_rounds)
```

**Everything durable lives in files**; the conversation is never the only copy of any state:

| Path | Contents | Tracked? |
|---|---|---|
| `data/litsearch/<id>.state.json` | per-survey pipeline state (the resume point) | yes |
| `data/queue.json` | queue, extended with `survey`/`role` fields | yes |
| `work/<slug>/` | paper.pdf, paper.txt, meta.json, figs/, critique-r*.json, response-r*.md, report.json | **no** (gitignored) |
| `.claude/agents/*.md`, `.claude/skills/*/SKILL.md` | agents & skills | yes (after §3.4) |
| `paper/<id>/` | LaTeX source for the survey PDF | yes |
| `public/surveys/<id>.pdf` | compiled survey PDF | yes |

Design rule: **state transitions are written *before* the report of them** — every step (a) does
idempotent work into `work/` or the data files, (b) records the new step via the state CLI. A kill
at any instant leaves either the old step (redo it — safe, idempotent) or the new step. No step's
correctness depends on conversation memory.

---

## 3. Workstream 1 — State & resumability infrastructure

### 3.1 `data/litsearch/<survey_id>.state.json`

One file per survey, deterministic key order, written atomically (temp + `os.replace`). Schema:

```json
{
  "version": 1,
  "survey": "agent-benchmarks",
  "topic": "LLM and Agent benchmarks",
  "created": "2026-07-18",
  "phase": "processing",
  "config": {
    "max_rounds": 3,
    "builder": {"model": "sonnet", "effort": "high"},
    "critic":  {"model": "opus",   "effort": "xhigh"},
    "process_foundational": false
  },
  "seeding": {"done": true, "date": "2026-07-18", "queries": ["..."], "seeded": 22},
  "current": {
    "slug": "liu-2023-agentbench",
    "queue_title": "AgentBench: Evaluating LLMs as Agents",
    "arxiv_id": "2308.03688",
    "step": "critique",
    "round": 1,
    "open_blockers": [
      {"id": "B1", "issue": "Table 2 SR for GPT-4 is 4.01 in the PDF, page 7; explainer says 4.41", "status": "open"}
    ]
  },
  "completed": [
    {"slug": "…", "rounds": 2, "verdict": "approved", "notes": [], "date": "2026-07-18"}
  ],
  "skipped": [ {"title": "…", "reason": "no PDF and no S2 record"} ],
  "survey_build": {"step": null, "rounds": 0, "taxonomy": false, "site": false, "pdf": false},
  "log": ["2026-07-18T14:02 seeded 22 papers", "…"]
}
```

- `phase`: `seeding | processing | survey | idle`.
- `current.step`: `resolve | fetch | figures | draft | critique | revise | verify | queue-ops`
  (absent/`null` current ⇒ between papers — the cleanest resume point).
- `current.open_blockers` **mirrors the critic's open blocking items** (the full critique lives in
  gitignored `work/`); this is what makes a cross-machine resume possible mid-loop.
- `log` is append-only, capped at the last ~50 entries.

### 3.2 `scripts/litsearch.py` — state CLI

Modeled on `tag_papers.py` (validating, canonical formatting, atomic writes). Subcommands:

```
litsearch.py init <survey_id> --topic "…"            # create state file (errors if exists)
litsearch.py status [<survey_id>] [--json]           # human table or JSON (drives /surveys)
litsearch.py start-paper <survey_id> <slug> --title … --arxiv …   # sets current, step=resolve
litsearch.py set-step <survey_id> <step> [--round N] # advance current.step (validates ordering)
litsearch.py set-blockers <survey_id> <file.json>    # sync open_blockers from a critique file
litsearch.py complete-paper <survey_id> --verdict approved|approved_with_notes [--notes …]
litsearch.py skip-paper <survey_id> --reason "…"
litsearch.py log <survey_id> "message"
```

Every mutation validates the schema and rejects illegal transitions (e.g. `set-step draft` while no
`current`). Both the orchestrator **and the builder agent** call this CLI — the builder checkpoints
its own internal progress (§5.1). Unit tests in `scripts/tests/test_litsearch_state.py`: init/round-
trip, illegal-transition rejection, atomicity (write to temp then rename), blockers sync.

### 3.3 Queue schema extension (backward-compatible)

Two **optional** fields appended to queue entries the pipeline creates:

```json
{ "…existing fields…", "survey": "agent-benchmarks", "role": "core" }
```

- `role`: `"core"` (seed papers + discovered core papers — the ones the survey must cover) or
  `"foundational"` (high-citation background worth a node but not survey-core).
- Ordering rule for the pipeline: among entries with `survey == <id>`, process all `core` (file
  order) before any `foundational`. Discovered-core entries are **inserted at the top of the
  queue**; foundational appended at the bottom. Entries without a `survey` field (the existing
  1,043) are untouched and are *never* processed by `/litsearch` — they remain Procedure-A
  territory ("run the next one").
- `scripts/tests/test_data_integrity.py` gains checks: `survey` values must exist in
  `surveys.json`; `role` ∈ {core, foundational}; no duplicate arxiv_id/title across queue+papers.

### 3.4 `.gitignore` surgery + `work/` dir

`.claude/` must stop being blanket-ignored so skills/agents/launch config are versioned, while the
secret-bearing local settings stay out:

```gitignore
# was: .claude/
.claude/*
!.claude/skills/
!.claude/agents/
!.claude/launch.json
!.claude/settings.json
# .claude/settings.local.json stays ignored via .claude/*
```

Add `work/` to `.gitignore` (per-paper scratch: PDFs, figures, extracted text, critiques). Layout
`work/<slug>/{paper.pdf, paper.txt, meta.json, figs/, figures.json, report.json,
critique-r1.json, response-r1.md, …}`. `paper.txt` is the full extracted text (PyMuPDF) — it is
what lets the **critic** check exact numbers without re-downloading anything.

---

## 4. Workstream 2 — Agent definitions (`.claude/agents/`)

Four custom subagents. Frontmatter carries `name`, `description`, `tools`, `model`, and `effort`
— both keys verified against the current Claude Code docs (code.claude.com/docs/en/sub-agents):
`model` accepts aliases (`sonnet`, `opus`) or full IDs (`claude-opus-4-8`), and `effort` accepts
`low | medium | high | xhigh | max`, overriding the session effort for that agent. E.g.:

```yaml
---
name: paper-critic
description: Adversarial reviewer for Paper Atlas explainers. Invoked by /litsearch only.
tools: Read, Bash, Grep, Glob
model: opus
effort: xhigh
---
```

### 4.1 `paper-builder.md` — model `sonnet`, effort `high`

Tools: `Read, Write, Edit, Bash, Grep, Glob, WebFetch, WebSearch`.

System prompt contents (write it from this spec, not verbatim):
- You build one explainer per invocation for the Paper Atlas repo. Follow CLAUDE.md's Procedure A
  steps 2–8 and the explainer page contract exactly (template `templates/explainer.html`, real
  figures via `scripts/extract_figures.py` + `scripts/inject_figures.py`, exact numbers only,
  canonical `source ↗` link, mobile contract).
- **Checkpoint protocol**: you receive `survey_id`, the queue entry JSON, `work/<slug>/`, and the
  current `step`. Resume from that step; after finishing each step, run
  `python3 scripts/litsearch.py set-step <survey_id> <next-step>`. Steps you own:
  - `resolve`: confirm arxiv_id/DOI (S2 + web, authors+year match); write `work/<slug>/meta.json`
    with the full S2 record **including `references` and `citations`** (the critic and queue-ops
    need them). → `fetch`
  - `fetch`: download PDF to `work/<slug>/paper.pdf` (verify `%PDF`, >50 KB); extract full text to
    `paper.txt`. No PDF obtainable → note it in `meta.json` (`"pdf": false`) and continue
    abstract-only. → `figures`
  - `figures`: run `extract_figures.py` into `work/<slug>/figs/`; choose which figures belong and
    record the choice + one-line rationale each in `figures.json`. → `draft`
  - `draft`: write `public/papers/<slug>.html`; inject figures; **update `data/papers.json`**
    (node with `date`, edges both directions per Procedure A step 8); apply survey tag via
    `tag_papers.py` if the paper meets the survey rubric; run
    `python3 scripts/lint_pages.py <slug> --fix` and make it exit 0. Then write
    `work/<slug>/report.json`:
    ```json
    {
      "slug": "…", "tagged": ["agent-benchmarks"], "tag_rationale": "…",
      "edges_added": 7,
      "queue_candidates": {
        "core": [ {"title": "…", "arxiv_id": "…", "authors": "…", "year": 2024, "venue": "…",
                    "citation_count": 312, "why": "…"} ],
        "foundational": [ … ]
      }
    }
    ```
    Candidate rules: `core` = matches the survey's `description` rubric and is not already in
    papers.json/queue.json; `foundational` = citation_count ≥ 1000 **or** cited by ≥ 2 existing
    nodes, and clearly background rather than survey-core. ≤ 5 of each. → hand back to orchestrator.
- **Revise mode**: you receive `work/<slug>/critique-r<N>.json`. Address **every blocking item**;
  write `response-r<N>.md` with one entry per blocker id — what you changed (file + section) or,
  if you believe the critic is factually wrong, the exact PDF quote proving it (the critic
  adjudicates). Never edit anything unrelated to a blocker. Re-run the lint. → `set-step critique --round N`.
- Report format: your final message is a terse machine-readable summary (step reached, files
  touched, blockers addressed) — the orchestrator, not the user, reads it.

### 4.2 `paper-critic.md` — model `opus`, effort `xhigh`

Tools: `Read, Bash, Grep, Glob` (read-only intent; Bash only for lint/build checks — no Write/Edit;
the critic never fixes, it only judges).

Prompt spec:
- Input: `slug`, `survey_id`, round `N`, paths (`public/papers/<slug>.html`, `work/<slug>/paper.txt`,
  `meta.json`, `figures.json`, `report.json`, the paper's node + edges in `data/papers.json`, the
  survey rubric from `data/surveys.json`; for N>1 also `critique-r<N-1>.json` + `response-r<N-1>.md`).
- **Round 1 — full review**, checked against ground truth (`paper.txt` is the paper):
  1. *Factual*: every number/claim in the explainer appears in the paper; no invented results;
     headline numbers match tables (quote page/table in evidence).
  2. *Contract*: section order (hero → gap → method → results → does-it-hold-up → takeaways),
     canonical arXiv `source ↗` link, real figures present and correctly captioned, no leftover
     placeholders, built from the template (mobile media-query block intact).
  3. *Critique-section quality*: the "does it hold up?" section must be sharp and specific
     (baselines fair? contamination? what the metric misses?) — generic filler is a blocker.
  4. *Graph*: node fields correct (`date` from arxiv id, topic, author_group, citation_count);
     spot-check edges against `meta.json`'s references/citations (missed edges to existing nodes
     = blocker; use the slug lookup in `data/papers.json`).
  5. *Tagging*: adversarially check the survey-tag decision against the rubric, both directions
     (wrongly tagged / wrongly untagged = blocker with rationale).
- Output — **exactly one JSON file** `work/<slug>/critique-r<N>.json`:
  ```json
  {
    "verdict": "approve" | "revise",
    "round": 1,
    "blocking": [
      {"id": "B1", "where": "results §, 2nd table", "issue": "…",
       "evidence": "paper.txt p.7: '…exact quote…'", "fix_hint": "…"}
    ],
    "suggestions": [ {"where": "…", "note": "…"} ]
  }
  ```
  Blocker bar (hard rule): only factual errors vs the PDF, contract violations, lint/build
  failures, graph/tag errors. Style, tone, length, "could be richer" → `suggestions`, never
  blocking.
- **Rounds N ≥ 2 — convergence rules (non-negotiable)**:
  - You may only (a) close or keep-open blockers from round N−1 (verify each against the diff and
    `response-r<N-1>.md`), and (b) open **new** blockers strictly *caused by* the revision
    (regressions). Anything you merely didn't notice earlier goes to `suggestions`.
  - If the builder rebutted a blocker with a PDF quote, adjudicate on the quote.
  - Verdict is `approve` iff zero open blockers.
- Final message: one line (`verdict + open blocker count + path to critique file`).

### 4.3 `survey-author.md` — model `opus`, effort `xhigh`

Tools: `Read, Write, Edit, Bash, Grep, Glob, WebFetch, WebSearch`. Used by `/survey` (§8). Writes
taxonomy JSON, survey-page prose/template, `stats_tokens.py`, and the LaTeX source; follows the
"no hand-typed numbers — every stat is a computed token" house rule; checkpoints via
`litsearch.py set-step` exactly like the paper-builder.

### 4.4 `survey-critic.md` — model `opus`, effort `xhigh`

Tools: `Read, Bash, Grep, Glob`. Same verdict JSON + convergence rules as the paper-critic; the
review dimensions differ (§8.5).

### 4.5 Convergence policy (shared, enforced by the orchestrator)

- `max_rounds = 3` (state-file config). Round counter lives in `current.round` — it survives
  restarts, so a token-death mid-loop cannot reset the count.
- The critic's structural rules (§4.2) prevent goalpost-moving; the round cap prevents ping-pong.
- If round `max_rounds` ends with open blockers: orchestrator marks the paper
  `approved_with_notes`, copies remaining blockers into `completed[].notes`, logs it, **continues
  the pipeline**, and lists it prominently in the end-of-run report for human review. The pipeline
  never wedges on one paper.
- If a critique file is malformed JSON: re-invoke the critic once with the parse error; on second
  failure treat the raw text as `revise` with a single blocker and continue.

---

## 5. Workstream 3 — `/litsearch` skill (the orchestrator)

`.claude/skills/litsearch/SKILL.md`. Invocation: `/litsearch <topic-or-survey-id> [N]`
(N = max papers this run; default unbounded — safe because every step checkpoints).

### 5.1 Flow

**Step 0 — resolve the survey.** Match the argument against `data/surveys.json` ids and labels
(case-insensitive, fuzzy). Exactly one match → use it. No match → this is a **new topic**: derive a
survey id (lowercase-hyphenated), pick a `color` distinct from existing survey colors *and* the
teal selection accent, and draft a sharp membership `description` (the rubric — what makes a paper
*core*); show all three to the user for a one-shot confirm, then append to `surveys.json` and
`litsearch.py init`. Ambiguous (>1 match) → ask one short question. If the survey exists but has no
state file (e.g. today's `benchmarks`), `init` it with `seeding.done = true` (its corpus was built
by hand) unless the user asked to re-seed — re-seeding an existing survey is a *gap-fill*: search
as below but expect most hits to dedupe away.

**Phase S — seeding** (skip if `seeding.done`). Multi-angle search, all against the S2 API with
`$S2_API_KEY` (backoff on 429, per CLAUDE.md):
1. S2 `/paper/search/bulk` with 3–5 query phrasings of the topic (e.g. "LLM agent benchmark",
   "language model agent evaluation environment", …), sorted by citations and by recency.
2. Web search for 1–2 recent survey/review papers of the topic; mine their reference lists — this
   is the highest-precision source of "the named entries a survey would cite".
3. Snowball: if the survey already has tagged nodes, take the union of their references/citations
   and rank by in-corpus degree.
Then: dedupe against `papers.json` + `queue.json` (arxiv_id → doi → normalized title), rank
(rubric relevance first, then citation count), and present the proposed seed list (title · authors ·
year · citations · one-line why) — **cap ~25, user confirms/edits once**. Append confirmed seeds to
the **top** of `data/queue.json` with `priority: "High"`, `role: "core"`, `survey: <id>`,
`source: "Lit search: <topic>"`. Mark `seeding.done`, log, checkpoint. *(This is Procedure B with
survey attribution; note the seeding step is the one interactive gate in the pipeline — after it,
the loop can run unattended.)*

**Phase P — per-paper loop.** Repeat while the survey has queue entries (core before foundational;
skip foundational entirely unless `config.process_foundational` or the user says otherwise) and N
not reached:

| Step | Actor | Does | Checkpoint after |
|---|---|---|---|
| pick | orchestrator | choose next entry; generate slug; `start-paper` | `current` set, step=`resolve` |
| resolve→fetch→figures→draft | **paper-builder** (one invocation) | Procedure A 2–8 + report.json; self-checkpoints each internal step via `set-step` | step=`critique`, round=1 |
| critique | **paper-critic** | critique-r`N`.json | orchestrator runs `set-blockers`; verdict `approve` → step=`verify`; else step=`revise` |
| revise | **paper-builder** (revise mode) | fix blockers, response-r`N`.md | step=`critique`, round=N+1 |
| verify | orchestrator | `npm run build`; `lint_pages.py <slug>`; browser check per Procedure A step 11 — node in the right quarter column, hover edges, explainer loads, no sideways scroll at 375px. Site bugs found here are fixed by the orchestrator and noted | step=`queue-ops` |
| queue-ops | orchestrator | from `report.json`: dedupe + insert `core` candidates at queue top / append `foundational` at bottom (both with `survey`+`role`); **remove the processed entry**; `complete-paper` | `current` cleared; paper in `completed[]` |

Agent invocations use the Agent tool with `subagent_type: paper-builder` / `paper-critic`,
`run_in_background: false` (the loop is inherently sequential; synchronous keeps state linear).

**End of run** (N reached, queue drained, or user stops): report — papers built (slug, rounds,
verdict), `approved_with_notes` items with their open notes, queue growth (X core inserted, Y
foundational appended), surveys tagged, and the standing reminder to review (`npm run dev`) and
commit. **Never auto-commit** (doctrine unchanged).

### 5.2 Resume protocol (the point of the whole design)

On every invocation, before anything else: read the state file.
- `current == null` → announce "resuming <survey>: M done, K core queued" and enter the loop.
- `current != null` → announce "resuming <slug> at step <step>, round <round>" and re-enter the
  table at that step. Steps are idempotent by construction: `resolve/fetch/figures` just redo into
  `work/`; a half-written `draft` is overwritten from template + cached inputs; a `critique` with no
  critique file on disk re-runs the critic; `verify`/`queue-ops` re-check before mutating (queue-ops
  dedupes, so a double-run cannot double-insert; removal of the processed entry is by exact match,
  so a second removal is a no-op).
- Special case: `work/<slug>/` missing while state says mid-paper (new machine, cleaned scratch) →
  restart that paper from `resolve`; only in-flight scratch is lost, nothing committed is.

**Token exhaustion is just this**: the session dies mid-step; nothing else needed. When tokens
refresh, the user runs `/litsearch <topic>` (or says "keep working on X") and it continues. The same
protocol covers Esc, Ctrl-C, crashes, and machine switches.

### 5.3 Failure handling

- **No PDF** → abstract-only build (Procedure A already allows it); critic told via `meta.json`.
- **Queue entry unresolvable** (can't confirm identity) → `skip-paper --reason`, remove from queue,
  continue.
- **Builder/critic agent dies** (terminal API error) → re-spawn once from the checkpointed step;
  second death → `skip-paper --reason "agent failure at <step>"`, leave the queue entry in place
  (marked `"blocked": true`), continue with the next paper, surface in the report.
- **S2 429s** → backoff and retry with the key (never drop it) — already doctrine.
- **`npm run build` breaks at verify** → orchestrator fixes (it owns site code), notes the fix.

### 5.4 `claude_loop.sh` integration (optional, small)

Add `--survey <id>`: sets the prompt to `"Continue the lit search for <id> (process one paper)."`
and swaps the progress gate from "queue shrank" to "queue shrank **or** `litsearch.py status <id>
--json` shows `completed` grew" (seeding and note-taking runs may grow the queue legitimately).
Everything else (build/lint/clean-tree gates, timeout, confirmation) is already right. This gives
an unattended overnight mode with per-paper commit hygiene enforced by the clean-tree gate.

---

## 6. Workstream 4 — `/surveys` status skill

`.claude/skills/surveys/SKILL.md`. Read-only; no agents. Implementation: run
`python3 scripts/litsearch.py status --json` (which joins `surveys.json` + state files + queue +
papers.json tag counts) and render:

```
survey            tagged  queue(core/found)  phase        current              page  pdf  last activity
benchmarks          137        0 / 0         idle         —                    ✓     —    2026-07-12
evaluations          66        0 / 0         idle         —                    ✓     —    2026-07-16
agent-benchmarks     14        9 / 3         processing   liu-2023-agentbench  —     —    2026-07-18
                                                          (critique, round 2)
```

…plus one suggested next command per non-idle survey ("`/litsearch agent-benchmarks` to continue —
9 core papers queued"). Also handles "what surveys exist?" asked in plain English (CLAUDE.md
routing, §9).

---

## 7. Workstream 5 — `/survey <id>`: the survey artifact (site + PDF)

`.claude/skills/survey/SKILL.md`. Requires the survey to have tagged papers (else: "run
`/litsearch` first"). Author = `survey-author` (opus/xhigh), critic = `survey-critic` (opus/xhigh),
same convergence policy (≤3 rounds, blockers-only re-review). State in `survey_build` within the
same state file; steps checkpoint identically, so this too is stop/resume-safe.

### 7.1 Step `corpus`
Collect tagged nodes + read their explainers (`public/papers/*.html` — the already-verified
summaries are the raw material). In **refine mode** (taxonomy already exists): diff the tagged set
vs the taxonomy — new papers to classify, departed papers to drop; only affected sections get
rewritten and re-critiqued.

### 7.2 Step `taxonomy`
Author produces/updates `data/<id>-taxonomy.json`: one record per tagged paper with 4–7
survey-specific facets (mirroring `evaluations-taxonomy.json`'s shape: slug + facet fields with
small controlled vocabularies), designed by the author for *this* topic, plus at least one **novel
organizing axis** (the evaluations survey's "reward-readiness" is the precedent — a survey should
say something, not just bucket). Validated by a small schema check added to
`test_data_integrity.py` (every tagged slug present, vocab closed).

### 7.3 Step `site`
New scaffolder `scripts/survey_scaffold/new_survey.py <id>` copies a skeleton into
`scripts/<id>_survey/`: `build_survey_page.py` (generic: reads the taxonomy, renders template
tokens), `survey_template.html` (dark long-read shell, same look as the existing two),
`stats_tokens.py` (author fills with computed tokens), chart hooks reusing
`scripts/survey_common/svgcharts.py`. The author writes the prose into the template with `{TOKEN}`
placeholders only — **no hand-typed numbers** — then runs the builder →
`public/surveys/<id>.html`. Register `"page": "surveys/<id>.html"` in `surveys.json` (existing
"read →" pill machinery picks it up). The two existing bespoke survey builders are left untouched.

### 7.4 Step `tex` + `pdf` — the LaTeX pipeline
- **Toolchain**: `tectonic` (single self-contained binary, fetches packages on first run). Preflight
  in the skill: `command -v tectonic || ask the user to approve "brew install tectonic"`. (Verified
  2026-07-18: no TeX on this machine; there is also no installed "latex" skill — this is built
  directly. If a latex skill is installed later, it can replace this step.)
- **Template**: vendor a common AI/CS preprint style into `paper/common/` — use the widely-used
  MIT-licensed `arxiv.sty` (kourgeorge/arxiv-style) preprint look (or a NeurIPS `preprint`-option
  style if licensing review prefers; decide once at implementation, then it's fixed for all
  surveys). Title = the survey's title; **author block: `Darvin Yi` only** (affiliation line:
  `research.darvinyi.com`); abstract from the survey page's lede.
- **Source**: `paper/<id>/main.tex` (+ `sections/*.tex` if long), authored by the survey-author
  from the same taxonomy + tokens (a tiny `scripts/survey_scaffold/tokens_to_tex.py` dumps the
  computed stats tokens as `\newcommand`s so the PDF's numbers are generated, same as the site's).
- **Bibliography**: `scripts/survey_scaffold/make_bib.py` — for every cited slug, emit a BibTeX
  entry from `papers.json` metadata, upgraded via the S2 `citationStyles.bibtex` field when
  available. `natbib` numeric citations.
- **Figures**: export the site's key SVG charts to PDF via `cairosvg` (add to
  `scripts/requirements-dev.txt`); charts land in `paper/<id>/figures/`.
- **Compile**: `tectonic paper/<id>/main.tex` → copy to `public/surveys/<id>.pdf`.
- **Linking (both directions)**: (a) add optional `"pdf": "surveys/<id>.pdf"` to the survey's
  `surveys.json` entry and render a second pill — `pdf ↓` — next to the "read →" pill in the map
  legend caption (`src/main.js` `.surveycap` block + `src/style.css .rd` sibling style); (b) the
  survey **page** hero gets a `download pdf ↓` link; (c) the PDF's footer/first page links the
  survey page URL. Backfill option: once this exists, the benchmarks/evaluations surveys can get
  PDFs the same way (separate, later runs of `/survey`).

### 7.5 Steps `critique` ↔ `revise`
`survey-critic` reviews, blockers-only JSON as §4.2, dimensions: every tagged paper appears in the
taxonomy and at least once in the prose; facet assignments spot-checked against explainers (cite
the explainer line as evidence); every number in page *and* PDF traces to a token; taxonomy is
internally coherent (no orphan categories, vocab actually discriminates); narrative has a thesis;
charts match the data; `main.tex` compiles clean and its content matches the site (no fork drift);
both build gates pass. Same round cap and `approved_with_notes` escape hatch.

### 7.6 Step `verify`
`npm run build`; open the page (desktop + 375px, no sideways scroll); PDF opens and has the
author/link block; legend pill appears; `?survey=<id>` deep link works.

---

## 8. Workstream 6 — CLAUDE.md & docs

- **Routing additions**: "run a lit search on X" / "start a literature search" / "keep working on
  <survey>" / "continue the lit search" → **Procedure E** (invoke `/litsearch`); "what surveys
  exist" / "survey status" → `/surveys`; "create/write the survey paper for X" / "make the survey
  PDF" → **Procedure F** (invoke `/survey`).
- New **Procedure E/F** sections: short — they describe intent and *defer to the skills* for
  mechanics (skills are the single source of truth; don't duplicate the state machine in prose).
- Document: the state files, queue `survey`/`role` fields, `work/` scratch, the agents + the
  convergence policy (max 3 rounds, `approved_with_notes`), and the PDF pipeline (tectonic,
  `paper/`, `surveys.json` `pdf` key).
- Data-shapes section: add the two queue fields and the `pdf` key to the examples.
- Keep every existing doctrine: never auto-commit; `tag_papers.py` owns tags; generated survey
  pages are never hand-edited; the render is the source of truth.
- Skills must pass the house standard (`skill-authoring-standard` skill + its lint script) since
  they now live in the repo.

---

## 9. Workstream 7 — Visual declutter (recommendations; all opt-in, defaults unchanged)

The map at 292 nodes / 3,151 edges is dense; these are ordered by (declutter value ÷ effort).
1–3 are recommended for this effort; 4–6 are backlog. Every one is a toggle that defaults to
today's behavior, so nothing regresses and CLAUDE.md's "spine is deliberately minimal" doctrine is
amended to "…with optional focus aids, off by default".

1. **Edge visibility toggle** (`edges: all | focus` in the topbar). In *focus* mode, edges render
   only when an endpoint is hovered/selected or on the active survey spine; otherwise hidden (not
   dimmed — hidden). This is the single biggest win: 3,151 always-on dim edges are most of the
   visual noise. Cheap: a style class flip in `src/main.js`; no layout change.
2. **Survey focus dim**: when a spine is active, a small `focus` checkbox dims non-member nodes to
   ~25% opacity (edges already handled by #1). Directly addresses "hard to tell what's going on"
   when working a survey. One style rule + the `applySurvey` block.
3. **Label level-of-detail**: below a zoom threshold, show `short` labels only for the top-K
   citation nodes per quarter column (K≈3); all labels at higher zoom or on hover. Kills label
   soup at the default zoom. Cytoscape `zoom` event + a precomputed per-column rank.
4. **Min-citation filter slider** (topbar): fade nodes (and their edges) under a citation floor.
5. **Node search box** with type-ahead → fly-to + select.
6. **Ego-network mode**: with a node selected, a keystroke hides everything outside its 1-hop
   neighborhood (complement to the survey spine for local reading).

Not recommended: edge bundling (fights the deliberate straight-line timeline aesthetic and is heavy
in cytoscape), and re-layout-on-filter (positional stability is worth more than density).

---

## 10. Implementation order, milestones, acceptance gates

Each milestone ends green on: `npm run build`, `python3 -m pytest scripts/tests/`,
`python3 scripts/lint_pages.py`. Nothing is auto-committed; each milestone ends with a review
reminder.

- **M1 — State infra** (small): `scripts/litsearch.py` + tests; queue-field validation in
  integrity tests; `.gitignore` surgery (§3.4); `work/` convention.
  *Gate*: state CLI round-trips; illegal transitions rejected; `.claude/skills/` is trackable.
- **M2 — `/surveys`** (small): status skill + `status --json`.
  *Gate*: correct table for `benchmarks`/`evaluations` (idle, no state files → shown as idle).
- **M3 — Agents + `/litsearch` seeding** (medium): four agent files; litsearch skill through
  Phase S.
  *Gate*: `/litsearch "LLM and Agent benchmarks"` resolves to a survey (likely adopting/gap-filling
  `benchmarks` or creating `agent-benchmarks` — ask the user which, once), runs a seed search, and
  queues confirmed seeds with `survey`+`role` fields at the top of the queue.
- **M4 — Per-paper loop + resume hardening** (large): the Phase-P state machine end-to-end.
  *Gates*: (a) one paper fully processed — explainer, node, edges, tag, critic-approved,
  verified desktop+mobile; (b) **the kill test**: start a second paper, kill the session mid-`draft`,
  re-invoke `/litsearch` — it must announce the resume point, finish the paper, and leave zero
  duplicate nodes/edges/queue entries (integrity tests confirm); (c) a forced 3-round paper exits
  as `approved_with_notes` without wedging.
- **M5 — `/survey` site path** (large): scaffolder, taxonomy step, author↔critic loop, generated
  page + `surveys.json` registration.
  *Gate*: a real survey page builds for the M3/M4 topic; every prose number is a token; critic
  approves; page renders desktop+mobile.
- **M6 — LaTeX PDF** (medium): tectonic preflight (user approves the brew install), vendored
  style, `make_bib.py`, `tokens_to_tex.py`, cairosvg figures, both-direction links.
  *Gate*: PDF compiles; sole author "Darvin Yi"; `pdf ↓` pill on the legend caption + page link;
  numbers in PDF match the site's tokens.
- **M7 — Visual toggles 1–3** (medium): edge-visibility toggle, survey focus dim, label LOD; CLAUDE.md
  conventions synced.
  *Gate*: defaults pixel-identical to today; toggles verified in the browser at desktop + 375px.

M1→M2→M3→M4 are sequential; M5/M6 depend on M4 only for having a corpus (can start against
`evaluations`' existing corpus if desired); M7 is independent and can go anytime.

## 11. Defaults chosen & open questions (decided here so implementation doesn't stall)

- **Chosen**: max_rounds = 3; builder=sonnet/high, paper-critic & both survey agents = opus/xhigh;
  seeds capped ~25 with one user confirmation; foundational threshold = citations ≥ 1000 or ≥ 2
  in-graph citers; foundational tier not processed by default; state files tracked in git;
  critiques in gitignored `work/` with blockers mirrored into state; tectonic for LaTeX;
  `arxiv.sty`-class preprint template; per-survey generated `scripts/<id>_survey/` (existing two
  bespoke builders untouched).
- **Ask the user during M3**: for "LLM and Agent benchmarks" — extend the existing `benchmarks`
  survey (gap-fill seeding) or create a distinct `agent-benchmarks` survey?
- **Ask during M6**: approve `brew install tectonic` (one-time, ~50 MB).
- **Resolved already** (verified against current Claude Code docs): per-agent effort is set with
  the `effort:` frontmatter key (`low|medium|high|xhigh|max`); `model:` accepts `sonnet`/`opus`
  aliases. No fallback mechanism needed.
- **Cost note** (so unattended runs aren't a surprise): each paper ≈ 1 sonnet builder run + 1–3
  opus-xhigh critic runs + 0–2 sonnet revise runs; a 25-paper seed list is a substantial multi-hour,
  multi-session job — which is exactly why every step checkpoints.
