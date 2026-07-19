#!/usr/bin/env python3
"""make_bib.py — emit a BibTeX file for a survey's citations.

    python3 scripts/survey_scaffold/make_bib.py <survey_id> [--slugs slug1,slug2,...]

Reads every paper tagged `<survey_id>` in data/papers.json (or an explicit
--slugs list, for citing papers outside the survey's own tagged corpus — a
method paper referenced in a `lineage` link, say) and writes
paper/<survey_id>/refs.bib, one BibTeX entry per paper, keyed by slug so
`\\citep{<slug>}` in the survey's .tex source just works.

Prefers Semantic Scholar's own `citationStyles.bibtex` field (sends
$S2_API_KEY per CLAUDE.md doctrine) when reachable — it's a complete,
correctly-formatted entry from the paper's own record. Falls back to
constructing a `@misc`/`@inproceedings` entry from papers.json's fields plus
the paper's arXiv id (read from its explainer's canonical `source ↗` link,
the same technique `scripts/backfill_dates.py` uses) when S2 is unavailable
or doesn't have the paper — this repo has run with no configured S2 key
before (see PIPELINE_PLAN.md's M3 worked example), so the fallback path is
not a theoretical case; it does one quick reachability probe up front rather
than retrying per paper, since 100+ papers against a rate-limited
unauthenticated API would otherwise take forever to all fail the same way.

Safe to include entries nothing ends up citing: BibTeX only emits entries
actually `\\cite{}`'d (or `\\nocite{}`'d) in the compiled .tex, so an author
doesn't need to pre-decide exactly what they'll reference before running
this — over-including here is harmless.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from latex_utils import latex_escape  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"

SOURCE_RE = re.compile(r'href="([^"]+)"\s*>\s*source', re.I)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.I)


def die(msg):
    sys.exit(f"make_bib: {msg}")


def s2_get(path, fields, timeout=8):
    url = f"{S2_BASE}/{path}?fields={fields}"
    req = urllib.request.Request(url)
    key = os.environ.get("S2_API_KEY")
    if key:
        req.add_header("x-api-key", key)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def s2_reachable():
    """One quick probe, not a per-paper retry loop -- if this fails we assume
    every subsequent S2 call would too (rate limit or outage) and go straight
    to local construction for the whole run."""
    try:
        s2_get("arXiv:1706.03762", "title", timeout=6)  # "Attention Is All You Need"
        return True
    except Exception as e:
        print(f"make_bib: S2 not reachable ({e.__class__.__name__}: {e}); "
              f"building every entry from local data instead.", file=sys.stderr)
        return False


def arxiv_id_of(slug):
    explainer = ROOT / "public" / "papers" / f"{slug}.html"
    if not explainer.exists():
        return None
    m = SOURCE_RE.search(explainer.read_text())
    if not m:
        return None
    a = ARXIV_RE.search(m.group(1))
    return a.group(1) if a else None


def bibtex_authors(authors_field):
    """papers.json's `authors` is a display string ("A, B, C" or, for long
    author lists, "A, B, …, Y, Z" with a literal ellipsis) -- convert to
    BibTeX's ' and '-separated convention. An ellipsis becomes a trailing bare
    `others` (the standard BibTeX idiom -- `author = {A and B and others}` --
    renders as "et al." in standard styles); everything after it is dropped
    since BibTeX has no "middle authors omitted" notation. `others` must be
    bare, not `{and others}`/`and others`: the join below already supplies
    the "and", so baking one into the token itself doubles it ("and and
    others")."""
    names = [n.strip() for n in authors_field.split(",")]
    if "…" in names:
        names = names[: names.index("…")] + ["others"]
    return " and ".join(n if n == "others" else latex_escape(n) for n in names)


def bibkey_from_s2_bibtex(bibtex, slug):
    """Replace S2's own generated cite key with our slug, so \\citep{<slug>}
    matches regardless of what key S2 assigned."""
    return re.sub(r"(@\w+\{)[^,]+,", rf"\1{slug},", bibtex, count=1)


def local_entry(paper, slug):
    aid = arxiv_id_of(slug)
    title = latex_escape(paper["title"])
    lines = [f"@misc{{{slug},"]
    lines.append(f"  title = {{{{{title}}}}},")
    lines.append(f"  author = {{{bibtex_authors(paper['authors'])}}},")
    lines.append(f"  year = {{{paper['year']}}},")
    if aid:
        lines.append(f"  eprint = {{{aid}}},")
        lines.append("  archivePrefix = {arXiv},")
        lines.append(f"  url = {{https://arxiv.org/abs/{aid}}},")
    else:
        lines.append(f"  howpublished = {{{latex_escape(paper.get('venue', 'arXiv'))}}},")
        lines.append(f"  url = {{https://research.darvinyi.com/{paper['explainer']}}},")
    lines.append("}")
    return "\n".join(lines)


def s2_entry(paper, slug, use_s2):
    if use_s2:
        aid = arxiv_id_of(slug)
        if aid:
            try:
                rec = s2_get(f"arXiv:{aid}", "citationStyles")
                bibtex = rec.get("citationStyles", {}).get("bibtex")
                if bibtex:
                    return bibkey_from_s2_bibtex(bibtex, slug), True
            except Exception:
                pass  # any failure (429, timeout, no record) -> fall through to local construction
    return local_entry(paper, slug), False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("survey")
    ap.add_argument("--slugs", help="comma-separated slug list, overriding the tagged-corpus default")
    a = ap.parse_args()

    papers = json.loads((ROOT / "data" / "papers.json").read_text())["papers"]
    by_slug = {p["slug"]: p for p in papers}

    if a.slugs:
        slugs = [s.strip() for s in a.slugs.split(",") if s.strip()]
        unknown = [s for s in slugs if s not in by_slug]
        if unknown:
            die(f"unknown slug(s): {unknown}")
    else:
        slugs = sorted(s for s, p in by_slug.items() if a.survey in p.get("tags", []))
        if not slugs:
            die(f"no papers tagged '{a.survey}' in data/papers.json, and no --slugs given.")

    use_s2 = s2_reachable()
    entries, s2_count = [], 0
    for slug in slugs:
        entry, from_s2 = s2_entry(by_slug[slug], slug, use_s2)
        entries.append(entry)
        s2_count += from_s2
        if use_s2:
            time.sleep(0.1)  # light pacing even when reachable, per CLAUDE.md S2 doctrine

    out_dir = ROOT / "paper" / a.survey
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "refs.bib"
    header = (f"% Auto-generated by scripts/survey_scaffold/make_bib.py for survey '{a.survey}'.\n"
              f"% {len(entries)} entries ({s2_count} from Semantic Scholar, "
              f"{len(entries) - s2_count} constructed locally). Do not hand-edit — re-run instead.\n\n")
    out_path.write_text(header + "\n\n".join(entries) + "\n")
    print(f"wrote {out_path} ({len(entries)} entries, {s2_count} from S2)")


if __name__ == "__main__":
    main()
