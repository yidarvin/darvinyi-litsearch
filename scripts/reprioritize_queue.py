#!/usr/bin/env python3
"""Reprioritize a survey's `core` queue entries in data/queue.json.

The /litsearch pipeline always processes the *first* `core` entry for a survey
in file order, so file order is the priority. Insertion order alone drifts badly
-- papers discovered while processing land at the bottom in citation-blind
arrival order, and the genuinely important seeds can end up behind them. Re-run
this every so often to restore a sane head of the queue.

Score (higher first), deliberately simple so a human can audit the printed table.
There are two scoring paths, because what "relevant" means depends on the survey.

`benchmarks` -- the original, unchanged:

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

every other survey -- citation-led, with relevance as a modifier:

    score = citations + 0.5 * relevance

  relevance in [0,1], starting from a neutral 0.5 and moved by that survey's
  PROFILE below -- or left flat at 0.5 when the survey has no profile, which
  makes the score a pure citation sort. For a profiled survey:
      +0.10  `topic` is one this survey cares about
      +0.25  a failure/phenomenon term in the title
      +0.10  a failure/phenomenon term in the `why` (our own gloss, so weaker
             evidence than the paper's own title)
      +0.20  a "canonical entry" term in the title -- survey, taxonomy,
             characterization: the papers a survey cites first
      -0.20  a term whose rubric sentence says the paper BELONGS to another
             survey (dataset/benchmark/metric)
      -0.15  a term the rubric admits only conditionally (mitigation, method)

Why the two paths differ, since it looks like an inconsistency:

1. The benchmarks weighting assumes the queue mixes benchmark and non-benchmark
   papers, so relevance has to dominate to separate them. That was true of the
   general queue this script was written against. It is NOT true of a survey's
   `core` entries: those were stamped `survey`/`role` by /litsearch only after
   passing that survey's `description` rubric, so membership is already decided
   and relevance is close to uniform inside the set. With membership settled,
   citation count is the main remaining signal and relevance is a tiebreaker.
2. Relevance weighted 2x against citations capped at 1.0 means the relevance
   tier wins absolutely: on failure-modes it put eleven papers with 11-228
   citations above a 616-citation hallucination survey, purely because their
   titles contained "Eval" or "Bench".

Known and left alone: the failure-modes head is hallucination-heavy (14 of the
top 20). That is the queue's real shape rather than a scoring artifact --
hallucination is 23% of its `core` entries and its median citation count is 241
against 14-140 for every other failure class -- so any citation-led order
surfaces it first. The `canonical` term does the part worth doing, putting the
surveys and characterizations ahead of the Nth mitigation method. Forcing spread
across failure classes would need a diversity/round-robin mechanism, which is a
different feature and would override the citation signal on purpose.

A survey's terms are NOT derived automatically from its `description` in
data/surveys.json, which is the obvious idea and was tried first. The rubrics
state scope in both directions -- "In scope: ... Distinct from ... are out" --
so 39 of the 90 content words in the failure-modes description sit inside its
out-of-scope sentences. Extracting terms naively scores `dataset`, `benchmarks`,
`agent`, `frameworks` and `capability` as positive for a survey whose rubric
explicitly routes those papers elsewhere: the exact inversion this change exists
to fix. Telling the two apart needs sentence polarity, not word extraction, and
the benchmarks description carries no "In scope:" marker to key off at all. So
the terms below are written by hand FROM each description, and each profile
records which description sentence it came from.

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

# Per-survey relevance profiles for every survey EXCEPT `benchmarks`, which keeps
# the legacy path above so its existing orderings do not churn.
#
# Each profile is written by hand from that survey's `description` in
# data/surveys.json, quoting the sentence it came from. Keep them in sync by
# hand when a description changes -- see the module docstring for why these are
# not extracted from the description automatically.
#
#   topics    -- `topic` values that count as on-rubric for this survey. Omit or
#                leave empty when the field carries no signal for it.
#   positive  -- the failure/method vocabulary the rubric puts IN scope.
#   negative  -- vocabulary the rubric routes to a DIFFERENT survey. Scored
#                negatively, not merely ignored: for failure-modes a
#                benchmark-titled paper is one the rubric says belongs under
#                `benchmarks` and carries this tag only additionally.
PROFILES = {
    "failure-modes": {
        # "In scope: hallucination and factual-error analyses, sycophancy, reward
        #  hacking and specification gaming, jailbreaks and prompt injection ...
        #  tool-use and function-calling breakdowns, error compounding and
        #  cascading ..., long-horizon planning collapse, goal misgeneralization,
        #  deception, situational awareness and sandbagging, unfaithful
        #  reasoning, and failure taxonomies or red-team studies"
        #
        # Names of failure PHENOMENA only. Words for the response to a failure
        # (mitigate, defend, guardrail, safety, risk, harm) are deliberately not
        # here: the rubric admits those papers conditionally, and scoring them as
        # phenomenon vocabulary fired on 82% of the queue, which is no signal.
        "topics": {"safety & red-teaming", "oversight", "agents"},
        "positive": re.compile(
            r"\b(hallucinat\w+|confabulat\w+|sycophan\w+|decept\w+"
            r"|scheming|sandbagg\w*|situational\s+awareness|specification\s+gaming"
            r"|reward\s+hack\w*|reward\s+tamper\w*|goal\s+misgeneral\w+"
            r"|misgeneraliz\w+|jailbreak\w*|prompt\s+injection|backdoor\w*"
            r"|unfaithful\w*|faithfulness|failure\s+mode\w*|failure\s+attribution"
            r"|error\s+(compound\w+|cascad\w+|propagat\w+)|overrefusal"
            r"|over[\s-]?refusal|misalign\w+|power[\s-]?seeking|self[\s-]?preservation)\b",
            re.IGNORECASE),
        # "...naming, taxonomizing, or empirically demonstrating a failure
        #  phenomenon", "and failure taxonomies or red-team studies that name and
        #  characterize a failure class."
        #
        # The rubric wants papers that NAME a failure class. Those are the entries
        # a survey cites first, so they outrank the Nth method that reduces an
        # already-named failure. Without this the head fills with mitigation
        # papers from whichever failure class happens to be best cited.
        "canonical": re.compile(
            r"\b(survey|taxonom\w+|characteri[sz]\w+|a\s+study\s+of|analy[sz]\w+"
            r"|position\s+paper|red[\s-]?team\w*|why\s+\w+\s+fail|how\s+\w+\s+fail"
            r"|anatomy|landscape|systematic\s+review|empirical\s+stud\w+)\b",
            re.IGNORECASE),
        # Two demotions, from two different rubric sentences with different
        # force. Neither is an exclusion — both kinds of paper can be real
        # members — so a phenomenon or canonical hit must be able to outweigh
        # them. Keep them separate rather than blending into one penalty: a
        # single -0.25 exactly cancelled a +0.25 phenomenon hit, which scored a
        # hallucination-mitigation paper identically to an off-rubric scaling-laws
        # paper.
        #
        # "Distinct from Benchmarks (named datasets/suites) and Evaluations (a new
        #  way to evaluate): a paper whose headline contribution is a dataset or a
        #  metric belongs there, and carries this tag additionally only when it
        #  genuinely characterizes the failure phenomenon as well."
        # -> the rubric says these BELONG elsewhere: the stronger demotion.
        "negative_routed": re.compile(
            r"(bench\w*)|\b(dataset|suite|leaderboard|arena|metric)\b",
            re.IGNORECASE),
        # "Mitigation, defense, guardrail, and alignment papers are members when
        #  they diagnose the failure they address (a jailbreak defense that first
        #  characterizes the attack surface is in; a general training method that
        #  merely reports fewer errors is out)."
        # -> conditional members, not relocated ones: the weaker demotion.
        "negative_method": re.compile(
            r"\b(mitigat\w+|alleviat\w+|reduc\w+|correct\w+|preventing"
            r"|suppress\w+|improv\w+|enhanc\w+|boost\w+)\b",
            re.IGNORECASE),
    },
    # `evaluations` has no profile yet and currently has no queue entries at all
    # (it was tagged by hand via Procedure D, never seeded through /litsearch).
    # With no profile it falls through to the flat-relevance path, i.e. a plain
    # citation sort over its core entries -- the right default until there are
    # entries to tune against.
}

# Weights for the profiled/unprofiled path. Relevance is deliberately worth less
# than a full citation decade here: membership is already settled for a `core`
# entry, so relevance breaks ties rather than deciding the order.
REL_WEIGHT = 0.5
NEUTRAL_RELEVANCE = 0.5


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


def bench_relevance(entry):
    """The original benchmarks-survey relevance. Unchanged on purpose."""
    r = 0.0
    if (entry.get("topic") or "").strip().lower() == "benchmarks & evals":
        r += 0.45
    if BENCH_KEYWORDS.search(entry.get("title") or ""):
        r += 0.35
    if BENCH_KEYWORDS.search(entry.get("why") or ""):
        r += 0.20
    return min(r, 1.0)


def profile_relevance(entry, profile):
    """Relevance for a survey with a PROFILE, in [0,1] around a 0.5 neutral.

    Positive terms in the title move it up, in the `why` move it up half as much
    (a `why` is our own one-line gloss, so it is weaker evidence than the paper's
    own title). Negative terms in the title pull it down, because the rubric puts
    those papers under a different survey.
    """
    r = NEUTRAL_RELEVANCE
    title = entry.get("title") or ""
    why = entry.get("why") or ""
    topics = profile.get("topics") or set()
    pos = profile.get("positive")
    canon = profile.get("canonical")
    routed = profile.get("negative_routed")
    method = profile.get("negative_method")

    if topics and (entry.get("topic") or "").strip().lower() in topics:
        r += 0.10
    if pos:
        if pos.search(title):
            r += 0.25
        if pos.search(why):
            r += 0.10
    if canon and canon.search(title):
        r += 0.20
    if routed and routed.search(title):
        r -= 0.20
    if method and method.search(title):
        r -= 0.15
    return max(0.0, min(r, 1.0))


def relevance(entry, survey=None):
    """Relevance for `entry` under `survey`'s scoring path."""
    if survey == "benchmarks" or survey is None:
        return bench_relevance(entry)
    profile = PROFILES.get(survey)
    if profile is None:
        # No profile: flat relevance, so `score` reduces to a pure citation sort.
        return NEUTRAL_RELEVANCE
    return profile_relevance(entry, profile)


def citation_score(entry):
    c = entry.get("citation_count")
    if not c or c < 0:
        return 0.0
    return min(math.log10(c + 1) / 5.0, 1.0)


def score(entry, survey=None):
    if survey == "benchmarks" or survey is None:
        return 2.0 * bench_relevance(entry) + citation_score(entry)
    return citation_score(entry) + REL_WEIGHT * relevance(entry, survey)


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
    sv = a.survey
    ranked = sorted(entries, key=lambda e: (-score(e, sv), (e.get("title") or "").lower()))

    if sv == "benchmarks":
        how = "2.0*relevance + citations (benchmarks keyword profile)"
    elif sv in PROFILES:
        how = f"citations + {REL_WEIGHT}*relevance ('{sv}' keyword profile)"
    else:
        how = (f"citations only (no relevance profile for '{sv}' - "
               f"membership already settled by its rubric)")
    print(f"\n=== reprioritized head of '{sv}' core queue "
          f"({len(ranked)} entries) ===")
    print(f"scoring: {how}")
    print(f"{'#':>3}  {'score':>5}  {'rel':>4}  {'cites':>6}  title")
    for rank, e in enumerate(ranked[:a.limit], 1):
        cites = e.get("citation_count")
        print(f"{rank:>3}  {score(e, sv):>5.2f}  {relevance(e, sv):>4.2f}  "
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
