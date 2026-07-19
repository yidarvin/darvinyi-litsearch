"""litsearch.py state-machine tests, run against a scratch data/ directory
(never the live data/litsearch/*.state.json, papers.json, or queue.json).
Mirrors test_tag_papers.py's monkeypatch-the-module-globals fixture pattern."""
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def ls(tmp_path, monkeypatch):
    """A freshly-imported litsearch module pointed at a scratch data/ dir:
    a copy of the real surveys.json plus a scratch `zztest` survey, and
    empty papers/queue files."""
    data = tmp_path / "data"
    data.mkdir()
    surveys = json.loads((ROOT / "data" / "surveys.json").read_text())
    surveys["surveys"].append({
        "id": "zztest", "label": "ZZ Test", "color": "#123456",
        "description": "scratch survey for litsearch.py tests",
    })
    (data / "surveys.json").write_text(json.dumps(surveys))
    (data / "papers.json").write_text(json.dumps({"papers": [], "edges": []}))
    (data / "queue.json").write_text(json.dumps([]))

    sys.modules.pop("litsearch", None)
    mod = importlib.import_module("litsearch")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "STATE_DIR", data / "litsearch")
    monkeypatch.setattr(mod, "SURVEYS_JSON", data / "surveys.json")
    return mod


def run(mod, *argv):
    """Exercise the real argparse wiring, like an actual CLI invocation."""
    args = mod.build_parser().parse_args(list(argv))
    return args.func(args)


def read_state(mod, survey="zztest"):
    return json.loads((mod.STATE_DIR / f"{survey}.state.json").read_text())


def walk_to(mod, survey, step):
    """Drive `current.step` from resolve up to (and including) `step`."""
    order = ["resolve", "fetch", "figures", "draft"]
    for s in order[1:order.index(step) + 1]:
        run(mod, "set-step", survey, s)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def test_init_creates_state_file_with_defaults(ls):
    run(ls, "init", "zztest", "--topic", "Test Topic")
    state = read_state(ls)
    assert state["survey"] == "zztest"
    assert state["topic"] == "Test Topic"
    assert state["phase"] == "seeding"
    assert state["config"] == {
        "max_rounds": 3,
        "builder": {"model": "sonnet", "effort": "high"},
        "critic": {"model": "opus", "effort": "xhigh"},
        "process_foundational": False,
    }
    assert state["current"] is None
    assert state["completed"] == []
    assert state["skipped"] == []
    assert state["seeding"]["done"] is False
    assert len(state["log"]) == 1


def test_init_unknown_survey_rejected(ls):
    with pytest.raises(SystemExit):
        run(ls, "init", "no-such-survey", "--topic", "x")


def test_init_twice_rejected(ls):
    run(ls, "init", "zztest", "--topic", "T")
    with pytest.raises(SystemExit):
        run(ls, "init", "zztest", "--topic", "T again")


def test_init_seeding_done_flag_sets_idle_phase(ls):
    run(ls, "init", "zztest", "--topic", "T", "--seeding-done")
    state = read_state(ls)
    assert state["phase"] == "idle"
    assert state["seeding"]["done"] is True


def test_seed_done_marks_phase_processing(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "seed-done", "zztest", "--seeded", "12", "--query", "q1", "--query", "q2")
    state = read_state(ls)
    assert state["phase"] == "processing"
    assert state["seeding"]["done"] is True
    assert state["seeding"]["queries"] == ["q1", "q2"]
    assert state["seeding"]["seeded"] == 12


# ---------------------------------------------------------------------------
# start-paper / set-step (the per-paper state machine)
# ---------------------------------------------------------------------------

def test_start_paper_sets_current_at_resolve(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1", "--arxiv-id", "2401.00001")
    state = read_state(ls)
    assert state["current"] == {
        "slug": "s1", "queue_title": "S1", "arxiv_id": "2401.00001",
        "step": "resolve", "round": None, "open_blockers": [],
    }
    assert state["phase"] == "processing"


def test_start_paper_rejects_when_current_in_progress(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    with pytest.raises(SystemExit):
        run(ls, "start-paper", "zztest", "s2", "--title", "S2")


def test_set_step_full_legal_chain(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", "draft")
    run(ls, "set-step", "zztest", "critique", "--round", "1")
    state = read_state(ls)
    assert state["current"]["step"] == "critique"
    assert state["current"]["round"] == 1


@pytest.mark.parametrize("from_step,to_step", [
    ("resolve", "critique"),
    ("resolve", "draft"),
    ("fetch", "verify"),
    ("figures", "queue-ops"),
])
def test_set_step_illegal_transition_rejected(ls, from_step, to_step):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", from_step)
    with pytest.raises(SystemExit):
        run(ls, "set-step", "zztest", to_step)


def test_set_step_same_step_is_idempotent(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    run(ls, "set-step", "zztest", "resolve")
    run(ls, "set-step", "zztest", "resolve")
    assert read_state(ls)["current"]["step"] == "resolve"


def test_set_step_critique_requires_round(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", "draft")
    with pytest.raises(SystemExit):
        run(ls, "set-step", "zztest", "critique")


def test_set_step_critique_round_must_increment_by_one(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", "draft")
    with pytest.raises(SystemExit):
        run(ls, "set-step", "zztest", "critique", "--round", "2")  # first round must be 1
    run(ls, "set-step", "zztest", "critique", "--round", "1")
    run(ls, "set-step", "zztest", "revise")
    with pytest.raises(SystemExit):
        run(ls, "set-step", "zztest", "critique", "--round", "3")  # must be 2 next
    run(ls, "set-step", "zztest", "critique", "--round", "2")
    assert read_state(ls)["current"]["round"] == 2


def test_set_step_no_current_rejected(ls):
    run(ls, "init", "zztest", "--topic", "T")
    with pytest.raises(SystemExit):
        run(ls, "set-step", "zztest", "fetch")


# ---------------------------------------------------------------------------
# set-blockers
# ---------------------------------------------------------------------------

def test_set_blockers_syncs_open_blockers(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", "draft")
    run(ls, "set-step", "zztest", "critique", "--round", "1")
    crit = tmp_path / "crit1.json"
    crit.write_text(json.dumps({"verdict": "revise", "round": 1,
                                 "blocking": [{"id": "B1", "issue": "bad number"}],
                                 "suggestions": []}))
    run(ls, "set-blockers", "zztest", str(crit))
    state = read_state(ls)
    assert state["current"]["open_blockers"] == [{"id": "B1", "issue": "bad number"}]


def test_set_blockers_round_mismatch_rejected_unless_forced(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", "draft")
    run(ls, "set-step", "zztest", "critique", "--round", "1")
    bad = tmp_path / "crit_bad.json"
    bad.write_text(json.dumps({"verdict": "revise", "round": 2, "blocking": [], "suggestions": []}))
    with pytest.raises(SystemExit):
        run(ls, "set-blockers", "zztest", str(bad))
    run(ls, "set-blockers", "zztest", str(bad), "--force-round")  # override succeeds
    assert read_state(ls)["current"]["open_blockers"] == []


def test_set_blockers_missing_file_rejected(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    with pytest.raises(SystemExit):
        run(ls, "set-blockers", "zztest", str(tmp_path / "nope.json"))


def test_set_blockers_missing_keys_rejected(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    bad = tmp_path / "malformed.json"
    bad.write_text(json.dumps({"verdict": "revise"}))  # no round/blocking
    with pytest.raises(SystemExit):
        run(ls, "set-blockers", "zztest", str(bad))


# ---------------------------------------------------------------------------
# complete-paper / skip-paper
# ---------------------------------------------------------------------------

def test_complete_paper_approved_requires_no_open_blockers(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", "draft")
    run(ls, "set-step", "zztest", "critique", "--round", "1")
    crit = tmp_path / "crit1.json"
    crit.write_text(json.dumps({"verdict": "revise", "round": 1,
                                 "blocking": [{"id": "B1", "issue": "bad"}], "suggestions": []}))
    run(ls, "set-blockers", "zztest", str(crit))
    with pytest.raises(SystemExit):
        run(ls, "complete-paper", "zztest", "--verdict", "approved")
    run(ls, "complete-paper", "zztest", "--verdict", "approved_with_notes")
    state = read_state(ls)
    assert state["current"] is None
    assert state["completed"][0]["verdict"] == "approved_with_notes"
    assert state["completed"][0]["notes"] == ["bad"]  # auto-filled from open blockers


def test_complete_paper_approved_clears_current(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    walk_to(ls, "zztest", "draft")
    run(ls, "set-step", "zztest", "critique", "--round", "1")
    run(ls, "set-step", "zztest", "verify")
    run(ls, "set-step", "zztest", "queue-ops")
    run(ls, "complete-paper", "zztest", "--verdict", "approved")
    state = read_state(ls)
    assert state["current"] is None
    assert state["completed"][0]["slug"] == "s1"
    assert state["completed"][0]["rounds"] == 1
    assert state["completed"][0]["notes"] == []


def test_complete_paper_explicit_notes_override_autofill(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    run(ls, "complete-paper", "zztest", "--verdict", "approved_with_notes",
        "--notes", "custom note one", "--notes", "custom note two")
    notes = read_state(ls)["completed"][0]["notes"]
    assert notes == ["custom note one", "custom note two"]


def test_complete_paper_requires_current(ls):
    run(ls, "init", "zztest", "--topic", "T")
    with pytest.raises(SystemExit):
        run(ls, "complete-paper", "zztest", "--verdict", "approved")


def test_skip_paper_moves_current_to_skipped(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    run(ls, "skip-paper", "zztest", "--reason", "no PDF obtainable")
    state = read_state(ls)
    assert state["current"] is None
    assert state["skipped"][0]["slug"] == "s1"
    assert state["skipped"][0]["reason"] == "no PDF obtainable"


def test_skip_paper_requires_current(ls):
    run(ls, "init", "zztest", "--topic", "T")
    with pytest.raises(SystemExit):
        run(ls, "skip-paper", "zztest", "--reason", "x")


def test_second_paper_can_start_after_first_completes(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    run(ls, "skip-paper", "zztest", "--reason", "x")
    run(ls, "start-paper", "zztest", "s2", "--title", "S2")
    assert read_state(ls)["current"]["slug"] == "s2"


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

def test_log_appends_and_caps_at_50(ls):
    run(ls, "init", "zztest", "--topic", "T")  # log entry 1
    for i in range(60):
        run(ls, "log", "zztest", f"message {i}")
    log = read_state(ls)["log"]
    assert len(log) == 50
    assert log[-1].endswith("message 59")
    assert log[0].endswith("message 10")  # oldest 11 (1 init + msgs 0-9) fell off


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_reports_idle_for_survey_without_state_file(ls):
    rows = ls.compute_status()
    row = next(r for r in rows if r["id"] == "zztest")
    assert row["phase"] == "idle"
    assert row["current"] is None
    assert row["tagged"] == 0


def test_status_reports_current_paper(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    rows = ls.compute_status()
    row = next(r for r in rows if r["id"] == "zztest")
    assert row["phase"] == "processing"
    assert row["current"]["slug"] == "s1"


def test_status_reflects_queue_survey_role_counts(ls):
    queue = [
        {"title": "A", "arxiv_id": None, "survey": "zztest", "role": "core"},
        {"title": "B", "arxiv_id": None, "survey": "zztest", "role": "core"},
        {"title": "C", "arxiv_id": None, "survey": "zztest", "role": "foundational"},
        {"title": "D", "arxiv_id": None, "survey": "other-survey", "role": "core"},
    ]
    (ls.ROOT / "data" / "queue.json").write_text(json.dumps(queue))
    rows = ls.compute_status()
    row = next(r for r in rows if r["id"] == "zztest")
    assert row["queue_core"] == 2
    assert row["queue_foundational"] == 1


def test_status_json_cli_output_is_valid_json(ls, capsys):
    run(ls, "init", "zztest", "--topic", "T")
    capsys.readouterr()  # discard init's stdout
    run(ls, "status", "--json")
    out = capsys.readouterr().out
    rows = json.loads(out)
    assert any(r["id"] == "zztest" for r in rows)


def test_status_unknown_survey_rejected(ls):
    with pytest.raises(SystemExit):
        run(ls, "status", "no-such-survey")


# ---------------------------------------------------------------------------
# atomicity & canonical formatting
# ---------------------------------------------------------------------------

def test_atomic_save_leaves_no_tmp_file(ls):
    run(ls, "init", "zztest", "--topic", "T")
    assert not (ls.STATE_DIR / "zztest.state.json.tmp").exists()


def test_state_key_order_is_canonical(ls):
    run(ls, "init", "zztest", "--topic", "T")
    state = read_state(ls)
    assert list(state.keys()) == ls.STATE_KEY_ORDER
    assert list(state["config"].keys()) == ls.CONFIG_KEY_ORDER


def test_current_key_order_is_canonical(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "start-paper", "zztest", "s1", "--title", "S1")
    state = read_state(ls)
    assert list(state["current"].keys()) == ls.CURRENT_KEY_ORDER


# ---------------------------------------------------------------------------
# survey-build step machine (used by the future /survey skill)
# ---------------------------------------------------------------------------

def test_survey_build_step_cannot_skip_ahead(ls):
    run(ls, "init", "zztest", "--topic", "T")
    with pytest.raises(SystemExit):
        run(ls, "set-survey-build-step", "zztest", "site")


def test_survey_build_step_legal_chain_sets_flags(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "set-survey-build-step", "zztest", "corpus")
    run(ls, "set-survey-build-step", "zztest", "taxonomy")
    run(ls, "set-survey-build-step", "zztest", "site")
    run(ls, "set-survey-build-step", "zztest", "tex")
    state = read_state(ls)
    assert state["survey_build"]["taxonomy"] is True
    assert state["survey_build"]["site"] is True
    assert state["survey_build"]["step"] == "tex"


def test_survey_build_site_can_skip_straight_to_critique(ls):
    """No LaTeX/PDF pipeline exists yet (that's milestone M6) — a survey must
    be able to go straight from `site` to `critique` without a PDF pass."""
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "set-survey-build-step", "zztest", "corpus")
    run(ls, "set-survey-build-step", "zztest", "taxonomy")
    run(ls, "set-survey-build-step", "zztest", "site")
    run(ls, "set-survey-build-step", "zztest", "critique")
    state = read_state(ls)
    assert state["survey_build"]["step"] == "critique"
    assert state["survey_build"]["round"] == 1


def test_survey_build_site_cannot_skip_straight_to_pdf(ls):
    """`pdf` still requires going through `tex` first — only `critique` gets
    the direct-from-`site` shortcut."""
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "set-survey-build-step", "zztest", "corpus")
    run(ls, "set-survey-build-step", "zztest", "taxonomy")
    run(ls, "set-survey-build-step", "zztest", "site")
    with pytest.raises(SystemExit):
        run(ls, "set-survey-build-step", "zztest", "pdf")


# ---------------------------------------------------------------------------
# survey-build blockers / completion (the survey_build sibling of
# set-blockers/complete-paper — mirrors those tests' shape)
# ---------------------------------------------------------------------------

def walk_survey_build_to_critique(mod, survey, round_=1):
    run(mod, "set-survey-build-step", survey, "corpus")
    run(mod, "set-survey-build-step", survey, "taxonomy")
    run(mod, "set-survey-build-step", survey, "site")
    run(mod, "set-survey-build-step", survey, "critique", "--round", str(round_))


def test_set_survey_blockers_syncs_open_blockers(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    walk_survey_build_to_critique(ls, "zztest")
    crit = tmp_path / "crit1.json"
    crit.write_text(json.dumps({"verdict": "revise", "round": 1,
                                 "blocking": [{"id": "B1", "issue": "stale number"}],
                                 "suggestions": []}))
    run(ls, "set-survey-blockers", "zztest", str(crit))
    state = read_state(ls)
    assert state["survey_build"]["open_blockers"] == [{"id": "B1", "issue": "stale number"}]


def test_set_survey_blockers_requires_build_in_progress(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    crit = tmp_path / "crit1.json"
    crit.write_text(json.dumps({"verdict": "approve", "round": 1, "blocking": [], "suggestions": []}))
    with pytest.raises(SystemExit):
        run(ls, "set-survey-blockers", "zztest", str(crit))


def test_set_survey_blockers_round_mismatch_rejected_unless_forced(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    walk_survey_build_to_critique(ls, "zztest")
    bad = tmp_path / "crit_bad.json"
    bad.write_text(json.dumps({"verdict": "revise", "round": 2, "blocking": [], "suggestions": []}))
    with pytest.raises(SystemExit):
        run(ls, "set-survey-blockers", "zztest", str(bad))
    run(ls, "set-survey-blockers", "zztest", str(bad), "--force-round")
    assert read_state(ls)["survey_build"]["open_blockers"] == []


def test_complete_survey_build_approved_requires_no_open_blockers(ls, tmp_path):
    run(ls, "init", "zztest", "--topic", "T")
    walk_survey_build_to_critique(ls, "zztest")
    crit = tmp_path / "crit1.json"
    crit.write_text(json.dumps({"verdict": "revise", "round": 1,
                                 "blocking": [{"id": "B1", "issue": "bad"}], "suggestions": []}))
    run(ls, "set-survey-blockers", "zztest", str(crit))
    with pytest.raises(SystemExit):
        run(ls, "complete-survey-build", "zztest", "--verdict", "approved")
    run(ls, "complete-survey-build", "zztest", "--verdict", "approved_with_notes")
    state = read_state(ls)
    assert state["survey_build"]["step"] is None
    assert state["survey_build"]["round"] == 0
    assert state["survey_build"]["open_blockers"] == []


def test_complete_survey_build_approved_resets_for_next_cycle(ls):
    run(ls, "init", "zztest", "--topic", "T")
    walk_survey_build_to_critique(ls, "zztest")
    run(ls, "complete-survey-build", "zztest", "--verdict", "approved")
    state = read_state(ls)
    assert state["survey_build"]["step"] is None
    assert state["survey_build"]["round"] == 0
    # taxonomy/site stay True as a historical "has this ever been built" record
    assert state["survey_build"]["taxonomy"] is True
    assert state["survey_build"]["site"] is True
    # a fresh cycle can start immediately — no wedging
    run(ls, "set-survey-build-step", "zztest", "corpus")
    assert read_state(ls)["survey_build"]["step"] == "corpus"


def test_complete_survey_build_requires_build_in_progress(ls):
    run(ls, "init", "zztest", "--topic", "T")
    with pytest.raises(SystemExit):
        run(ls, "complete-survey-build", "zztest", "--verdict", "approved")


def test_survey_build_key_order_is_canonical(ls):
    run(ls, "init", "zztest", "--topic", "T")
    run(ls, "set-survey-build-step", "zztest", "corpus")
    state = read_state(ls)
    assert list(state["survey_build"].keys()) == ls.SURVEY_BUILD_KEY_ORDER
