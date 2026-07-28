#!/usr/bin/env python3
"""Reprioritize a survey's `core` queue entries in data/queue.json.

The /litsearch pipeline always processes the *first* `core` entry for a survey
in file order, so file order is the priority. Insertion order alone drifts badly
-- papers discovered while processing land at the bottom in citation-blind
arrival order, and the genuinely important seeds can end up behind them. Re-run
this every so often to restore a sane head of the queue.

Score (higher first), deliberately simple so a human can audit the printed table:

    score = 2.0 * relevance + 1.0 * citations

  relevance in [0,1] -- is this a benchmark/eval paper?
      0.45  topic == "Benchmarks & Evals"
      0.35  a benchmark/eval keyword in the title
      0.20  a benchmark/eval keyword in the `why`
  citations in [0,1] -- log10(citation_count + 1) / 5, clipped
      (5 == 100k citations; log keeps a 40k-citation foundational paper from
      swamping every purpose-built benchmark, matching how the map caps node
      size for the same reason)

Relevance is weighted 2x so benchmark papers outrank better-cited non-benchmark
ones, while citations still order papers within the same relevance tier.

Entries with a null `citation_count` are backfilled from Semantic Scholar first
(batch endpoint, `$S2_API_KEY` honoured per CLAUDE.md). Anything still unknown
scores 0 for citations and is flagged in the output rather than guessed.

CAVEAT -- the backfill looks up `arXiv:<id>`, and for a paper RETITLED between
preprint and camera-ready that id can resolve to a stale preprint record whose
citation count is a small fraction of the real one. EmpatheticDialogues is the
worst case seen: `arXiv:1811.00207` returns "I Know the Feeling: Learning to
Converse with Empathy" with 51 citations, while the ACL camera-ready record
(P19-1534) has 1195 -- a 23x undercount that ranks a foundational dataset like
a minor workshop paper. There is no cheap automatic fix (the two records aren't
cross-linked), so treat a surprisingly low count on a well-known paper as
suspect and re-search S2 by the camera-ready title before trusting the order.

Only the ordering of that survey's `core` entries changes: each keeps one of the
slots those entries already occupied, so the ~1,000 hand-curated general entries
and every `foundational` entry stay exactly where they are. Nothing is added,
dropped, or edited.

Usage:
    python3 scripts/reprioritize_queue.py <survey_id> [--apply] [--no-backfill]
                                          [--limit N]

Without --apply it prints the plan and writes nothing.
"""
import argparse
import json
import math
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"

KEY_ORDER = ["title", "arxiv_id", "doi", "authors", "year", "venue",
             "citation_count", "topic", "priority", "source", "why",
             "survey", "role"]

# Words that signal the paper's contribution *is* an evaluation artifact.
# `bench`/`eval` are matched as bare substrings, NOT \b-anchored: this corpus is
# full of compound benchmark names (AssistantBench, SWE-bench, TaskBench,
# tau-bench) where the token is glued to a preceding word, and a \b would score
# them as non-benchmarks. The remaining nouns are \b-anchored because they are
# ordinary words that would over-match as substrings.
BENCH_KEYWORDS = re.compile(
    r"(bench\w*|eval\w*)"
    r"|\b(dataset|test\s?bed|suite|arena|leaderboard|challenge|probe"
    r"|diagnostic|task\s?set|question\s?answering|qa)\b",
    re.IGNORECASE)


def dump_queue(queue):
    lines = ["["]
    for i, entry in enumerate(queue):
        ordered = {k: entry[k] for k in KEY_ORDER if k in entry}
        for k in entry:
            ordered.setdefault(k, entry[k])
        tail = "," if i < len(queue) - 1 else ""
        lines.append("  " + json.dumps(ordered, ensure_ascii=False,
                                       separators=(",", ":")) + tail)
    lines.append("]")
    return "\n".join(lines) + "\n"


def relevance(entry):
    r = 0.0
    if (entry.get("topic") or "").strip().lower() == "benchmarks & evals":
        r += 0.45
    if BENCH_KEYWORDS.search(entry.get("title") or ""):
        r += 0.35
    if BENCH_KEYWORDS.search(entry.get("why") or ""):
        r += 0.20
    return min(r, 1.0)


def citation_score(entry):
    c = entry.get("citation_count")
    if not c or c < 0:
        return 0.0
    return min(math.log10(c + 1) / 5.0, 1.0)


def score(entry):
    return 2.0 * relevance(entry) + citation_score(entry)


def backfill_citations(entries):
    """Fill null citation_counts from S2's batch endpoint. Returns (filled, failed)."""
    need = [e for e in entries if e.get("citation_count") is None and e.get("arxiv_id")]
    if not need:
        return 0, 0
    key = os.environ.get("S2_API_KEY")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["x-api-key"] = key
    filled = 0
    # the batch endpoint caps at 500 ids per call
    for i in range(0, len(need), 100):
        chunk = need[i:i + 100]
        body = json.dumps({"ids": [f"arXiv:{e['arxiv_id']}" for e in chunk]}).encode()
        req = urllib.request.Request(
            S2_BATCH + "?fields=citationCount", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                results = json.load(resp)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            print(f"  ! S2 batch failed for chunk {i // 100}: {exc}")
            continue
        for entry, result in zip(chunk, results):
            if result and result.get("citationCount") is not None:
                entry["citation_count"] = result["citationCount"]
                filled += 1
    return filled, len(need) - filled


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("survey")
    ap.add_argument("--apply", action="store_true",
                    help="write data/queue.json (default is a dry-run preview)")
    ap.add_argument("--no-backfill", action="store_true",
                    help="skip the Semantic Scholar citation backfill")
    ap.add_argument("--limit", type=int, default=20,
                    help="how many rows of the new head to print (default 20)")
    a = ap.parse_args()

    queue_path = ROOT / "data/queue.json"
    queue = json.loads(queue_path.read_text())

    slots = [i for i, e in enumerate(queue)
             if e.get("survey") == a.survey and e.get("role") == "core"]
    if not slots:
        print(f"no `core` queue entries for survey '{a.survey}' - nothing to do.")
        return
    entries = [queue[i] for i in slots]

    if not a.no_backfill:
        filled, failed = backfill_citations(entries)
        print(f"citation backfill: {filled} filled"
              + (f", {failed} still unknown" if failed else ""))

    before = [e.get("title") for e in entries]
    ranked = sorted(entries, key=lambda e: (-score(e), (e.get("title") or "").lower()))

    print(f"\n=== reprioritized head of '{a.survey}' core queue "
          f"({len(ranked)} entries) ===")
    print(f"{'#':>3}  {'score':>5}  {'rel':>4}  {'cites':>6}  title")
    for rank, e in enumerate(ranked[:a.limit], 1):
        cites = e.get("citation_count")
        print(f"{rank:>3}  {score(e):>5.2f}  {relevance(e):>4.2f}  "
              f"{(cites if cites is not None else '?'):>6}  {(e.get('title') or '')[:62]}")
    if len(ranked) > a.limit:
        print(f"     ... {len(ranked) - a.limit} more")

    moved = sum(1 for b, r in zip(before, [e.get("title") for e in ranked]) if b != r)
    print(f"\n{moved} of {len(ranked)} entries change position.")

    for slot, entry in zip(slots, ranked):
        queue[slot] = entry

    if a.apply:
        queue_path.write_text(dump_queue(queue))
        print("APPLIED.")
    else:
        print("(dry run - pass --apply to write)")


if __name__ == "__main__":
    main()
