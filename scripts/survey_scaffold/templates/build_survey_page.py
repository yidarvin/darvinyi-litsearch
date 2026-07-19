#!/usr/bin/env python3
"""Generate public/surveys/{{ID}}.html — the {{PAGE_TITLE}} survey page.
Reads data/{{ID}}-taxonomy.json (the classified corpus); emits a self-contained
dark long-read with inline-SVG charts and a filterable paper table.
Run: python scripts/{{ID}}_survey/build_survey_page.py

Scaffolded by scripts/survey_scaffold/new_survey.py — every TODO below is a
place the survey-author is expected to design for THIS survey's subject.
Follow the pattern in scripts/benchmarks_survey/build_survey_page.py (a
7-kingdom taxonomy tree) or scripts/evaluations_survey/build_survey_page.py +
charts_custom.py + stats_tokens.py (a more factored version with a novel
organizing axis) for two worked examples — don't reinvent the chart helpers,
scripts/survey_common/svgcharts.py already has stacked_bars/heatmap/MONO/etc.
"""
import json, collections, html, pathlib, sys

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent.parent
OUT = REPO / 'public' / 'surveys' / '{{ID}}.html'

# survey_common/svgcharts.py is the shared chart-primitive library — add it to
# the import path rather than copying it (unlike the two original bespoke
# builders, which predate this scaffold and each keep their own copy).
sys.path.insert(0, str(REPO / 'scripts' / 'survey_common'))
import svgcharts as sc

M = json.load(open(REPO / 'data' / '{{ID}}-taxonomy.json'))
N = len(M)

# ---------------- shared vocab ----------------
# TODO(survey-author): design 4-7 closed-vocabulary facets for this survey's
# subject (don't reuse another survey's facets by default). Every facet needs
# three things: the values list (order = display order), a hex-color map, and
# a display-label map. Example shape (delete once you have real facets):
EXAMPLE = ['value-a', 'value-b', 'value-c']
EXAMPLE_C = {'value-a': '#2dd4bf', 'value-b': '#c084fc', 'value-c': '#ffd166'}
EXAMPLE_L = {'value-a': 'Value A', 'value-b': 'Value B', 'value-c': 'Value C'}

ERAS = ['≤2018', '2019–20', '2021–22', '2023', '2024', '2025', '2026']
def era(y):
    if y <= 2018: return '≤2018'
    if y <= 2020: return '2019–20'
    if y <= 2022: return '2021–22'
    return str(y)

# ---------------- cross-tabs ----------------
# TODO(survey-author): one cross_era(...) per facet you want an era-trend
# chart for, mirroring either existing builder.
def cross_era(fn):
    c = collections.OrderedDict((e, collections.Counter()) for e in ERAS)
    for r in M:
        c[era(r['year'])][fn(r)] += 1
    return c

# ---------------- charts ----------------
charts = {}
# TODO(survey-author): replace with a real cross-tab once you have real facets.
_example_era = cross_era(lambda r: r.get('example_facet', 'value-a'))
charts['example'] = sc.stacked_bars(_example_era, EXAMPLE, EXAMPLE_C, EXAMPLE_L, pct=True,
                                    legend_cols=3, x_label='share of papers per era · example facet')

# ---------------- dimension-card chips ----------------
def chip_counts(fn, labels, colors=None, top=None):
    c = collections.Counter(fn(r) for r in M)
    items = c.most_common(top) if top else sorted(c.items(), key=lambda x: -x[1])
    outs = []
    for k, n in items:
        dot = f"<span class='d' style='background:{colors[k]}'></span>" if colors and k in colors else ''
        outs.append(f"<span class='chip'>{dot}{html.escape(str(labels.get(k, k)))} <b>{n}</b></span>")
    return ''.join(outs)

chips = {
    'example': chip_counts(lambda r: r.get('example_facet', 'value-a'), EXAMPLE_L, EXAMPLE_C),
}

# ---------------- the tree (optional — delete this block + the #tree section
# in survey_template.html if this survey doesn't need a kingdom/family
# taxonomy) ----------------
# TODO(survey-author): if used, every record needs `kingdom` ('X-name') and
# `family` ('X1-name') fields where family's first letter matches kingdom's.
tree_blocks_html = ''  # populate via a tree_blocks() function, see the two originals

# ---------------- table data ----------------
tbl = []
for r in sorted(M, key=lambda r: (-r['year'], r['short'].lower())):
    tbl.append({'s': r['slug'], 'n': r['short'], 'y': r['year']})
    # TODO(survey-author): add your facet keys here (short 1-2 letter keys,
    # matching the pattern in the two original builders) so the table's JS
    # filters can read them.
TABLE_JSON = json.dumps(tbl, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

# ---------------- numeric tokens (never hand-type a number in the template —
# compute it here or in stats_tokens.py and substitute via @@TOKEN@@) --------
import stats_tokens as st
tokens = st.compute(M, era, ERAS)
tokens['N'] = N

# ---------------- assemble ----------------
page = open(HERE / 'survey_template.html').read()
for k, v in charts.items():
    page = page.replace(f'@@CHART_{k.upper()}@@', v)
for k, v in chips.items():
    page = page.replace(f'@@CHIPS_{k.upper()}@@', v)
page = (page.replace('@@TABLE_JSON@@', TABLE_JSON)
            .replace('@@TREE_BLOCKS@@', tree_blocks_html))
for k, v in tokens.items():
    page = page.replace(f'@@{k}@@', str(v))

assert '@@' not in page, 'unresolved token: ' + page[page.index('@@'):page.index('@@') + 48]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page)
print(f'wrote {OUT} ({len(page) / 1024:.0f} KB)')
