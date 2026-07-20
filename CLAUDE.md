# CLAUDE.md — Paper Atlas operations

This repo is **Paper Atlas**: a dark, citation-map site of ML/eval papers, deployed at litsearch.darvinyi.com. Two tiers:

- the **index map** — a citation **timeline** that reads `data/papers.json`: papers flow left→right by publication date (quarter bands, ordered to minimize edge crossings), nodes coloured by topic/author/venue, edges dimmed until you hover a node. The layout math lives in `src/timeline.js`; the renderer, hover behaviour, and the time-axis overlay in `src/main.js` + `index.html` (`#axis`) + `src/style.css`.
- one **explainer page per paper** at `public/papers/<slug>.html` (dark, self-contained long-reads)

On top of the map sits a **survey** overlay: a survey is a named tag (e.g. *Benchmarks*) defined in `data/surveys.json`, and a paper's membership lives in its node's `tags` array. The topbar `survey` dropdown lets a reader pick one — its tagged papers are pulled into a centred horizontal **spine** and ringed in the survey colour; the rest of the map is left exactly as-is (no dimming, no edge colouring), so the only change is the centred, ringed subset. Surveys are the backbone of the actual survey papers you'll write: tag the core papers of a topic, then read them off the spine. (`scripts/tag_papers.py` is the tagging tool; see **Procedure D**.)

A local **queue** (`data/queue.json`) lists papers waiting to become explainers. You (the agent) process them one at a time and grow the queue with newly-discovered papers.

You have web access, bash (curl/wget), and Python (PyMuPDF / Pillow). **Never auto-commit, push, or deploy.** End every task with a short summary of what changed and a reminder for me to review (`npm run dev`) and commit.

**Semantic Scholar API key.** A key lives in the `$S2_API_KEY` env var (set in the gitignored `.claude/settings.local.json` — never hardcode or echo it). Send it on **every** Semantic Scholar request as a header: `curl -s -H "x-api-key: $S2_API_KEY" "https://api.semanticscholar.org/graph/v1/..."`. This raises the rate limit; without it the API throttles aggressively. If a call still 429s, back off and retry rather than dropping the key.

## Command routing
- "run the next one" / "go down the queue" / "next paper" / "do the next one" → **Procedure A — Process next**
- "add X to the queue" / "queue up X" / "add all papers by/from …" → **Procedure B — Add to queue**
- "review the existing papers" / "audit the graph" / "refresh citations" / "recheck the connections" → **Procedure C — Audit the graph**
- "tag X as a benchmark" / "tag these for the <survey> survey" / "mark X as a <survey> paper" / "re-tag the graph for <survey>" / "create a new survey called …" → **Procedure D — Tag for a survey**
- "run a lit search on X" / "start a literature search" / "search the literature for X" / "keep working on <survey>" / "continue the lit search" / "resume <survey>" → **`/litsearch`** (`.claude/skills/litsearch/`) — the topic-driven, stop/resume-safe pipeline: seeds a survey's queue via multi-angle search, then processes papers one at a time with a sonnet-builder/opus-critic loop (PIPELINE_PLAN.md). Distinct from Procedure A: it only ever touches queue entries carrying a `survey`/`role` pair, never the general queue.
- "what surveys exist" / "survey status" / "how's the <survey> survey going" / "what's left to process" → **`/surveys`** (`.claude/skills/surveys/`) — a read-only status report over every survey's tag count, queue depth, and in-progress paper. Never mutates anything.
- "create/write/refresh the survey paper for X" / "build the <survey> survey page" / "update the taxonomy for <survey>" / "make the survey PDF" → **`/survey`** (`.claude/skills/survey/`) — builds or refines the survey artifact (taxonomy → generated page → optional LaTeX/PDF companion, sole author Darvin Yi, with a `survey-author`/`survey-critic` review round) for a survey whose corpus is already tagged.
- "make the podcast for X" / "add a podcast episode for X" / "make an audio episode for X" / "narrate X" → **Procedure A, opt-in podcast step** — produce & link one podcast episode for an **existing** explainer (the paper must already be a node). Expensive and strictly opt-in; never run automatically for the queue.

If a message is ambiguous, ask one short question before acting.

## Data shapes

### `data/queue.json` — ordered list, top = next
```json
[
  {
    "title": "GDPval: Evaluating AI Model Performance on Real-World Economically Valuable Tasks",
    "arxiv_id": "2510.04374",
    "doi": null,
    "authors": "Patwardhan et al.",
    "year": 2025,
    "venue": "arXiv",
    "citation_count": null,
    "topic": "Benchmarks & Evals",
    "priority": "High",
    "source": "Manual",
    "why": "one-line reason it's worth covering"
  }
]
```
Two more fields are **optional**, written together (never one without the other): `"survey"` (a survey id from `data/surveys.json`) and `"role"` (`"core"` or `"foundational"`). The `/litsearch` pipeline stamps these on entries it queues so it can find and prioritize its own work inside the shared queue without touching the ~1,000 hand-curated entries that predate it — see `data/litsearch/` below. An entry with neither field is ordinary Procedure-B/manual queue content.

### `data/papers.json` — the graph the map renders
```json
{
  "papers": [
    {
      "slug": "patwardhan-2025-gdpval",
      "short": "GDPval",
      "title": "GDPval: Evaluating AI Model Performance on Real-World Economically Valuable Tasks",
      "authors": "Patwardhan, Lee, …",
      "year": 2025,
      "date": "2025-09",
      "venue": "arXiv",
      "citation_count": 142,
      "topic": "Benchmarks & Evals",
      "author_group": "OpenAI",
      "abstract": "1–2 sentence summary for the side panel.",
      "explainer": "papers/patwardhan-2025-gdpval.html",
      "audio_url": "https://pod.darvinyi.com/audio/patwardhan-2025-gdpval.mp3",
      "tags": ["benchmarks"]
    }
  ],
  "edges": [ { "from": "<citing slug>", "to": "<cited slug>" } ]
}
```
Edges are directed (citing → cited). The map lays papers out as a **left→right timeline** by publication date (`src/timeline.js`): papers are binned into quarter bands, and each column is ordered to minimize edge crossings. `date` is `"YYYY-MM"` (month precision, from the paper's arxiv id); the layout falls back to `year` mid-year if it's missing. Node size is `12 + 14·log10(citation_count+1)` px, **capped** (see `size()` in `src/main.js`) so 70k-citation foundational nodes don't blow out a column. The color-by dimensions are `topic`, `author_group`, and `venue`. Edges sit dim and brighten on hover/selection. The map reads this file directly, so updating it **is** updating the map — no separate map edit.

`audio_url` is **optional** and goes **right after `explainer`** (before `tags`). **Absent means no podcast episode** — most nodes have no `audio_url` key. When present it must be the canonical published URL for the slug: `https://pod.darvinyi.com/audio/<slug>.mp3` (the episode is produced in the separate `darvinyi-podcast` repo; see the opt-in podcast step in Procedure A). Don't hand-write it — `python scripts/inject_podcast.py --set <slug>` stamps it deterministically (canonical key order preserved) **and** injects the on-page player; `test_data_integrity.py` enforces the canonical value.

`tags` is **optional** and goes **last** in the node (after `explainer`/`audio_url`); it is an array of survey ids (see `data/surveys.json`) — a paper can belong to several surveys. **Absent means untagged** — most papers have no `tags` key. It is written **inline** (`"tags": ["benchmarks"]`) and kept sorted & de-duplicated; let `scripts/tag_papers.py` own it so the canonical formatting (and the rest of `papers.json`) is preserved. Membership drives the survey spine (Procedure D); it is independent of `topic` (a paper's topic can be "Benchmarks & Evals" without being a *core* benchmark paper, and vice-versa).

### `data/surveys.json` — survey (tag) definitions
```json
{
  "surveys": [
    {
      "id": "benchmarks",
      "label": "Benchmarks",
      "color": "#ffd166",
      "description": "Core benchmark, evaluation-dataset, and agent-evaluation-environment papers — the named entries a survey of LLM & agent benchmarks would cite."
    }
  ]
}
```
`id` is the stable token stored in each node's `tags` (lowercase, hyphenated; never change it once papers reference it). `label` is the dropdown text, `color` the spine ring colour (pick one distinct from the teal selection accent), `description` the intent — *what makes a paper a core member*, which is the rubric Procedure D and the Procedure A tagging step apply. The site reads this file directly; adding a survey here makes it appear in the topbar `survey` dropdown. A survey may also carry an optional `page` (e.g. `"surveys/benchmarks.html"`): a self-contained write-up served from `public/<page>` — when present, the legend's survey caption shows a "read →" pill linking to it, and the page links back with `/?survey=<id>` (a deep link that opens the map with that spine active). It may separately carry an optional `pdf` (e.g. `"surveys/benchmarks.pdf"`, PIPELINE_PLAN.md M6) — a compiled LaTeX preprint, sole author Darvin Yi, built via `/survey`'s `tex`/`pdf` steps; when present, the legend caption shows a second "pdf ↓" pill next to "read →" (`.surveycap .capLinks` in `src/style.css` + `src/main.js`'s `renderLegend`), the survey page's hero gets a matching "download pdf ↓" link, and the PDF itself links back to the survey page — add the key only after the PDF file actually exists (`scripts/tests/test_data_integrity.py`'s `test_surveys_pdf_points_to_an_existing_file` enforces this). The Benchmarks survey page is **generated** and, as of milestone M5 (PIPELINE_PLAN.md), **owned by the `/survey` pipeline** rather than by hand: never hand-edit `public/surveys/benchmarks.html`, and don't run `scripts/benchmarks_survey/build_survey_page.py` ad hoc either — updates go through `/survey benchmarks` (`.claude/skills/survey/`), which diffs the tagged corpus against `data/benchmarks-taxonomy.json` (137→ papers, each classified across domain/task-shape/grading/complexity/provenance/contamination-defense/saturation/tool-access **plus** a 7-kingdom/24-family taxonomy tree and a cross-paper `lineage` graph — read a record in that file before extending it, the schema is rich and load-bearing), regenerates via `scripts/benchmarks_survey/build_survey_page.py` (unchanged — it already follows the generic per-survey-builder pattern: taxonomy JSON → computed stats → template → inline SVG charts, so it didn't need rewriting to become pipeline-owned), and gates the result through a `survey-author`/`survey-critic` review round before it ships. `scripts/survey_scaffold/new_survey.py` scaffolds the equivalent structure for a **new** survey id that has no existing builder. The **Evaluations** survey page (*The Anatomy of a Verdict*) is likewise generated but stays on its original bespoke, hand-run path for now — never hand-edit `public/surveys/evaluations.html`; edit `scripts/evaluations_survey/` (builder + `survey_template.html` + `charts_custom.py` + `stats_tokens.py`, reusing `svgcharts.py`) and/or `data/evaluations-taxonomy.json` (59 eval-methodology papers × 7 facets — verdict engine, construct, reference standard, signal fidelity, **reward-readiness** (the novel axis), validation depth, grader gap — plus a 7-kingdom/22-family role tree), then re-run `python scripts/evaluations_survey/build_survey_page.py`. All prose numbers in both surveys come from computed tokens (never hand-typed), so re-tagging or new nodes only require re-classifying and rebuilding.

### `data/litsearch/<survey_id>.state.json` — the /litsearch resume point
One file per survey that has ever been run through the `/litsearch` pipeline (PIPELINE_PLAN.md), owned by `scripts/litsearch.py`. Never hand-edit it — every mutation goes through the CLI's subcommands (`init`, `start-paper`, `set-step`, `set-blockers`, `complete-paper`, `skip-paper`, `log`, `status`, `set-survey-build-step`, `set-survey-blockers`, `complete-survey-build`), which validate the state-machine transitions and write atomically. A survey with no state file (e.g. `evaluations`, still built by hand via Procedure D) simply reports as `"phase": "idle"`; that's normal, not an error. The file tracks: `phase` (`seeding | processing | survey | idle`), `config` (builder/critic model+effort, `max_rounds`, `process_foundational`), `seeding` (done/queries/count), `current` (the in-progress paper — `slug`, `step` in `resolve → fetch → figures → draft → critique ⇄ revise → verify → queue-ops`, critique `round`, `open_blockers`), `completed`/`skipped` history, `survey_build` (the `/survey` artifact's own step machine — `step` in `corpus → taxonomy → site → tex → pdf → critique ⇄ revise → verify`, with `site → critique` also legal directly for a run that isn't touching the PDF; its own `round`/`open_blockers`, plus `taxonomy`/`site`/`pdf` booleans recording whether each has ever completed), and a capped `log`. `python3 scripts/litsearch.py status [--json]` is the read path — that's what the `/surveys` skill runs; see also `scripts/tests/test_litsearch_state.py` for the exact transition rules.

### `paper/<survey_id>/` — the LaTeX source for a survey's PDF companion
Owned by `/survey`'s `tex`/`pdf` steps (PIPELINE_PLAN.md M6); a survey with no PDF yet simply has no `paper/<id>/` directory. `main.tex` is genuine per-survey authored content (condensed from the site's narrative, not a mechanical dump) built on the vendored `paper/common/arxiv.sty` (MIT-licensed, kourgeorge/arxiv-style — see `paper/common/LICENSE-arxiv-style.txt`; never hand-edit `arxiv.sty` itself). `tokens.tex` (via `scripts/survey_scaffold/tokens_to_tex.py`) and `refs.bib` (via `scripts/survey_scaffold/make_bib.py`) are both regenerated, never hand-edited — same "no hand-typed numbers" rule as the site, enforced by reusing the site's own computed `tokens` dict rather than a second, driftable computation. Compiled with `tectonic paper/<id>/main.tex`; figures exported from the site's SVG charts via `cairosvg`, which needs the dedicated `.venv-cairo/` (see `scripts/requirements-tex.txt` — a real macOS SIP trap is documented there, already hit and fixed once).

### Slug
`firstauthor-year-keywords`, lowercase, hyphenated. Generated once; it is the explainer filename **and** the graph node id. Never change a paper's slug.

## Explainer page contract
Each `public/papers/<slug>.html` is one self-contained **dark** long-read built from `templates/explainer.html`:
- Sections in order: **hero → the gap (problem) → how it works (method) → what they found (results) → does it hold up? (eval-rigor critique — the signature section) → takeaways.**
- The paper's **real figures**, extracted from the PDF and inlined as base64. Equations as HTML/CSS. No external scripts except web fonts. Dark theme matching the index.
- **Optional podcast block (opt-in, injector-managed).** If the node has an `audio_url`, `scripts/inject_podcast.py` inserts a `listen ♪` pill in the hero (next to `source ↗`) and an `<audio controls preload="none">` player under the dek — delimited by `<!--pod-pill-->`/`<!--pod-player-->` markers; never hand-place or hand-edit it (run the injector). The player's external MP3 `src` is the **one intentional exception** to "no external resources but fonts": it is media, not a script, and `preload="none"` means nothing loads until the reader hits play. Its scoped CSS keeps `audio{width:100%;max-width:100%}`, so it never breaks the mobile no-horizontal-scroll contract.
- The hero **`source ↗` link (`{{SOURCE_URL}}`) must be the paper's own canonical URL** — prefer the arXiv `abs` URL. It is load-bearing: `scripts/backfill_dates.py` reads the arXiv id out of this link to recover the node's `date` (the timeline's month precision), so a wrong or missing `source` link breaks the timeline placement.
- Quote **exact numbers** from the paper; never invent. Write the critique as a sharp, specific eval read: are the baselines fair and current? contamination / leakage? what the headline metric misses? what would raise confidence?
- **Must be mobile-safe (≤640px).** Always build from `templates/explainer.html` so you inherit its `@media(max-width:640px)` block — never hand-roll a page or strip that CSS. That block is the canonical mobile contract; **all existing pages have been backfilled to match it**, so if you ever change it, change the template *and* every `public/papers/*.html` together (they share an identical media-query string — a single find/replace across all of them keeps them in sync). What it guarantees: the page never scrolls **horizontally** — wide results `table`s become their own horizontal scroll box (`display:block;overflow-x:auto`); the `.verdict` critique grid stacks to one column (key above value) instead of cramming a `1fr` column behind a wide key gutter; long unbreakable tokens wrap (`overflow-wrap:anywhere`, plus `min-width:0` so grid/flex children can shrink). If you introduce a **new** wide structure (a custom grid, a fixed-width figure wrapper, a long inline `code`/`mono` token), verify it doesn't reintroduce sideways scroll and, if it does, add a matching mobile rule to the template + all pages.

---

## Procedure A — Process the next paper

1. **Pick.** Read `data/queue.json`. If empty, say so and stop. Otherwise take the top entry (highest `priority`, then order in file) and state which paper you're processing.
2. **Resolve identifiers.** If the entry has no `arxiv_id`/`doi`, find it: search Semantic Scholar and the web by title, and confirm the match (authors + year). Record the arXiv id (or a direct PDF URL) and the canonical metadata.
3. **Download the PDF.** `curl -L -o /tmp/paper.pdf https://arxiv.org/pdf/<arxiv_id>`. Verify it's real (`%PDF` header, size > 50 KB). If no PDF is obtainable (paywalled / non-arXiv), continue from the abstract + Semantic Scholar and skip figure extraction (note this in the report).
4. **Fetch metadata + citation graph.** From Semantic Scholar `/paper/<id>`: authors, year, venue, `citationCount`, `publicationDate`, `references`, `citations` (fall back to OpenAlex). Keep all of it — `publicationDate` is the `date` fallback for non-arXiv papers.
5. **Slug.** Generate it if not already set.
6. **Extract figures.** `python scripts/extract_figures.py /tmp/paper.pdf figs/` — auto-detects every `Figure N:` and writes tight PNGs. You then choose which figures actually belong in the page.
7. **Write the explainer.** Read the PDF (text + figures) and fill `templates/explainer.html` → `public/papers/<slug>.html`, per the explainer contract: write each section in your own words at expert depth, place the relevant real figures, quote exact numbers, and write the critique. Run `python scripts/inject_figures.py` to base64-inline the chosen figures. Verify the result is self-contained (no `{{FIG}}` placeholders remain; no external scripts but fonts).
8. **Update the graph (`data/papers.json`).** Add this paper's node (slug, short label, title, authors, year, `date`, venue, citation_count, topic, author_group, abstract, explainer path). Set `date` to `"YYYY-MM"` (placed right after `year`) from the arXiv id you already resolved (`2510.xxxxx` → `"2025-10"`); it drives the timeline's quarter bands. For a non-arXiv paper, use the S2 `publicationDate` month, else `"<year>-07"` (mid-year). (To backfill a node that's missing it, `python scripts/backfill_dates.py` re-derives every node's `date` from its explainer's `source` link.) Judge `topic` from the abstract (Benchmarks & Evals / Post-training & RL / Reasoning / Agents / Safety & Red-teaming / …) and set `author_group`. Add **edges**: for every reference that is already a node (match by arxiv_id/doi/title) add `{from: <this slug>, to: <ref slug>}`; for every existing node whose paper this one's `citations` list shows citing it, add the reverse edge. Write the file deterministically (stable key order) for clean diffs.
   - **Tag for surveys.** Check each survey in `data/surveys.json`: if this paper is a *core member* by that survey's `description` rubric, add its id to the node's `tags` (e.g. a core benchmark paper → `tags: ["benchmarks"]`). Be strict — a paper that merely *uses/reports* a benchmark is not a core benchmark paper (models, training methods, agent frameworks: no); tag only when the benchmark/eval is the paper's headline contribution. Most papers qualify for **none** (no `tags` key). Easiest is `python scripts/tag_papers.py add <survey_id> <slug>` once the node exists (it validates the id + slug and preserves formatting); or write the `tags` field directly as the last key, inline. State which surveys (if any) you tagged and why.
9. **Grow the queue.** From this paper's references/citations, pick the most important papers **not already** in `papers.json` or `queue.json` (dedupe by arxiv_id/doi/title), ranked by citation count and by how many existing nodes cite them. List the top ~5 with one-line reasons and append them to `data/queue.json` (`source: "Cited by <this slug>"`).
10. **Remove the processed paper** from `data/queue.json`.
11. **Verify it actually renders — desktop *and* mobile.** A clean `papers.json` does **not** guarantee the map shows the node — the render is the source of truth. Run `npm run build` (must succeed) and load the site (`npm run dev`, or drive it with the browser tools): confirm the **new node appears on the map in its publication-quarter column** (the timeline places it by `date`, so a wrong/missing `date` lands it in the wrong column or — only as a `year` fallback — mid-year), that **hovering it brightens its citation edges**, and that its **explainer page loads** self-contained. Pay special attention to UI state transitions you don't normally exercise (e.g. the empty→first-paper case, or a `date` that opens a brand-new quarter band on the time axis). **Then check the explainer at a phone width (≈375px):** it must not scroll **horizontally** — the quickest signal is `document.documentElement.scrollWidth <= clientWidth` (anything wider means a child is overflowing; tables and the `.verdict` grid are the usual culprits — see the mobile contract above); the index map itself should also not cause sideways document scroll (it pans internally). If the node is missing/mis-placed or a page overflows sideways despite correct data, it's a site bug — fix it (and note the fix in the report). Also run `python3 scripts/lint_pages.py <slug>` — it checks the new page against its node (citation-count sync, H1-matches-canonical-title, as-of date format, unescaped entities) and must exit 0; `--fix` applies the mechanical corrections.
12. **Report.** "Built `papers/<slug>.html`; added 1 node + N edges; tagged for <surveys or none>; queued M new papers; removed 1 from the queue; verified it renders (desktop + mobile, no sideways scroll)." Then remind me to `npm run dev` and commit.

**Opt-in — podcast episode (only when asked; never automatic).** Producing an episode is expensive (a large LLM script pass + ~18 min TTS render), so it is **per-paper opt-in** and is **never** triggered while processing the queue. This is also the whole of the standalone "make the podcast for `<slug>`" command. The paper must already be a node (do Procedure A first). Then:
1. **Produce it in the separate podcast repo.** `cd ~/Documents/Projects/darvinyi-podcast` and run the user-level `litsearch-podcast` skill for the slug. It reads **this** repo's `public/papers/<slug>.html` (its `litsearch.repo`/`content_hint` point here) plus the paper PDF, writes a 3-voice script to `scripts/<slug>.md`, renders the MP3 with Kokoro, publishes it to the NAS, and rebuilds the RSS feed. Integration is via the shared slug **only** — never merge the podcast repo into this one.
2. **Confirm the MP3 is live:** `curl -sI https://pod.darvinyi.com/audio/<slug>.mp3` → `200`.
3. **Link it:** `python scripts/inject_podcast.py --set <slug>` — stamps the node's canonical `audio_url` in `data/papers.json` (deterministic write) **and** injects the on-page `listen ♪` pill + `<audio>` player into the explainer.
4. **Verify the player renders** (desktop + phone ≈375px, no sideways scroll): the `<audio>` control appears under the dek, the pill is in the hero, and both point at the live MP3. To backfill/refresh many pages at once: `python scripts/inject_podcast.py --all`. To undo: `python scripts/inject_podcast.py --remove <slug>`.
5. **Report** the episode URL alongside the usual summary; remind me to review and commit. Never auto-commit/deploy.

---

## Procedure B — Add to the queue

Input is a phrase **X**. First classify it:
- **A specific paper** — "GDPval", "RLI", "SWE-Bench Pro", or a full title.
- **An author** — "all papers by John Smith".
- **An organization** — "all papers from Scale AI".
- **A topic** — "papers on rubric-based evaluation".

1. **Resolve candidates.**
   - *Specific paper:* search Semantic Scholar + web for the name/abbreviation; take the best title match. If two readings are plausible (e.g., a common acronym), ask which. Pull arxiv_id, authors, year, venue, citationCount.
   - *Author:* Semantic Scholar author search → that author's papers (or OpenAlex). If the list is large, confirm scope first (e.g., "first/last-authored only?" or a year cutoff).
   - *Organization:* OpenAlex institution search, or the org's own papers page when it has one (for Scale AI, `https://labs.scale.com/papers`). For big sets, confirm before adding all.
   - *Topic:* web + Semantic Scholar search; rank by citation count and relevance; propose the top set.
2. **Dedupe.** Drop any candidate already in `data/papers.json` (already an explainer) or `data/queue.json` (already queued), matching on arxiv_id / doi / title.
3. **Confirm if large.** A single clear paper: just add it. An author/org/topic returning many: show the list (title · authors · year · citations) and confirm before adding, or let me cap or filter.
4. **Append** each to `data/queue.json` with: title, arxiv_id, doi, authors, year, venue, citation_count, `source` (how it was found — e.g., "Author: John Smith" / "Org: Scale AI" / "Lit search: rubric eval"), and `priority`/`why` if obvious. Capture `arxiv_id` accurately — Procedure A derives the node's timeline `date` (month precision) from it.
5. **Report** what was added and the new queue length, and remind me to commit (`data/queue.json` changed).

---

## Procedure C — Audit the graph

Reconcile `data/papers.json` against reality: every citation **between papers already in the graph** should be an edge, and every node's `citation_count` should be current. This adds **no new nodes** and writes **no explainers** — it only fixes edges and counts among existing nodes. (To find *new* papers to cover, that's Procedure B.)

1. **Load the graph.** Read `data/papers.json`. List the nodes (slug · title · arxiv_id/doi) and note the current edge count. If there are no nodes, say so and stop. Build a lookup from arxiv_id / doi / normalized-title → slug so references and citations can be matched back to nodes.
2. **Refresh each node's metadata + citation graph.** For every node, query Semantic Scholar `/paper/<id>` (fall back to OpenAlex) for the current `citationCount`, plus its `references` and `citations`. Cache each result — you'll need both directions. If a node can't be resolved, note it and keep its existing values rather than zeroing them.
3. **Rebuild the expected edge set.** For every **ordered pair** of existing nodes (A, B): an edge `A → B` belongs in the graph if A's `references` include B **or** B's `citations` include A (match by arxiv_id/doi/title). Union both directions so an edge is caught even when only one paper's API record lists the link. This expected set is what the graph *should* contain.
4. **Diff against the current edges.**
   - **Missing edges** (expected but not present) → add them. These are the main point of the audit — citations that were not caught when each paper was first processed.
   - **Duplicate edges** (same from/to listed more than once) → collapse to one.
   - **Dangling edges** (an endpoint slug no longer exists) → remove them.
   - Do **not** remove a real edge just because one API call now omits it; only drop edges that are dangling or duplicated. If an edge looks genuinely wrong (e.g., direction reversed), flag it in the report rather than silently deleting.
5. **Update citation counts.** Set each node's `citation_count` to the refreshed value. If a count changed a lot, it's worth a line in the report. Leave a node untouched if it couldn't be resolved in step 2.
6. **Write `data/papers.json` deterministically** (stable key order, edges sorted) so the diff is reviewable. Don't touch `slug`, `short`, `date`, `explainer`, `tags`, or prose fields (`abstract`, `topic`, `author_group`) — those are owned by Procedures A/D. (If the audit surfaces a node with **no `date`**, that's the one exception: run `python scripts/backfill_dates.py` to give it one so it leaves the mid-year fallback column.)
7. **Verify it renders.** Run `npm run build` (must succeed) and load the site (`npm run dev`, or the browser tools): confirm the timeline map still renders and the **new connections actually appear** — hover a node whose degree changed and check its citation edges light up as expected. The render is the source of truth — a clean JSON diff isn't enough.
8. **Report.** "Audited N nodes; added E edges, removed D dangling/duplicate; refreshed C citation counts; verified it renders." Call out any nodes that couldn't be resolved and any edges you flagged but didn't change. Then remind me to `npm run dev` and commit (`data/papers.json` changed).

---

## Procedure D — Tag for a survey

A **survey** is a named tag (`data/surveys.json`); membership lives in each node's `tags` array and drives the topbar `survey` spine. This procedure writes **only** `tags` (and, when creating a survey, `data/surveys.json`) — it adds **no nodes** and writes **no explainers**. Three shapes of request:
- **Tag specific papers** — "tag SWE-Bench Pro as a benchmark", "mark these as benchmark papers" (a slug/title list).
- **(Re)tag the whole graph** for a survey — "re-tag the graph for benchmarks", "find every benchmark paper" — classify every existing node against the rubric.
- **Create a new survey** — "create a survey called Agents", then (usually) tag for it.

0. **Know the rubric.** Read the target survey's `description` in `data/surveys.json` — that *is* the membership test. For **benchmarks**: a paper's **primary contribution** is a benchmark / eval dataset / eval suite / agent-evaluation environment that a survey would cite as a *named entry*; models, training/RL methods, reasoning techniques, agent frameworks, training datasets, and analysis/metric papers that merely **use** benchmarks are **out** (a "benchmark + method" paper is in only if the benchmark is a first-class named contribution). If **creating** a survey, add it to `data/surveys.json` first — unique lowercase `id`, `label`, a `color` distinct from the teal selection accent, and a sharp `description` that states what makes a paper a core member — then proceed.
1. **Resolve the papers.**
   - *Specific papers:* match each name/title to a node slug (the slug is the id; confirm ambiguous matches). Tagging applies only to **existing nodes** — if a paper isn't a node yet, queue it via Procedure B instead of tagging.
   - *Whole-graph (re)tag:* classify every node against the rubric from its `title` + `abstract` (read the explainer/PDF when borderline). Be strict and **adversarially double-check the YES set** — the cheap failure is tagging a model/method/framework that merely names a benchmark. For a job this size, fan out (one classifier per ~20-node batch → a skeptical verify pass over the YES set → a completeness sweep over the NO set); a single pass both over-tags the borderline and misses the long tail.
2. **Apply the tags** with the tool, so `papers.json` formatting stays canonical:
   - `python scripts/tag_papers.py add <survey_id> <slug> [<slug> …]` — or pipe slugs: `… | python scripts/tag_papers.py add <survey_id> -`.
   - `python scripts/tag_papers.py remove <survey_id> <slug> …` to untag; `list <survey_id>` / `surveys` to inspect.
   It validates the survey id + every slug, keeps `tags` sorted & de-duplicated, drops the key when a paper has none left, and rewrites the file in its exact style.
3. **Show the result for review.** List what you tagged (and untagged) with a one-line reason each, and **call out the borderline calls** you included/excluded so I can overrule them. For a whole-graph retag, give the count and the notable judgment calls.
4. **Verify it renders.** `npm run build` (must succeed), then load the site and pick the survey in the topbar `survey` dropdown: confirm the tagged papers form the **centred spine**, ringed in the survey colour, with the rest of the map unchanged (no dimming), that hovering/selecting still works on top of it, and that there's no sideways document scroll at ≈375px. The render is the source of truth.
5. **Report.** "Tagged N papers for `<survey>` (M total); verified the spine renders (desktop + mobile)." Remind me to `npm run dev` and commit (`data/papers.json`, plus `data/surveys.json` if a survey was added).

---

## Conventions
- Keep the identifier and slug consistent across the queue, the explainer filename, and the graph node.
- Citation counts drift; they're refreshed whenever a paper is processed, and a page may note "as of <date>".
- Write `data/*.json` deterministically (stable key order) so commits stay readable.
- The rendered map is the source of truth, not the JSON — always confirm a new node actually appears (in its publication-quarter column) before calling a run done (Procedure A, step 11).
- The map is a **timeline**: every node needs a `date` (`"YYYY-MM"`) to sit in the right quarter column — `scripts/backfill_dates.py` re-derives it from each explainer's hero `source` link, so keep that link canonical. Node size is **capped** in `src/main.js`. The layout (`src/timeline.js`), the time-axis overlay (`#axis` in `index.html` + `src/style.css`), and the renderer/hover (`src/main.js`) move together: if you change one — band granularity (quarter↔half), column spacing, the size cap, edge dimming — keep the others and this file in sync.
- **`date` vs `year`, by design.** `date` is the arXiv **preprint** month (what places the node in the timeline); `year` is the paper's own displayed publication year (what the side panel's kick line shows), and the two can legitimately differ when a paper's venue appearance postdates its arXiv posting — e.g. a paper posted in `2018-10` (`date`) that appeared at a `2019` conference (`year`). A handful of nodes show this gap (BERT, T5, Med-PaLM, MMMU, MathVista, ILSVRC, CIDEr, MRBench among them); that's expected, not a data bug — don't "fix" a node's `date` to match its `year` or vice versa. If a node's `date` and `year` disagree by more than a few months, sanity-check it once (arXiv id vs `year`), but a one-quarter or one-year gap from a slow conference cycle is normal.
- Every explainer must be mobile-safe (no horizontal scroll at ≤640px). The mobile rules live in `templates/explainer.html`'s `@media(max-width:640px)` block, mirrored identically across all `public/papers/*.html`; build new pages from the template and keep that block in sync if you ever touch it (see the explainer page contract). The index map must likewise not cause sideways **document** scroll on a phone (it pans/zooms internally; the axis collapses to year-only labels under 640px).
- **Surveys** are tags, not a second graph: definitions in `data/surveys.json`, membership in each node's `tags`, the spine logic in `src/timeline.js` (`centerSet`) + `src/main.js` (the `applySurvey` block + the `node.survey` ring style + the `?survey=<id>` deep-link read at dropdown init) + the `#survey` dropdown in `index.html` + `.surveyby`/`.surveycap` (incl. the `.rd` "read →" pill for surveys with a `page`) in `src/style.css`. These move together — if you change the survey-spine behaviour, keep them and this file in sync. The spine is deliberately minimal: it centres + rings the tagged nodes and changes nothing else (no dimming, no edge colouring). Always mutate `tags` through `scripts/tag_papers.py` (canonical formatting); pick `color`s distinct from the teal selection accent so a survey ring never reads as a selection. Tagging is part of Procedure A (step 8) — don't let a new core benchmark paper land untagged.
- **Podcast is opt-in, expensive, and lives in a separate repo.** A paper's explainer can link to a podcast episode via the optional node field `audio_url` (`https://pod.darvinyi.com/audio/<slug>.mp3`); the on-page `listen ♪` pill + `<audio>` player are owned by `scripts/inject_podcast.py` (never hand-edit them). The episode itself is built in `~/Documents/Projects/darvinyi-podcast` (the user-level `litsearch-podcast` skill), integrated here **through the shared slug only** — never merge the repos, and never generate episodes automatically for the queue (it's an opt-in step in Procedure A).
- Never auto-commit, push, or deploy — finish each run with a summary and "review and commit when ready."
