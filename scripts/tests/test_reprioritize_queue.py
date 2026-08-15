"""reprioritize_queue.py scoring tests — pure functions, no data/ touched.

The point of these is the two-path split: `benchmarks` must keep its original
scoring exactly (existing queue orderings must not churn), while every other
survey scores citation-led with its own relevance profile.
Mirrors test_litsearch_state.py's sys.path-insert import pattern."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

rq = importlib.import_module("reprioritize_queue")


def entry(title, cites, topic="Benchmarks & Evals", why=""):
    return {"title": title, "citation_count": cites, "topic": topic, "why": why}


# --- benchmarks: the original scoring, frozen -------------------------------

def test_benchmarks_scoring_is_the_original_formula():
    """2.0*relevance + citations, with the benchmark keyword profile."""
    e = entry("SWE-bench: Can Language Models Resolve Real-World GitHub Issues?", 1000)
    # topic 0.45 + title keyword 0.35 = 0.80
    assert rq.relevance(e, "benchmarks") == 0.80
    assert rq.score(e, "benchmarks") == 2.0 * 0.80 + rq.citation_score(e)


def test_benchmarks_relevance_still_outweighs_citations():
    """The 2x weight is load-bearing for benchmarks and must not be softened:
    a purpose-built benchmark outranks a better-cited non-benchmark paper."""
    bench = entry("MMLU: Measuring Massive Multitask Language Understanding", 500)
    other = entry("Attention Is All You Need", 100000, topic="Foundation Models")
    assert rq.score(bench, "benchmarks") > rq.score(other, "benchmarks")


def test_survey_none_falls_back_to_benchmarks_path():
    """Callers that pass no survey get the legacy behaviour unchanged."""
    e = entry("HELM: Holistic Evaluation of Language Models", 900)
    assert rq.score(e, None) == rq.score(e, "benchmarks")


# --- failure-modes: the reported bug ----------------------------------------

def test_failure_modes_fixes_the_reported_inversion():
    """The regression this profile exists for.

    Under the benchmarks profile these ranked SycEval (122 cites) first, because
    'Eval' in a title scored as benchmark vocabulary, while a 5,167-citation
    hallucination survey sank below it. Order by failure-modes score must put
    the canonical survey first and the narrow recent paper last."""
    syceval = entry("SycEval: Evaluating LLM Sycophancy", 122,
                    why="framework for measuring sycophancy in LLMs")
    survey = entry("Survey of Hallucination in Natural Language Generation", 5167,
                   why="foundational survey of hallucination")
    inevitable = entry("Hallucination is Inevitable: An Innate Limitation of "
                       "Large Language Models", 644,
                       why="formal argument that hallucination cannot be eliminated")

    ranked = sorted([syceval, survey, inevitable],
                    key=lambda e: -rq.score(e, "failure-modes"))
    assert [e["title"].split(":")[0] for e in ranked] == [
        "Survey of Hallucination in Natural Language Generation",
        "Hallucination is Inevitable",
        "SycEval",
    ]
    # and the same three under the old path reproduce the bug, so this test
    # would have caught it
    old = sorted([syceval, survey, inevitable],
                 key=lambda e: -rq.score(e, "benchmarks"))
    assert old[0] is syceval


def test_failure_modes_prefers_characterization_over_mitigation():
    """The rubric admits mitigation papers only when they diagnose the failure,
    and names taxonomies/red-team studies as in scope. A better-cited mitigation
    method must not outrank a characterization paper by too much."""
    survey = entry("A Survey of Hallucination in Large Foundation Models", 616)
    mitigation = entry("Mitigating Object Hallucinations in Large "
                       "Vision-Language Models", 774)
    assert rq.relevance(survey, "failure-modes") > rq.relevance(mitigation, "failure-modes")
    assert rq.score(survey, "failure-modes") > rq.score(mitigation, "failure-modes")


def test_failure_modes_demotes_but_does_not_exclude_benchmark_titles():
    """A benchmark-titled paper is one the rubric routes to `benchmarks`, and it
    carries this tag only additionally — so it is penalised, not zeroed, and a
    phenomenon hit still lifts it above an off-rubric paper."""
    benchy = entry("BrokenMath: A Benchmark for Sycophancy in Theorem Proving", 25)
    offrubric = entry("Scaling Laws for Neural Language Models", 25,
                      topic="Foundation Models")
    assert 0.0 < rq.relevance(benchy, "failure-modes")
    assert rq.relevance(benchy, "failure-modes") > rq.relevance(offrubric, "failure-modes")


def test_failure_modes_relevance_does_not_saturate():
    """The original bug was a relevance term that pinned most of the queue to one
    value, making the tier — not the citation count — decide the order. Guard the
    property, not a specific spread: the phenomenon vocabulary must distinguish
    these four."""
    seen = {rq.relevance(e, "failure-modes") for e in [
        entry("A Survey of Hallucination in Large Foundation Models", 1),
        entry("Mitigating Object Hallucinations in Vision-Language Models", 1),
        entry("Scaling Laws for Neural Language Models", 1, topic="Foundation Models"),
        entry("AgentNoiseBench: Benchmarking Robustness of Tool-Using Agents", 1),
    ]}
    assert len(seen) == 4


# --- surveys with no profile ------------------------------------------------

def test_unprofiled_survey_is_a_pure_citation_sort():
    """`evaluations` (and any future survey) has no profile, so relevance is flat
    and score reduces to the citation term. That is the documented default: a
    `core` entry already passed its survey's rubric, so membership is settled."""
    assert "evaluations" not in rq.PROFILES
    a = entry("Chatbot Arena: An Open Platform for Evaluating LLMs", 50)
    b = entry("G-Eval: NLG Evaluation using GPT-4", 2000)
    assert rq.relevance(a, "evaluations") == rq.relevance(b, "evaluations")
    assert rq.score(b, "evaluations") > rq.score(a, "evaluations")
    # flat relevance means the ordering is exactly the citation ordering
    ranked = sorted([a, b], key=lambda e: -rq.score(e, "evaluations"))
    by_cites = sorted([a, b], key=lambda e: -(e["citation_count"] or 0))
    assert ranked == by_cites


def test_profiles_reference_real_surveys():
    """A profile keyed to a survey id that no longer exists would silently never
    fire. Every profiled id must be a real survey in data/surveys.json."""
    import json
    ids = {s["id"] for s in json.loads((ROOT / "data/surveys.json").read_text())["surveys"]}
    assert set(rq.PROFILES) <= ids


def test_missing_citation_count_scores_zero_not_crash():
    e = {"title": "Some Hallucination Taxonomy", "citation_count": None,
         "topic": "Safety & Red-teaming", "why": ""}
    assert rq.citation_score(e) == 0.0
    assert rq.score(e, "failure-modes") == rq.REL_WEIGHT * rq.relevance(e, "failure-modes")
