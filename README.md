# Paper Atlas

A dark, static **citation map** of ML / evaluation papers, with a long-read
**explainer** behind every node. Deployed at
[research.darvinyi.com](https://research.darvinyi.com).

Two tiers:

- the **index map** (`index.html` + `src/`) — a cytoscape citation **timeline**
  that renders from [`data/papers.json`](data/papers.json): papers flow
  left→right by publication date (quarter columns, ordered to minimize edge
  crossings), coloured by topic/author/venue, with edges dimmed until you hover
  a node;
- one **explainer page per paper** at `public/papers/<slug>.html` — dark,
  self-contained long-reads built from [`templates/explainer.html`](templates/explainer.html).

## Run it locally

```bash
npm install
npm run dev      # local preview at http://localhost:5173
npm run build    # → dist/  (pure static)
npm run preview  # serve the built dist/
npm test         # vitest: computeTimeline layout invariants (src/tests/)
```

Python-side checks (data integrity, script round-trips, and the page↔node
linter) need `pytest`, on top of the figure-extraction deps:

```bash
pip install -r scripts/requirements.txt -r scripts/requirements-dev.txt
python -m pytest scripts/tests/ -v
python scripts/lint_pages.py            # --fix applies the mechanical fixes
```

CI (`.github/workflows/ci.yml`) runs the build, both test suites, and the
linter on every push/PR.

`data/papers.json` starts empty, so a fresh checkout shows a friendly
empty-state map. Nodes appear as papers are processed.

## Deploy (Vercel)

Framework preset **Vite**, build `npm run build`, output **dist**. No backend,
no serverless functions. Files in `public/` are copied verbatim, so direct
links like `/papers/<slug>.html` resolve as real static pages.

## Day-to-day work runs through `CLAUDE.md`

The content pipeline is operated by the agent, not by hand. See
[`CLAUDE.md`](CLAUDE.md) for the full procedures and data shapes. The two
commands:

- **“run the next one”** — process the top paper in
  [`data/queue.json`](data/queue.json): fetch its PDF + citation graph, write
  the explainer, add the node + edges to `data/papers.json`, and grow the queue.
- **“add X to the queue”** — queue a specific paper, an author's papers, an
  org's papers, or a topic search.

## Layout

```
index.html              # map entry (Vite); holds the #axis time-axis overlay
src/main.js             # graph build + interactions; capped node size, hover-to-brighten edges
src/timeline.js         # time-ordered layout: papers → quarter columns by `date`, crossing-minimized
src/style.css           # dark theme, teal accent, #axis styling
data/papers.json        # the graph the map renders (nodes + edges); each node has a `date` (YYYY-MM)
data/queue.json         # papers waiting to become explainers
templates/explainer.html# the dark long-read template ({{...}} placeholders)
scripts/extract_figures.py  # auto-detect & crop figures from a PDF (PyMuPDF)
scripts/inject_figures.py   # base64-inline {{FIGn}} into a filled page (Pillow)
scripts/backfill_dates.py   # re-derive each node's `date` from its explainer's source link
public/papers/          # generated explainers land here (served as static files)
```

The figure scripts need Python deps: `pip install -r scripts/requirements.txt`.

> Never auto-commit, push, or deploy from the agent — each run ends with a
> summary; review with `npm run dev` and commit when ready.
