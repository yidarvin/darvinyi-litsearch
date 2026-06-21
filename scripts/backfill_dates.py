#!/usr/bin/env python3
"""Backfill a month-level `date` field onto every node in data/papers.json.

papers.json nodes carry only `year`, which is too coarse for the timeline map's
quarter bands. Every explainer page, however, links the paper's *own* arxiv URL
in its hero `source` link:

    <span class="fact"><a href="https://arxiv.org/abs/2310.06770">source ↗</a></span>

The arxiv id encodes the month (YYMM.NNNNN -> 20YY-MM), so we can recover a
"YYYY-MM" date for each node fully offline — no network calls. We then insert a
`"date"` field right after `"year"` on each node via a targeted text edit, so the
diff is date-only and the (compact, one-line) edges block stays byte-identical.

Idempotent: re-running rewrites the same dates and never duplicates the field.
Usage:  python scripts/backfill_dates.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS_JSON = ROOT / "data" / "papers.json"
EXPLAINER_DIR = ROOT / "public" / "papers"

# the hero "source" link is the paper's own canonical URL (see templates/explainer.html)
SOURCE_RE = re.compile(r'href="([^"]+)"\s*>\s*source', re.I)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{2})(\d{2})\.\d{4,5}", re.I)


def date_from_explainer(slug: str, year: int):
    """Return ("YYYY-MM", note) for a node, parsed from its explainer source link.

    Falls back to mid-year ("<year>-07") when the source link isn't an arxiv URL.
    """
    f = EXPLAINER_DIR / f"{slug}.html"
    if not f.exists():
        return f"{year}-07", "WARN no explainer file -> mid-year fallback"
    html = f.read_text(encoding="utf-8")
    m = SOURCE_RE.search(html)
    if m:
        a = ARXIV_RE.search(m.group(1))
        if a:
            yy, mm = int(a.group(1)), int(a.group(2))
            yr, mo = 2000 + yy, max(1, min(12, mm))
            note = ""
            if yr > year:
                note = f"WARN arxiv year {yr} > node year {year}"
            return f"{yr:04d}-{mo:02d}", note
    return f"{year}-07", "WARN source link not arxiv -> mid-year fallback"


def main():
    raw = PAPERS_JSON.read_text(encoding="utf-8")
    data = json.loads(raw)
    papers = data["papers"]

    # 1) resolve a date for every node
    dates, warnings = {}, []
    for p in papers:
        d, note = date_from_explainer(p["slug"], p.get("year"))
        dates[p["slug"]] = d
        if note:
            warnings.append(f"  {p['slug']}: {note} (date={d})")

    # 2) insert `"date": "..."` after each paper's `"year": ...,` line via a text
    #    cursor walking the file in node order — keeps everything else identical.
    out, pos = [], 0
    for p in papers:
        slug = p["slug"]
        anchor = raw.find(f'"slug": "{slug}"', pos)
        if anchor == -1:
            sys.exit(f"could not locate slug {slug} in papers.json")
        ym = re.search(r'\n([ \t]*)"year":\s*\d+,', raw[anchor:])
        if not ym:
            sys.exit(f"could not locate year line for {slug}")
        yr_end = anchor + ym.end()
        indent = ym.group(1)
        # idempotency: skip if a date line already follows
        after = raw[yr_end:yr_end + 60]
        if re.match(r'\s*"date":', after):
            nxt = raw.find('"date":', yr_end)
            line_end = raw.find("\n", nxt)
            out.append(raw[pos:yr_end])
            out.append(f'\n{indent}"date": "{dates[slug]}",')
            pos = line_end  # drop the old date line
            continue
        out.append(raw[pos:yr_end])
        out.append(f'\n{indent}"date": "{dates[slug]}",')
        pos = yr_end
    out.append(raw[pos:])
    result = "".join(out)

    PAPERS_JSON.write_text(result, encoding="utf-8")

    # 3) report
    print(f"backfilled date on {len(papers)} nodes")
    print("\nspot-check (first 6):")
    for slug, d in list(dates.items())[:6]:
        print(f"  {slug}: {d}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        print("\n".join(warnings))
    else:
        print(f"\nall {len(papers)} dates from arxiv source links (no fallbacks)")


if __name__ == "__main__":
    main()
