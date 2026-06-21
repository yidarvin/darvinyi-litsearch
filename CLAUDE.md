# CLAUDE.md — Paper Atlas operations

This repo is **Paper Atlas**: a dark, citation-map site of ML/eval papers, deployed at research.darvinyi.com. Two tiers:

- the **index map** — a citation **timeline** that reads `data/papers.json`: papers flow left→right by publication date (quarter bands, ordered to minimize edge crossings), nodes coloured by topic/author/venue, edges dimmed until you hover a node. The layout math lives in `src/timeline.js`; the renderer, hover behaviour, and the time-axis overlay in `src/main.js` + `index.html` (`#axis`) + `src/style.css`.
- one **explainer page per paper** at `public/papers/<slug>.html` (dark, self-contained long-reads)

A local **queue** (`data/queue.json`) lists papers waiting to become explainers. You (the agent) process them one at a time and grow the queue with newly-discovered papers.

You have web access, bash (curl/wget), and Python (PyMuPDF / Pillow). **Never auto-commit, push, or deploy.** End every task with a short summary of what changed and a reminder for me to review (`npm run dev`) and commit.

**Semantic Scholar API key.** A key lives in the `$S2_API_KEY` env var (set in the gitignored `.claude/settings.local.json` — never hardcode or echo it). Send it on **every** Semantic Scholar request as a header: `curl -s -H "x-api-key: $S2_API_KEY" "https://api.semanticscholar.org/graph/v1/..."`. This raises the rate limit; without it the API throttles aggressively. If a call still 429s, back off and retry rather than dropping the key.

## Command routing
- "run the next one" / "go down the queue" / "next paper" / "do the next one" → **Procedure A — Process next**
- "add X to the queue" / "queue up X" / "add all papers by/from …" → **Procedure B — Add to queue**
- "review the existing papers" / "audit the graph" / "refresh citations" / "recheck the connections" → **Procedure C — Audit the graph**

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
      "explainer": "papers/patwardhan-2025-gdpval.html"
    }
  ],
  "edges": [ { "from": "<citing slug>", "to": "<cited slug>" } ]
}
```
Edges are directed (citing → cited). The map lays papers out as a **left→right timeline** by publication date (`src/timeline.js`): papers are binned into quarter bands, and each column is ordered to minimize edge crossings. `date` is `"YYYY-MM"` (month precision, from the paper's arxiv id); the layout falls back to `year` mid-year if it's missing. Node size = `sqrt(citation_count)`, **capped** (see `size()` in `src/main.js`) so 26k-citation foundational nodes don't blow out a column. The color-by dimensions are `topic`, `author_group`, and `venue`. Edges sit dim and brighten on hover/selection. The map reads this file directly, so updating it **is** updating the map — no separate map edit.

### Slug
`firstauthor-year-keywords`, lowercase, hyphenated. Generated once; it is the explainer filename **and** the graph node id. Never change a paper's slug.

## Explainer page contract
Each `public/papers/<slug>.html` is one self-contained **dark** long-read built from `templates/explainer.html`:
- Sections in order: **hero → the gap (problem) → how it works (method) → what they found (results) → does it hold up? (eval-rigor critique — the signature section) → takeaways.**
- The paper's **real figures**, extracted from the PDF and inlined as base64. Equations as HTML/CSS. No external scripts except web fonts. Dark theme matching the index.
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
9. **Grow the queue.** From this paper's references/citations, pick the most important papers **not already** in `papers.json` or `queue.json` (dedupe by arxiv_id/doi/title), ranked by citation count and by how many existing nodes cite them. List the top ~5 with one-line reasons and append them to `data/queue.json` (`source: "Cited by <this slug>"`).
10. **Remove the processed paper** from `data/queue.json`.
11. **Verify it actually renders — desktop *and* mobile.** A clean `papers.json` does **not** guarantee the map shows the node — the render is the source of truth. Run `npm run build` (must succeed) and load the site (`npm run dev`, or drive it with the browser tools): confirm the **new node appears on the map in its publication-quarter column** (the timeline places it by `date`, so a wrong/missing `date` lands it in the wrong column or — only as a `year` fallback — mid-year), that **hovering it brightens its citation edges**, and that its **explainer page loads** self-contained. Pay special attention to UI state transitions you don't normally exercise (e.g. the empty→first-paper case, or a `date` that opens a brand-new quarter band on the time axis). **Then check the explainer at a phone width (≈375px):** it must not scroll **horizontally** — the quickest signal is `document.documentElement.scrollWidth <= clientWidth` (anything wider means a child is overflowing; tables and the `.verdict` grid are the usual culprits — see the mobile contract above); the index map itself should also not cause sideways document scroll (it pans internally). If the node is missing/mis-placed or a page overflows sideways despite correct data, it's a site bug — fix it (and note the fix in the report).
12. **Report.** "Built `papers/<slug>.html`; added 1 node + N edges; queued M new papers; removed 1 from the queue; verified it renders (desktop + mobile, no sideways scroll)." Then remind me to `npm run dev` and commit.

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
6. **Write `data/papers.json` deterministically** (stable key order, edges sorted) so the diff is reviewable. Don't touch `slug`, `short`, `date`, `explainer`, or prose fields (`abstract`, `topic`, `author_group`) — those are owned by Procedure A. (If the audit surfaces a node with **no `date`**, that's the one exception: run `python scripts/backfill_dates.py` to give it one so it leaves the mid-year fallback column.)
7. **Verify it renders.** Run `npm run build` (must succeed) and load the site (`npm run dev`, or the browser tools): confirm the timeline map still renders and the **new connections actually appear** — hover a node whose degree changed and check its citation edges light up as expected. The render is the source of truth — a clean JSON diff isn't enough.
8. **Report.** "Audited N nodes; added E edges, removed D dangling/duplicate; refreshed C citation counts; verified it renders." Call out any nodes that couldn't be resolved and any edges you flagged but didn't change. Then remind me to `npm run dev` and commit (`data/papers.json` changed).

---

## Conventions
- Keep the identifier and slug consistent across the queue, the explainer filename, and the graph node.
- Citation counts drift; they're refreshed whenever a paper is processed, and a page may note "as of <date>".
- Write `data/*.json` deterministically (stable key order) so commits stay readable.
- The rendered map is the source of truth, not the JSON — always confirm a new node actually appears (in its publication-quarter column) before calling a run done (Procedure A, step 11).
- The map is a **timeline**: every node needs a `date` (`"YYYY-MM"`) to sit in the right quarter column — `scripts/backfill_dates.py` re-derives it from each explainer's hero `source` link, so keep that link canonical. Node size is **capped** in `src/main.js`. The layout (`src/timeline.js`), the time-axis overlay (`#axis` in `index.html` + `src/style.css`), and the renderer/hover (`src/main.js`) move together: if you change one — band granularity (quarter↔half), column spacing, the size cap, edge dimming — keep the others and this file in sync.
- Every explainer must be mobile-safe (no horizontal scroll at ≤640px). The mobile rules live in `templates/explainer.html`'s `@media(max-width:640px)` block, mirrored identically across all `public/papers/*.html`; build new pages from the template and keep that block in sync if you ever touch it (see the explainer page contract). The index map must likewise not cause sideways **document** scroll on a phone (it pans/zooms internally; the axis collapses to year-only labels under 640px).
- Never auto-commit, push, or deploy — finish each run with a summary and "review and commit when ready."
