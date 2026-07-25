#!/usr/bin/env python3
"""queue-ops for the /litsearch per-paper loop (PIPELINE_PLAN.md, Phase P).

Reads `work/<slug>/report.json`'s `queue_candidates`, dedupes them against
`data/papers.json` + `data/queue.json`, appends the survivors to
`data/queue.json`, and removes the just-processed entry.

**It is a queue, not a stack.** Both `core` and `foundational` candidates are
appended at the *bottom*. Pushing discovered papers onto the top turns the
pipeline into a depth-first crawl that tunnels into whatever the last paper
cited and starves the seeds the search was launched for. Ordering is corrected
periodically by `reprioritize_queue.py`, never by insertion position.

Dedup order is arxiv_id -> doi -> normalized title, matching
`scripts/tests/test_data_integrity.py`. arxiv_id is checked *first* and trusted
over titles: a title starting with a non-ASCII character (tau-bench) collapses
to a near-empty, falsely-distinct string under the ASCII-only normalization, so
a title-only check silently misses real duplicates.

Usage:
    python3 scripts/queue_ops.py <slug> [--survey benchmarks] [--apply]

Without --apply it prints the plan and writes nothing.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# canonical data/queue.json key order -- entries are written one per line as
# compact JSON so the file stays greppable and diffs stay readable
KEY_ORDER = ["title", "arxiv_id", "doi", "authors", "year", "venue",
             "citation_count", "topic", "priority", "source", "why",
             "survey", "role"]


def norm(t):
    """Normalization used by test_data_integrity.py's duplicate checks."""
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def load(rel):
    return json.loads((ROOT / rel).read_text())


def dump_queue(queue):
    lines = ["["]
    for i, entry in enumerate(queue):
        ordered = {k: entry[k] for k in KEY_ORDER if k in entry}
        for k in entry:  # preserve any unexpected keys rather than dropping them
            ordered.setdefault(k, entry[k])
        tail = "," if i < len(queue) - 1 else ""
        lines.append("  " + json.dumps(ordered, ensure_ascii=False,
                                       separators=(",", ":")) + tail)
    lines.append("]")
    return "\n".join(lines) + "\n"


def build_entry(cand, slug, survey, role):
    return {
        "title": cand.get("title"),
        "arxiv_id": cand.get("arxiv_id"),
        "doi": cand.get("doi"),
        "authors": cand.get("authors"),
        "year": cand.get("year"),
        "venue": cand.get("venue") or "arXiv",
        "citation_count": cand.get("citation_count"),
        "topic": cand.get("topic") or "Benchmarks & Evals",
        "priority": cand.get("priority") or "High",
        "source": cand.get("source") or f"Cited by {slug}",
        "why": cand.get("why", ""),
        "survey": survey,
        "role": role,
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--survey", default="benchmarks")
    ap.add_argument("--apply", action="store_true",
                    help="write data/queue.json (default is a dry-run preview)")
    a = ap.parse_args()

    papers = load("data/papers.json")["papers"]
    queue = load("data/queue.json")
    report = load(f"work/{a.slug}/report.json")

    # papers.json nodes carry no arxiv_id, so the graph is deduped by title --
    # the same basis test_queue_no_overlap_with_graph uses.
    graph_titles = {norm(p.get("title", "")) for p in papers}
    q_arxiv = {e["arxiv_id"] for e in queue if e.get("arxiv_id")}
    q_doi = {e["doi"] for e in queue if e.get("doi")}
    q_titles = {norm(e.get("title", "")) for e in queue}

    seen_arxiv, seen_titles = set(), set()

    def duplicate_reasons(cand):
        ax, doi = cand.get("arxiv_id"), cand.get("doi")
        nt = norm(cand.get("title", ""))
        reasons = []
        if ax and ax in q_arxiv:
            reasons.append(f"already queued (arxiv {ax})")
        if doi and doi in q_doi:
            reasons.append(f"already queued (doi {doi})")
        if nt and nt in q_titles:
            reasons.append("already queued (title)")
        if nt and nt in graph_titles:
            reasons.append("already a graph node (title)")
        if ax and ax in seen_arxiv:
            reasons.append("duplicate within this batch (arxiv)")
        if nt and nt in seen_titles:
            reasons.append("duplicate within this batch (title)")
        return reasons

    candidates = report.get("queue_candidates", {})
    if isinstance(candidates, list):  # tolerate a flat list
        candidates = {"core": candidates, "foundational": []}

    accepted, skipped = [], []
    for role in ("core", "foundational"):
        for cand in candidates.get(role, []):
            # A foundational candidate with no arXiv id is out of scope for an
            # ML/eval atlas -- these are pre-internet psych/humanities classics
            # (Maslow, Goffman, ELIZA) that can never become nodes, and
            # foundational entries are not processed anyway.
            if role == "foundational" and not cand.get("arxiv_id"):
                skipped.append((role, cand,
                                ["foundational with no arXiv id - out of atlas scope"]))
                continue
            reasons = duplicate_reasons(cand)
            if reasons:
                skipped.append((role, cand, reasons))
                continue
            if cand.get("arxiv_id"):
                seen_arxiv.add(cand["arxiv_id"])
            if norm(cand.get("title", "")):
                seen_titles.add(norm(cand.get("title", "")))
            accepted.append(build_entry(cand, a.slug, a.survey, role))

    # Remove the just-processed entry. Matching the in-progress paper from the
    # state file (not the report) keeps this correct on a resumed run.
    state = load(f"data/litsearch/{a.survey}.state.json")
    current = state.get("current") or {}
    proc_title, proc_arxiv = current.get("queue_title"), current.get("arxiv_id")

    def is_processed(e):
        if proc_arxiv and e.get("arxiv_id") == proc_arxiv:
            return True
        return bool(proc_title) and norm(e.get("title", "")) == norm(proc_title)

    removed = [e for e in queue if is_processed(e)]
    remaining = [e for e in queue if not is_processed(e)]
    new_queue = remaining + accepted  # appended at the bottom: queue, not stack

    print(f"=== queue-ops for {a.slug} (survey={a.survey}) ===")
    print(f"processed entry removed: {len(removed)}"
          f" (title={proc_title!r}, arxiv={proc_arxiv})")
    print(f"appended at bottom: {len(accepted)}")
    for e in accepted:
        ident = e["arxiv_id"] or e["doi"] or "-"
        print(f"   + [{e['role']:12s}] {ident:18s} | {(e['title'] or '')[:58]}")
    print(f"skipped: {len(skipped)}")
    for role, cand, reasons in skipped:
        ident = cand.get("arxiv_id") or cand.get("doi") or "-"
        print(f"   - [{role:12s}] {ident:18s} | "
              f"{(cand.get('title') or '')[:44]} :: {'; '.join(reasons)}")
    print(f"queue length: {len(queue)} -> {len(new_queue)}")

    if a.apply:
        (ROOT / "data/queue.json").write_text(dump_queue(new_queue))
        print("APPLIED.")
    else:
        print("(dry run - pass --apply to write)")


if __name__ == "__main__":
    main()
