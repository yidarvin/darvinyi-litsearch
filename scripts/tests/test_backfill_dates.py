"""backfill_dates.py idempotency test — the near-miss that motivated it (see
R-20 in CRITIQUE.md: a re-run once silently regressed 9 non-arXiv nodes' precise
dates to the cruder mid-year fallback). Runs against a scratch copy of the real
data/papers.json; reads the real (read-only) public/papers/ explainers."""
import importlib
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def bd(tmp_path, monkeypatch):
    papers_copy = tmp_path / "papers.json"
    shutil.copy(ROOT / "data" / "papers.json", papers_copy)

    sys.modules.pop("backfill_dates", None)
    mod = importlib.import_module("backfill_dates")
    monkeypatch.setattr(mod, "PAPERS_JSON", papers_copy)
    # EXPLAINER_DIR stays pointed at the real public/papers/ — read-only access
    return mod


def test_rerun_is_byte_identical(bd):
    """The core idempotency guarantee: running twice must not change a third
    time. (The bug this regresses against needed one run on already-correct
    data to surface, so this asserts the fixed-point property directly.)"""
    bd.main()
    after_first = bd.PAPERS_JSON.read_text()
    bd.main()
    after_second = bd.PAPERS_JSON.read_text()
    assert after_first == after_second


def test_rerun_never_regresses_a_precise_date_to_mid_year(bd):
    """A node whose current date is NOT a generic mid-year guess (i.e. it came
    from a real source, arXiv or S2) must keep that exact date after a re-run,
    even if backfill_dates.py itself can't independently re-derive it (e.g. a
    non-arXiv source link). Regressing it to "<year>-07" is exactly the R-20 bug."""
    import json
    before = {p["slug"]: p["date"] for p in json.loads(bd.PAPERS_JSON.read_text())["papers"]}
    bd.main()
    after = {p["slug"]: p["date"] for p in json.loads(bd.PAPERS_JSON.read_text())["papers"]}
    regressed = [
        slug for slug, d in before.items()
        if after[slug] != d and after[slug].endswith("-07") and not d.endswith("-07")
    ]
    assert not regressed, f"date(s) regressed to mid-year fallback on re-run: {regressed}"


def test_no_node_left_without_a_date(bd):
    import json
    bd.main()
    data = json.loads(bd.PAPERS_JSON.read_text())
    missing = [p["slug"] for p in data["papers"] if not p.get("date")]
    assert not missing, f"node(s) with no date after backfill: {missing}"
