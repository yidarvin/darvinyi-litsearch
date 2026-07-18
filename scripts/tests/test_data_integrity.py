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
              "citation_count", "topic", "author_group", "abstract", "explainer", "tags"]


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


def test_surveys_have_page_or_are_intentionally_pageless(surveys):
    """Every survey with a `page` must point at a file that actually exists."""
    for s in surveys:
        if s.get("page"):
            assert (ROOT / "public" / s["page"]).exists(), f"{s['id']}: page {s['page']} missing"
