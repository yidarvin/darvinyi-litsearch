#!/usr/bin/env python3
"""Generate public/surveys/benchmarks.html — the Benchmarks survey taxonomy page.
Reads data/benchmarks-taxonomy.json (the classified corpus); emits a self-contained
dark long-read with inline-SVG charts and a filterable paper table.
Run: python scripts/benchmarks_survey/build_survey_page.py"""
import json, collections, html, pathlib
import svgcharts as sc

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent.parent
OUT = REPO / 'public' / 'surveys' / 'benchmarks.html'

merged = json.load(open(REPO / 'data' / 'benchmarks-taxonomy.json'))
N = len(merged)

# ---------------- shared vocab ----------------
ERAS = ['≤2018', '2019–20', '2021–22', '2023', '2024', '2025', '2026']
def era(y):
    if y <= 2018: return '≤2018'
    if y <= 2020: return '2019–20'
    if y <= 2022: return '2021–22'
    return str(y)

GR = ['proxy-metric', 'exact-match', 'programmatic', 'human', 'llm-judge', 'rubric-judge']
GR_C = {'proxy-metric': '#64748b', 'exact-match': '#2dd4bf', 'programmatic': '#4ade80',
        'human': '#fb923c', 'llm-judge': '#f472b6', 'rubric-judge': '#c084fc'}
GR_L = {'proxy-metric': 'proxy metric', 'exact-match': 'exact match', 'programmatic': 'programmatic',
        'human': 'human', 'llm-judge': 'LLM judge', 'rubric-judge': 'rubric + judge'}

LEV = ['L1-seconds', 'L2-minutes', 'L3-hours', 'L4-days', 'L5-weeks']
LEV_C = {'L1-seconds': '#2dd4bf', 'L2-minutes': '#4ade80', 'L3-hours': '#ffd166',
         'L4-days': '#fb923c', 'L5-weeks': '#f87171'}
LEV_L = {'L1-seconds': 'L1 · seconds', 'L2-minutes': 'L2 · minutes', 'L3-hours': 'L3 · hours',
         'L4-days': 'L4 · days', 'L5-weeks': 'L5 · weeks'}

SHAPES = ['single-turn', 'multi-turn', 'interactive-env']
SH_C = {'single-turn': '#64748b', 'multi-turn': '#22d3ee', 'interactive-env': '#ffd166'}
SH_L = {'single-turn': 'single-turn', 'multi-turn': 'multi-turn dialogue', 'interactive-env': 'interactive environment'}

PROV = ['crowdsourced', 'exam-derived', 'aggregated', 'synthetic-generated', 'user-traffic',
        'expert-authored', 'real-work-mined']
PR_C = {'crowdsourced': '#64748b', 'exam-derived': '#94a3b8', 'expert-authored': '#ffd166',
        'real-work-mined': '#fb923c', 'synthetic-generated': '#c084fc', 'user-traffic': '#f472b6',
        'aggregated': '#22d3ee'}
PR_L = {'crowdsourced': 'crowdsourced', 'exam-derived': 'exam-derived', 'expert-authored': 'expert-authored',
        'real-work-mined': 'real-work-mined', 'synthetic-generated': 'synthetic', 'user-traffic': 'user traffic',
        'aggregated': 'aggregated'}

CONTAM = ['none-public', 'canary', 'procedural', 'private-holdout', 'live-refresh']
CT_C = {'none-public': '#3f3f46', 'private-holdout': '#2dd4bf', 'canary': '#94a3b8',
        'procedural': '#c084fc', 'live-refresh': '#ffd166'}
CT_L = {'none-public': 'public, no defense', 'private-holdout': 'private holdout', 'canary': 'canary strings',
        'procedural': 'procedural generation', 'live-refresh': 'live refresh'}

SAT_C = {'saturated': '#f87171', 'closing': '#fb923c', 'open': '#4ade80', 'not-applicable': '#64748b'}

DOM_L = {'coding': 'coding', 'math': 'math', 'science': 'science', 'knowledge': 'knowledge',
         'language': 'language', 'reasoning': 'reasoning', 'agentic-web': 'web & computer use',
         'tool-use': 'tool use', 'professional': 'professional work', 'ai-rd': 'AI R&D',
         'safety': 'safety', 'instruction-following': 'instruction following', 'long-context': 'long context & retrieval',
         'multimodal': 'multimodal', 'conversation': 'conversation', 'forecasting': 'forecasting',
         'social-moral': 'social & moral'}
TOOL_L = {'none': 'none', 'code-exec': 'code exec', 'search-retrieval': 'search', 'browser': 'browser',
          'computer-os': 'computer/OS', 'domain-api': 'domain APIs'}

# ---------------- cross-tabs ----------------
def cross_era(fn):
    c = collections.OrderedDict((e, collections.Counter()) for e in ERAS)
    for r in merged:
        c[era(r['year'])][fn(r)] += 1
    return c

era_grading = cross_era(lambda r: r['grading_primary'])
era_shape = cross_era(lambda r: r['task_shape'])
era_prov = cross_era(lambda r: r['provenance'])
era_contam = cross_era(lambda r: r['contamination_defense'])

era_n = {e: sum(v.values()) for e, v in era_grading.items()}
def era_lbl(c):
    return collections.OrderedDict((f'{e}', v) for e, v in c.items())

cx_grid = collections.defaultdict(collections.Counter)
for r in merged:
    cx_grid[r['complexity']][r['grading_primary']] += 1

l3plus = []
for e in ERAS:
    rows = [r for r in merged if era(r['year']) == e]
    share = 100 * sum(1 for r in rows if r['complexity'] in ('L3-hours', 'L4-days', 'L5-weeks')) / len(rows)
    l3plus.append((e, round(share)))

sat_by_lev = collections.defaultdict(collections.Counter)
for r in merged:
    sat_by_lev[r['complexity']][r['saturation']] += 1

# ---------------- charts ----------------
charts = {}
charts['waves'] = sc.stacked_bars(era_grading, GR, GR_C, GR_L, pct=True, legend_cols=3,
                                  x_label='share of new benchmark papers per era · headline grading mechanism')
charts['frontier'] = sc.heatmap(LEV, GR, cx_grid, LEV_L, GR_L, accent='#ffd166', pad_l=126)
charts['climb'] = sc.line_chart(l3plus, color='#ffd166', y_max=100,
                                y_ticks=[0, 25, 50, 75, 100], y_fmt=lambda v: f'{int(v)}%',
                                dot_labels=lambda v: f'{v}%')
charts['shape'] = sc.stacked_bars(era_shape, SHAPES, SH_C, SH_L, pct=True, legend_cols=3,
                                  x_label='share of new benchmark papers per era · task shape')
charts['prov'] = sc.stacked_bars(era_prov, PROV, PR_C, PR_L, pct=True, legend_cols=4,
                                 x_label='share of new benchmark papers per era · where the task items come from')
charts['contam'] = sc.stacked_bars(era_contam, CONTAM, CT_C, CT_L, pct=True, legend_cols=3,
                                   x_label='share of new benchmark papers per era · strongest shipped defense')

# horizon ladder (custom): ascending steps L1→L5
def ladder_svg():
    W, H = 860, 356
    ranges = ['&lt; 1 min', '1–30 min', '30 min – 1 day', '1 day – 2 wks', '&gt; 2 wks']
    examples = [['MMLU', 'HellaSwag', 'ImageNet'], ['GSM8K', 'HumanEval', 'MT-Bench'],
                ['SWE-bench', 'MLE-bench', 'BrowseComp'], ['GDPval', 'PaperBench', 'RLI'], ['(empty)']]
    counts = [sum(1 for r in merged if r['complexity'] == l) for l in LEV]
    step_w, x0 = 158, 24
    hb, rise = 132, 32          # equal-height tiles, tops ascending left→right
    base_top = 172              # L1 tile top; tile i top = base_top - i*rise
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    for i, l in enumerate(LEV):
        x = x0 + i * (step_w + 8)
        y = base_top - i * rise
        col = LEV_C[l]
        empty = counts[i] == 0
        fill = 'none' if empty else col
        out.append(f"<rect x='{x}' y='{y}' width='{step_w}' height='{hb}' rx='9' fill='{fill}' fill-opacity='{0 if empty else 0.16}' stroke='{col}' stroke-width='1.6' stroke-dasharray='{'5 5' if empty else 'none'}'/>")
        out.append(f"<text x='{x + 12}' y='{y + 24}' font-size='14' font-weight='700' fill='{col}' {sc.MONO}>{l.split('-')[0]}</text>")
        out.append(f"<text x='{x + 12}' y='{y + 42}' font-size='11' fill='{sc.DIM}' {sc.MONO}>{ranges[i]}</text>")
        out.append(f"<text x='{x + step_w - 12}' y='{y + 24}' text-anchor='end' font-size='12' fill='{sc.MUTED}' {sc.MONO}>n={counts[i]}</text>")
        for j, ex in enumerate(examples[i]):
            out.append(f"<text x='{x + 12}' y='{y + 66 + j * 16}' font-size='10.5' fill='{sc.MUTED}' {sc.SANS}>{ex}</text>")
    out.append(f"<line x1='{x0}' y1='{H - 40}' x2='{W - 30}' y2='{H - 40}' stroke='{sc.LINE}' stroke-width='1'/>")
    out.append(f"<text x='{W - 30}' y='{H - 47}' text-anchor='end' font-size='10' fill='{sc.MUTED}' {sc.MONO}>longer&nbsp;→</text>")
    out.append(f"<text x='{x0}' y='{H - 16}' font-size='11' fill='{sc.MUTED}' {sc.MONO}>task horizon = wall-clock time one typical task instance costs a competent human expert</text>")
    out.append('</svg>')
    return ''.join(out)
charts['ladder'] = ladder_svg()

# grading-cost ladder (custom)
def grading_ladder_svg():
    W, H = 860, 268
    fams = [
        ('exact-match', 'string / choice match', '≈ free per item', 'answer key is the grader'),
        ('programmatic', 'tests · checkers · env state', 'build a harness once', 'ABC: 7/10 graders unsound'),
        ('llm-judge', 'holistic model judge', 'one model call', 'GPT-4↔human 85% (humans 81%)'),
        ('rubric-judge', 'per-item rubric + judge', 'experts author criteria', 'HealthBench: 48,562 criteria'),
        ('human', 'expert / preference grading', 'expert-hours per item', 'GDPval: &gt;1 h per grade'),
    ]
    bw, gap, x0, y0, bh = 152, 10, 24, 96, 92
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    # verifiable bracket over first two
    out.append(f"<path d='M{x0} 62 v-10 h{bw * 2 + gap} v10' fill='none' stroke='#4ade80' stroke-width='1.4'/>")
    out.append(f"<text x='{x0 + bw + gap / 2}' y='40' text-anchor='middle' font-size='11' fill='#4ade80' {sc.MONO}>mechanically verifiable → reusable as an RL reward</text>")
    # model-graded bracket over 3rd+4th
    bx = x0 + 2 * (bw + gap)
    out.append(f"<path d='M{bx} 62 v-10 h{bw * 2 + gap} v10' fill='none' stroke='#c084fc' stroke-width='1.4'/>")
    out.append(f"<text x='{bx + bw + gap / 2}' y='40' text-anchor='middle' font-size='11' fill='#c084fc' {sc.MONO}>model-graded → who grades the grader?</text>")
    for i, (k, sub, cost, note) in enumerate(fams):
        x = x0 + i * (bw + gap)
        col = GR_C[k]
        out.append(f"<rect x='{x}' y='{y0}' width='{bw}' height='{bh}' rx='9' fill='{col}' fill-opacity='0.13' stroke='{col}' stroke-width='1.5'/>")
        out.append(f"<text x='{x + 11}' y='{y0 + 23}' font-size='12.5' font-weight='700' fill='{col}' {sc.MONO}>{GR_L[k]}</text>")
        out.append(f"<text x='{x + 11}' y='{y0 + 42}' font-size='10' fill='{sc.DIM}' {sc.SANS}>{sub}</text>")
        out.append(f"<text x='{x + 11}' y='{y0 + 60}' font-size='10' fill='{sc.MUTED}' {sc.SANS}>{cost}</text>")
        out.append(f"<text x='{x + bw / 2}' y='{y0 + bh + (22 if i % 2 == 0 else 40)}' text-anchor='middle' font-size='9.3' fill='{sc.MUTED}' {sc.SANS}>{note}</text>")
        if i < 4:
            out.append(f"<text x='{x + bw + gap / 2}' y='{y0 + bh / 2 + 4}' text-anchor='middle' font-size='13' fill='{sc.MUTED}'>→</text>")
    out.append(f"<line x1='{x0}' y1='{H - 26}' x2='{W - 30}' y2='{H - 26}' stroke='{sc.LINE}' stroke-width='1'/>")
    out.append(f"<text x='{x0}' y='{H - 8}' font-size='10.5' fill='{sc.MUTED}' {sc.MONO}>cost to grade one item →   (proxy metrics — BLEU/ROUGE, n={sum(1 for r in merged if r['grading_primary'] == 'proxy-metric')} — sit outside the ladder: cheap but no longer trusted)</text>")
    out.append('</svg>')
    return ''.join(out)
charts['grladder'] = grading_ladder_svg()

# saturation-by-horizon horizontal bars (custom)
def sat_bars_svg():
    W, H = 860, 230
    x0, bw_max, bh, gap, y0 = 150, 620, 34, 12, 18
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    for i, l in enumerate(LEV[:4]):
        y = y0 + i * (bh + gap)
        d = sat_by_lev[l]
        tot = sum(d.values()) or 1
        out.append(f"<text x='{x0 - 12}' y='{y + bh / 2 + 4}' text-anchor='end' font-size='11' fill='{sc.DIM}' {sc.MONO}>{LEV_L[l]}</text>")
        x = x0
        for s in ['saturated', 'closing', 'open', 'not-applicable']:
            v = d.get(s, 0)
            if not v: continue
            w = bw_max * v / tot
            out.append(f"<rect x='{x:.1f}' y='{y}' width='{max(w - 2, 1):.1f}' height='{bh}' rx='4' fill='{SAT_C[s]}' fill-opacity='0.75'><title>{LEV_L[l]} · {s}: {v}/{tot}</title></rect>")
            if w > 34:
                out.append(f"<text x='{x + w / 2:.1f}' y='{y + bh / 2 + 4}' text-anchor='middle' font-size='10.5' font-weight='600' fill='#0a0a0b' {sc.MONO}>{v}</text>")
            x += w
        satpct = round(100 * d.get('saturated', 0) / tot)
        out.append(f"<text x='{x0 + bw_max + 10}' y='{y + bh / 2 + 4}' font-size='10.5' fill='{sc.MUTED}' {sc.MONO}>{satpct}% sat.</text>")
    ly = y0 + 4 * (bh + gap) + 10
    for j, (s, lbl) in enumerate([('saturated', 'saturated (frontier ≳90%)'), ('closing', 'closing (60–90%)'), ('open', 'open (<60%)'), ('not-applicable', 'n/a (no ceiling)')]):
        cx = x0 + j * 165
        out.append(f"<rect x='{cx}' y='{ly - 8}' width='9' height='9' rx='2' fill='{SAT_C[s]}'/>")
        out.append(f"<text x='{cx + 14}' y='{ly}' font-size='10' fill='{sc.DIM}' {sc.MONO}>{lbl}</text>")
    out.append('</svg>')
    return ''.join(out)
charts['satbars'] = sat_bars_svg()

# ---------------- dimension-card chips ----------------
def chip_counts(fn, labels, colors=None, top=None):
    c = collections.Counter(fn(r) for r in merged)
    items = c.most_common(top) if top else sorted(c.items(), key=lambda x: -x[1])
    outs = []
    for k, n in items:
        dot = f"<span class='d' style='background:{colors[k]}'></span>" if colors and k in colors else ''
        outs.append(f"<span class='chip'>{dot}{html.escape(str(labels.get(k, k)))} <b>{n}</b></span>")
    return ''.join(outs)

chips = {
    'domain': chip_counts(lambda r: r['domain_primary'], DOM_L, top=8) + "<span class='chip more'>+9 more</span>",
    'shape': chip_counts(lambda r: r['task_shape'], SH_L, SH_C),
    'grading': chip_counts(lambda r: r['grading_primary'], GR_L, GR_C),
    'complexity': ''.join(f"<span class='chip'><span class='d' style='background:{LEV_C[l]}'></span>{LEV_L[l]} <b>{sum(1 for r in merged if r['complexity'] == l)}</b></span>" for l in LEV),
    'tools': chip_counts(lambda r: 'none' if r['tool_access'] == ['none'] else 'tools', {'none': 'none (pure text)', 'tools': 'some tool / environment'}, None),
    'prov': chip_counts(lambda r: r['provenance'], PR_L, PR_C),
    'contam': chip_counts(lambda r: r['contamination_defense'], CT_L, CT_C),
    'sat': chip_counts(lambda r: r['saturation'], {'saturated': 'saturated', 'closing': 'closing', 'open': 'open', 'not-applicable': 'n/a'}, SAT_C),
}

# ---------------- the tree: kingdoms / families ----------------
KING_C = {'A-capability': '#2dd4bf', 'B-audit': '#f472b6', 'C-frontier-walls': '#f87171',
          'D-deployment': '#ffd166', 'E-hazard': '#fb923c', 'F-reward-factories': '#c084fc',
          'G-meta-evaluation': '#22d3ee'}
KING_L = {
    'A-capability': ('capability probes', 'Can models do X yet?'),
    'B-audit': ('audit instruments', 'Is our measurement lying?'),
    'C-frontier-walls': ('frontier walls', 'Can we build something that stays unsolved?'),
    'D-deployment': ('deployment rehearsals', 'What happens when we ship it into this job?'),
    'E-hazard': ('hazard probes', 'What could go wrong?'),
    'F-reward-factories': ('reward factories', 'Can the benchmark generate its own training signal?'),
    'G-meta-evaluation': ('meta-evaluation & protocols', 'How should we evaluate at all?'),
}
FAM_L = {
    'A1-perception-parsing': ('A1 · perception & parsing', 'recognize, parse, entail, retrieve'),
    'A2-knowledge-exams': ('A2 · knowledge & exams', 'recall and apply knowledge under exam conditions'),
    'A3-closed-form-reasoning': ('A3 · closed-form reasoning', 'math, logic, puzzles with checkable answers'),
    'A4-program-synthesis': ('A4 · program synthesis', 'write, repair, and reason about code'),
    'A5-embodied-operation': ('A5 · embodied operation', 'operate an interactive environment'),
    'A6-tool-orchestration': ('A6 · tool orchestration', 'select and sequence external tools & APIs'),
    'A7-communication': ('A7 · communication', 'follow instructions, converse, clarify'),
    'A8-research-execution': ('A8 · research execution', 'conduct open-ended knowledge work end-to-end'),
    'B1-contamination-twins': ('B1 · contamination twins', 'rebuilt withheld twins that measure overfitting'),
    'B2-grader-hardening': ('B2 · grader hardening', 'fix a broken grader of an existing benchmark'),
    'B3-desaturation-sequels': ('B3 · de-saturation sequels', 'same construct, headroom restored'),
    'B4-construct-audits': ('B4 · construct audits', 'expose that a score means something else'),
    'C1-summit-exams': ('C1 · summit exams', 'expert-authored, maximally hard, static'),
    'C2-inverse-verification': ('C2 · inverse verification', 'hard to solve, engineered easy to verify'),
    'C3-living-walls': ('C3 · living walls', 'unsaturable by construction — refresh by design'),
    'D1-economic-rehearsals': ('D1 · economic rehearsals', 'real paid work, dollar-weighted'),
    'D2-occupational-probes': ('D2 · occupational probes', 'professional-domain competence suites'),
    'D3-collaboration-rehearsals': ('D3 · collaboration rehearsals', 'the human stays in the loop'),
    'E1-attack-surfaces': ('E1 · attack surfaces', 'jailbreaks, injections, agent hijacking'),
    'E2-dangerous-capability-propensity': ('E2 · dangerous capability & propensity', 'hazardous knowledge, deception, unsafe preference'),
    'E3-values-judgment': ('E3 · values & judgment', 'moral, ethical, social judgment quality'),
    'F1-reward-factories': ('F1 · reward factories', 'generators and sandboxes meant to be trained on'),
    'G1-panoramas': ('G1 · panoramas', 'holistic aggregations of the eval landscape'),
    'G2-preference-protocols': ('G2 · preference protocols', 'arenas, Elo, pairwise judging as the contribution'),
    'G3-grader-benchmarks': ('G3 · grader benchmarks', 'judge protocols and error taxonomies'),
}
KINGS = list(KING_L)
by_family = collections.defaultdict(list)
for r in merged:
    by_family[r['family']].append(r)
for f in by_family:
    by_family[f].sort(key=lambda r: (r['year'], r['short'].lower()))


# ---------------- table data ----------------
tbl = []
for r in sorted(merged, key=lambda r: (-r['year'], r['short'].lower())):
    tbl.append({
        's': r['slug'], 'n': r['short'], 'y': r['year'],
        'd': r['domain_primary'], 'g': r['grading_primary'], 'c': r['complexity'].split('-')[0],
        'sh': r['task_shape'], 't': '·'.join(TOOL_L[t] for t in r['tool_access']),
        'k': r['kingdom'], 'f': r['family'],
        'o': r['one_line'],
    })
TABLE_JSON = json.dumps(tbl, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

DOM_OPTS = ''.join(f"<option value='{k}'>{v}</option>" for k, v in sorted(DOM_L.items(), key=lambda x: x[1]))
GR_OPTS = ''.join(f"<option value='{k}'>{GR_L[k]}</option>" for k in GR)
LEV_OPTS = ''.join(f"<option value='{l.split('-')[0]}'>{LEV_L[l]}</option>" for l in LEV[:4])
SH_OPTS = ''.join(f"<option value='{k}'>{SH_L[k]}</option>" for k in SHAPES)
KING_OPTS = ''.join(f"<option value='{k}'>{KING_L[k][0]}</option>" for k in KINGS)

# colour maps for the table renderer
JS_COLORS = json.dumps({'d': {k: '#9aa0aa' for k in DOM_L}, 'g': GR_C,
                        'c': {l.split('-')[0]: LEV_C[l] for l in LEV},
                        'sh': SH_C, 'k': KING_C}, separators=(',', ':'))
JS_LABELS = json.dumps({'d': DOM_L, 'g': GR_L, 'c': {l.split('-')[0]: LEV_L[l] for l in LEV}, 'sh': SH_L,
                        'f': {f: FAM_L[f][0] for f in FAM_L}},
                       ensure_ascii=False, separators=(',', ':'))

def tree_skeleton_svg():
    fams = [f for k in KINGS for f in FAM_L if f[0] == k[0]]
    row_h, top = 25, 16
    H = top + len(fams) * row_h + 18
    W = 860
    kx, fx = 250, 520
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    rooty = top + len(fams) * row_h / 2
    out.append(f"<text x='18' y='{rooty + 4:.0f}' font-size='12.5' font-weight='700' fill='{sc.FG}' {sc.MONO}>126</text>")
    out.append(f"<text x='18' y='{rooty + 20:.0f}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>benchmarks</text>")
    y = top
    for k in KINGS:
        kf = [f for f in fams if f[0] == k[0]]
        n = sum(len(by_family[f]) for f in kf)
        y0, y1 = y, y + len(kf) * row_h
        ky = (y0 + y1) / 2
        col = KING_C[k]
        out.append(f"<path d='M62 {rooty:.0f} C 120 {rooty:.0f} 120 {ky:.0f} {kx - 96} {ky:.0f}' fill='none' stroke='{sc.LINE}' stroke-width='1.4'/>")
        out.append(f"<text x='{kx - 88}' y='{ky + 4:.0f}' font-size='11.5' font-weight='700' fill='{col}' {sc.MONO}>{KING_L[k][0]}</text>")
        out.append(f"<text x='{kx + 116}' y='{ky + 4:.0f}' font-size='10' fill='{sc.MUTED}' {sc.MONO}>{n}</text>")
        for f in kf:
            fy = y + row_h / 2
            out.append(f"<path d='M{kx + 136} {ky:.0f} C {kx + 190} {ky:.0f} {kx + 190} {fy:.0f} {fx - 12} {fy:.0f}' fill='none' stroke='{sc.LINE}' stroke-width='1'/>")
            cnt = len(by_family[f])
            out.append(f"<text x='{fx}' y='{fy + 3.5:.0f}' font-size='10.5' fill='{sc.DIM}' {sc.MONO}>{FAM_L[f][0]}</text>")
            out.append(f"<rect x='{fx + 250}' y='{fy - 5:.0f}' width='{cnt * 5.5:.0f}' height='10' rx='2.5' fill='{col}' fill-opacity='0.55'/>")
            out.append(f"<text x='{fx + 256 + cnt * 5.5:.0f}' y='{fy + 3.5:.0f}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>{cnt}</text>")
            y += row_h
    out.append('</svg>')
    return ''.join(out)
charts['tree'] = tree_skeleton_svg()

def tree_blocks():
    out = []
    for k in KINGS:
        col = KING_C[k]
        name, q = KING_L[k]
        kf = [f for f in FAM_L if f[0] == k[0]]
        n = sum(len(by_family[f]) for f in kf)
        fams_html = []
        for f in kf:
            chips = ''.join(
                f"<a class='tchip' href='/papers/{r['slug']}.html' title='{html.escape(r.get('placement_reason', ''), quote=True)}'>{html.escape(r['short'])}<span>’{str(r['year'])[2:]}</span></a>"
                for r in by_family[f])
            lbl, dfn = FAM_L[f]
            fams_html.append(f"<div class='fam'><div class='fnm mono'>{lbl} <span class='fdef'>— {dfn}</span><span class='fn'>{len(by_family[f])}</span></div><div class='tchips'>{chips}</div></div>")
        out.append(f"<div class='kingdom' style='--kc:{col}'><div class='khead'><span class='klet mono'>{k[0]}</span><div class='kt'><div class='knm'>{name}</div><div class='kq'>{q}</div></div><span class='kn mono'>{n}</span></div>{''.join(fams_html)}</div>")
    return ''.join(out)

# audit-shadow timeline (verified pairs from the connections pass)
AUDIT_PAIRS = [
    ('ImageNet', 2009, 'ImageNetV2', 2019, 'fresh twin'),
    ('GLUE', 2018, 'SuperGLUE', 2019, 'harder sequel'),
    ('Natural Questions', 2019, 'SimpleQA', 2024, 'adversarial'),
    ('MMLU', 2020, 'MMLU-Pro', 2024, 'filtered rebuild'),
    ('HumanEval', 2021, 'EvalPlus', 2023, 'test audit'),
    ('HumanEval', 2021, 'LiveCodeBench', 2024, 'contamination'),
    ('GSM8K', 2021, 'GSM1k', 2024, 'private twin'),
    ('CUAD', 2021, 'ContractEval', 2025, 're-audit'),
    ('MT-Bench', 2023, 'Arena-Hard', 2024, 'separability'),
    ('LegalBench', 2023, 'LegalBench-RAG', 2024, 'inversion'),
    ('GPQA', 2023, 'HLE', 2025, 'replacement'),
    ('IFEval', 2023, 'AdvancedIF', 2025, 'harder sequel'),
    ('SWE-bench', 2023, 'SWE-Bench Pro', 2025, 'hardening'),
    ('SimpleQA', 2024, 'BrowseComp', 2025, 'same-lab'),
    ('MultiChallenge', 2025, 'Audio MultiChallenge', 2025, 'modality twin'),
    ('MCP-Universe', 2025, 'MCP-Atlas', 2026, 'verifier audit'),
]
def audit_shadow_svg():
    W = 960
    row_h, top, pad_l, pad_r = 25, 34, 200, 250
    H = top + len(AUDIT_PAIRS) * row_h + 40
    y0, y1 = 2008.5, 2026.5
    def X(yr):
        return pad_l + (yr - y0) / (y1 - y0) * (W - pad_l - pad_r)
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    for yr in range(2009, 2027, 2):
        x = X(yr)
        out.append(f"<line x1='{x:.0f}' y1='{top - 12}' x2='{x:.0f}' y2='{H - 30}' stroke='{sc.LINE}' stroke-width='1'/>")
        out.append(f"<text x='{x:.0f}' y='{top - 18}' text-anchor='middle' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>{yr}</text>")
    for i, (t, ty, a, ay, mode) in enumerate(AUDIT_PAIRS):
        y = top + i * row_h + row_h / 2
        lag = ay - ty
        col = '#f87171' if lag >= 5 else ('#fb923c' if lag >= 2 else '#4ade80')
        x1, x2 = X(ty), X(ay)
        out.append(f"<text x='{pad_l - 10}' y='{y + 3.5:.0f}' text-anchor='end' font-size='10' fill='{sc.DIM}' {sc.MONO}>{t}</text>")
        out.append(f"<circle cx='{x1:.0f}' cy='{y:.0f}' r='3.5' fill='{col}'/>")
        if x2 - x1 > 8:
            out.append(f"<line x1='{x1 + 4:.0f}' y1='{y:.0f}' x2='{x2 - 5:.0f}' y2='{y:.0f}' stroke='{col}' stroke-width='1.8'/>")
            out.append(f"<path d='M{x2 - 5:.0f} {y - 3.5:.0f} L{x2 + 1:.0f} {y:.0f} L{x2 - 5:.0f} {y + 3.5:.0f} Z' fill='{col}'/>")
        else:
            out.append(f"<circle cx='{x2:.0f}' cy='{y:.0f}' r='3.5' fill='none' stroke='{col}' stroke-width='1.6'/>")
        out.append(f"<text x='{x2 + 8:.0f}' y='{y + 3.5:.0f}' font-size='9.5' fill='{sc.DIM}' {sc.MONO}>{a} <tspan fill='{sc.MUTED}'>({lag}y · {mode})</tspan></text>")
    out.append(f"<text x='{pad_l}' y='{H - 10}' font-size='10' fill='{sc.MUTED}' {sc.MONO}>target ● ──▶ audit/sequel · red ≥5y, orange 2–4y, green ≤1y — the shadow arrives faster every generation</text>")
    out.append('</svg>')
    return ''.join(out)
charts['auditshadow'] = audit_shadow_svg()

page = open(HERE / 'survey_template.html').read()
for k, v in charts.items():
    page = page.replace(f'@@CHART_{k.upper()}@@', v)
for k, v in chips.items():
    page = page.replace(f'@@CHIPS_{k.upper()}@@', v)
page = (page.replace('@@TABLE_JSON@@', TABLE_JSON)
            .replace('@@DOM_OPTS@@', DOM_OPTS).replace('@@GR_OPTS@@', GR_OPTS)
            .replace('@@LEV_OPTS@@', LEV_OPTS).replace('@@SH_OPTS@@', SH_OPTS)
            .replace('@@KING_OPTS@@', KING_OPTS)
            .replace('@@TREE_BLOCKS@@', tree_blocks())
            .replace('@@JS_COLORS@@', JS_COLORS).replace('@@JS_LABELS@@', JS_LABELS))

assert '@@' not in page, 'unresolved token: ' + page[page.index('@@'):page.index('@@') + 40]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page)
print(f'wrote {OUT} ({len(page) / 1024:.0f} KB)')
