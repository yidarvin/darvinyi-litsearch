#!/usr/bin/env python3
"""export_figures.py — export a survey page's inline SVG charts to PDF figures.

    .venv-cairo/bin/python3 scripts/survey_scaffold/export_figures.py <survey_id> \\
        [chart ...] [--viewbox-width NAME=W]

Third sibling of tokens_to_tex.py and make_bib.py, and the same trick: import
`scripts/<id>_survey/build_survey_page.py` (running its build as a harmless,
idempotent side effect) and read the module-level `charts` dict it computes, so
a figure in the PDF is the *same chart the site draws from the same taxonomy*,
not a re-drawn copy that can drift from it. Writes `paper/<id>/figures/<name>.pdf`
for each requested chart (default: all of them).

MUST be run with `.venv-cairo/bin/python3`, not a bare `python3` — cairosvg's
native cairo dylib is unreachable from the system interpreter this repo's other
scripts use. See scripts/requirements-tex.txt for the setup and for the macOS
SIP trap behind it.

Three normalisations happen on the way out, all because the charts are authored
for *inline* SVG inside an HTML page while cairosvg parses standalone XML:

  1. `&nbsp;` and bare `&` ("A1 · perception & parsing") -> XML entities. The
     HTML parser tolerates both; an XML parser rejects the document outright.
  2. bare `<` in text ("open (<60%)") -> `&lt;`, same reason.
  3. four glyphs the charts use -> ASCII. The browser resolves 'JetBrains
     Mono'/'Inter' plus a deep fallback chain; cairo resolves whatever is
     installed locally, and (verified 2026-08-15 by rendering all thirteen
     non-ASCII glyphs the benchmarks charts use) exactly four are missing from
     it and come out as tofu boxes. The other nine render fine and are left
     alone. Substituting is a rendering fallback, not an edit: no number, name,
     or label changes.

None of the three is fixed in the chart source, because the chart source is
correct for its primary target (an HTML page) and the site is the artifact
readers actually load.

`--viewbox-width NAME=W` widens one chart's viewBox for the export only. Its
use so far: the benchmarks tree draws family bars `count * 5.5` px wide from
x=770 inside an 860-wide viewBox, so at 369 papers the biggest families run off
the right edge and their count labels are clipped away entirely. Widening the
*viewport* moves no drawing coordinate and re-lays-out nothing; the already-drawn
bars simply stop being clipped.
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

GLYPH_FALLBACK = {'→': '->', '↔': '<->', '≳': '>~', '▶': '>'}


def die(msg):
    sys.exit(f"export_figures: {msg}")


def load_charts(survey_id):
    survey_dir = ROOT / "scripts" / f"{survey_id}_survey"
    build_script = survey_dir / "build_survey_page.py"
    if not build_script.exists():
        die(f"{build_script} not found — run the 'site' step first.")
    sys.path.insert(0, str(survey_dir))  # its bare `import svgcharts` resolves here
    spec = importlib.util.spec_from_file_location(f"{survey_id}_build_survey_page", build_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "charts"):
        die(f"{build_script} has no module-level `charts` dict "
            f"({{name: svg_string}}) — see scripts/benchmarks_survey/ for the pattern.")
    return module.charts


def normalise(svg, viewbox_width=None):
    svg = svg.replace("&nbsp;", "&#160;")
    for glyph, ascii_ in GLYPH_FALLBACK.items():
        svg = svg.replace(glyph, ascii_)
    svg = re.sub(r"&(?!(?:amp|lt|gt|quot|apos);|#\d+;)", "&amp;", svg)
    svg = re.sub(r"<(?![/?!a-zA-Z])", "&lt;", svg)
    if viewbox_width:
        svg = re.sub(r"viewBox='0 0 [\d.]+ ", f"viewBox='0 0 {viewbox_width} ", svg, count=1)
    return svg


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("survey")
    ap.add_argument("charts", nargs="*", help="chart names (default: every chart the builder computes)")
    ap.add_argument("--viewbox-width", action="append", default=[], metavar="NAME=W",
                    help="widen one chart's viewBox for the export only")
    a = ap.parse_args()

    widen = {}
    for spec in a.viewbox_width:
        if "=" not in spec:
            die(f"--viewbox-width wants NAME=W, got {spec!r}")
        name, _, w = spec.partition("=")
        widen[name] = w

    charts = load_charts(a.survey)
    names = a.charts or sorted(charts)
    unknown = [n for n in names if n not in charts] + [n for n in widen if n not in charts]
    if unknown:
        die(f"unknown chart(s) {sorted(set(unknown))}; builder computes {sorted(charts)}")

    try:
        import cairosvg
    except ImportError:
        die("cairosvg not importable — run this with .venv-cairo/bin/python3 "
            "(see scripts/requirements-tex.txt).")

    out_dir = ROOT / "paper" / a.survey / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        dest = out_dir / f"{name}.pdf"
        cairosvg.svg2pdf(bytestring=normalise(charts[name], widen.get(name)).encode("utf-8"),
                         write_to=str(dest), background_color="#141417")  # the page's --panel
        print(f"wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
