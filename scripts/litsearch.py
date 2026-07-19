#!/usr/bin/env python3
"""State CLI for the /litsearch pipeline (PIPELINE_PLAN.md workstream 1).

Owns data/litsearch/<survey_id>.state.json — the on-disk resume point for a
survey's literature-search run. Every mutation is atomic (write to a temp file
then os.replace) and validated, so a kill at any instant leaves either the old
state or the new state, never a half-written file. The orchestrator skill
(/litsearch) and the paper-builder agent are the two callers; both drive the
pipeline purely through this CLI so state transitions stay legal and durable.

State machine (per paper, tracked in `current.step`):
    resolve -> fetch -> figures -> draft -> critique <-> revise -> verify -> queue-ops

`current.round` is the critique round number: draft->critique enters round 1;
each revise->critique bump is round+1; revise itself keeps the round of the
critique whose blockers it is addressing (so critique-rN.json pairs with
response-rN.md).

Usage
-----
  # create a survey's state file (the survey id must already exist in
  # data/surveys.json — add it there first)
  python scripts/litsearch.py init <survey_id> --topic "…" \\
      [--max-rounds 3] [--builder-model sonnet] [--builder-effort high] \\
      [--critic-model opus] [--critic-effort xhigh] [--process-foundational] \\
      [--seeding-done]

  # mark seeding complete (records the queries used + how many were seeded)
  python scripts/litsearch.py seed-done <survey_id> --seeded 22 \\
      [--query "…" --query "…" ...]

  # start work on one paper (sets `current`, step=resolve)
  python scripts/litsearch.py start-paper <survey_id> <slug> --title "…" \\
      [--arxiv-id 2308.03688]

  # advance the current paper's step (validates the transition is legal)
  python scripts/litsearch.py set-step <survey_id> <step> [--round N]

  # sync open blockers from a critique-rN.json file onto `current`
  python scripts/litsearch.py set-blockers <survey_id> <critique.json>

  # finish the current paper (moves it into `completed`, clears `current`)
  python scripts/litsearch.py complete-paper <survey_id> \\
      --verdict approved|approved_with_notes [--notes "…" ...]

  # abandon the current paper (moves it into `skipped`, clears `current`)
  python scripts/litsearch.py skip-paper <survey_id> --reason "…"

  # append a log line (capped at the last 50)
  python scripts/litsearch.py log <survey_id> "message"

  # human table (all surveys, or one) / machine JSON for the /surveys skill
  python scripts/litsearch.py status [<survey_id>] [--json]

  # advance the survey-artifact build step (taxonomy/site/pdf), used by /survey
  python scripts/litsearch.py set-survey-build-step <survey_id> <step> [--round N]

  # sync open blockers from a survey-critique file onto survey_build
  python scripts/litsearch.py set-survey-blockers <survey_id> <critique.json>

  # finish the current survey-build cycle (resets step/round for the next one)
  python scripts/litsearch.py complete-survey-build <survey_id> \\
      --verdict approved|approved_with_notes [--notes "…"]

Run from the repo root.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "data" / "litsearch"
SURVEYS_JSON = ROOT / "data" / "surveys.json"

STATE_KEY_ORDER = [
    "version", "survey", "topic", "created", "phase", "config",
    "seeding", "current", "completed", "skipped", "survey_build", "log",
]
CURRENT_KEY_ORDER = ["slug", "queue_title", "arxiv_id", "step", "round", "open_blockers"]
CONFIG_KEY_ORDER = ["max_rounds", "builder", "critic", "process_foundational"]
SURVEY_BUILD_KEY_ORDER = ["step", "round", "open_blockers", "taxonomy", "site", "pdf"]

# per-paper step machine: legal next steps from each step (self included so a
# retried/idempotent call is never an error)
PAPER_STEPS = ["resolve", "fetch", "figures", "draft", "critique", "revise", "verify", "queue-ops"]
PAPER_TRANSITIONS = {
    None: {"resolve"},
    "resolve": {"resolve", "fetch"},
    "fetch": {"fetch", "figures"},
    "figures": {"figures", "draft"},
    "draft": {"draft", "critique"},
    "critique": {"critique", "revise", "verify"},
    "revise": {"revise", "critique"},
    "verify": {"verify", "queue-ops"},
    "queue-ops": {"queue-ops"},
}

# survey-artifact build step machine (mirrors the paper machine's shape; used
# by the future /survey skill — see PIPELINE_PLAN.md workstream 5)
SURVEY_BUILD_STEPS = ["corpus", "taxonomy", "site", "tex", "pdf", "critique", "revise", "verify"]
SURVEY_BUILD_TRANSITIONS = {
    None: {"corpus"},
    "corpus": {"corpus", "taxonomy"},
    "taxonomy": {"taxonomy", "site"},
    # "site" -> "critique" directly is legal: the LaTeX/PDF pipeline (tex/pdf
    # steps) is milestone M6 territory (PIPELINE_PLAN.md) and doesn't exist
    # yet, so a survey can go straight to review without a PDF. "tex" stays
    # reachable from "site" for once M6 lands and wants a PDF pass before
    # critique.
    "site": {"site", "tex", "critique"},
    "tex": {"tex", "pdf"},
    "pdf": {"pdf", "critique"},
    "critique": {"critique", "revise", "verify"},
    "revise": {"revise", "critique"},
    "verify": {"verify"},
}

LOG_CAP = 50


def die(msg):
    sys.exit(f"litsearch: {msg}")


def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")


def today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# load / save
# ---------------------------------------------------------------------------

def state_path(survey_id):
    return STATE_DIR / f"{survey_id}.state.json"


def survey_ids():
    if not SURVEYS_JSON.exists():
        return set()
    return {s["id"] for s in json.loads(SURVEYS_JSON.read_text()).get("surveys", [])}


def load_state(survey_id):
    p = state_path(survey_id)
    if not p.exists():
        die(f"no state file for survey '{survey_id}' ({p}). Run `init` first.")
    return json.loads(p.read_text())


def _ordered(d, order):
    """Re-key a dict into `order`, dropping keys not in `d` and appending any
    unexpected extra keys at the end (defensive — should never trigger)."""
    out = {k: d[k] for k in order if k in d}
    for k in d:
        if k not in out:
            out[k] = d[k]
    return out


def _canonicalize(state):
    state = _ordered(state, STATE_KEY_ORDER)
    state["config"] = _ordered(state["config"], CONFIG_KEY_ORDER)
    if state.get("current") is not None:
        state["current"] = _ordered(state["current"], CURRENT_KEY_ORDER)
    if state.get("survey_build") is not None:
        state["survey_build"] = _ordered(state["survey_build"], SURVEY_BUILD_KEY_ORDER)
    return state


def save_state(survey_id, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = _canonicalize(state)
    text = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    tmp = state_path(survey_id).with_suffix(".json.tmp")
    tmp.write_text(text)
    os.replace(tmp, state_path(survey_id))


def append_log(state, message):
    state.setdefault("log", []).append(f"{now_stamp()} {message}")
    state["log"] = state["log"][-LOG_CAP:]


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def cmd_init(a):
    if a.survey not in survey_ids():
        die(f"'{a.survey}' is not a known survey id. Add it to data/surveys.json first "
            f"(known: {sorted(survey_ids())}).")
    if state_path(a.survey).exists():
        die(f"state file already exists for '{a.survey}' ({state_path(a.survey)}). "
            f"Delete it first if you really want to re-init.")
    state = {
        "version": 1,
        "survey": a.survey,
        "topic": a.topic,
        "created": today(),
        "phase": "seeding" if not a.seeding_done else "idle",
        "config": {
            "max_rounds": a.max_rounds,
            "builder": {"model": a.builder_model, "effort": a.builder_effort},
            "critic": {"model": a.critic_model, "effort": a.critic_effort},
            "process_foundational": a.process_foundational,
        },
        "seeding": {"done": a.seeding_done, "date": today() if a.seeding_done else None,
                    "queries": [], "seeded": 0},
        "current": None,
        "completed": [],
        "skipped": [],
        "survey_build": {"step": None, "round": 0, "open_blockers": [],
                          "taxonomy": False, "site": False, "pdf": False},
        "log": [],
    }
    append_log(state, f"initialized (topic: {a.topic!r})")
    save_state(a.survey, state)
    print(f"initialized {state_path(a.survey)}")


def cmd_seed_done(a):
    state = load_state(a.survey)
    state["seeding"] = {"done": True, "date": today(), "queries": a.query or [], "seeded": a.seeded}
    state["phase"] = "processing"
    append_log(state, f"seeding done: {a.seeded} paper(s) queued")
    save_state(a.survey, state)
    print(f"seeding marked done for '{a.survey}' ({a.seeded} seeded).")


# ---------------------------------------------------------------------------
# per-paper step machine
# ---------------------------------------------------------------------------

def cmd_start_paper(a):
    state = load_state(a.survey)
    if state.get("current") is not None:
        die(f"'{a.survey}' already has a paper in progress ({state['current']['slug']}, "
            f"step={state['current']['step']}). Finish or skip it first.")
    state["current"] = {
        "slug": a.slug,
        "queue_title": a.title,
        "arxiv_id": a.arxiv_id,
        "step": "resolve",
        "round": None,
        "open_blockers": [],
    }
    state["phase"] = "processing"
    append_log(state, f"started {a.slug} ({a.title!r})")
    save_state(a.survey, state)
    print(f"started '{a.slug}' for '{a.survey}' at step=resolve.")


def cmd_set_step(a):
    state = load_state(a.survey)
    cur = state.get("current")
    if cur is None:
        die(f"'{a.survey}' has no paper in progress. Call start-paper first.")
    prev = cur["step"]
    allowed = PAPER_TRANSITIONS.get(prev, set())
    if a.step not in allowed:
        die(f"illegal step transition for '{cur['slug']}': {prev!r} -> {a.step!r} "
            f"(allowed from {prev!r}: {sorted(allowed)}).")
    if a.step == "critique":
        if a.round is None:
            die("set-step critique requires --round.")
        prev_round = cur.get("round")
        expected = 1 if prev_round is None else prev_round + 1
        if a.round != expected:
            die(f"round mismatch for '{cur['slug']}': expected --round {expected} "
                f"(current round is {prev_round}), got {a.round}.")
        cur["round"] = a.round
    cur["step"] = a.step
    append_log(state, f"{cur['slug']}: step -> {a.step}" + (f" (round {cur['round']})" if a.step == "critique" else ""))
    save_state(a.survey, state)
    print(f"'{cur['slug']}' step -> {a.step}" + (f", round {cur['round']}" if a.step == "critique" else "") + ".")


def cmd_set_blockers(a):
    state = load_state(a.survey)
    cur = state.get("current")
    if cur is None:
        die(f"'{a.survey}' has no paper in progress.")
    critique_path = Path(a.critique_file)
    if not critique_path.exists():
        die(f"critique file not found: {critique_path}")
    critique = json.loads(critique_path.read_text())
    for key in ("verdict", "round", "blocking"):
        if key not in critique:
            die(f"critique file missing required key '{key}': {critique_path}")
    if critique["round"] != cur.get("round") and not a.force_round:
        die(f"critique round {critique['round']} does not match current round "
            f"{cur.get('round')} for '{cur['slug']}'. Pass --force-round to override.")
    cur["open_blockers"] = critique["blocking"]
    n = len(critique["blocking"])
    append_log(state, f"{cur['slug']}: {n} open blocker(s) from round {critique['round']} "
                       f"(verdict: {critique['verdict']})")
    save_state(a.survey, state)
    print(f"'{cur['slug']}' now has {n} open blocker(s) (round {critique['round']}, "
          f"verdict={critique['verdict']}).")


def cmd_complete_paper(a):
    state = load_state(a.survey)
    cur = state.get("current")
    if cur is None:
        die(f"'{a.survey}' has no paper in progress.")
    if a.verdict == "approved" and cur.get("open_blockers"):
        die(f"cannot complete '{cur['slug']}' as 'approved' with "
            f"{len(cur['open_blockers'])} open blocker(s) still on record. "
            f"Use --verdict approved_with_notes, or clear blockers first.")
    notes = list(a.notes or [])
    if a.verdict == "approved_with_notes" and not notes:
        notes = [b.get("issue", str(b)) for b in cur.get("open_blockers", [])]
    entry = {
        "slug": cur["slug"],
        "rounds": cur.get("round") or 0,
        "verdict": a.verdict,
        "notes": notes,
        "date": today(),
    }
    state.setdefault("completed", []).append(entry)
    append_log(state, f"completed {cur['slug']} (verdict={a.verdict}, rounds={entry['rounds']})")
    state["current"] = None
    save_state(a.survey, state)
    print(f"completed '{entry['slug']}' (verdict={a.verdict}, rounds={entry['rounds']}).")


def cmd_skip_paper(a):
    state = load_state(a.survey)
    cur = state.get("current")
    if cur is None:
        die(f"'{a.survey}' has no paper in progress to skip.")
    entry = {"title": cur["queue_title"], "slug": cur["slug"], "reason": a.reason, "date": today()}
    state.setdefault("skipped", []).append(entry)
    append_log(state, f"skipped {cur['slug']} ({a.reason})")
    state["current"] = None
    save_state(a.survey, state)
    print(f"skipped '{entry['slug']}': {a.reason}")


def cmd_log(a):
    state = load_state(a.survey)
    append_log(state, a.message)
    save_state(a.survey, state)
    print("logged.")


# ---------------------------------------------------------------------------
# survey-artifact build step machine (used by the future /survey skill)
# ---------------------------------------------------------------------------

def _default_survey_build():
    return {"step": None, "round": 0, "open_blockers": [], "taxonomy": False, "site": False, "pdf": False}


def cmd_set_survey_build_step(a):
    state = load_state(a.survey)
    sb = state.setdefault("survey_build", _default_survey_build())
    prev = sb.get("step")
    allowed = SURVEY_BUILD_TRANSITIONS.get(prev, set())
    if a.step not in allowed:
        die(f"illegal survey-build transition: {prev!r} -> {a.step!r} "
            f"(allowed from {prev!r}: {sorted(allowed)}).")
    if a.step == "critique":
        prev_round = sb.get("round") or 0
        expected = prev_round + 1
        if a.round is not None and a.round != expected:
            die(f"round mismatch: expected --round {expected} (current round is {prev_round}), "
                f"got {a.round}.")
        sb["round"] = expected
    sb["step"] = a.step
    if a.step == "taxonomy":
        sb["taxonomy"] = True
    if a.step == "site":
        sb["site"] = True
    append_log(state, f"survey_build: step -> {a.step}")
    save_state(a.survey, state)
    print(f"survey_build step -> {a.step}.")


def cmd_set_survey_blockers(a):
    state = load_state(a.survey)
    sb = state.setdefault("survey_build", _default_survey_build())
    if sb.get("step") is None:
        die(f"'{a.survey}' has no survey-build in progress.")
    critique_path = Path(a.critique_file)
    if not critique_path.exists():
        die(f"critique file not found: {critique_path}")
    critique = json.loads(critique_path.read_text())
    for key in ("verdict", "round", "blocking"):
        if key not in critique:
            die(f"critique file missing required key '{key}': {critique_path}")
    if critique["round"] != sb.get("round") and not a.force_round:
        die(f"critique round {critique['round']} does not match current survey_build round "
            f"{sb.get('round')} for '{a.survey}'. Pass --force-round to override.")
    sb["open_blockers"] = critique["blocking"]
    n = len(critique["blocking"])
    append_log(state, f"survey_build: {n} open blocker(s) from round {critique['round']} "
                       f"(verdict: {critique['verdict']})")
    save_state(a.survey, state)
    print(f"survey_build now has {n} open blocker(s) (round {critique['round']}, "
          f"verdict={critique['verdict']}).")


def cmd_complete_survey_build(a):
    state = load_state(a.survey)
    sb = state.setdefault("survey_build", _default_survey_build())
    if sb.get("step") is None:
        die(f"'{a.survey}' has no survey-build in progress.")
    if a.verdict == "approved" and sb.get("open_blockers"):
        die(f"cannot complete survey_build as 'approved' with "
            f"{len(sb['open_blockers'])} open blocker(s) still on record. "
            f"Use --verdict approved_with_notes, or clear blockers first.")
    notes = list(a.notes or [])
    if a.verdict == "approved_with_notes" and not notes:
        notes = [b.get("issue", str(b)) for b in sb.get("open_blockers", [])]
    rounds = sb.get("round") or 0
    append_log(state, f"survey_build completed (verdict={a.verdict}, rounds={rounds})"
                       + (f"; notes: {'; '.join(notes)}" if notes else ""))
    # reset for the next build cycle (a future refine run starts clean at `corpus`);
    # taxonomy/site stay True as a historical "has this ever been built" record.
    sb["step"] = None
    sb["round"] = 0
    sb["open_blockers"] = []
    save_state(a.survey, state)
    print(f"survey_build completed (verdict={a.verdict}, rounds={rounds}).")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def _load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def compute_status():
    surveys = _load_json(SURVEYS_JSON, {"surveys": []})["surveys"]
    papers = _load_json(ROOT / "data" / "papers.json", {"papers": []})["papers"]
    queue = _load_json(ROOT / "data" / "queue.json", [])

    rows = []
    for s in surveys:
        sid = s["id"]
        tagged = sum(1 for p in papers if sid in p.get("tags", []))
        q_core = sum(1 for q in queue if q.get("survey") == sid and q.get("role") == "core")
        q_found = sum(1 for q in queue if q.get("survey") == sid and q.get("role") == "foundational")
        sp = state_path(sid)
        state = json.loads(sp.read_text()) if sp.exists() else None
        row = {
            "id": sid,
            "label": s.get("label", sid),
            "tagged": tagged,
            "queue_core": q_core,
            "queue_foundational": q_found,
            "phase": (state or {}).get("phase", "idle"),
            "current": (state or {}).get("current"),
            "page": s.get("page"),
            "page_exists": bool(s.get("page")) and (ROOT / "public" / s["page"]).exists(),
            "pdf": s.get("pdf"),
            "pdf_exists": bool(s.get("pdf")) and (ROOT / "public" / s["pdf"]).exists(),
            "last_activity": (state["log"][-1] if state and state.get("log") else state["created"] if state else None),
        }
        rows.append(row)
    return rows


def cmd_status(a):
    rows = compute_status()
    if a.survey:
        rows = [r for r in rows if r["id"] == a.survey]
        if not rows:
            die(f"unknown survey id '{a.survey}'.")
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        print("no surveys defined in data/surveys.json.")
        return
    w_id = max(len("survey"), max(len(r["id"]) for r in rows))
    header = f"{'survey':<{w_id}}  {'tagged':>6}  {'core':>4}  {'found':>5}  {'phase':<11}  current"
    print(header)
    print("-" * len(header))
    for r in rows:
        cur = r["current"]
        cur_desc = "-"
        if cur:
            cur_desc = f"{cur['slug']} ({cur['step']}" + (f", round {cur['round']}" if cur.get("round") else "") + ")"
        print(f"{r['id']:<{w_id}}  {r['tagged']:>6}  {r['queue_core']:>4}  {r['queue_foundational']:>5}  "
              f"{r['phase']:<11}  {cur_desc}")


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="litsearch.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init")
    sp.add_argument("survey")
    sp.add_argument("--topic", required=True)
    sp.add_argument("--max-rounds", type=int, default=3)
    sp.add_argument("--builder-model", default="sonnet")
    sp.add_argument("--builder-effort", default="high")
    sp.add_argument("--critic-model", default="opus")
    sp.add_argument("--critic-effort", default="xhigh")
    sp.add_argument("--process-foundational", action="store_true")
    sp.add_argument("--seeding-done", action="store_true")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("seed-done")
    sp.add_argument("survey")
    sp.add_argument("--seeded", type=int, required=True)
    sp.add_argument("--query", action="append")
    sp.set_defaults(func=cmd_seed_done)

    sp = sub.add_parser("start-paper")
    sp.add_argument("survey")
    sp.add_argument("slug")
    sp.add_argument("--title", required=True)
    sp.add_argument("--arxiv-id", default=None)
    sp.set_defaults(func=cmd_start_paper)

    sp = sub.add_parser("set-step")
    sp.add_argument("survey")
    sp.add_argument("step", choices=PAPER_STEPS)
    sp.add_argument("--round", type=int, default=None)
    sp.set_defaults(func=cmd_set_step)

    sp = sub.add_parser("set-blockers")
    sp.add_argument("survey")
    sp.add_argument("critique_file")
    sp.add_argument("--force-round", action="store_true")
    sp.set_defaults(func=cmd_set_blockers)

    sp = sub.add_parser("complete-paper")
    sp.add_argument("survey")
    sp.add_argument("--verdict", required=True, choices=["approved", "approved_with_notes"])
    sp.add_argument("--notes", action="append")
    sp.set_defaults(func=cmd_complete_paper)

    sp = sub.add_parser("skip-paper")
    sp.add_argument("survey")
    sp.add_argument("--reason", required=True)
    sp.set_defaults(func=cmd_skip_paper)

    sp = sub.add_parser("log")
    sp.add_argument("survey")
    sp.add_argument("message")
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("set-survey-build-step")
    sp.add_argument("survey")
    sp.add_argument("step", choices=SURVEY_BUILD_STEPS)
    sp.add_argument("--round", type=int, default=None)
    sp.set_defaults(func=cmd_set_survey_build_step)

    sp = sub.add_parser("set-survey-blockers")
    sp.add_argument("survey")
    sp.add_argument("critique_file")
    sp.add_argument("--force-round", action="store_true")
    sp.set_defaults(func=cmd_set_survey_blockers)

    sp = sub.add_parser("complete-survey-build")
    sp.add_argument("survey")
    sp.add_argument("--verdict", required=True, choices=["approved", "approved_with_notes"])
    sp.add_argument("--notes", action="append")
    sp.set_defaults(func=cmd_complete_survey_build)

    sp = sub.add_parser("status")
    sp.add_argument("survey", nargs="?", default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
