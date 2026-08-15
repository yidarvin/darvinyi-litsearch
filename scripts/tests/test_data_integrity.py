"""Read-only invariants over data/papers.json, data/queue.json, and
data/surveys.json. Mirrors the checks in .critique/check_data.py (the ad-hoc
audit script from the repo-critique run) as durable, CI-checkable assertions.

Run: pytest scripts/tests/test_data_integrity.py -v
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
CANON_KEYS = ["slug", "short", "title", "authors", "year", "date", "venue",
              "citation_count", "topic", "author_group", "abstract", "explainer",
              "audio_url", "tags"]

# The deterministic podcast URL scheme (scripts/inject_podcast.py); a node's
# optional `audio_url` must be exactly this when present.
AUDIO_URL_FMT = "https://pod.darvinyi.com/audio/{slug}.mp3"

# benchmarks-taxonomy.json's controlled vocabulary, mirrored from the definitions in
# scripts/benchmarks_survey/build_survey_page.py (DOM_L, SHAPES, GR, LEV, PROV, CONTAM,
# TOOL_L, KING_L, FAM_L) — keep these two in sync if that file's vocab changes; this is
# the survey-author's schema to extend deliberately, not to drift accidentally.
BENCH_DOMAINS = {"coding", "math", "science", "knowledge", "language", "reasoning", "agentic-web",
                  "tool-use", "professional", "ai-rd", "safety", "instruction-following",
                  "long-context", "multimodal", "conversation", "forecasting", "social-moral"}
BENCH_SHAPES = {"single-turn", "multi-turn", "interactive-env"}
BENCH_GRADING = {"proxy-metric", "exact-match", "programmatic", "human", "llm-judge", "rubric-judge"}
BENCH_COMPLEXITY = {"L1-seconds", "L2-minutes", "L3-hours", "L4-days", "L5-weeks"}
BENCH_PROVENANCE = {"crowdsourced", "exam-derived", "aggregated", "synthetic-generated",
                     "user-traffic", "expert-authored", "real-work-mined"}
BENCH_CONTAM = {"none-public", "canary", "procedural", "private-holdout", "live-refresh"}
BENCH_SATURATION = {"saturated", "closing", "open", "not-applicable"}
BENCH_TOOLS = {"none", "code-exec", "search-retrieval", "browser", "computer-os", "domain-api"}
BENCH_KINGDOMS = {"A-capability", "B-audit", "C-frontier-walls", "D-deployment", "E-hazard",
                   "F-reward-factories", "G-meta-evaluation"}
BENCH_FAMILIES = {
    "A1-perception-parsing", "A2-knowledge-exams", "A3-closed-form-reasoning",
    "A4-program-synthesis", "A5-embodied-operation", "A6-tool-orchestration",
    "A7-communication", "A8-research-execution",
    "B1-contamination-twins", "B2-grader-hardening", "B3-desaturation-sequels", "B4-construct-audits",
    "C1-summit-exams", "C2-inverse-verification", "C3-living-walls",
    "D1-economic-rehearsals", "D2-occupational-probes", "D3-collaboration-rehearsals",
    "E1-attack-surfaces", "E2-dangerous-capability-propensity", "E3-values-judgment",
    "F1-reward-factories",
    "G1-panoramas", "G2-preference-protocols", "G3-grader-benchmarks",
}
BENCH_TAXONOMY_REQUIRED_KEYS = {
    "slug", "short", "title", "year", "date", "venue", "group", "citations", "explainer",
    "evals_tag", "domain_primary", "domain_secondary", "task_shape", "grading_primary",
    "grading_all", "complexity", "human_time", "tool_access", "provenance",
    "contamination_defense", "saturation", "frontier_score", "items_count", "one_line",
    "confidence", "notes", "kingdom", "family", "placement_reason", "lineage", "dynasty",
    "gravity",
}

# failure-modes-taxonomy.json's controlled vocabulary. Six analytic facets (elicitation is
# the survey's novel organizing axis) plus an 8-kingdom/36-family placement tree and a
# lineage graph. Keep this in sync with the survey builder when the schema is extended;
# this is the survey-author's schema to grow deliberately, not to drift into.
FM_ELICITATION = {"spontaneous", "prompted", "optimized", "constructed-scenario",
                  "trained-in", "not-elicited"}
# Trimmed to the three values the corpus actually uses. "shown-insensitive" and
# "discussed-untested" were declared in the first draft and had zero members: no
# paper in the corpus reports a null evaluation-awareness effect, and the
# explainers don't reliably distinguish authors who raise the confound without
# measuring it. That absence is a finding for the prose, not a vocabulary slot —
# a closed vocab with dead values invites a reader to wonder what's missing.
FM_EVAL_AWARENESS = {"shown-sensitive", "not-tested", "n-a"}
FM_LOCUS = {"weights-prior", "context-window", "reasoning-trace", "agent-trajectory",
            "multi-agent-system", "training-loop", "eval-harness", "deployment-system"}
FM_EVIDENCE = {"behavioural-rate", "controlled-counterfactual", "internals-probe",
               "formal-proof", "corpus-synthesis", "case-demonstration"}
FM_DETECTABILITY = {"output-alone", "needs-ground-truth", "needs-trace", "needs-internals",
                    "needs-counterfactual", "undetectable-in-practice"}
FM_MITIGATION = {"none-proposed", "proposed-untested", "partial-mitigation",
                 "effective-mitigation", "defenses-fail"}
FM_HARM_BEARER = {"user", "third-party", "operator", "society", "research-integrity"}
# Same rule as FM_EVAL_AWARENESS above: "attacks" and "audits" were declared in the
# first draft and never used by any of the lineage edges, and a closed vocab with dead
# slots invites a reader to wonder what's missing. Trimmed to the seven in use.
FM_RELATIONS = {"descends-from", "responds-to", "generalizes", "formalizes",
                "defends-against", "measures", "qualifies"}
# Relations that assert the child was built on top of an existing parent, so a parent
# dated after its child is an inverted edge. Checked strictly: no tolerance, because
# with the right relations selected there is nothing to tolerate (the worst forward gap
# among these is 0 months).
#
# `responds-to` is deliberately NOT here. A node's `date` is its arXiv v1 month, but a
# paper responds to the literature as of whatever version made the response — Carroll's
# manipulation paper is dated 2023-03 (v1) and appeared at EAAMO in October 2023, so its
# camera-ready can engage an August 2023 paper with no simultaneity involved at all. That
# gap has no principled ceiling, so a month threshold on `responds-to` would be a fitted
# number wearing a mechanism's name. Excluding the relation states the actual rule: any
# version of a paper may respond to anything published before that version.
#
# Five inverted ancestral edges were found and removed in survey critique round 1 (two of
# which already carried the correct reverse edge, making the graph contain contradictory
# 2-cycles).
FM_ANCESTRAL_RELATIONS = {"descends-from", "generalizes", "formalizes"}
FM_KINGDOMS = {"A-objective-corruption", "B-competence-cliffs", "C-truthfulness-breakdown",
               "D-interaction-failure", "E-oversight-erosion", "F-adversarial-breach",
               "G-agentic-breakdown", "H-measurement-integrity"}
FM_FAMILIES = {
    "A1-failure-taxonomies", "A2-overoptimization-dynamics", "A3-goal-misgeneralization",
    "B1-reasoning-collapse", "B2-knowledge-asymmetry", "B3-context-degradation",
    "B4-instruction-adherence",
    "C1-hallucination-foundations", "C2-source-faithfulness", "C3-perceptual-hallucination",
    "C4-imitative-falsehood", "C5-strategic-falsehood",
    "D1-sycophancy", "D2-manipulation", "D3-refusal-miscalibration",
    "E1-cot-unfaithfulness", "E2-monitor-evasion", "E3-deception-and-propensity",
    "F1-handcrafted-jailbreaks", "F2-optimized-jailbreaks", "F3-prompt-injection",
    "F4-defenses-and-durability", "F5-attack-suites", "F6-red-team-generation",
    "F7-hazard-uplift",
    "G1-long-horizon-collapse", "G2-multi-agent-breakdown", "G3-tool-use-failures",
    "G4-failure-attribution", "G5-deployment-conduct-envs", "G6-clarification-and-escalation",
    "G7-agentic-risk-foundations",
    "H1-judge-bias", "H2-prompt-fragility", "H3-harness-validity", "H4-metric-meta-evaluation",
}
FM_TAXONOMY_REQUIRED_KEYS = {
    "slug", "short", "title", "year", "date", "venue", "group", "citations", "explainer",
    "elicitation", "elicitation_reason", "eval_awareness", "locus", "evidence_mode",
    "detectability", "mitigation_status", "harm_bearer", "kingdom", "family",
    "placement_reason", "lineage", "gravity", "one_line", "key_number", "confidence",
}
# Optional per-facet justifications, written where a call is non-obvious. A key that is
# present must carry text — an empty reason is worse than no reason.
FM_TAXONOMY_OPTIONAL_KEYS = {
    "eval_awareness_reason", "locus_reason", "evidence_mode_reason", "detectability_reason",
    "mitigation_status_reason", "harm_bearer_reason", "notes",
}


@pytest.fixture(scope="module")
def papers_data():
    return json.loads((ROOT / "data" / "papers.json").read_text())


@pytest.fixture(scope="module")
def papers(papers_data):
    return papers_data["papers"]


@pytest.fixture(scope="module")
def edges(papers_data):
    return papers_data["edges"]


@pytest.fixture(scope="module")
def surveys():
    return json.loads((ROOT / "data" / "surveys.json").read_text())["surveys"]


@pytest.fixture(scope="module")
def survey_ids(surveys):
    return {s["id"] for s in surveys}


@pytest.fixture(scope="module")
def queue():
    return json.loads((ROOT / "data" / "queue.json").read_text())


@pytest.fixture(scope="module")
def benchmarks_taxonomy():
    return json.loads((ROOT / "data" / "benchmarks-taxonomy.json").read_text())


@pytest.fixture(scope="module")
def failure_modes_taxonomy():
    return json.loads((ROOT / "data" / "failure-modes-taxonomy.json").read_text())


def test_no_duplicate_slugs(papers):
    slugs = [p["slug"] for p in papers]
    assert len(slugs) == len(set(slugs)), "duplicate slug(s) in papers.json"


def test_canonical_key_order(papers):
    bad = []
    for p in papers:
        want = [k for k in CANON_KEYS if k in p]
        if list(p.keys()) != want:
            bad.append(p["slug"])
    assert not bad, f"non-canonical key order: {bad}"


def test_date_format_and_year_consistency(papers):
    """`date` must be YYYY-MM; a year mismatch is allowed (preprint vs venue
    year, see CLAUDE.md's date-vs-year policy) but must be a real calendar month."""
    bad_format = []
    for p in papers:
        if not re.fullmatch(r"\d{4}-\d{2}", str(p.get("date", ""))):
            bad_format.append(p["slug"])
            continue
        month = int(p["date"][5:7])
        if not (1 <= month <= 12):
            bad_format.append(p["slug"])
    assert not bad_format, f"malformed date field: {bad_format}"


def test_citation_count_present(papers):
    missing = [p["slug"] for p in papers if p.get("citation_count") is None]
    assert not missing, f"missing citation_count: {missing}"


def test_abstract_nonempty(papers):
    empty = [p["slug"] for p in papers if not p.get("abstract", "").strip()]
    assert not empty, f"empty abstract: {empty}"


def test_tags_sorted_deduped_and_known(papers, survey_ids):
    bad = []
    for p in papers:
        if "tags" not in p:
            continue
        tags = p["tags"]
        if tags != sorted(set(tags)) or not set(tags) <= survey_ids:
            bad.append((p["slug"], tags))
    assert not bad, f"bad tags: {bad}"


def test_audio_url_is_canonical(papers):
    """`audio_url` must be the deterministic published URL for that slug — the
    explainer's on-page player and the injector (scripts/inject_podcast.py) both
    assume it."""
    bad = [(p["slug"], p["audio_url"]) for p in papers
           if p.get("audio_url") is not None
           and p["audio_url"] != AUDIO_URL_FMT.format(slug=p["slug"])]
    assert not bad, f"non-canonical audio_url: {bad}"


def test_every_node_has_a_podcast_episode(papers):
    """A paper is not done until its TTS episode is published and linked
    (CLAUDE.md), so a node without an `audio_url` is unfinished work, not a
    normal state. `litsearch.py complete-paper` enforces the same invariant at
    write time; this catches anything that got in another way — a hand-added
    node, or a `git checkout` that reverted an injector run."""
    missing = [p["slug"] for p in papers if not p.get("audio_url")]
    assert not missing, (
        f"{len(missing)} node(s) with no podcast episode: {missing}. "
        f"Produce each via the litsearch-podcast skill in ~/Projects/darvinyi-podcast, "
        f"then link with `python3 scripts/inject_podcast.py --set <slug>`.")


def test_explainer_files_exist(papers):
    missing = [p["slug"] for p in papers
               if not (ROOT / "public" / p["explainer"]).exists()]
    assert not missing, f"node references missing explainer file: {missing}"


def test_no_orphan_explainer_files(papers):
    referenced = {p["explainer"].split("/")[-1] for p in papers}
    on_disk = {f.name for f in (ROOT / "public" / "papers").glob("*.html")}
    orphans = on_disk - referenced
    assert not orphans, f"explainer file with no owning node: {orphans}"


def test_edges_reference_existing_nodes(papers, edges):
    slugs = {p["slug"] for p in papers}
    dangling = [e for e in edges if e["from"] not in slugs or e["to"] not in slugs]
    assert not dangling, f"dangling edge(s): {dangling}"


def test_no_duplicate_or_self_edges(edges):
    seen = set()
    dupes, selfies = [], []
    for e in edges:
        key = (e["from"], e["to"])
        if e["from"] == e["to"]:
            selfies.append(key)
        if key in seen:
            dupes.append(key)
        seen.add(key)
    assert not dupes, f"duplicate edge(s): {dupes}"
    assert not selfies, f"self edge(s): {selfies}"


def test_no_isolated_nodes(papers, edges):
    """Every node should have at least one citation edge in or out — a
    degree-0 node is either mis-linked or a processing artifact."""
    slugs = {p["slug"] for p in papers}
    degree = {s: 0 for s in slugs}
    for e in edges:
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1
    isolated = [s for s, d in degree.items() if d == 0]
    assert not isolated, f"isolated node(s): {isolated}"


def test_queue_no_internal_duplicates(queue):
    def norm(t):
        return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
    titles = [norm(q["title"]) for q in queue]
    dupes = {t for t in titles if titles.count(t) > 1}
    assert not dupes, f"duplicate title(s) in queue.json: {dupes}"
    ids = [q["arxiv_id"] for q in queue if q.get("arxiv_id")]
    id_dupes = {i for i in ids if ids.count(i) > 1}
    assert not id_dupes, f"duplicate arxiv_id(s) in queue.json: {id_dupes}"


def test_queue_no_overlap_with_graph(queue, papers):
    def norm(t):
        return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
    paper_titles = {norm(p["title"]) for p in papers}
    overlap = [q["title"] for q in queue if norm(q["title"]) in paper_titles]
    assert not overlap, f"queue entries already present as graph nodes: {overlap}"


def test_queue_survey_field_is_a_known_survey_id(queue, survey_ids):
    """The /litsearch pipeline stamps `survey` on entries it queues (PIPELINE_PLAN.md
    workstream 1); a value that doesn't match data/surveys.json is a data bug, not a
    typo a reader can catch by eye."""
    bad = [(q["title"], q["survey"]) for q in queue
           if q.get("survey") is not None and q["survey"] not in survey_ids]
    assert not bad, f"queue entries with unknown survey id: {bad}"


def test_queue_role_field_is_valid(queue):
    bad = [(q["title"], q["role"]) for q in queue
           if q.get("role") is not None and q["role"] not in ("core", "foundational")]
    assert not bad, f"queue entries with invalid role (want core|foundational): {bad}"


def test_queue_survey_and_role_are_paired(queue):
    """`survey` and `role` are written together by the pipeline — one present
    without the other means a partially-written entry."""
    bad = [q["title"] for q in queue if bool(q.get("survey")) != bool(q.get("role"))]
    assert not bad, f"queue entries with survey/role set unpaired: {bad}"


def test_surveys_have_page_or_are_intentionally_pageless(surveys):
    """Every survey with a `page` must point at a file that actually exists."""
    for s in surveys:
        if s.get("page"):
            assert (ROOT / "public" / s["page"]).exists(), f"{s['id']}: page {s['page']} missing"


def test_surveys_pdf_points_to_an_existing_file(surveys):
    """Every survey with a `pdf` (the LaTeX companion, PIPELINE_PLAN.md M6) must
    point at a file that actually exists — a survey with no PDF yet simply
    omits the key (never registered before the file is compiled)."""
    for s in surveys:
        if s.get("pdf"):
            assert (ROOT / "public" / s["pdf"]).exists(), f"{s['id']}: pdf {s['pdf']} missing"


def test_benchmarks_taxonomy_matches_tagged_papers(papers, benchmarks_taxonomy):
    """Every benchmarks-tagged node has a taxonomy record and vice versa — the /survey
    pipeline's `corpus` step (PIPELINE_PLAN.md §7.1) diffs exactly this pair to find
    what needs classifying or dropping."""
    tagged_slugs = {p["slug"] for p in papers if "benchmarks" in p.get("tags", [])}
    taxonomy_slugs = {r["slug"] for r in benchmarks_taxonomy}
    missing = tagged_slugs - taxonomy_slugs
    orphaned = taxonomy_slugs - tagged_slugs
    assert not missing, f"benchmarks-tagged papers missing from the taxonomy: {missing}"
    assert not orphaned, f"taxonomy records for papers no longer tagged benchmarks: {orphaned}"


def test_benchmarks_taxonomy_records_have_all_required_keys(benchmarks_taxonomy):
    bad = {r["slug"]: sorted(BENCH_TAXONOMY_REQUIRED_KEYS - set(r.keys()))
           for r in benchmarks_taxonomy if not BENCH_TAXONOMY_REQUIRED_KEYS <= set(r.keys())}
    assert not bad, f"taxonomy record(s) missing required key(s): {bad}"


def test_benchmarks_taxonomy_vocab_closed(benchmarks_taxonomy):
    bad = []
    for r in benchmarks_taxonomy:
        s = r["slug"]
        if r["domain_primary"] not in BENCH_DOMAINS:
            bad.append((s, "domain_primary", r["domain_primary"]))
        for d in r["domain_secondary"]:
            if d not in BENCH_DOMAINS:
                bad.append((s, "domain_secondary", d))
        if r["task_shape"] not in BENCH_SHAPES:
            bad.append((s, "task_shape", r["task_shape"]))
        if r["grading_primary"] not in BENCH_GRADING:
            bad.append((s, "grading_primary", r["grading_primary"]))
        for g in r["grading_all"]:
            if g not in BENCH_GRADING:
                bad.append((s, "grading_all", g))
        if r["complexity"] not in BENCH_COMPLEXITY:
            bad.append((s, "complexity", r["complexity"]))
        if r["provenance"] not in BENCH_PROVENANCE:
            bad.append((s, "provenance", r["provenance"]))
        if r["contamination_defense"] not in BENCH_CONTAM:
            bad.append((s, "contamination_defense", r["contamination_defense"]))
        if r["saturation"] not in BENCH_SATURATION:
            bad.append((s, "saturation", r["saturation"]))
        for t in r["tool_access"]:
            if t not in BENCH_TOOLS:
                bad.append((s, "tool_access", t))
        if r["kingdom"] not in BENCH_KINGDOMS:
            bad.append((s, "kingdom", r["kingdom"]))
        if r["family"] not in BENCH_FAMILIES:
            bad.append((s, "family", r["family"]))
    assert not bad, f"benchmarks-taxonomy.json value(s) outside the controlled vocab: {bad}"


def test_benchmarks_taxonomy_family_matches_kingdom(benchmarks_taxonomy):
    """A record's `family` prefix letter ('A1-...') must match its `kingdom` prefix
    letter ('A-...') — the tree in the survey page groups families under kingdoms by
    this exact convention (see `by_family`/`tree_blocks` in build_survey_page.py)."""
    bad = [(r["slug"], r["kingdom"], r["family"]) for r in benchmarks_taxonomy
           if r["family"][0] != r["kingdom"][0]]
    assert not bad, f"family/kingdom prefix mismatch: {bad}"


def test_benchmarks_taxonomy_lineage_parents_exist(benchmarks_taxonomy, papers):
    """A lineage parent can be any graph node, not just a benchmark-taxonomy member —
    e.g. tau-bench's lineage legitimately points at ReAct (a method paper, not a
    benchmark), so this checks against all of data/papers.json, not just the taxonomy."""
    graph_slugs = {p["slug"] for p in papers}
    bad = [(r["slug"], link["parent"]) for r in benchmarks_taxonomy
           for link in r["lineage"] if link["parent"] not in graph_slugs]
    assert not bad, f"lineage parent(s) not found anywhere in the graph: {bad}"


def test_failure_modes_taxonomy_matches_tagged_papers(papers, failure_modes_taxonomy):
    """Every failure-modes-tagged node has a taxonomy record and vice versa — the /survey
    pipeline's `corpus` step diffs exactly this pair to find what needs classifying or
    dropping."""
    tagged_slugs = {p["slug"] for p in papers if "failure-modes" in p.get("tags", [])}
    taxonomy_slugs = {r["slug"] for r in failure_modes_taxonomy}
    missing = tagged_slugs - taxonomy_slugs
    orphaned = taxonomy_slugs - tagged_slugs
    assert not missing, f"failure-modes-tagged papers missing from the taxonomy: {missing}"
    assert not orphaned, f"taxonomy records for papers no longer tagged failure-modes: {orphaned}"


def test_failure_modes_taxonomy_no_duplicate_slugs(failure_modes_taxonomy):
    slugs = [r["slug"] for r in failure_modes_taxonomy]
    assert len(slugs) == len(set(slugs)), "duplicate slug(s) in failure-modes-taxonomy.json"


def test_failure_modes_taxonomy_records_have_all_required_keys(failure_modes_taxonomy):
    bad = {r["slug"]: sorted(FM_TAXONOMY_REQUIRED_KEYS - set(r.keys()))
           for r in failure_modes_taxonomy if not FM_TAXONOMY_REQUIRED_KEYS <= set(r.keys())}
    assert not bad, f"taxonomy record(s) missing required key(s): {bad}"


def test_failure_modes_taxonomy_has_no_unknown_keys(failure_modes_taxonomy):
    known = FM_TAXONOMY_REQUIRED_KEYS | FM_TAXONOMY_OPTIONAL_KEYS
    bad = {r["slug"]: sorted(set(r.keys()) - known)
           for r in failure_modes_taxonomy if set(r.keys()) - known}
    assert not bad, f"taxonomy record(s) carrying unknown key(s): {bad}"


def test_failure_modes_taxonomy_reasons_are_non_empty(failure_modes_taxonomy):
    """A `*_reason` (or `notes`) key that is present must carry text: the whole point of the
    optional-reason convention is that its absence means 'the call was obvious', which an
    empty string would silently launder into 'unexplained'."""
    bad = [(r["slug"], k) for r in failure_modes_taxonomy
           for k in FM_TAXONOMY_OPTIONAL_KEYS | {"elicitation_reason", "placement_reason"}
           if k in r and not str(r[k]).strip()]
    assert not bad, f"empty reason field(s): {bad}"


def test_failure_modes_taxonomy_vocab_closed(failure_modes_taxonomy):
    checks = [("elicitation", FM_ELICITATION), ("eval_awareness", FM_EVAL_AWARENESS),
              ("locus", FM_LOCUS), ("evidence_mode", FM_EVIDENCE),
              ("detectability", FM_DETECTABILITY), ("mitigation_status", FM_MITIGATION),
              ("harm_bearer", FM_HARM_BEARER), ("kingdom", FM_KINGDOMS),
              ("family", FM_FAMILIES), ("confidence", {"high", "medium", "low"})]
    bad = [(r["slug"], key, r.get(key)) for r in failure_modes_taxonomy
           for key, vocab in checks if r.get(key) not in vocab]
    assert not bad, f"failure-modes-taxonomy.json value(s) outside the controlled vocab: {bad}"


def test_failure_modes_taxonomy_family_matches_kingdom(failure_modes_taxonomy):
    """A record's `family` prefix letter ('A1-...') must match its `kingdom` prefix letter
    ('A-...') — the survey page's tree groups families under kingdoms by this convention."""
    bad = [(r["slug"], r["kingdom"], r["family"]) for r in failure_modes_taxonomy
           if r["family"][0] != r["kingdom"][0]]
    assert not bad, f"family/kingdom prefix mismatch: {bad}"


def test_failure_modes_taxonomy_lineage_is_well_formed(failure_modes_taxonomy, papers):
    """Lineage parents must be real graph nodes (not necessarily taxonomy members), the
    relation must come from the closed vocabulary, and nothing descends from itself."""
    graph_slugs = {p["slug"] for p in papers}
    bad = []
    for r in failure_modes_taxonomy:
        for link in r["lineage"]:
            if set(link.keys()) != {"parent", "relation"}:
                bad.append((r["slug"], "shape", sorted(link.keys())))
            if link.get("parent") not in graph_slugs:
                bad.append((r["slug"], "parent", link.get("parent")))
            if link.get("relation") not in FM_RELATIONS:
                bad.append((r["slug"], "relation", link.get("relation")))
            if link.get("parent") == r["slug"]:
                bad.append((r["slug"], "self-lineage", link.get("parent")))
    assert not bad, f"malformed lineage link(s): {bad}"


def test_failure_modes_taxonomy_lineage_points_backwards_in_time(failure_modes_taxonomy, papers):
    """An edge that says the child was built on an existing parent is inverted if the parent
    postdates the child — and the survey page leans on this graph as evidence for who descends
    from whom. Strict: a parent dated even one month after its child fails. See
    FM_ANCESTRAL_RELATIONS for why `responds-to` is exempt rather than merely tolerant. Dates
    come from papers.json (month precision), which is also what the timeline map lays out."""
    dates = {p["slug"]: p.get("date") for p in papers}

    def months(d):
        y, m = d.split("-")
        return int(y) * 12 + int(m)

    bad = []
    for r in failure_modes_taxonomy:
        child = dates.get(r["slug"])
        for link in r["lineage"]:
            parent = dates.get(link["parent"])
            if not child or not parent or link["relation"] not in FM_ANCESTRAL_RELATIONS:
                continue
            gap = months(parent) - months(child)
            if gap > 0:
                bad.append((r["slug"], child, link["relation"], link["parent"], parent, gap))
    assert not bad, (
        "lineage edge(s) whose parent postdates the child (slug, date, relation, parent, "
        f"parent date, months): {bad}")


def test_failure_modes_taxonomy_gravity_matches_lineage(failure_modes_taxonomy):
    """`gravity` is a computed field: the number of taxonomy records naming this paper as a
    lineage parent. It is regenerated on every build, so drift means a hand edit."""
    children = {}
    for r in failure_modes_taxonomy:
        for link in r["lineage"]:
            children[link["parent"]] = children.get(link["parent"], 0) + 1
    bad = [(r["slug"], r["gravity"], children.get(r["slug"], 0))
           for r in failure_modes_taxonomy if r["gravity"] != children.get(r["slug"], 0)]
    assert not bad, f"gravity out of sync with the lineage graph (slug, stored, computed): {bad}"


def test_failure_modes_taxonomy_metadata_matches_papers(failure_modes_taxonomy, papers):
    """Slug-keyed metadata (title, date, explainer path) is copied from papers.json, so it
    must not drift from it."""
    by_slug = {p["slug"]: p for p in papers}
    bad = []
    for r in failure_modes_taxonomy:
        p = by_slug[r["slug"]]
        if r["title"] != p["title"]:
            bad.append((r["slug"], "title"))
        if r["date"] != p.get("date"):
            bad.append((r["slug"], "date"))
        if r["explainer"] != p["explainer"]:
            bad.append((r["slug"], "explainer"))
    assert not bad, f"taxonomy metadata out of sync with papers.json: {bad}"
