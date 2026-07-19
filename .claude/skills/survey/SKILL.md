---
name: survey
description: Build or refine the survey artifact — taxonomy, generated site page, and a companion LaTeX/PDF preprint (sole author Darvin Yi) — with an opus-author/opus-critic review round, for a Paper Atlas survey whose corpus is already tagged. Use whenever the user says "build/create/write the survey paper for <topic>", "update the <survey> taxonomy", "refresh the <survey> survey page", "make/rebuild the survey PDF", "add these newly-tagged papers to the <survey> writeup", or asks for a taxonomy/survey page/PDF once papers are already tagged for a survey (`data/surveys.json` + each paper's `tags`). Do NOT use for tagging papers into a survey in the first place (that's Procedure D / `/litsearch`'s per-paper loop), for seeding or processing a survey's paper queue (`/litsearch`), or for read-only status (`/surveys`).
---

# /survey — build or refine a survey artifact

Orchestrates one survey's `survey_build` state inside
`data/litsearch/<id>.state.json` (the same file `/litsearch` uses — read
[CLAUDE.md](../../../CLAUDE.md)'s data-shapes section before your first
run), stepping through `corpus → taxonomy → site → tex → pdf → critique ⇄
revise → verify`. The `tex`/`pdf` steps are optional per run — the state
machine also allows `site → critique` directly — for a survey that only
wants its site page refreshed, or hasn't set up its PDF yet; run them when
the survey either has no PDF at all yet, or its PDF needs to reflect changes
this run made (new papers, revised taxonomy).

## Invocation

`/survey <survey-id-or-topic>` — resolve the same way `/litsearch` resolves
a topic (fuzzy match against `data/surveys.json`'s `id`/`label`), except a
survey with **zero tagged papers** is a hard stop: tell the user to tag or
seed some first (`/litsearch <topic>`), don't proceed with an empty corpus.

## Step 0 — resolve state

1. Match the argument to a survey id in `data/surveys.json`. No match, or
   the survey has no tagged papers → stop and say so.
2. If the survey has no `data/litsearch/<id>.state.json` yet, `python3
   scripts/litsearch.py init <id> --topic "<label>" --seeding-done` (its
   corpus already exists by definition — you're here because papers are
   tagged — so seeding is trivially done).
3. Read `state.survey_build.step` and resume there (see **Resume
   protocol** below) rather than restarting from `corpus` — a survey
   artifact run checkpoints exactly like a paper does.

## Step `corpus`

Checkpoint: `python3 scripts/litsearch.py set-survey-build-step <id> corpus`.

List every node tagged `<id>` in `data/papers.json`. If
`data/<id>-taxonomy.json` doesn't exist yet, this is a **fresh build** —
every tagged paper needs classifying. If it exists, this is a **refine**:
diff the tagged set against the taxonomy's slugs (`python3 -m pytest
scripts/tests/test_data_integrity.py -k benchmarks_taxonomy_matches -v` is
the exact check the `benchmarks` survey uses — mirror its pattern for
another survey id if one exists) — new papers need classifying, taxonomy
records for papers no longer tagged need dropping. Read each affected
paper's explainer (`public/papers/<slug>.html`) as your source material —
it's already a verified summary, re-reading the original PDF is only
needed if a specific fact is unclear.

## Step `taxonomy`

Checkpoint: `set-survey-build-step <id> taxonomy`.

Write/update `data/<id>-taxonomy.json`: one record per tagged paper, 4–7
survey-specific facets with small closed vocabularies, **plus at least one
novel organizing axis** — a taxonomy that just re-buckets the obvious
category (task type, model family) says nothing a reader couldn't derive
themselves. The bar is `data/evaluations-taxonomy.json`'s **reward-
readiness** axis (see `public/surveys/evaluations.html`'s "reward-
readiness" section for what that means in practice) and
`data/benchmarks-taxonomy.json`'s 7-kingdom/24-family placement tree +
cross-paper `lineage` graph (see `public/surveys/benchmarks.html`'s "the
tree" section). Design facets fresh for *this* survey's subject — don't
carry over another survey's vocabulary by default.

**If `<id>` is `benchmarks` specifically**: the taxonomy already exists and
is rich (17 domains, 6 grading mechanisms, a 7-kingdom/24-family tree,
lineage links, `dynasty`/`gravity` fields) — read a few existing records in
`data/benchmarks-taxonomy.json` before classifying a new one, and match
that schema exactly (every field in `BENCH_TAXONOMY_REQUIRED_KEYS`,
`scripts/tests/test_data_integrity.py`). Placing a new paper in the
kingdom/family tree requires real judgment: read `KING_L`/`FAM_L` in
`scripts/benchmarks_survey/build_survey_page.py` for the full definitions
and pick the family whose one-line question the paper's own problem
statement is actually answering — not the family that merely sounds
topically close.

Validate before moving on: `python3 -m pytest
scripts/tests/test_data_integrity.py -q` must pass (vocab-closed, required-
keys, family/kingdom-prefix, lineage-parents-exist checks — see that file
for the exact assertions if you're extending `benchmarks`; write the
equivalent checks into that file for a new survey's first taxonomy).

## Step `site`

Checkpoint: `set-survey-build-step <id> site`.

- **Existing builder** (a `scripts/<id>_survey/` directory already exists —
  true for `benchmarks` today): just rebuild it — `python3
  scripts/<id>_survey/build_survey_page.py` — after the taxonomy is
  updated. Update the builder's prose/chart sections too if the new
  papers change what a chart or finding claims (a stale finding that no
  longer matches the data is a defect, not a style choice).
- **New survey, no builder yet**: `python3
  scripts/survey_scaffold/new_survey.py <id>` first (refuses if
  `scripts/<id>_survey/` already exists or `<id>` isn't in
  `data/surveys.json`), then fill in every `TODO(survey-author)` marker in
  the three scaffolded files — facets, at least one chart, the findings
  section, the filterable table's columns — before building. The scaffold
  is a starting shell, not a finished page; see
  `scripts/benchmarks_survey/` or `scripts/evaluations_survey/` for what a
  finished one looks like.

**No hand-typed numbers, ever**: every count/percentage/ratio the page
states must trace to a value computed from the taxonomy at build time
(`stats_tokens.py`'s `compute()` for evaluations-style builders, or the
inline cross-tabs in `benchmarks_survey/build_survey_page.py`) —
never type a number directly into `survey_template.html` prose.

Register `"page": "surveys/<id>.html"` in `data/surveys.json` if it isn't
already there (it already is for `benchmarks`).

## Step `tex` (optional — skip straight to `critique` if this run isn't
touching the PDF)

Checkpoint: `set-survey-build-step <id> tex`.

The toolchain (`tectonic`, `cairosvg`) is installed and verified — see
`scripts/requirements-tex.txt` for the exact setup and a real trap already
hit and fixed once (`brew install python3` silently redirects this repo's
*other* scripts' bare `python3` to an interpreter missing their
dependencies — `brew unlink` it immediately after any cairosvg work).

1. **Template.** `paper/<id>/` is this survey's LaTeX source directory —
   create it if new. It uses the vendored `paper/common/arxiv.sty` (MIT-
   licensed, kourgeorge/arxiv-style — see `paper/common/LICENSE-arxiv-style.txt`
   for provenance; never hand-edit `arxiv.sty` itself). Author `paper/<id>/main.tex`:
   `\documentclass{article}` + `\usepackage{arxiv}`, title = the survey's
   title, **author block: `Darvin Yi` only** (no co-authors, no ORCID
   placeholder — affiliation line `research.darvinyi.com`), abstract
   condensed from the site's hero `dek`. The body is a genuine condensation
   of the site's narrative into paper form (sections mirroring the site's:
   corpus, facets/taxonomy, findings, connections) — not a mechanical dump
   of the HTML, and not a wholly independent rewrite either: every *fact*
   must match the site exactly (see `critique`'s "no fork drift" check
   below).
2. **Numbers.** `python3 scripts/survey_scaffold/tokens_to_tex.py <id>` —
   dumps the survey's already-computed stats tokens (the exact same
   `tokens` dict the site's `@@TOKEN@@` substitution uses) as LaTeX
   `\newcommand`s into `paper/<id>/tokens.tex` (auto-generated names like
   `\TokN`, `\TokPctKingCap` — see the file's own header comment for the
   `N_ERA_2122`-style-token → `\TokNEraTwoOneTwoTwo`-style-macro naming
   rule). Requires `scripts/<id>_survey/build_survey_page.py` to expose its
   computed stats as a module-level `tokens` dict — `scripts/benchmarks_survey/`
   and the scaffold template already do; a survey whose builder still
   discards the dict into a bare loop (as `scripts/evaluations_survey/`
   does, pre-dating this convention) needs that one-line fix first.
   `\input{tokens.tex}` in `main.tex` and cite every number in prose via its
   macro (`\TokN{}` papers, `\TokPctKingCap\%` are...) — **never hand-type a
   number in `main.tex` either**, same rule as the site, same reason (a
   real defect this pipeline already found once on the site side — see the
   Worked example).
3. **Bibliography.** `python3 scripts/survey_scaffold/make_bib.py <id>` —
   writes `paper/<id>/refs.bib`, one entry per tagged paper (or `--slugs`
   for an explicit list, e.g. to also cite a lineage-linked method paper
   outside the survey's own tagged corpus), preferring Semantic Scholar's
   own `citationStyles.bibtex` when reachable and falling back to a
   constructed entry from `data/papers.json` + the paper's arXiv id
   otherwise — safe to over-include, BibTeX only emits what `main.tex`
   actually `\citep{}`s. Use `\usepackage{natbib}` + `\citep{<slug>}` +
   `\bibliographystyle{plainnat}` + `\bibliography{refs}`.
4. **Figures.** Export the site's key SVG charts to PDF via the dedicated
   venv: `.venv-cairo/bin/python3 -c "import cairosvg;
   cairosvg.svg2pdf(url='chart.svg', write_to='paper/<id>/figures/chart.pdf")"`
   (or write a small script if exporting several — there's no
   `svg_to_figures.py` yet, this is a case-by-case step). Land them in
   `paper/<id>/figures/`, `\includegraphics` them from `main.tex`.
5. Compile once here to catch errors early (the real compile-and-verify
   gate is step `pdf` below): `tectonic paper/<id>/main.tex`.

## Step `pdf`

Checkpoint: `set-survey-build-step <id> pdf`.

1. `tectonic paper/<id>/main.tex` → `paper/<id>/main.pdf`; copy/rename to
   `public/surveys/<id>.pdf`.
2. **Both-direction linking** (do all three, not just one):
   - `data/surveys.json`: add `"pdf": "surveys/<id>.pdf"` to this survey's
     entry (validated by `scripts/tests/test_data_integrity.py`'s
     `test_surveys_pdf_points_to_an_existing_file` — the file must already
     exist when you add the key, so do this *after* step 1, not before).
     The map's legend caption (`src/main.js`'s `renderLegend`,
     `.surveycap .capLinks` in `src/style.css`) picks this up automatically
     as a "pdf ↓" pill next to "read →" — no further site code changes
     needed, that wiring already exists.
   - The survey **page**'s hero gets a `download pdf ↓` fact link (see
     `scripts/benchmarks_survey/survey_template.html`'s hero `.facts` row
     for the exact pattern — `<a href="<id>.pdf">download pdf&nbsp;↓</a>`,
     relative to the page's own directory).
   - The PDF's own first page or footer links back to the survey page URL
     (`https://research.darvinyi.com/surveys/<id>.html`) — a `\thanks{}` on
     the title or a footnote near the abstract is the natural spot; see
     `paper/common`'s vendored template's `\thanks` pattern for the
     mechanism.
3. Rebuild the site too (`python3 scripts/<id>_survey/build_survey_page.py`)
   so the new "download pdf ↓" hero link actually appears — the `pdf` key
   change alone doesn't touch `public/surveys/<id>.html`.

## Step `critique` ⇄ `revise`

Same contract, same convergence policy, same round cap
(`config.max_rounds`, default 3) as `/litsearch`'s paper loop — see
`.claude/agents/survey-critic.md` / `survey-author.md` for the full spec;
the orchestrator logic is identical to the per-paper `critique`/`revise`
branch in `.claude/skills/litsearch/SKILL.md`'s Phase P, using
`set-survey-blockers`/`complete-survey-build` (the `survey_build` siblings
of `set-blockers`/`complete-paper` — added to `scripts/litsearch.py`
specifically because this skill needed them; see the Worked example) in
place of the per-paper commands: sync each round's verdict with
`set-survey-blockers <id> work/<id>-survey/critique-r<N>.json`, and once
approved (zero open blockers, or `round == max_rounds` with blockers still
open → `approved_with_notes`, exactly like the round-cap escape hatch
elsewhere in this pipeline), call `complete-survey-build <id> --verdict
<approved|approved_with_notes>` — this resets `step`/`round` so the next
`/survey <id>` run starts clean at `corpus` rather than picking up a
finished cycle.

`survey-critic`'s dimensions (from its own file, restated here as the
orchestrator's checklist for what to expect back): every tagged paper
appears in the taxonomy *and* in the prose at least once; facet
assignments spot-checked against explainers; taxonomy coherence (no orphan
categories, the novel axis actually organizes); a real thesis, not a
paper-by-paper list; charts match their claimed data; no hand-typed
numbers on the site; and — once a PDF exists — no hand-typed numbers in
`main.tex` either, `main.tex` compiles clean with `tectonic`, and **no fork
drift**: every fact stated in the PDF must match what the site states for
the same fact (a number, a superlative, a finding) — the two are meant to
be the same survey in two formats, not two independently-maintained
narratives that can quietly disagree.

## Step `verify`

`npm run build` must succeed. Load `public/surveys/<id>.html` at desktop
width and at ≈375px — confirm no sideways document scroll
(`document.documentElement.scrollWidth <= clientWidth`), figures/tables
that are meant to scroll horizontally do so inside their own box (not the
whole page), and the map's legend caption shows the "read →" pill (and, if
this run built a PDF, a "pdf ↓" pill next to it — check via
`window.cy`/the DOM, not just visually, per this pipeline's established
render-verification pattern) linking here. Confirm the `/?survey=<id>` deep
link opens the map with this survey's spine centered. If a PDF exists,
open it and confirm: sole author "Darvin Yi", the numbers match the site's
(spot-check a handful against the live page), and the back-link to the
survey page URL is present. Checkpoint: `set-survey-build-step <id>
verify`.

## Resume protocol

Identical shape to `/litsearch`'s: re-read `state.survey_build` before
doing anything — never trust conversation memory for which step a survey
artifact run is on. `corpus`/`taxonomy`/`site` are safe to redo (they
overwrite the same output files). `critique`: if
`work/<id>-survey/critique-r<round>.json` already exists, read it and
branch immediately rather than re-invoking `survey-critic`. `revise`:
same check against `response-r<round>.md`. A kill mid-run loses at most
the in-flight step.

## When NOT to use this skill

- Tagging papers into a survey — that's Procedure D, or automatic during
  `/litsearch`'s per-paper `draft` step. This skill only touches
  `data/<id>-taxonomy.json`, `scripts/<id>_survey/`,
  `public/surveys/<id>.html`, and (registration only) `data/surveys.json`.
- Seeding or processing a survey's paper queue — `/litsearch`.
- Read-only status — `/surveys`.

## Worked example

A real run against this repo, 2026-07-18 — `/survey benchmarks` in refine
mode (137 → 139 tagged papers after `/litsearch` processed two new ones):

**`corpus`.** `data/papers.json` had 139 nodes tagged `benchmarks`;
`data/benchmarks-taxonomy.json` had 137 records. The diff was exactly the
two just-processed papers — `maharana-2024-locomo` (LoCoMo) and
`xu-2022-msc` (MSC), both multi-turn conversational-memory benchmarks.

**`taxonomy`.** Classified both into the existing 31-key schema (read from
several existing records first, per this file's guidance) — kingdom
`A-capability`, family `A7-communication` for both, with real `lineage`
links found by reading each paper's own bibliography (LoCoMo
`descends-from` MSC; both `transplants-method-of` a method paper already in
the graph). `python3 -m pytest scripts/tests/test_data_integrity.py -q`
caught nothing wrong with the new records, but the *run itself* surfaced a
larger pre-existing defect: `scripts/benchmarks_survey/build_survey_page.py`
computed `N = len(merged)` but never emitted it as a token — every
statistic on the page was a hand-typed literal, correct at N=126 but stale
since the corpus grew past it (a violation of this skill's own "no hand-
typed numbers" rule, undetected until this run actually tried to enforce
it). Fixing that properly — a new `stats_tokens.py`, ~40 number→`@@TOKEN@@`
swaps in the template, one narrative rewrite where the raw share crossed a
threshold ("never exceeds ~8%" → "~10%" once the true max, 9.5%, rounds up)
— was itself the bulk of this step's work, not a detour from it.

**`site`.** Rebuilt via the existing `scripts/benchmarks_survey/
build_survey_page.py` (no scaffolding needed — the builder already
existed). `assert '@@' not in page` passed: zero unresolved tokens.

**`critique` round 1 → `revise` → `critique` round 2.** The critic found
one real blocker: a *different* hand-typed number (`"HumanEval … 43
in-corpus citations to APPS's 12"`) that the author had defensibly, but
incorrectly, judged to be a frozen historical fact — the critic showed it
was a trivially recomputable live graph statistic (real value: 46/13) and
distinguished it precisely from the genuinely-frozen numbers nearby (a
one-time inter-rater-agreement study, correctly left alone). One revise
round tokenized it (`GRAV_HUMANEVAL`/`GRAV_APPS`, computed from the
in-corpus subgraph of `data/papers.json`); round 2 approved with zero
blockers.

**A real gap this run exposed in the pipeline itself**: `survey_build` had
no blocker-tracking sibling to `current.open_blockers` — `set-blockers`
only ever worked on `current` (the per-paper field), so there was no way
to sync a survey-critique's verdict into state at all. Added
`set-survey-blockers` and `complete-survey-build` to `scripts/litsearch.py`
(mirroring `set-blockers`/`complete-paper` exactly) plus their test
coverage — this is why those two commands exist in this file's Step
`critique`/`revise` instructions above, not because they were planned in
advance.

**`verify`.** `npm run build` and the full test suite (77 tests) both
green throughout. Checked via the map's own `window.cy` cytoscape instance
and direct DOM queries rather than screenshot-guessing: the survey
dropdown read `"Benchmarks (139)"`, the legend's `read →` pill linked to
`surveys/benchmarks.html`, the page itself showed `papers 139` in its hero
facts (proving the token pipeline actually ran), and
`document.documentElement.scrollWidth <= clientWidth` held at both desktop
and 375px.

**M6, same survey, immediately after — the `tex`/`pdf` steps, real:**
`tokens_to_tex.py benchmarks` emitted 58 `\newcommand`s from the site's own
computed `tokens` dict (required one prerequisite fix: the survey's
`build_survey_page.py` was discarding that dict into a bare loop variable
instead of naming it — a one-line change, `scripts/benchmarks_survey/`'s
own convention gap, not a design flaw). `make_bib.py benchmarks` emitted
139 entries and, during its own development (before ever touching
`main.tex`), caught two real defects a synthetic test alone wouldn't have:
unescaped LaTeX-special characters in real titles ("SWE-Lancer: Can
Frontier LLMs Earn $1 Million...", "GPQA: A Graduate-Level Google-Proof
Q&A Benchmark" — `$`/`&` unescaped would have broken compilation on ~4 of
139 real entries) and a missing-glyph font warning for "τ-bench"'s Greek
character (fixed by mapping it to `$\tau$` in the shared
`latex_utils.latex_escape()` both scripts import, rather than duplicating
the fix). `survey-author` then wrote a genuine ~4,600-word `main.tex`
condensation (not a mechanical HTML dump), exported 3 SVG charts to PDF
via `.venv-cairo`, and compiled clean with `tectonic` on the first attempt
after those two script-level fixes were already in place. `survey-critic`
independently re-verified 20+ specific facts against the live site (not
just spot-checking a couple), re-ran the compile itself rather than
trusting the report, and confirmed the round-1 blocker from the *site*
critique (the stale 43/12 HumanEval/APPS numbers) stayed fixed in the PDF
too — approved round 1, zero blockers.

The `verify` step's own browser check caught a real UI bug the critic's
text-only review couldn't have: the legend's survey caption (`.surveycap`)
was a single non-wrapping flex row sized for exactly one link pill
("read →"); adding "pdf ↓" as a second pill overflowed the fixed-width
legend panel by 43px (measured via `getBoundingClientRect`, not eyeballed
— a screenshot alone showed the pill "there but cut off" ambiguously).
Fixed with `flex-wrap:wrap` on `.surveycap` so the link pills drop to
their own line when they don't fit next to the label — verified
`scrollWidth - clientWidth == 0` after the fix, both survey pills fully
inside the panel, screenshotted at desktop and confirmed no regression on
`evaluations`' still-single-pill case. This is exactly why `verify` drives
a real browser rather than trusting that "the HTML has the right
`href`" — the pill was correctly wired and completely broken at the same
time.

## Provenance and maintenance

- **Authored: 2026-07-18** (milestone M5: taxonomy/site/critique loop,
  against the real shape of `data/benchmarks-taxonomy.json` — 137 records,
  31 keys each, verified by direct inspection — and
  `data/evaluations-taxonomy.json`'s `stats_tokens.py` pattern; milestone
  M6 added the `tex`/`pdf` steps — `tectonic`, the vendored
  `paper/common/arxiv.sty`, `tokens_to_tex.py`, and `make_bib.py` were each
  verified individually against real repo data (a full compile citing all
  139 `benchmarks` papers; real LaTeX-special-character titles like "SWE-
  Lancer: Can Frontier LLMs Earn $1 Million..." and "τ-bench" caught and
  fixed before either script shipped) — see the Worked example below for
  the first real end-to-end survey PDF built through this skill).
- **Re-verify with:**
  ```bash
  python3 -m pytest scripts/tests/test_data_integrity.py -k benchmarks_taxonomy -v
  python3 scripts/litsearch.py status benchmarks --json   # confirm survey_build state shape
  tectonic --version && .venv-cairo/bin/python3 -c "import cairosvg"  # confirm the M6 toolchain
  ```
- **Most likely to go stale:** the exact `BENCH_TAXONOMY_REQUIRED_KEYS` /
  kingdom-family vocab (grows as the survey grows — always read
  `scripts/benchmarks_survey/build_survey_page.py`'s `KING_L`/`FAM_L`
  directly rather than trusting a cached list); which surveys currently
  have a PDF (check `data/surveys.json`'s `pdf` keys directly, don't
  assume only `benchmarks` still does).
