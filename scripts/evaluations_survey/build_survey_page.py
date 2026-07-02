#!/usr/bin/env python3
"""Generate public/surveys/evaluations.html — the Evaluations (evaluation-methodology) survey page.
Reads data/evaluations-taxonomy.json (the classified corpus of 59 eval-method papers); emits a
self-contained dark long-read with inline-SVG charts and a filterable table.
Run: python scripts/evaluations_survey/build_survey_page.py"""
import json, collections, html, pathlib
import svgcharts as sc

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent.parent
OUT = REPO / 'public' / 'surveys' / 'evaluations.html'

M = json.load(open(REPO / 'data' / 'evaluations-taxonomy.json'))
N = len(M)

# ---------------- shared vocab ----------------
ERAS = ['≤2018', '2019–21', '2022', '2023', '2024', '2025', '2026']
def era(y):
    if y <= 2018: return '≤2018'
    if y <= 2021: return '2019–21'
    return str(y)

# verdict engine — the ladder (cheap+rigid -> expensive+general)
ENG = ['lexical-overlap', 'learned-metric', 'execution-oracle', 'human-grading',
       'model-judge', 'decomposed-judge', 'process-monitor', 'statistical-protocol']
ENG_C = {'lexical-overlap': '#64748b', 'learned-metric': '#94a3b8', 'execution-oracle': '#4ade80',
         'human-grading': '#fb923c', 'model-judge': '#f472b6', 'decomposed-judge': '#c084fc',
         'process-monitor': '#22d3ee', 'statistical-protocol': '#ffd166'}
ENG_L = {'lexical-overlap': 'lexical overlap', 'learned-metric': 'learned metric',
         'execution-oracle': 'execution oracle', 'human-grading': 'human grading',
         'model-judge': 'model judge', 'decomposed-judge': 'decomposed judge',
         'process-monitor': 'process monitor', 'statistical-protocol': 'statistical protocol'}

CON = ['text-quality', 'task-capability', 'factuality', 'honesty', 'preference-alignment',
       'safety-propensity', 'security-robustness', 'fairness', 'oversight-viability', 'measurement-integrity']
CON_L = {'text-quality': 'text quality', 'task-capability': 'task capability', 'factuality': 'factuality',
         'honesty': 'honesty', 'preference-alignment': 'preference / helpfulness',
         'safety-propensity': 'safety & propensity', 'security-robustness': 'security & robustness',
         'fairness': 'fairness', 'oversight-viability': 'oversight viability',
         'measurement-integrity': 'measurement integrity'}

REF = ['gold-reference', 'test-oracle', 'human-preference', 'expert-rubric', 'judge-prior',
       'private-twin', 'model-process', 'none-self-referential']
REF_C = {'gold-reference': '#64748b', 'test-oracle': '#4ade80', 'human-preference': '#fb923c',
         'expert-rubric': '#ffd166', 'judge-prior': '#f472b6', 'private-twin': '#2dd4bf',
         'model-process': '#22d3ee', 'none-self-referential': '#3f3f46'}
REF_L = {'gold-reference': 'gold reference', 'test-oracle': 'test oracle', 'human-preference': 'human preference',
         'expert-rubric': 'expert rubric', 'judge-prior': 'judge’s own prior', 'private-twin': 'private twin',
         'model-process': 'model’s own process', 'none-self-referential': 'none / self-referential'}

FID = ['direct-outcome', 'expert-judgment', 'decomposed-proxy', 'holistic-model-proxy',
       'surface-correlate', 'elicited-behavior', 'aggregate-inference', 'process-transparency']
FID_C = {'direct-outcome': '#4ade80', 'expert-judgment': '#fb923c', 'decomposed-proxy': '#c084fc',
         'holistic-model-proxy': '#f472b6', 'surface-correlate': '#64748b', 'elicited-behavior': '#f87171',
         'aggregate-inference': '#ffd166', 'process-transparency': '#22d3ee'}
FID_L = {'direct-outcome': 'direct outcome', 'expert-judgment': 'expert judgment', 'decomposed-proxy': 'decomposed proxy',
         'holistic-model-proxy': 'holistic model proxy', 'surface-correlate': 'surface correlate',
         'elicited-behavior': 'elicited behavior', 'aggregate-inference': 'aggregate inference',
         'process-transparency': 'process transparency'}

RWD = ['reward-native', 'reward-adapted', 'diagnostic-only', 'optimization-forbidden']
RWD_C = {'reward-native': '#4ade80', 'reward-adapted': '#c084fc', 'diagnostic-only': '#64748b',
         'optimization-forbidden': '#f87171'}
RWD_L = {'reward-native': 'reward-native', 'reward-adapted': 'reward-adapted',
         'diagnostic-only': 'diagnostic-only', 'optimization-forbidden': 'optimization-forbidden'}

VAL = ['none', 'human-agreement', 'bias-audited', 'adversarial-stress']
VAL_C = {'none': '#3f3f46', 'human-agreement': '#22d3ee', 'bias-audited': '#c084fc', 'adversarial-stress': '#f87171'}
VAL_L = {'none': 'none', 'human-agreement': 'human agreement', 'bias-audited': 'bias-audited',
         'adversarial-stress': 'adversarial stress'}

GAP = ['no-model', 'weaker-ok', 'peer-or-stronger', 'human-anchored']
GAP_C = {'no-model': '#4ade80', 'weaker-ok': '#2dd4bf', 'peer-or-stronger': '#f472b6', 'human-anchored': '#fb923c'}
GAP_L = {'no-model': 'no model', 'weaker-ok': 'weaker grader OK', 'peer-or-stronger': 'peer-or-stronger judge',
         'human-anchored': 'human-anchored'}

# ---------------- cross-tabs ----------------
def cross_era(fn):
    c = collections.OrderedDict((e, collections.Counter()) for e in ERAS)
    for r in M:
        c[era(r['year'])][fn(r)] += 1
    return c

era_eng = cross_era(lambda r: r['verdict_engine'])
era_rwd = cross_era(lambda r: r['reward_readiness'])
era_ref = cross_era(lambda r: r['reference_standard'])
era_gap = cross_era(lambda r: r['grader_gap'])
era_val = cross_era(lambda r: r['validation_depth'])

# fidelity × reward-readiness heatmap grid
fid_rwd = collections.defaultdict(collections.Counter)
for r in M:
    fid_rwd[r['signal_fidelity']][r['reward_readiness']] += 1

# validation depth × engine
val_eng = collections.defaultdict(collections.Counter)
for r in M:
    val_eng[r['verdict_engine']][r['validation_depth']] += 1

# ---------------- charts (assigned after custom fns defined) ----------------
charts = {}
charts['engwaves'] = sc.stacked_bars(era_eng, ENG, ENG_C, ENG_L, pct=True, legend_cols=3,
                                     x_label='share of new evaluation-method papers per era · headline verdict engine')
charts['rwdwaves'] = sc.stacked_bars(era_rwd, RWD, RWD_C, RWD_L, pct=True, legend_cols=2,
                                     x_label='share of new evaluation-method papers per era · reward-readiness class')
charts['refwaves'] = sc.stacked_bars(era_ref, REF, REF_C, REF_L, pct=True, legend_cols=3,
                                     x_label='share per era · what the method consumes as ground truth')
charts['gapwaves'] = sc.stacked_bars(era_gap, GAP, GAP_C, GAP_L, pct=True, legend_cols=2,
                                     x_label='share per era · how capable the grader must be vs the graded')
charts['heat_fid_rwd'] = sc.heatmap(FID, RWD, fid_rwd, FID_L, RWD_L, accent='#c084fc', pad_l=150)
charts['heat_val_eng'] = sc.heatmap(ENG, VAL, val_eng, ENG_L, VAL_L, accent='#22d3ee', pad_l=150)

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
    'engine': chip_counts(lambda r: r['verdict_engine'], ENG_L, ENG_C),
    'construct': chip_counts(lambda r: r['construct'], CON_L, top=10),
    'ref': chip_counts(lambda r: r['reference_standard'], REF_L, REF_C),
    'fid': chip_counts(lambda r: r['signal_fidelity'], FID_L, FID_C),
    'rwd': chip_counts(lambda r: r['reward_readiness'], RWD_L, RWD_C),
    'val': chip_counts(lambda r: r['validation_depth'], VAL_L, VAL_C),
    'gap': chip_counts(lambda r: r['grader_gap'], GAP_L, GAP_C),
}

# ---------------- the tree ----------------
KING_C = {'S-scoring-metrics': '#64748b', 'V-verification-harnesses': '#4ade80',
          'P-preference-courts': '#fb923c', 'I-behavioral-probes': '#f87171',
          'M-process-surveillance': '#22d3ee', 'F-forensics-audits': '#c084fc',
          'T-measurement-theory': '#ffd166'}
KING_L = {
    'S-scoring-metrics': ('scoring metrics', 'What number captures this output’s quality?'),
    'V-verification-harnesses': ('verification harnesses', 'How do we make correctness mechanical?'),
    'P-preference-courts': ('preference courts', 'Which output do people or models prefer?'),
    'I-behavioral-probes': ('behavioral probes', 'What does the model do when we stage the situation?'),
    'M-process-surveillance': ('process surveillance', 'Can we watch it think — and does that survive optimization?'),
    'F-forensics-audits': ('forensics & audits', 'Is the measurement itself lying?'),
    'T-measurement-theory': ('measurement theory', 'What should we measure, and how do we aggregate it?'),
}
FAM_L = {
    'S1-lexical-overlap': ('S1 · lexical-overlap metrics', 'surface n-gram / LCS match to references'),
    'S2-learned-neural': ('S2 · learned & neural metrics', 'a trained model scores against a reference'),
    'S3-reference-free-scorers': ('S3 · reference-free scorers', 'a model scores quality with no gold key'),
    'V1-execution-oracles': ('V1 · execution oracles', 'run it, check the outcome mechanically'),
    'V2-rubric-verifiers': ('V2 · rubric verifiers', 'decompose the verdict into checkable criteria'),
    'V3-agentic-work-harnesses': ('V3 · agentic-work harnesses', 'score competence inside an interactive task'),
    'P1-human-preference-arenas': ('P1 · human-preference arenas', 'crowd pairwise votes, aggregated'),
    'P2-judge-protocols': ('P2 · judge protocols', 'a model-judge pairwise protocol as the contribution'),
    'I1-honesty-deception': ('I1 · honesty & deception probes', 'stage a temptation to lie or scheme'),
    'I2-danger-propensity': ('I2 · dangerous-capability & propensity', 'would it, and can the skill be recovered?'),
    'I3-adversarial-robustness': ('I3 · adversarial-robustness probes', 'attack the model and score what breaks'),
    'I4-fairness-harm-audits': ('I4 · fairness & harm audits', 'disaggregate accuracy or clinical harm'),
    'M1-cot-monitoring': ('M1 · CoT monitoring & monitorability', 'read the reasoning trace for intent'),
    'M2-faithfulness-tests': ('M2 · faithfulness tests', 'does the CoT reflect the real computation?'),
    'M3-control-protocols': ('M3 · control protocols', 'worst-case safety of a deployment protocol'),
    'F1-contamination-forensics': ('F1 · contamination forensics', 'measure test-set leakage into scores'),
    'F2-judge-bias-audits': ('F2 · judge-bias audits', 'expose the biases of model-judges'),
    'F3-metric-construct-critiques': ('F3 · metric & construct critiques', 'show a metric measures the wrong thing'),
    'F4-reward-hacking-forensics': ('F4 · reward-hacking forensics', 'catch a policy gaming its own reward'),
    'F5-benchmark-rigor-standards': ('F5 · benchmark-rigor standards', 'a checklist for building sound evals'),
    'T1-holistic-frameworks': ('T1 · holistic frameworks', 'aggregate many scenarios and metrics'),
    'T2-capability-axis-instruments': ('T2 · capability-axis instruments', 'a single non-saturating measuring stick'),
}
KINGS = list(KING_L)
by_family = collections.defaultdict(list)
for r in M:
    by_family[r['family']].append(r)
for f in by_family:
    by_family[f].sort(key=lambda r: (r['year'], r['short'].lower()))
FAMS_BY_KING = {k: [f for f in FAM_L if f.startswith(k[0] + ('' if f[1].isdigit() else ''))] for k in KINGS}
# families belong to a kingdom by first letter
FAMS_BY_KING = {k: [f for f in FAM_L if f[0] == k[0]] for k in KINGS}

# ---------------- table data ----------------
tbl = []
for r in sorted(M, key=lambda r: (-r['year'], r['short'].lower())):
    tbl.append({
        's': r['slug'], 'n': r['short'], 'y': r['year'],
        'e': r['verdict_engine'], 'co': r['construct'], 'rf': r['reference_standard'],
        'fi': r['signal_fidelity'], 'rw': r['reward_readiness'], 'va': r['validation_depth'],
        'ga': r['grader_gap'], 'k': r['kingdom'], 'f': r['family'],
        'm': 1 if r['meta_eval'] else 0, 'o': r['one_line'],
    })
TABLE_JSON = json.dumps(tbl, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

ENG_OPTS = ''.join(f"<option value='{k}'>{ENG_L[k]}</option>" for k in ENG)
CON_OPTS = ''.join(f"<option value='{k}'>{v}</option>" for k, v in sorted(CON_L.items(), key=lambda x: x[1]))
RWD_OPTS = ''.join(f"<option value='{k}'>{RWD_L[k]}</option>" for k in RWD)
KING_OPTS = ''.join(f"<option value='{k}'>{KING_L[k][0]}</option>" for k in KINGS)

JS_COLORS = json.dumps({'e': ENG_C, 'rw': RWD_C, 'k': KING_C, 'rf': REF_C, 'fi': FID_C,
                        'va': VAL_C, 'ga': GAP_C}, separators=(',', ':'))
JS_LABELS = json.dumps({'e': ENG_L, 'co': CON_L, 'rf': REF_L, 'fi': FID_L, 'rw': RWD_L,
                        'va': VAL_L, 'ga': GAP_L, 'k': {k: KING_L[k][0] for k in KINGS},
                        'f': {f: FAM_L[f][0] for f in FAM_L}}, ensure_ascii=False, separators=(',', ':'))

# ---- custom charts (defined in a second module section for readability) ----
import charts_custom as cc
cc.bind(M, sc, dict(ENG=ENG, ENG_C=ENG_C, ENG_L=ENG_L, RWD=RWD, RWD_C=RWD_C, RWD_L=RWD_L,
                    KINGS=KINGS, KING_C=KING_C, KING_L=KING_L, FAM_L=FAM_L, by_family=by_family,
                    FAMS_BY_KING=FAMS_BY_KING, era=era, ERAS=ERAS))
charts['engladder'] = cc.engine_ladder_svg()
charts['rwdladder'] = cc.reward_ladder_svg()
charts['tree'] = cc.tree_skeleton_svg()
charts['absorption'] = cc.absorption_svg()

def tree_blocks():
    out = []
    for k in KINGS:
        col = KING_C[k]
        name, q = KING_L[k]
        kf = FAMS_BY_KING[k]
        n = sum(len(by_family[f]) for f in kf)
        fams_html = []
        for f in kf:
            chips_h = ''.join(
                f"<a class='tchip' href='/papers/{r['slug']}.html' title='{html.escape(r.get('placement_reason', ''), quote=True)}'>{html.escape(r['short'])}<span>’{str(r['year'])[2:]}</span></a>"
                for r in by_family[f])
            lbl, dfn = FAM_L[f]
            if not by_family[f]:
                continue
            fams_html.append(f"<div class='fam'><div class='fnm mono'>{lbl} <span class='fdef'>— {dfn}</span><span class='fn'>{len(by_family[f])}</span></div><div class='tchips'>{chips_h}</div></div>")
        out.append(f"<div class='kingdom' style='--kc:{col}'><div class='khead'><span class='klet mono'>{k[0]}</span><div class='kt'><div class='knm'>{name}</div><div class='kq'>{q}</div></div><span class='kn mono'>{n}</span></div>{''.join(fams_html)}</div>")
    return ''.join(out)

# ---------------- assemble ----------------
page = open(HERE / 'survey_template.html').read()
for k, v in charts.items():
    page = page.replace(f'@@CHART_{k.upper()}@@', v)
for k, v in chips.items():
    page = page.replace(f'@@CHIPS_{k.upper()}@@', v)
page = (page.replace('@@TABLE_JSON@@', TABLE_JSON)
            .replace('@@ENG_OPTS@@', ENG_OPTS).replace('@@CON_OPTS@@', CON_OPTS)
            .replace('@@RWD_OPTS@@', RWD_OPTS).replace('@@KING_OPTS@@', KING_OPTS)
            .replace('@@TREE_BLOCKS@@', tree_blocks())
            .replace('@@JS_COLORS@@', JS_COLORS).replace('@@JS_LABELS@@', JS_LABELS))

# numeric tokens computed from the corpus (so prose never drifts from data)
import stats_tokens as st
for k, v in st.compute(M, era, ERAS).items():
    page = page.replace(f'@@{k}@@', str(v))

assert '@@' not in page, 'unresolved token: ' + page[page.index('@@'):page.index('@@') + 48]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page)
print(f'wrote {OUT} ({len(page) / 1024:.0f} KB)')
