# Critique: Paper Atlas (darvinyi-litsearch)

2026-07-18 · `c40de97` · reviewed by Claude (Fable 5) via repo-critique · workspace: `.critique/`

## Verdict

Paper Atlas is trying to be three things at once — a citation-timeline map that renders correctly everywhere, a corpus of 277 expert paper explainers whose numbers are real, and two survey write-ups good enough to grow into publishable surveys — and it is much closer than most solo projects get. The data layer is close to immaculate (zero duplicate slugs, zero dangling edges, perfect node↔page bijection across 277 files), the explainer corpus survived a 12-reviewer adversarial sweep with only two genuine numeric defects, and the Evaluations survey's reward-readiness axis is a real intellectual contribution with mechanically verified citation claims. What holds it back is not quality but three specific gaps: **the flagship survey interaction is invisible at the zoom the site itself sets** (plus two viewport bugs that can leave the map blank or cropped), **the two surveys cite instruments the atlas has never ingested** (τ-bench, RewardBench, JudgeBench, FrontierMath and the entire prior-work shelf — the first things a referee would check), and **the 1,052-item queue has stopped functioning as a roadmap** (its head is twelve legacy computer-vision papers; priority is null or "High" for 78% of entries). One survey also ships a factual cross-check its own embedded data refutes, and the other admits 6 of its 7 facets were classified in a single LLM pass. All of this is fixable in weeks, and the foundation — pipeline discipline, honest method sections, per-paper taxonomy reasoning — is unusually worth building on.

## Scorecard

| Dimension | Score /10 | One-line justification |
|---|---|---|
| Data integrity | 9 | check_data.py found zero structural defects across 277 nodes / 2,920 edges / 1,052 queue rows; only 6 suspect edge directions and 8 date/year mismatches. |
| Explainer accuracy | 8 | 12-batch adversarial sweep: 2 real numeric defects (M-07, m-13) in 277 pages; critiques uniformly paper-specific; internal table math verified on ~40 pages. |
| Survey scholarship | 7 | Reward-readiness axis is novel and well-argued; citation/gravity claims verified mechanically to the digit; but one refuted cross-check (M-04), one single-pass taxonomy (M-05), one shoehorned placement (m-16). |
| Coverage / completeness | 5 | The corpus is deep 2023–26 but the surveys' own named instruments and the 2026 model-card canon are absent or buried in the queue (M-08); long-context, judge-audit, and statistical-rigor families have holes. |
| Site correctness | 6 | Build clean and the happy path is excellent, but three real rendering bugs: init-fit race (M-03), minZoom clamp (M-02), invisible survey activation (M-01). |
| Mobile | 8 | No horizontal document scroll anywhere at 375px (verified on all four page types); the debt is fixed-width survey charts (m-11) and the clamp-limited initial map view. |
| Process & tooling | 4 | The queue is dead as a prioritizer (M-09), the actual headless loop has zero gates while the gated loop belongs to another repo (M-11), and mutating scripts write non-atomically. |
| Testing | 3 | Zero tests, zero CI, on 145 lines of layout math and scripts that rewrite the single source of truth (M-12). |
| Documentation consistency | 6 | CLAUDE.md is an excellent operating contract, but it documents a node-size rule the code abandoned (M-10) and two stale "dimming" comments contradict the shipped behavior. |
| Accessibility / meta | 5 | Canvas map has no keyboard path, legend is click-only divs, and there is not one OG tag on a 280-page public site (m-10). |

## What genuinely works

Calibrate trust with these, all verified: the canonical key order, inline-tags formatting, and edge hygiene of `data/papers.json` are byte-consistent across 277 nodes (`.critique/check_data.out`); every explainer has all six contract sections, ≥3,100 words, real figures (one deliberate exception), zero leftover placeholders, zero external scripts (`check_pages.out`); the hero `source ↗` link is a canonical arXiv `abs` URL on 266/277 pages and the 11 exceptions are genuinely non-arXiv papers; the survey pages' mechanical claims — 598 and 161 in-corpus edges, HumanEval 43/17, APPS 12, MT-Bench 15 gravity counts, kingdom/family sums, the 28-paper tag overlap, 25 meta-evals — all reproduce exactly; both taxonomy JSONs are in perfect bijection with the tags and carry per-paper `placement_reason` prose of real quality; and several explainers (FORTRESS, LegalBench-RAG) catch arithmetic errors in their *source papers*. The selection/panel/hover flow on the map is genuinely excellent.

## Findings

### Blockers

None. Nothing ships broken on the common path; the worst defects below are Major by the ladder's definition, and inflating them would be noise.

### Major

**M-01 · Selecting a survey produces almost no visible change at the zoom the site itself sets** — `src/main.js:192` (ring `border-width: 4`), `applySurvey` post-animation fit
Evidence: ring renders 4px × zoom = 0.64px at the 0.16 fit zoom applySurvey ends on; node labels are hidden below `min-zoomed-font-size: 7`. Before/after screenshots of selecting Benchmarks are near-identical except the dropdown. Rings are legible only ≥~0.4 zoom (verified at 0.55).
Why: the survey spine is the flagship feature and the landing state of every `/?survey=` deep link from the survey pages; its activation currently reads as "nothing happened." → R-03.

**M-02 · `minZoom: 0.16` exceeds the zoom needed to fit the timeline; the full map can never fit, and phones land on an arbitrary mid-window** — `src/main.js:175`; layout bbox measured 8,436×1,707
Evidence: fit needs ≈0.135 at 1280px (manual fit clamps to exactly 0.16; 268/277 nodes visible); at 375px fit needs ≈0.044, so a phone shows ~28% of the timeline (screenshot: opens on 2019–2022; BLEU and 2025-26 both off-screen). → R-02.

**M-03 · Initial `cy.fit()` silently no-ops when the container is 0-sized, and nothing ever re-fits** — `src/main.js:421`
Evidence: reproduced live — a load while the window reports zero size (background tab, embedded view) leaves zoom=1/pan={0,0}: one node (BLEU) in a corner, 7/277 visible; `cy.on('pan zoom resize', placeAxis)` only moves the axis. → R-01.

**M-04 · Benchmarks survey claims its pre-2021 cohort "reproduces almost exactly" an external ~50% saturation figure; its own data says 82%** — `public/surveys/benchmarks.html` prior-work section
Evidence: linked study (arXiv 2602.16763, 60 benchmarks) verified: "nearly half … exhibit saturation." Corpus computed: year≤2020 → 14/17 saturated (82%); ≤2021 → 71%; whole corpus → 25%. No cut lands near half. → R-04.

**M-05 · Evaluations survey shipped with 6 of 7 facets single-pass classified — and the one facet that was re-audited needed 7/59 corrections** — `public/surveys/evaluations.html` method section
Evidence: page text: "A planned second independent pass was largely lost to a rate-limit event; in its place … reward-readiness … was re-audited in full … corrected 7 of 59 labels." A ~12% correction rate is the best available estimate of single-pass error on the other six facets, which drive findings 01–07. The Benchmarks page's dual-pass protocol (94.8% agreement) is the house standard. → R-07.

**M-06 · `topic` is unreliable on a visible slice of nodes — "Reasoning" is a catch-all, with at least one outright wrong label** — `data/papers.json`
Evidence: shoeybi-2019-megatron-lm topic="Reasoning" (tensor-parallel training infra); levine-2025-rebel page shows "RAG / Reranking" vs node "Reasoning"; simclr/palm/flashattention/gsm8k/graphrag/moco/s4 all "Reasoning". Topic drives the map's default color dimension. → R-06.

**M-07 · Self-consistency explainer's headline deltas contradict its own table** — `public/papers/wang-2022-self-consistency.html`
Evidence: prose "+17.9, +12.2, +11.0, +6.4, +3.9"; adjacent table computes +17.9, +12.5, +7.6, +6.3, +3.5. The contract's core promise is "quote exact numbers." → R-05.

**M-08 · The surveys cite instruments the atlas has never ingested, and the 2026 canon is absent or buried** — both survey pages, `data/queue.json`
Evidence: named in survey prose but not nodes: τ-bench (queue pos 17), RewardBench (73), JudgeBench (616), FrontierMath (201); prior-work shelves largely un-ingested (BetterBench q445, Chang q500, Yehudai q389, Kapoor q48; McIntosh/Bean/Cao/Gu/Li/Jacobs&Wallach/Tangled-up-in-BLEU missing entirely); 2026 model-card canon split queued-buried (WebArena 25, GAIA 18, RE-Bench 23, LiveBench 30, MMMU-Pro 617, RULER 667) / missing (BFCL, SuperGPQA, BBEH, HELMET, NoLiMa, Video-MME, MedQA, Leaderboard Illusion, Elo Uncovered, Miller error-bars). Full classification: `.critique/lit-gaps.md` + `canon_diff.out`. → R-08/R-09/R-10.

**M-09 · The queue is dead as a prioritization instrument** — `data/queue.json`, CLAUDE.md Procedure A step 1
Evidence: head = 12 legacy CV papers (GlideNet, Cityscapes attributes, dermatology, OCR), all priority:null; distribution null=437/High=383/Medium=225/Low=7; ≤2022 entries = 439. claude_loop.sh compensates with a prompt ("Prioritize papers about Benchmarks & Evals"), proving the file's order isn't trusted. → R-08.

**M-10 · CLAUDE.md/README/in-file comments document a node-size rule the code no longer uses** — `src/main.js:11,135`, CLAUDE.md, README.md:51
Evidence: docs say "sqrt(citation_count), capped"; code is `12 + 14·log10(c+1)`. CLAUDE.md is the operating contract the agent follows every run. → R-18.

**M-11 · The headless loop that actually runs this repo has zero gates** — `claude_loop.sh` (tracked); contrast `runqueue.sh` (untracked, wrong repo)
Evidence: 1000 iterations of `claude -p … --dangerously-skip-permissions` with no build check, no stop-on-nonzero-exit, no dirty-tree guard, no timeout; runqueue.sh has all four gates but preflights on `prompts/queue.md`, which doesn't exist here. → R-13.

**M-12 · Zero automated tests, zero CI** — repo-wide
Evidence: no test files; package.json scripts = dev/build/preview. Scariest untested modules: `tag_papers.py` (rewrites papers.json wholesale), `timeline.js` (layout + spine pack), `backfill_dates.py` (regex surgery on papers.json). → R-24.

### Minor

**m-01 · 6 edges where the citing paper predates the cited by >3 months** — `data/papers.json`; e.g. phan-2025-hle→arora-2025-healthbench (2025-01→2025-05); likely reversed or revision-era. → R-12.
**m-02 · 12 mutual-citation pairs (A→B and B→A)** — spot-verify the implausible ones. → R-12.
**m-03 · 8 nodes where `date` year ≠ `year`** — legitimate preprint-vs-venue tension, but the axis label contradicts the node's year; needs a stated policy. → R-23.
**m-04 · 28 queue entries lack both arxiv_id and doi** — resolve-or-drop pass. → R-08.
**m-05 · Non-atomic writes to papers.json** — `tag_papers.py:107`, `backfill_dates.py:95`; truncate-then-write, no temp+rename. → R-20.
**m-06 · `svgcharts.py` is an identical 121-line copy in both survey builders** — will drift. → R-19.
**m-07 · `runqueue.sh` is untracked cruft from a different repo family** — remove or adapt. → R-13.
**m-08 · Two stale comments still describe survey dimming removed in e4a4325** — `src/main.js:27-30`, `src/style.css:30-31`. → R-18.
**m-09 · 33 explainers carry a whitespace-minified copy of the mobile media block** — semantically identical CSS, but the documented find/replace sync mechanism now misses them (slugs in `check_pages.out`). → R-14.
**m-10 · No OG/social meta anywhere; map a11y gaps** — 0 `og:` tags across 280 pages; legend rows are click-only divs; panel ref links unfocusable. → R-15.
**m-11 · Survey-page charts are fixed 640px SVGs — a phone shows ~52% in an unlabeled scroll box** — measured at 375px. → R-16.
**m-12 · Axis labels collide into mush in the sparse region at fit zoom** — "4 2005 2009 2014 Q2Q3…"; no zoom-dependent thinning. → R-17.
**m-13 · VeRO explainer computes "+8" against a different baseline than the sentence names** — 0.61−0.50=11; deltas are vs the 0.53 row. → R-05.
**m-14 · Page↔node drift class: hand-typed hero facts with no reconciliation pass** — citation drifts (mt-bench 9,197/9,198; swe-bench 2,596/2,597; browsecomp 439/440; akyurek 0/16 — the real one), "as of" format zoo (5+ formats), lexglue's on-page year self-contradiction (kicker "2021 · ACL" vs chip "ACL 2022"), 4 truncated/paraphrased H1 titles (researchqa, evalplus, mcp-universe, mrbench), spreadsheetbench's unexpanded byline, one unescaped `&` (si-2024), venue strings with/without year, questbench venue stale in JSON. → R-11.
**m-15 · fabbri-2025-multinrc has zero figures** — 27.8KB page vs 130KB+ siblings; contract says "the paper's real figures"; confirm editorial choice or extract. → R-11.
**m-16 · GDPval mis-housed in the evaluations tree's "fairness & harm audits" family** — its own placement_reason concedes it's a capability instrument placed by proximity. → R-22.
**m-17 · Two survey-page audit citations are quoted more precisely than their sources' abstracts support** — "22 of 23" (McIntosh) and "7 of 10 … unsound graders" (ABC) are not in the abstracts (ABC's own explainer says "holes in every one" of ten); verify from the PDFs or soften. → R-04.
**m-18 · Bundle is a single 933 kB JS chunk (282 kB gzip)** — cytoscape; fine for now, note only. No task.
**m-19 · Queue staleness: 439 entries ≤2022** — archive candidates. → R-08.

### Nits

One rolled-up list: `timeline.js` exports `timeOf()` nothing imports · `INST_WEIGHT` default 50 outranks listed tier-40 orgs (METR) in attribution · `design/prototype.html` stale CDN prototype at repo root · unescaped `<` in "open (<60%)" legend text (benchmarks page) · "59−3 of 59" phrasing on evaluations method section · cytoscape wheel-sensitivity console warning on every load · `.critique/`-adjacent: `npm install` warns about unapproved fsevents install script · hint text says "hover a node" on touch devices.

## Claim verification

| # | Claim (quoted) | Location | Verdict | Source | Note |
|---|---|---|---|---|---|
| 1 | "roughly half of all benchmarks saturated" (external study) | benchmarks page | CONFIRMED | arXiv 2602.16763 abstract | but the "reproduces almost exactly" cohort claim is REFUTED by own data (82%) → M-04 |
| 2 | "GSM1k measured up to 8-point inflation" | benchmarks page | CONFIRMED | final PDF via atlas explainer (worst 8.0, Yi-6B) | v1 abstract said 13%; camera-ready is 8 |
| 3 | "Engstrom … roughly two-thirds of it was artifact" | connection 01 | CONFIRMED | PMLR 119: 11.7% → 3.6% unexplained | ≈69% |
| 4 | "Bean et al. (2025) … 445 benchmarks" | benchmarks page | CONFIRMED | arXiv 2511.04703 | 29 expert reviewers |
| 5 | "McIntosh … 22 of 23" | benchmarks page | PLAUSIBLE | abstract says 23 assessed, no count | verify from body or soften → m-17 |
| 6 | "ABC: 7 of 10 … unsound graders" | both pages | PLAUSIBLE | abstract + own explainer ("holes in every one") | verify grader-specific subset → m-17 |
| 7 | "BetterBench … 24 benchmarks on 46 criteria" | benchmarks page | CONFIRMED | paper (memory, high confidence) | |
| 8 | "METR … ~7-month doubling" | both pages | CONFIRMED | arXiv 2503.14499 | |
| 9 | "MT-Bench 85% judge-human (humans 81%)" | both pages | CONFIRMED | MT-Bench paper | |
| 10 | "EvalPlus 80× tests; up to ~29% wrong" | both pages | CONFIRMED | EvalPlus paper (28.9%) | |
| 11 | "SWE-bench Pro ~25–30-pt public→commercial collapse" | connection 07 | CONFIRMED | own explainer: 23–44% → 9–18% | |
| 12 | "598 edges among the 126" / "161 among the 59" / gravity counts | both pages | CONFIRMED | recomputed from papers.json | exact |
| 13 | "25 of 59 (42%) are meta-evaluations" | evaluations page | CONFIRMED | meta_eval flags in taxonomy | |
| 14 | Rubric Reward Hacking 39→65% / 78% | evaluations page | NOT INDEPENDENTLY CHECKED | 2026 paper post-cutoff; internally consistent per batch review | flag for PDF check in R-04 |

## Comparative analysis

Against the graph tools (Connected Papers, Litmaps, ResearchRabbit, Inciteful): they win on corpus breadth, search, and zero-maintenance freshness; Paper Atlas wins on everything they cannot do — a hand-written expert critique behind every node, a timeline layout that encodes publication order, and survey overlays with real taxonomies. None of them has an answer to the "does it hold up?" section; that layer is the defensible 20%. Against benchmark trackers (Epoch AI's Benchmarking Hub, HELM, llm-stats-style aggregators): they win on live scores and model coverage; the atlas's survey pages win on methodology analysis — nothing public crosses facet classification × era trends × citation-mined connection stories. Against the academic survey PDFs the pages themselves cite (Chang, Guo, the judge surveys, BetterBench): those are static, uncorpused, and unlinked; the atlas's pages are the only ones where every claim is one click from a full explainer and the classification data regenerates from source. The honest weakness in the comparison: every alternative covers more ground, and the atlas's authority depends on its curation being *visibly complete* for its chosen scope — which is exactly what M-08 currently undercuts. (Confidence note: comparison drawn from working knowledge, not a fresh audit of each tool.)

## Remediation plan

Execute top-to-bottom within each wave; Wave 1 before Wave 2 before Wave 3. Every task is self-contained. Workspace evidence lives in `.critique/` (gitignored). **Never auto-commit/push/deploy; end each session with a summary for review.**

### Wave 1 — site correctness & survey-content accuracy

### R-01 · One-shot refit when the map initializes unsized  [S] deps: —
Files: `src/main.js`
Current: `cy.ready(() => { cy.fit(undefined, 70); placeAxis(); })` (line ~421) no-ops if the container measures 0×0 (background tab/embedded load); map stays at zoom 1 on a corner forever (M-03).
Desired: if `cy.width()===0 || cy.height()===0` at ready time, register a one-shot `cy.on('resize')` handler that calls `cy.resize(); cy.fit(undefined, 70); placeAxis()` on the first non-zero size, then de-registers. Do not refit after the user has interacted.
Change sketch: wrap the existing fit in `const fitNow = () => {…}`; in ready: `if (!cy.width() || !cy.height()) { const h = () => { if (cy.width() && cy.height()) { cy.off('resize', h); fitNow(); } }; cy.on('resize', h); } else fitNow();`
Accept: dev server; in a desktop browser run `window.dispatchEvent(new Event('resize'))` after loading the page in a background tab, foreground it → map is fitted (≥260 nodes visible via the console check in `.critique/code-review.md`). Normal foreground load unchanged.

### R-02 · Derive minZoom from the layout so fit can always fit  [S] deps: —
Files: `src/main.js`
Current: `minZoom: .16` hardcoded (line ~175); needed fit zoom is 0.135 @1280px and 0.044 @375px, so fit clamps and crops (M-02).
Desired: after computing `positions`, compute the bbox fit zoom for the actual container (or simply set `minZoom` post-init: `cy.minZoom(Math.min(0.16, cyFitZoomForBbox * 0.9))`); full timeline fits on desktop and phone.
Change sketch: after `cy.ready` fit, read `cy.zoom()`; if it equals `cy.minZoom()`, lower minZoom to `fitZoom*0.9` (compute fitZoom = min((w-140)/bb.w, (h-140)/bb.h) from `cy.elements().boundingBox()`) and re-fit.
Accept: at 1280×720 after load, `cy.nodes().filter(visible).length === 277`; at 375×812 the whole timeline (BLEU through 2026) is on screen after load.

### R-03 · Make survey activation visible at fit zoom  [M] deps: R-02
Files: `src/main.js` (style block + `applySurvey`)
Current: 4px ring ≈ 0.64 rendered px at fit zoom; labels hidden; activation invisible (M-01).
Desired: the ringed subset is unmistakable at any zoom.
Change sketch (pick 1–2): (a) make ring width zoom-compensated via a style function, e.g. `'border-width': ele => Math.max(4, 3/cy.zoom())` (cap ~24 so close zoom isn't absurd); (b) additionally dim non-members slightly ONLY if product owner agrees (conflicts with the "no dimming" doctrine in CLAUDE.md — do not do this without approval); (c) have `applySurvey` fit to the tagged subset + padding (`cy.fit(cy.$('node.survey'), 60)`) instead of the whole graph, so rings land at legible zoom. Recommended: (a)+(c). Update the CLAUDE.md survey-conventions paragraph if behavior changes.
Accept: select Benchmarks at default desktop view → screenshot visibly differs from no-survey state (rings clearly visible without manual zoom); `/?survey=evaluations` deep link lands with visible rings; deselect restores exactly.

### R-04 · Fix the saturation cross-check sentence + verify the two soft audit citations  [S] deps: —
Files: `scripts/benchmarks_survey/` (builder or template — find the sentence; **never hand-edit `public/surveys/benchmarks.html`**), then rebuild.
Current: "…finds roughly half of all benchmarks saturated — a number this corpus reproduces almost exactly for its pre-2021 cohort." Own data: 82% (M-04). Also "22 of 23" (McIntosh) and "7 of 10 unsound graders" (ABC) exceed abstract support (m-17); and claim 14 (Rubric Reward Hacking 39→65/78) is unverified externally.
Desired: a true sentence — e.g. "…finds roughly half of all benchmarks saturated; in this corpus the effect is starker: 82% of the pre-2021 cohort is saturated against 25% overall — saturation concentrates in exactly the short-horizon strata findings 03/07 describe." Verify or soften the McIntosh/ABC counts against their PDFs (download, grep the tables); spot-check Rubric Reward Hacking's 39%/65%/78% against its PDF.
Accept: `python scripts/benchmarks_survey/build_survey_page.py` succeeds; rebuilt page contains the corrected sentence and no longer contains "reproduces almost exactly"; McIntosh/ABC sentences match what their PDFs actually say (quote them in the commit message); `grep -c 'reproduces almost exactly' public/surveys/benchmarks.html` → 0.

### R-05 · Fix the two numeric-defect explainers  [S] deps: —
Files: `public/papers/wang-2022-self-consistency.html`, `public/papers/ursekar-2026-vero.html`
Current: self-consistency prose deltas contradict its own table (M-07: +12.2/+11.0/+6.4/+3.9 vs computed +12.5/+7.6/+6.3/+3.5); VeRO says "from a 0.50 baseline to 0.61 (+8 points)" where +8 is vs the 0.53 row (m-13).
Desired: prose agrees with the tables shown. For self-consistency, first check the paper (arXiv 2203.11171) — if the paper's own abstract deltas differ from the page's table, quote the paper and add "(paper's figures)"; otherwise recompute from the table. For VeRO: "…from the 0.53 no-VeRO Claude Code baseline to 0.61 (+8 points; +11 over the 0.50 raw baseline)".
Accept: recompute every delta in both edited passages from the adjacent tables by hand — all agree; pages still pass the mobile check (`document.documentElement.scrollWidth <= clientWidth` at 375px).

### R-06 · Audit the `topic` field (the "Reasoning" catch-all)  [M] deps: —
Files: `data/papers.json` (topic fields only), affected `public/papers/*.html` hero topic strings
Current: 37 nodes carry topic "Reasoning" incl. megatron-lm (training infra), simclr/moco (vision SSL), s4/flashattention (architecture/systems), palm (scaling), graphrag (RAG); levine-2025-rebel node says "Reasoning" while its page says "RAG / Reranking" (M-06).
Desired: every node's topic defensible from its abstract; page hero strings match nodes. Options: re-bucket into existing topics where honest (megatron→? none fit) or add 1–2 topics (e.g. "Architectures & Systems", "Representation Learning") — adding topics is fine (palette cycles; legend sorts by count).
Change sketch: list all 37 Reasoning nodes + every node whose page hero topic ≠ node topic (script it: extract hero kick line, compare); propose new topic per node in the commit message; apply; update page hero strings to match.
Accept: `python3 -c` sweep shows zero page-hero/node topic mismatches; no node named in M-06 still says "Reasoning" unless justified in the commit message; `npm run build` passes and the legend renders the new categories.

### R-07 · Run the deferred second classification pass on the Evaluations taxonomy  [L] deps: —
Files: `data/evaluations-taxonomy.json`, `scripts/evaluations_survey/`, rebuild `public/surveys/evaluations.html`
Current: 6 of 7 facets single-pass (M-05); the re-audited facet needed 7/59 corrections.
Desired: an independent second pass over the six un-audited facets (verdict_engine, construct, reference_standard, signal_fidelity, validation_depth, grader_gap) with different paper groupings, disagreements adjudicated against source text; method section updated to report the real two-pass agreement; findings re-checked against corrected counts (if any finding's number changes, update its prose).
Change sketch: for each facet, classify all 59 from explainers in batches ≠ the original grouping (subagents fine); diff vs current JSON; adjudicate each disagreement with a third read; record agreement %; update the method paragraph (replace the rate-limit apology with the real protocol); rebuild.
Accept: build script runs; method section states two-pass agreement for all seven facets; every chart count in findings 01–07 matches a fresh recount from the JSON (write a 20-line assert script, keep it in `scripts/evaluations_survey/`); GDPval placement revisited in the same pass (see R-22).

### Wave 2 — coverage, queue, and content ops

### R-08 · Queue triage: reorder, re-prioritize, archive  [M] deps: —
Files: `data/queue.json` (+ new `data/queue-archive.json`)
Current: head = 12 off-mission CV papers; priority null=437/High=383; 439 entries ≤2022 (M-09, m-19); 28 entries lack both ids (m-04).
Desired: file order = build order, with the literature-gap papers first. Structure: (1) move the Tier-A+top-B papers from `.critique/lit-gaps.md` §A/§B to the top with priority "High" and a `why` naming the survey gap (exact list in R-10); (2) move all ≤2022 entries EXCEPT canon items (list in lit-gaps §B) plus the 12 CV-era heads into `data/queue-archive.json` (same schema; recoverable); (3) resolve-or-drop the 28 id-less entries (S2 title search; drop only if unresolvable, log in commit message); (4) backfill priority on remaining nulls (Medium default).
Accept: `python3 .critique/check_data.py` still reports zero dupes; queue length ≈ 1052 − archived − dropped; first 20 entries are all survey-gap or High-priority eval-era papers; archive file parses and its length + queue length + drops = 1052.

### R-09 · Add the missing canon papers to the queue  [S] deps: R-08
Files: `data/queue.json`
Current: `.critique/lit-gaps.md` §C lists papers in neither graph nor queue.
Desired: append (top of file, priority High, `source: "Lit-gap: <survey>"`, one-line `why`) with accurate arxiv_ids (resolve via S2 with `x-api-key: $S2_API_KEY`): BFCL paper; τ²-bench; ScienceAgentBench; SuperGPQA; BBEH; HELMET; NoLiMa; Video-MME; EgoSchema; MedQA (Jin et al. 2020); MedXpertQA; Vending-Bench; BALROG; CRMArena; The Leaderboard Illusion; Elo Uncovered; "Adding Error Bars to Evals" (Miller 2024); Style over Substance; tinyBenchmarks; a data-contamination survey (pick the canonical one via S2); McIntosh 2402.09880; Bean 2511.04703; Cao 2504.18838; Gu 2411.15594; Li 2412.05579; Zhong 2504.12328; rubric survey 2606.08625; Jacobs & Wallach 1912.05511; Tangled up in BLEU 2006.06264; one canonical WMT metrics shared-task paper. (Dedupe against graph+queue by arxiv_id/title first — Procedure B.)
Accept: check_data.py shows no queue dupes and no overlap with graph; every added entry has arxiv_id or doi; queue length grew by the number added.

### R-10 · Build the 15-paper "survey credibility core" (Procedure A runs)  [L] deps: R-08, R-09
Files: everything Procedure A touches
Current: the surveys' referee-bait gaps (M-08).
Desired: process, in order: τ-bench, WebArena, GAIA, RewardBench, JudgeBench, FrontierMath, MBPP, RE-Bench, AI Agents That Matter, BetterBench, The Leaderboard Illusion, Miller Adding-Error-Bars, LiveBench, ToolLLM, VisualWebArena — one full Procedure A run each (explainer, node, edges, tags per rubric: e.g. τ-bench → benchmarks+evaluations; RewardBench/JudgeBench/BetterBench/Leaderboard-Illusion/Miller → evaluations; WebArena/GAIA/FrontierMath/MBPP/LiveBench/ToolLLM/VWA → benchmarks; RE-Bench → benchmarks; AAM → evaluations).
Accept: per Procedure A step 11 for each (renders desktop+mobile); after all 15, re-run both survey builders — the new papers appear in their family lists; `python scripts/tag_papers.py surveys` shows benchmarks ≥ 137, evaluations ≥ 65 (±, per tagging judgment); note every tagging judgment call in the session summary.

### R-11 · Write the page↔node reconcile-and-lint script  [M] deps: —
Files: new `scripts/lint_pages.py`
Current: hand-typed hero facts drift (m-14, m-15); no automated check exists.
Desired: a read-only linter that, for every node/page pair, reports: citation-count mismatch (page fact chip vs JSON, comma-insensitive); H1 vs canonical title mismatch (normalized); kicker year vs chip venue-year contradiction; venue string w/wo year inconsistency; "as of" stamp not matching `YYYY-MM-DD`; unescaped bare `&`/`<` in text nodes; missing figures (0 `data:image`); byline that equals the node's abbreviated `authors` string. Exit 1 on any finding; `--fix` mode optional for the mechanical ones (as-of format, escaping).
Accept: running it on HEAD reproduces exactly the m-14/m-15 list (akyurek 0/16, lexglue year, 4 title drifts, spreadsheetbench byline, si-2024 `&`, multinrc 0 figs, as-of zoo); after the fixes it exits 0. Wire into CLAUDE.md Procedure A step 11 (one line).

### R-12 · Verify and fix the 6 suspect edges + implausible mutual pairs  [S] deps: —
Files: `data/papers.json` (edges only)
Current: m-01/m-02 lists (phan-2025-hle→arora-2025-healthbench etc.; 12 mutual pairs).
Desired: for each, query S2 (`x-api-key: $S2_API_KEY`) references of both endpoints; keep edges S2 confirms, flip reversed ones, drop phantom ones; leave plausible revision-era citations with a note in the commit message.
Accept: check_data.py "edges where citing predates cited by >3mo" count ≤ 2, each remaining one justified in the commit message; edge count change ≤ 12.

### R-13 · Replace claude_loop.sh with a gated queue.json-aware loop  [M] deps: R-08
Files: `claude_loop.sh` (rewrite), delete `runqueue.sh`
Current: M-11 / m-07.
Desired: port runqueue.sh's gates to this repo: stop on nonzero claude exit; run `npm run build` + `python3 scripts/lint_pages.py` (R-11) + a queue-progress check (queue length must shrink by ≥1 per iteration) after each item; optional `-n N` cap and per-item timeout; keep `--dangerously-skip-permissions` only behind an explicit flag.
Accept: `./claude_loop.sh --dry-run` prints the plan without executing; a deliberate failure (temporarily break papers.json in a scratch branch) stops the loop at gate 1.

### Wave 3 — polish & hardening

### R-14 · Normalize the 33 whitespace-forked mobile blocks  [S] deps: —
Files: the 33 pages listed in `.critique/check_pages.out` (hash c1fe5226cb)
Change sketch: replace each one-line block with the template's multi-line block verbatim (script it; the CSS is semantically identical so rendering is unchanged).
Accept: re-run `.critique/check_pages.py` → media-block hash distribution shows a single hash equal to the template's, 277/277.

### R-15 · OG/social meta site-wide  [M] deps: —
Files: `index.html`, `templates/explainer.html`, both survey builders/templates, backfill all `public/papers/*.html`
Change sketch: `og:title`/`og:description`/`og:type`/`og:url` (+`twitter:card`) per page from existing title/dek; explainers get it templated + a one-off backfill script (insert after `<title>`; identical structure across pages so a single scripted edit works — same mechanism as the media-block sync).
Accept: `grep -L 'property="og:title"' public/papers/*.html public/surveys/*.html index.html` returns nothing; `npm run build` passes.

### R-16 · Responsive survey charts  [M] deps: —
Files: `scripts/*/svgcharts.py` (via R-19's shared copy), rebuild both pages
Change sketch: emit `style="max-width:100%;height:auto"` + keep `viewBox`; where 52%-scale text would be illegible (dense stacked bars), instead add a `scroll →` affordance (a fading right-edge gradient + caption note) to the chart wrapper.
Accept: at 375px, each chart either fits the viewport or its wrapper shows the affordance; no document-level horizontal scroll (both pages, measured).

### R-17 · Zoom-dependent axis label thinning  [S] deps: —
Files: `src/main.js` (`placeAxis`), `src/style.css`
Change sketch: in `placeAxis()`, when `zoom * colGap < ~70px`, add a class on `#axis` that hides `.tick:not(.yr) .lb` (same rule the ≤640px media query already applies).
Accept: at fit zoom on desktop, the 2004–2018 region shows only year labels (no overlap); zooming past the threshold restores quarter labels.

### R-18 · Sync the docs with the code they describe  [S] deps: —
Files: `CLAUDE.md`, `README.md:51`, `src/main.js:11,27-30`, `src/style.css:30-31`
Change sketch: describe the real `size()` (log10, ~12–80px) in all three places; delete/fix the two stale "dim the rest" comments; while in CLAUDE.md, add the R-11 lint to Procedure A step 11 and the R-08 queue-ordering policy to Procedure A step 1.
Accept: `grep -rn "sqrt(citation_count)" CLAUDE.md README.md src/` → 0 matches; `grep -n "dim" src/style.css src/main.js` shows no stale survey-dimming claims.

### R-19 · Single shared svgcharts.py  [S] deps: before R-16
Change sketch: move to `scripts/survey_common/svgcharts.py`; both builders import it (sys.path insert or package-relative); delete the copies.
Accept: `diff`-able single file; both builders run and reproduce byte-identical pages (except intended changes).

### R-20 · Atomic writes in mutating scripts  [S] deps: —
Files: `scripts/tag_papers.py`, `scripts/backfill_dates.py`
Change sketch: write to `<file>.tmp` then `os.replace`.
Accept: grep shows no bare `open(PAPERS,'w')` writes; scripts still round-trip papers.json byte-identically on a no-op run.

### R-21 · Nits batch  [S] deps: —
Change sketch: remove `timeOf` export or use it; comment the INST_WEIGHT default-50 quirk (or set unknown=45); move `design/prototype.html` to an `archive/` dir or delete; escape `(<60%)` → `(&lt;60%)` in the benchmarks builder; fix "59−3 of 59" phrasing to "56 of 59" in the evaluations builder; fix si-2024 `&`; expand spreadsheetbench byline; fix lexglue year (per R-11 output); suppress the wheel-sensitivity warning by removing the custom `wheelSensitivity` or accepting default; make the hint text touch-aware ("tap a node · tap to open").
Accept: R-11 linter exits 0; rebuilt survey pages contain neither raw `(<60%)` nor "59−3".

### R-22 · Re-house or re-name GDPval's evaluations family  [S] deps: R-07
Files: `data/evaluations-taxonomy.json`, evaluations builder, rebuild
Change sketch: either rename I4 to "expert human audits" (covers Gender Shades/Med-PaLM/GDPval honestly) or move GDPval and add it to the method section's borderline list. Keep family count consistent everywhere (hero chip says 22 families).
Accept: rebuilt page's I4 label/reason and borderline list are self-consistent; family sum still 59.

### R-23 · State the date-vs-year policy  [S] deps: —
Files: `CLAUDE.md` (conventions), optionally node tooltip in `src/main.js`
Change sketch: one paragraph: `date` = preprint month (timeline position), `year` = venue publication year (display); the 8 known mismatch nodes are correct as-is. Optionally render both in the panel kick ("2019 preprint · JMLR 2020").
Accept: paragraph exists; the 8 nodes from `check_data.out` are referenced as expected examples.

### R-24 · Minimum test net + CI  [M] deps: R-11
Files: new `tests/` (or `scripts/tests/`), `package.json`, optional GitHub Actions
Change sketch: (1) Python: tag_papers round-trip test (add+remove on a fixture copy → byte-identical), check_data invariants as pytest against `data/`, backfill_dates idempotency on a fixture; (2) JS (vitest): `computeTimeline` invariants — no NaN positions, per-column no-overlap (gap ≥ vGap−ε), centerSet members centered (|mean y| < column half-height), bands sorted; (3) `npm test` + `pip` deps documented; CI optional but recommended (build + tests + lint_pages).
Accept: `npm test` and `pytest` green locally; breaking the spine pack (mutate a sign) fails a test.

### R-25 · Non-paper-instrument policy note in both surveys  [S] deps: —
Files: both survey builders' method sections, rebuild
Change sketch: one sentence naming the exclusion: "The 2026 model-card canon also includes non-paper instruments (SWE-bench Verified, Aider Polyglot, AIME, ARC-AGI leaderboards, needle-in-a-haystack probes); this corpus covers papers only."
Accept: sentence present on both rebuilt pages.

### Literature-gap campaign (beyond the 15-paper core)
After R-10, continue Procedure A through `.critique/lit-gaps.md` §B then §C in the R-08 file order (~45 more papers). Tag each per the survey rubrics as built; re-run both survey builders every ~10 papers so family lists and finding counts stay current; watch for the L5 row (still empty) and the "missing middle" (multi-turn) claims — new corpus members may change those survey sentences, which is a feature: re-generate, re-read, re-verify the findings' numbers after each rebuild (the builders compute them from the JSONs, but narrative sentences with hardcoded numbers must be re-checked — grep each rebuilt page for the finding numbers and reconcile).

## Appendix

**Coverage.** Read in full: all of `src/` (main.js, timeline.js, style.css), index.html, vite.config.js, both shell loops, tag_papers.py, backfill_dates.py, CLAUDE.md, README.md, both survey pages (every word, via tag-stripped extraction), both taxonomy JSONs (structure + distributions + sampled rows). Read via 12 Sonnet subagent batches with a fixed rubric: all 277 explainers (every page checked against its node + contract; 36 pages fully read end-to-end; critique sections read on all). Sampled/skimmed only: extract_figures.py, inject_figures.py, the two survey builders' internals (~1,190 lines Python — structure and outputs verified, line-by-line logic not audited), design/prototype.html. Not audited: figure-crop quality per page; explainer numbers against source PDFs (internal consistency only — flagged as the known residual risk; the two defects found were both internal contradictions).

**Method.** Commands (all exit 0 unless noted): `npm install`, `npm run build` (933 kB chunk warning), `python3 .critique/check_data.py`, `python3 .critique/check_pages.py`, `python3 .critique/canon_diff.py`; live exercise on Vite dev server (desktop 1280×720 + mobile 375×812, both surveys, deep link, panel, node click, four page types measured for horizontal overflow). External research: 3 web searches + 4 arXiv abstract fetches (log: `.critique/research-log.md`). Subagent usage: 12 explainer-review batches (~1.8M tokens total).

**Confidence notes.** (1) The init-fit race (M-03) was reproduced in an embedded pane whose window reports zero size; standard foreground tabs are unaffected — the Major rating rests on background-tab/webview loads being common for shared links. (2) The comparative analysis is from working knowledge, not fresh audits. (3) Claim 14 (Rubric Reward Hacking) and the McIntosh/ABC counts are internally consistent but not verified against PDFs — folded into R-04. (4) The canon list behind M-08 is one expert's list cross-checked against one 2026 model-card sweep; it is a floor, not a census. (5) All 12 batch reviewers were Sonnet subagents; their zero-defect batches were spot-checked only via their own verdict tables.
