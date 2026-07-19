#!/usr/bin/env python3
"""new_survey.py — scaffold scripts/<id>_survey/ for a brand-new survey.

    python scripts/survey_scaffold/new_survey.py <survey_id>

Stamps out `build_survey_page.py`, `survey_template.html`, and
`stats_tokens.py` from `scripts/survey_scaffold/templates/` into
`scripts/<id>_survey/`, following the same structural pattern the two
original (pre-scaffold) survey builders already use —
`scripts/benchmarks_survey/` and `scripts/evaluations_survey/` — but wired to
import the shared chart library (`scripts/survey_common/svgcharts.py`)
instead of keeping a private copy.

Only for a genuinely NEW survey id with no existing builder — this script
refuses to touch `scripts/benchmarks_survey/` or `scripts/evaluations_survey/`.
The output is a *starting point*, not a finished page: every file has
TODO(survey-author) markers where real facets, charts, and narrative belong;
see .claude/agents/survey-author.md for who fills those in and how.

Run from the repo root. Requires the survey id to already exist in
data/surveys.json (add it there first — Procedure D / the /litsearch skill's
Step 0 does this when a new topic is confirmed).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES = Path(__file__).resolve().parent / "templates"
SURVEYS_JSON = ROOT / "data" / "surveys.json"


def die(msg):
    sys.exit(f"new_survey: {msg}")


def hex_to_rgba(hexcolor, alpha):
    h = hexcolor.lstrip("#")
    if len(h) != 6:
        die(f"expected a 6-digit hex color, got {hexcolor!r}")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def main():
    if len(sys.argv) != 2:
        die("usage: new_survey.py <survey_id>")
    survey_id = sys.argv[1]

    surveys = json.loads(SURVEYS_JSON.read_text())["surveys"]
    entry = next((s for s in surveys if s["id"] == survey_id), None)
    if entry is None:
        die(f"'{survey_id}' is not in data/surveys.json. Add it there first "
            f"(known ids: {sorted(s['id'] for s in surveys)}).")

    out_dir = ROOT / "scripts" / f"{survey_id}_survey"
    if out_dir.exists():
        die(f"{out_dir} already exists. This script only scaffolds a brand-new "
            f"survey builder — if '{survey_id}' already has one, edit it directly "
            f"(or, for 'benchmarks'/'evaluations' specifically, see CLAUDE.md: "
            f"those are owned by the /survey pipeline / a bespoke hand-run script "
            f"respectively, never re-scaffolded).")

    color = entry.get("color", "#2dd4bf")
    accent_hex = color.lstrip("#")
    subs = {
        "{{ID}}": survey_id,
        "{{PAGE_TITLE}}": entry.get("label", survey_id),
        "{{DEK}}": entry.get("description", "TODO: one-sentence description."),
        "{{ACCENT_HEX}}": accent_hex,
        "{{ACCENT_SOFT}}": hex_to_rgba(color, ".12"),
    }

    out_dir.mkdir(parents=True)
    for tmpl_path in sorted(TEMPLATES.iterdir()):
        text = tmpl_path.read_text()
        for token, value in subs.items():
            text = text.replace(token, value)
        (out_dir / tmpl_path.name).write_text(text)
        print(f"wrote {out_dir / tmpl_path.name}")

    print(f"\nScaffolded scripts/{survey_id}_survey/. Next steps for the survey-author:")
    print(f"  1. Design 4-7 facets for '{survey_id}' in data/{survey_id}-taxonomy.json "
          f"(one record per tagged paper) — see data/evaluations-taxonomy.json for the shape.")
    print(f"  2. Fill in the TODO(survey-author) markers in "
          f"scripts/{survey_id}_survey/{{build_survey_page.py,survey_template.html,stats_tokens.py}}.")
    print(f"  3. Run: python scripts/{survey_id}_survey/build_survey_page.py")
    print(f"  4. Register \"page\": \"surveys/{survey_id}.html\" in data/surveys.json.")


if __name__ == "__main__":
    main()
