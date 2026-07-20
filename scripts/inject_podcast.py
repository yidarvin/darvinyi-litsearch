#!/usr/bin/env python3
"""
inject_podcast.py — link a paper's explainer page to its podcast episode.

The podcast lives in a SEPARATE repo (~/Projects/darvinyi-podcast) and
is produced by the user-level `litsearch-podcast` skill; integration here is via
the shared slug only. When an episode exists it is published to a deterministic
URL:

    https://pod.darvinyi.com/audio/<slug>.mp3        (feed: .../feed.xml)

This script is the parallel of inject_figures.py, but for audio: it reads the
optional `audio_url` field from a node in data/papers.json and injects (or
refreshes / removes) a small, self-contained podcast block into that node's
explainer page — a `listen ♪` pill in the hero next to `source ↗`, and an
`<audio controls preload="none">` player under the dek. Episodes are expensive
and OPT-IN per paper; this tool only touches pages you point it at.

Usage
-----
    # sync the on-page block(s) from papers.json's audio_url (HTML only)
    python scripts/inject_podcast.py <slug> [<slug> ...]

    # sync every node that has an audio_url (backfill-safe, idempotent)
    python scripts/inject_podcast.py --all

    # stamp the node's audio_url = canonical URL, then sync the page
    python scripts/inject_podcast.py --set <slug> [<slug> ...]

    # clear the node's audio_url and strip the on-page block
    python scripts/inject_podcast.py --remove <slug> [<slug> ...]

Run from the repo root. papers.json writes reuse tag_papers.py's canonical
serializer (`audio_url` placed right after `explainer`, before `tags`) so diffs
stay minimal. The on-page block is delimited by marker comments and managed by
strip-then-reinsert, so every mode is idempotent: re-running is a no-op.
"""
import argparse
import json
import os
import re
import sys

# scripts/ is on sys.path[0] when run as `python scripts/inject_podcast.py`, so
# reuse the canonical papers.json serializer that tag_papers.py already owns.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tag_papers  # noqa: E402  (dumps_papers, PAPERS path)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(ROOT, "data", "papers.json")
PAPERS_DIR = os.path.join(ROOT, "public", "papers")

# Canonical node key order (mirrors scripts/tests/test_data_integrity.py's
# CANON_KEYS): audio_url sits right after explainer, before the optional tags.
CANON_KEYS = ["slug", "short", "title", "authors", "year", "date", "venue",
              "citation_count", "topic", "author_group", "abstract", "explainer",
              "audio_url", "tags"]

AUDIO_BASE = "https://pod.darvinyi.com/audio"
FEED_URL = "https://pod.darvinyi.com/feed.xml"


def canonical_url(slug):
    return f"{AUDIO_BASE}/{slug}.mp3"


# ── on-page block (idempotent via marker comments) ──────────────────────────
PILL_RE = re.compile(r"\n[ \t]*<!--pod-pill-->.*?<!--/pod-pill-->", re.S)
PLAYER_RE = re.compile(r"\n[ \t]*<!--pod-player-->.*?<!--/pod-player-->", re.S)
FACTS_RE = re.compile(r'(<div class="facts">)(.*?)(</div>)', re.S)
DEK_RE = re.compile(r'(<p class="dek">.*?</p>)', re.S)


def build_pill(url):
    return (f'<!--pod-pill--><span class="fact">'
            f'<a href="{url}">listen&nbsp;♪</a></span><!--/pod-pill-->')


def build_player(url):
    # 6-space indent to match the hero's block level; scoped <style> keeps the
    # page self-contained (the injector is the sole owner of the podcast CSS,
    # just as figures' base64 is injector-owned). audio{width:100%;max-width:
    # 100%} + a max-width:100% wrapper => cannot cause horizontal scroll, so no
    # @media rule is needed to satisfy the mobile contract.
    return (
        "      <!--pod-player-->\n"
        "      <style>\n"
        "      .podcast{background:var(--elev);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 22px}\n"
        "      .podcast .plabel{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--accent);letter-spacing:.04em;margin-bottom:9px}\n"
        "      .podcast audio{display:block;width:100%;max-width:100%}\n"
        "      .podcast .psub{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);margin-top:9px}\n"
        "      .podcast .psub a{color:var(--muted)}\n"
        "      </style>\n"
        '      <div class="podcast">\n'
        '        <div class="plabel">♪ listen — audio episode</div>\n'
        f'        <audio controls preload="none" src="{url}"></audio>\n'
        f'        <div class="psub">3-voice deep dive · <a href="{url}">mp3 ↗</a> · <a href="{FEED_URL}">rss feed ↗</a></div>\n'
        "      </div>\n"
        "      <!--/pod-player-->"
    )


def strip_page_block(html):
    """Remove any injected pill/player regions, restoring the pristine page."""
    html = PILL_RE.sub("", html)
    html = PLAYER_RE.sub("", html)
    return html


def sync_page(html, url):
    """Return html with the podcast block matching `url` (None => removed).
    strip-then-reinsert makes this idempotent and makes remove == the strip."""
    html = strip_page_block(html)
    if not url:
        return html

    if not DEK_RE.search(html) or not FACTS_RE.search(html):
        raise ValueError("page is missing the .dek or .facts hero anchor; "
                         "cannot inject the podcast block")

    # pill: append as the last chip in the fact row (after `source ↗`).
    def add_pill(m):
        inner = m.group(2)
        stripped = inner.rstrip("\n ")          # whitespace before </div>
        trailing = inner[len(stripped):]        # e.g. "\n      "
        return m.group(1) + stripped + "\n        " + build_pill(url) + trailing + m.group(3)

    html = FACTS_RE.sub(add_pill, html, count=1)
    # player: right after the dek paragraph.
    html = DEK_RE.sub(lambda m: m.group(1) + "\n" + build_player(url), html, count=1)
    return html


# ── papers.json helpers (deterministic writes) ──────────────────────────────
def load_papers():
    with open(PAPERS, encoding="utf-8") as f:
        return json.load(f)


def save_papers(d):
    tmp = PAPERS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(tag_papers.dumps_papers(d))
    os.replace(tmp, PAPERS)


def node_by_slug(d, slug):
    for p in d["papers"]:
        if p["slug"] == slug:
            return p
    return None


def reorder(node):
    """Rewrite the node in-place with canonical key order (present keys only)."""
    ordered = {k: node[k] for k in CANON_KEYS if k in node}
    extra = {k: v for k, v in node.items() if k not in CANON_KEYS}
    node.clear()
    node.update(ordered)
    node.update(extra)  # keep any unexpected keys rather than dropping them


# ── page write ──────────────────────────────────────────────────────────────
def page_path(slug):
    return os.path.join(PAPERS_DIR, f"{slug}.html")


def write_page(slug, url):
    """Sync one page to `url` (None strips). Returns True if the file changed."""
    path = page_path(slug)
    if not os.path.isfile(path):
        sys.exit(f"error: no explainer page for slug '{slug}': {path}")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    new = sync_page(html, url)
    if new != html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    return new != html


# ── commands ────────────────────────────────────────────────────────────────
def require_node(d, slug):
    node = node_by_slug(d, slug)
    if node is None:
        sys.exit(f"error: slug '{slug}' is not a node in papers.json")
    return node


def cmd_sync(slugs):
    """Default: sync each page from its node's current audio_url. HTML only."""
    d = load_papers()
    for slug in slugs:
        node = require_node(d, slug)
        url = node.get("audio_url")
        changed = write_page(slug, url)
        state = "player+pill" if url else "no episode (stripped)"
        print(f"{slug}: {state}{'' if changed else ' — already in sync'}")


def cmd_all():
    d = load_papers()
    touched = 0
    for node in d["papers"]:
        slug, url = node["slug"], node.get("audio_url")
        if write_page(slug, url):
            touched += 1
            print(f"{slug}: synced ({'player+pill' if url else 'stripped'})")
    print(f"\n{touched} page(s) changed across {len(d['papers'])} node(s).")


def cmd_set(slugs):
    d = load_papers()
    for slug in slugs:
        node = require_node(d, slug)
        url = canonical_url(slug)
        node["audio_url"] = url
        reorder(node)
    save_papers(d)
    for slug in slugs:
        write_page(slug, canonical_url(slug))
        print(f"{slug}: audio_url set → {canonical_url(slug)}; page synced (player+pill)")


def cmd_remove(slugs):
    d = load_papers()
    for slug in slugs:
        node = require_node(d, slug)
        node.pop("audio_url", None)
    save_papers(d)
    for slug in slugs:
        write_page(slug, None)
        print(f"{slug}: audio_url cleared; on-page block stripped")


def main():
    ap = argparse.ArgumentParser(
        description="Inject/refresh/remove a paper's podcast block from papers.json audio_url.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="sync every node's page from its audio_url")
    g.add_argument("--set", action="store_true",
                   help="stamp audio_url = canonical URL on each slug, then sync its page")
    g.add_argument("--remove", action="store_true",
                   help="clear audio_url on each slug and strip its on-page block")
    ap.add_argument("slugs", nargs="*", help="paper slug(s)")
    args = ap.parse_args()

    if args.all:
        if args.slugs:
            ap.error("--all takes no slugs")
        cmd_all()
    elif not args.slugs:
        ap.error("provide at least one slug (or use --all)")
    elif args.set:
        cmd_set(args.slugs)
    elif args.remove:
        cmd_remove(args.slugs)
    else:
        cmd_sync(args.slugs)


if __name__ == "__main__":
    main()
