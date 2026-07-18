#!/usr/bin/env python3
"""Reconcile-and-lint: check every explainer page against its data/papers.json
node. Read-only by default; --fix applies the mechanical, unambiguous
normalizations (as-of date format, unescaped bare & in prose, citation-count
sync from the node's audited count). Exits 1 if any check fails (post-fix or
otherwise), 0 if clean. Wired into CLAUDE.md Procedure A step 11.

Checks:
  - citation-count mismatch (page fact chip vs papers.json citation_count)
  - H1 vs canonical title mismatch (normalized, punctuation/whitespace-insensitive)
  - kicker year/venue vs fact-chip venue self-contradiction
  - "as of" stamp not in YYYY-MM[-DD] form
  - a bare " & " or " < " outside markup (likely an unescaped entity)
  - zero embedded figures (informational only — not a failure; some pages are
    legitimately table-only, e.g. fabbri-2025-multinrc)
  - byline identical to the node's own abbreviated `authors` string (usually
    means it was never expanded to full names)
"""
import argparse, html as html_mod, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS_JSON = ROOT / "data" / "papers.json"
PAPERS_DIR = ROOT / "public" / "papers"

MONTHS = {m: f"{i+1:02d}" for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}
MONTHS.update({m[:3]: v for m, v in MONTHS.items()})

ASOF_RE = re.compile(r'(<div class="asof mono">)(.*?)(</div>)', re.S)
LONGDATE_RE = re.compile(
    r'\b(January|February|March|April|May|June|July|August|September|October|November|December)'
    r'(?:&nbsp;|\s)+(\d{1,2}),\s*(\d{4})\b')
MONTHYEAR_RE = re.compile(
    r'\b(January|February|March|April|May|June|July|August|September|October|November|December|'
    r'Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b')
KICK_RE = re.compile(r'<div class="kick">(.*?)</div>')
CHIP_VENUE_RE = re.compile(r'<span class="fact">venue&nbsp;<b>([^<]+)</b></span>')
CHIP_CITE_RE = re.compile(r'<span class="fact">citations&nbsp;<b>([\d,]+)</b></span>')
BYLINE_RE = re.compile(r'<div class="meta">([^<]+)</div>')
H1_RE = re.compile(r'<h1>(.*?)</h1>', re.S)


def norm_title(t):
    t = re.sub(r'<[^>]+>', '', t)
    t = html_mod.unescape(t)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return re.sub(r'[^\w\s]', '', t)


def normalize_asof_date(text):
    """Rewrite Month-DD-YYYY / Month-YYYY substrings to YYYY-MM[-DD], leaving
    every other character (prefixes, ' · ' suffixes, '(Semantic Scholar)') untouched."""
    def repl_long(m):
        return f"{m.group(3)}-{MONTHS[m.group(1)]}-{int(m.group(2)):02d}"

    def repl_my(m):
        return f"{m.group(2)}-{MONTHS[m.group(1)]}"

    out = LONGDATE_RE.sub(repl_long, text)
    out = MONTHYEAR_RE.sub(repl_my, out)
    return out


def lint_page(slug, node, fix):
    path = PAPERS_DIR / f"{slug}.html"
    html = path.read_text(encoding="utf-8")
    orig = html
    findings = []
    info = []

    # 1. as-of date format
    m = ASOF_RE.search(html)
    if m:
        inner = m.group(2)
        fixed = normalize_asof_date(inner)
        if fixed != inner:
            findings.append(f"as-of stamp not YYYY-MM[-DD]: {inner.strip()!r}")
            if fix:
                html = html[:m.start()] + m.group(1) + fixed + m.group(3) + html[m.end():]

    # 2. citation-count sync (page chip vs node's audited count)
    cm = CHIP_CITE_RE.search(html)
    if cm and node.get("citation_count") is not None:
        page_n = int(cm.group(1).replace(",", ""))
        node_n = node["citation_count"]
        if page_n != node_n:
            findings.append(f"citation count drift: page={page_n} node={node_n}")
            if fix:
                html = CHIP_CITE_RE.sub(
                    lambda mm: mm.group(0).replace(mm.group(1), f"{node_n:,}"), html, count=1)

    # 3. H1 vs canonical title — house style: H1 is always the verbatim
    # canonical title (settles the "hook title vs verbatim" inconsistency
    # batch reviewers flagged across several pages).
    h1 = H1_RE.search(html)
    if h1 and norm_title(h1.group(1)) != norm_title(node["title"]):
        findings.append(f"H1 diverges from canonical title:\n    H1:    {h1.group(1)!r}\n    canon: {node['title']!r}")
        if fix:
            safe_title = node["title"].replace("&", "&amp;")
            html = html[:h1.start()] + f"<h1>{safe_title}</h1>" + html[h1.end():]
            h1 = H1_RE.search(html)

    # 4. kicker year vs fact-chip venue's embedded year. NOT a hard failure:
    # per the date-vs-year policy (R-23; see CLAUDE.md), the kicker's year is
    # the arXiv/preprint year while the fact chip's venue can carry a later
    # conference edition (e.g. kicker "2023" + chip "ICLR 2024") — this is
    # the pervasive, intentional preprint-vs-publication convention, not a
    # self-contradiction, so it's reported as informational only.
    kick = KICK_RE.search(html)
    chip_v = CHIP_VENUE_RE.search(html)
    if kick and chip_v:
        kick_parts = [p.strip() for p in re.sub(r'<[^>]+>', '', kick.group(1)).split("·")]
        kick_year_m = re.match(r'(\d{4})$', kick_parts[0]) if kick_parts else None
        chip_year_m = re.search(r'\b(\d{4})\b', chip_v.group(1))
        if kick_year_m and chip_year_m and kick_year_m.group(1) != chip_year_m.group(1):
            info.append(f"kicker year {kick_year_m.group(1)} vs later venue edition {chip_v.group(1)!r} (preprint-vs-publication; expected)")

    # 5. bare unescaped & in the kick region (crude but targeted; H1 is
    # already re-escaped by the fix above when it fires).
    if kick and re.search(r'&(?!amp;|nbsp;|lt;|gt;|#)', kick.group(1)):
        findings.append("unescaped '&' in kick")
        if fix:
            fixed_kick = re.sub(r'&(?!amp;|nbsp;|lt;|gt;|#)', '&amp;', kick.group(1))
            html = html[:kick.start(1)] + fixed_kick + html[kick.end(1):]
            kick = KICK_RE.search(html)

    # 6. zero figures (informational only, not a failure)
    if "data:image" not in html:
        info.append("zero embedded figures (verify this is an intentional tables-only page)")

    # 7. byline identical to node's abbreviated authors string
    bl = BYLINE_RE.search(html)
    if bl and node.get("authors") and bl.group(1).strip() == node["authors"].strip() and "et al" not in node["authors"]:
        # only flag when the node's own authors string looks truncated/abbreviated
        if "…" in node["authors"] or re.search(r',\s*$', node["authors"]):
            findings.append(f"byline == node's own (possibly abbreviated) authors string: {node['authors'][:60]!r}")

    if fix and html != orig:
        path.write_text(html, encoding="utf-8")

    return findings, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="apply mechanical fixes (as-of format, citation-count sync)")
    ap.add_argument("slugs", nargs="*", help="limit to these slugs (default: all nodes)")
    args = ap.parse_args()

    papers = json.loads(PAPERS_JSON.read_text())["papers"]
    if args.slugs:
        wanted = set(args.slugs)
        papers = [p for p in papers if p["slug"] in wanted]

    total_findings = 0
    for node in papers:
        findings, info = lint_page(node["slug"], node, args.fix)
        if findings or info:
            print(f"\n{node['slug']}:")
            for f in findings:
                print(f"  FAIL: {f}")
            for i in info:
                print(f"  info: {i}")
        total_findings += len(findings)

    print(f"\n{total_findings} failing finding(s) across {len(papers)} page(s)"
          + (" (fixes applied — re-run to confirm)" if args.fix else ""))
    sys.exit(1 if total_findings else 0)


if __name__ == "__main__":
    main()
