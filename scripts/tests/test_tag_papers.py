"""tag_papers.py round-trip and validation tests, run against a scratch copy
of the real data/papers.json + data/surveys.json (never the live files)."""
import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def tp(tmp_path, monkeypatch):
    """A freshly-imported tag_papers module pointed at a scratch copy of the
    real papers.json/surveys.json, so mutation tests never touch live data."""
    papers_copy = tmp_path / "papers.json"
    surveys_copy = tmp_path / "surveys.json"
    shutil.copy(ROOT / "data" / "papers.json", papers_copy)
    shutil.copy(ROOT / "data" / "surveys.json", surveys_copy)

    sys.modules.pop("tag_papers", None)
    mod = importlib.import_module("tag_papers")
    monkeypatch.setattr(mod, "PAPERS", str(papers_copy))
    monkeypatch.setattr(mod, "SURVEYS", str(surveys_copy))
    return mod


def test_add_then_remove_is_byte_identical(tp):
    original = Path(tp.PAPERS).read_text()
    d, sd = tp.load()
    slug = d["papers"][0]["slug"]
    survey_id = sd["surveys"][0]["id"]

    tp.cmd_mutate(d, sd, "add", survey_id, [slug])
    d2, _ = tp.load()  # re-read from disk, not the in-memory dict
    tp.cmd_mutate(d2, sd, "remove", survey_id, [slug])

    assert Path(tp.PAPERS).read_text() == original


def test_add_is_idempotent(tp):
    d, sd = tp.load()
    slug = d["papers"][0]["slug"]
    survey_id = sd["surveys"][0]["id"]

    tp.cmd_mutate(d, sd, "add", survey_id, [slug])
    d2, _ = tp.load()
    after_first = Path(tp.PAPERS).read_text()

    tp.cmd_mutate(d2, sd, "add", survey_id, [slug])
    after_second = Path(tp.PAPERS).read_text()

    assert after_first == after_second


def test_unknown_slug_rejected(tp):
    d, sd = tp.load()
    survey_id = sd["surveys"][0]["id"]
    with pytest.raises(SystemExit):
        tp.cmd_mutate(d, sd, "add", survey_id, ["this-slug-does-not-exist"])


def test_unknown_survey_rejected(tp):
    d, sd = tp.load()
    slug = d["papers"][0]["slug"]
    with pytest.raises(SystemExit):
        tp.cmd_mutate(d, sd, "add", "no-such-survey", [slug])


def test_tags_stay_sorted_and_deduped(tp):
    d, sd = tp.load()
    slug = d["papers"][0]["slug"]
    survey_id = sd["surveys"][0]["id"]

    tp.cmd_mutate(d, sd, "add", survey_id, [slug])
    d2, _ = json.load(open(tp.PAPERS)), None
    node = next(p for p in d2["papers"] if p["slug"] == slug)
    assert node["tags"] == sorted(set(node["tags"]))

    tp.cmd_mutate(d2, sd, "remove", survey_id, [slug])  # cleanup for the assertion below
    d3 = json.load(open(tp.PAPERS))
    node3 = next(p for p in d3["papers"] if p["slug"] == slug)
    assert survey_id not in node3.get("tags", [])
