# CLAUDE.md — Paper Atlas operations

This repo is **Paper Atlas**: a dark, citation-map site of ML/eval papers, deployed at research.darvinyi.com. Two tiers:

- the **index map** — a citation graph that reads `data/papers.json`
- one **explainer page per paper** at `public/papers/<slug>.html` (dark, self-contained long-reads)

A local **queue** (`data/queue.json`) lists papers waiting to become explainers. You (the agent) process them one at a time and grow the queue with newly-discovered papers.

You have web access, bash (curl/wget), and Python (PyMuPDF / Pillow). **Never auto-commit, push, or deploy.** End every task with a short summary of what changed and a reminder for me to review (`npm run dev`) and commit.

## Command routing
- "run the next one" / "go down the queue" / "next paper" / "do the next one" → **Procedure A — Process next**
- "add X to the queue" / "queue up X" / "add all papers by/from …" → **Procedure B — Add to queue**

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
Edges are directed (citing → cited). Node size on the map = `sqrt(citation_count)`. The color-by dimensions are `topic`, `author_group`, and `venue`. The map reads this file directly, so updating it **is** updating the map — no separate map edit.

### Slug
`firstauthor-year-keywords`, lowercase, hyphenated. Generated once; it is the explainer filename **and** the graph node id. Never change a paper's slug.

## Explainer page contract
Each `public/papers/<slug>.html` is one self-contained **dark** long-read built from `templates/explainer.html`:
- Sections in order: **hero → the gap (problem) → how it works (method) → what they found (results) → does it hold up? (eval-rigor critique — the signature section) → takeaways.**
- The paper's **real figures**, extracted from the PDF and inlined as base64. Equations as HTML/CSS. No external scripts except web fonts. Dark theme matching the index.
- Quote **exact numbers** from the paper; never invent. Write the critique as a sharp, specific eval read: are the baselines fair and current? contamination / leakage? what the headline metric misses? what would raise confidence?

---

## Procedure A — Process the next paper

1. **Pick.** Read `data/queue.json`. If empty, say so and stop. Otherwise take the top entry (highest `priority`, then order in file) and state which paper you're processing.
2. **Resolve identifiers.** If the entry has no `arxiv_id`/`doi`, find it: search Semantic Scholar and the web by title, and confirm the match (authors + year). Record the arXiv id (or a direct PDF URL) and the canonical metadata.
3. **Download the PDF.** `curl -L -o /tmp/paper.pdf https://arxiv.org/pdf/<arxiv_id>`. Verify it's real (`%PDF` header, size > 50 KB). If no PDF is obtainable (paywalled / non-arXiv), continue from the abstract + Semantic Scholar and skip figure extraction (note this in the report).
4. **Fetch metadata + citation graph.** From Semantic Scholar `/paper/<id>`: authors, year, venue, `citationCount`, `references`, `citations` (fall back to OpenAlex). Keep all of it.
5. **Slug.** Generate it if not already set.
6. **Extract figures.** `python scripts/extract_figures.py /tmp/paper.pdf figs/` — auto-detects every `Figure N:` and writes tight PNGs. You then choose which figures actually belong in the page.
7. **Write the explainer.** Read the PDF (text + figures) and fill `templates/explainer.html` → `public/papers/<slug>.html`, per the explainer contract: write each section in your own words at expert depth, place the relevant real figures, quote exact numbers, and write the critique. Run `python scripts/inject_figures.py` to base64-inline the chosen figures. Verify the result is self-contained (no `{{FIG}}` placeholders remain; no external scripts but fonts).
8. **Update the graph (`data/papers.json`).** Add this paper's node (slug, short label, title, authors, year, venue, citation_count, topic, author_group, abstract, explainer path). Judge `topic` from the abstract (Benchmarks & Evals / Post-training & RL / Reasoning / Agents / Safety & Red-teaming / …) and set `author_group`. Add **edges**: for every reference that is already a node (match by arxiv_id/doi/title) add `{from: <this slug>, to: <ref slug>}`; for every existing node whose paper this one's `citations` list shows citing it, add the reverse edge. Write the file deterministically (stable key order) for clean diffs.
9. **Grow the queue.** From this paper's references/citations, pick the most important papers **not already** in `papers.json` or `queue.json` (dedupe by arxiv_id/doi/title), ranked by citation count and by how many existing nodes cite them. List the top ~5 with one-line reasons and append them to `data/queue.json` (`source: "Cited by <this slug>"`).
10. **Remove the processed paper** from `data/queue.json`.
11. **Report.** "Built `papers/<slug>.html`; added 1 node + N edges; queued M new papers; removed 1 from the queue." Then remind me to `npm run dev` and commit.

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
4. **Append** each to `data/queue.json` with: title, arxiv_id, doi, authors, year, venue, citation_count, `source` (how it was found — e.g., "Author: John Smith" / "Org: Scale AI" / "Lit search: rubric eval"), and `priority`/`why` if obvious.
5. **Report** what was added and the new queue length, and remind me to commit (`data/queue.json` changed).

---

## Conventions
- Keep the identifier and slug consistent across the queue, the explainer filename, and the graph node.
- Citation counts drift; they're refreshed whenever a paper is processed, and a page may note "as of <date>".
- Write `data/*.json` deterministically (stable key order) so commits stay readable.
- Never auto-commit, push, or deploy — finish each run with a summary and "review and commit when ready."
