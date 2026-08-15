#!/usr/bin/env python3
"""Generate public/surveys/failure-modes.html — the Failure Modes survey page.
Reads data/failure-modes-taxonomy.json (the classified corpus); emits a self-contained
dark long-read with inline-SVG charts and a filterable paper table.
Run: python scripts/failure-modes_survey/build_survey_page.py

Structure follows scripts/evaluations_survey/ (builder + charts_custom + stats_tokens),
with the shared chart primitives imported from scripts/survey_common/svgcharts.py rather
than copied. Every number the page states is a computed token — see stats_tokens.py.
"""
import json, collections, html, pathlib, sys

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent.parent
OUT = REPO / 'public' / 'surveys' / 'failure-modes.html'

# survey_common/svgcharts.py is the shared chart-primitive library — add it to
# the import path rather than copying it (unlike the two original bespoke
# builders, which predate this scaffold and each keep their own copy).
sys.path.insert(0, str(REPO / 'scripts' / 'survey_common'))
sys.path.insert(0, str(HERE))
import svgcharts as sc

M = json.load(open(REPO / 'data' / 'failure-modes-taxonomy.json'))
N = len(M)

# ---------------- shared vocab ----------------
# Seven facets, each a closed question you can ask of any failure paper. `elicitation`
# is the load-bearing, novel one: it classifies the *experiment*, not the failure, and
# is ordered by how much of the failure the researcher had to build.
ELI = ['spontaneous', 'prompted', 'optimized', 'constructed-scenario',
       'trained-in', 'not-elicited']
ELI_C = {'spontaneous': '#64748b', 'prompted': '#22d3ee', 'optimized': '#4ade80',
         'constructed-scenario': '#fb923c', 'trained-in': '#f87171',
         'not-elicited': '#52525b'}
ELI_L = {'spontaneous': 'spontaneous', 'prompted': 'prompted', 'optimized': 'optimized',
         'constructed-scenario': 'constructed scenario', 'trained-in': 'trained in',
         'not-elicited': 'not elicited'}

LOC = ['weights-prior', 'context-window', 'reasoning-trace', 'agent-trajectory',
       'multi-agent-system', 'training-loop', 'eval-harness', 'deployment-system']
LOC_C = {'weights-prior': '#c084fc', 'context-window': '#22d3ee', 'reasoning-trace': '#f472b6',
         'agent-trajectory': '#fb923c', 'multi-agent-system': '#facc15',
         'training-loop': '#f87171', 'eval-harness': '#64748b', 'deployment-system': '#4ade80'}
LOC_L = {'weights-prior': 'weights / prior', 'context-window': 'context window',
         'reasoning-trace': 'reasoning trace', 'agent-trajectory': 'agent trajectory',
         'multi-agent-system': 'multi-agent system', 'training-loop': 'training loop',
         'eval-harness': 'eval harness', 'deployment-system': 'deployment system'}

EVD = ['behavioural-rate', 'controlled-counterfactual', 'internals-probe',
       'formal-proof', 'case-demonstration', 'corpus-synthesis']
EVD_C = {'behavioural-rate': '#22d3ee', 'controlled-counterfactual': '#4ade80',
         'internals-probe': '#f472b6', 'formal-proof': '#ffd166',
         'case-demonstration': '#fb923c', 'corpus-synthesis': '#52525b'}
EVD_L = {'behavioural-rate': 'behavioural rate', 'controlled-counterfactual': 'controlled counterfactual',
         'internals-probe': 'internals probe', 'formal-proof': 'formal proof',
         'case-demonstration': 'case demonstration', 'corpus-synthesis': 'corpus synthesis'}

DET = ['output-alone', 'needs-ground-truth', 'needs-trace', 'needs-counterfactual',
       'needs-internals', 'undetectable-in-practice']
DET_C = {'output-alone': '#4ade80', 'needs-ground-truth': '#ffd166', 'needs-trace': '#22d3ee',
         'needs-counterfactual': '#c084fc', 'needs-internals': '#f472b6',
         'undetectable-in-practice': '#f87171'}
DET_L = {'output-alone': 'output alone', 'needs-ground-truth': 'needs ground truth',
         'needs-trace': 'needs the trace', 'needs-counterfactual': 'needs a counterfactual',
         'needs-internals': 'needs internals', 'undetectable-in-practice': 'undetectable in practice'}

MIT = ['effective-mitigation', 'partial-mitigation', 'defenses-fail',
       'proposed-untested', 'none-proposed']
MIT_C = {'effective-mitigation': '#4ade80', 'partial-mitigation': '#a3e635',
         'defenses-fail': '#f87171', 'proposed-untested': '#fb923c', 'none-proposed': '#52525b'}
MIT_L = {'effective-mitigation': 'effective mitigation', 'partial-mitigation': 'partial mitigation',
         'defenses-fail': 'defenses fail', 'proposed-untested': 'proposed, untested',
         'none-proposed': 'none proposed'}

HRM = ['user', 'operator', 'third-party', 'society', 'research-integrity']
HRM_C = {'user': '#22d3ee', 'operator': '#c084fc', 'third-party': '#fb923c',
         'society': '#f87171', 'research-integrity': '#ffd166'}
HRM_L = {'user': 'the user', 'operator': 'the operator', 'third-party': 'a third party',
         'society': 'society', 'research-integrity': 'research integrity'}

AWR = ['shown-sensitive', 'not-tested', 'n-a']
AWR_C = {'shown-sensitive': '#f87171', 'not-tested': '#fb923c', 'n-a': '#3f3f46'}
AWR_L = {'shown-sensitive': 'measured — and it mattered', 'not-tested': 'not tested',
         'n-a': 'not applicable'}

ERAS = ['≤2018', '2019–20', '2021–22', '2023', '2024', '2025', '2026']
def era(y):
    if y <= 2018: return '≤2018'
    if y <= 2020: return '2019–20'
    if y <= 2022: return '2021–22'
    return str(y)

# ---------------- cross-tabs ----------------
def cross_era(fn):
    c = collections.OrderedDict((e, collections.Counter()) for e in ERAS)
    for r in M:
        c[era(r['year'])][fn(r)] += 1
    return c

era_eli = cross_era(lambda r: r['elicitation'])
era_det = cross_era(lambda r: r['detectability'])
era_mit = cross_era(lambda r: r['mitigation_status'])
era_loc = cross_era(lambda r: r['locus'])
era_hrm = cross_era(lambda r: r['harm_bearer'])

def cross(fa, fb):
    g = collections.defaultdict(collections.Counter)
    for r in M:
        g[fa(r)][fb(r)] += 1
    return g

eli_det = cross(lambda r: r['elicitation'], lambda r: r['detectability'])
eli_mit = cross(lambda r: r['elicitation'], lambda r: r['mitigation_status'])
king_eli = cross(lambda r: r['kingdom'], lambda r: r['elicitation'])
det_mit = cross(lambda r: r['detectability'], lambda r: r['mitigation_status'])

# ---------------- the tree ----------------
KING_C = {'A-objective-corruption': '#f87171', 'B-competence-cliffs': '#fb923c',
          'C-truthfulness-breakdown': '#ffd166', 'D-interaction-failure': '#a3e635',
          'E-oversight-erosion': '#22d3ee', 'F-adversarial-breach': '#f472b6',
          'G-agentic-breakdown': '#c084fc', 'H-measurement-integrity': '#64748b'}
KING_L = {
    'A-objective-corruption': ('objective corruption', 'The goal we optimized was not the goal we meant.'),
    'B-competence-cliffs': ('competence cliffs', 'It works — until the problem shifts slightly.'),
    'C-truthfulness-breakdown': ('truthfulness breakdown', 'The output is fluent, confident, and false.'),
    'D-interaction-failure': ('interaction failure', 'The failure is in the relationship with the user.'),
    'E-oversight-erosion': ('oversight erosion', 'We can no longer trust what we see it doing.'),
    'F-adversarial-breach': ('adversarial breach', 'Someone made it do what it was trained not to do.'),
    'G-agentic-breakdown': ('agentic breakdown', 'It came apart over a long run with real actions.'),
    'H-measurement-integrity': ('measurement integrity', 'The failure is in our instrument, not the model.'),
}
FAM_L = {
    'A1-failure-taxonomies': ('A1 · failure taxonomies', 'name the classes before measuring any'),
    'A2-overoptimization-dynamics': ('A2 · over-optimization dynamics', 'what happens as you push a proxy reward'),
    'A3-goal-misgeneralization': ('A3 · goal misgeneralization', 'competent off-distribution, wrong goal'),
    'B1-reasoning-collapse': ('B1 · reasoning collapse', 'the chain breaks when the problem is dressed up'),
    'B2-knowledge-asymmetry': ('B2 · knowledge asymmetry', 'what it learned one way it cannot use the other'),
    'B3-context-degradation': ('B3 · context degradation', 'the answer depends on where the evidence sits'),
    'B4-instruction-adherence': ('B4 · instruction adherence', 'constraints silently dropped across turns'),
    'C1-hallucination-foundations': ('C1 · hallucination foundations', 'what it is, and whether it can be removed'),
    'C2-source-faithfulness': ('C2 · source faithfulness', 'the output contradicts the document it cites'),
    'C3-perceptual-hallucination': ('C3 · perceptual hallucination', 'it describes what is not in the image'),
    'C4-imitative-falsehood': ('C4 · imitative falsehood', 'it repeats human misconceptions because we did'),
    'C5-strategic-falsehood': ('C5 · strategic falsehood', 'it says what it does not believe, on purpose'),
    'D1-sycophancy': ('D1 · sycophancy', 'the answer bends to the user’s stated view'),
    'D2-manipulation': ('D2 · manipulation', 'the system moves the user rather than informing them'),
    'D3-refusal-miscalibration': ('D3 · refusal miscalibration', 'safety training refusing the benign'),
    'E1-cot-unfaithfulness': ('E1 · CoT unfaithfulness', 'the stated reason is not the operative one'),
    'E2-monitor-evasion': ('E2 · monitor evasion', 'the trace stays clean while the behaviour does not'),
    'E3-deception-and-propensity': ('E3 · deception & propensity', 'stage a temptation, watch what it chooses'),
    'F1-handcrafted-jailbreaks': ('F1 · handcrafted jailbreaks', 'a human writes the prompt that breaks alignment'),
    'F2-optimized-jailbreaks': ('F2 · optimized jailbreaks', 'a search writes it for you'),
    'F3-prompt-injection': ('F3 · prompt injection', 'untrusted data captures the instruction channel'),
    'F4-defenses-and-durability': ('F4 · defenses & durability', 'what holds, against what, for how long'),
    'F5-attack-suites': ('F5 · attack suites', 'standardize the attack so results compare'),
    'F6-red-team-generation': ('F6 · red-team generation', 'automate the adversary'),
    'F7-hazard-uplift': ('F7 · hazard uplift', 'does the model measurably help a bad actor'),
    'G1-long-horizon-collapse': ('G1 · long-horizon collapse', 'the run degrades the longer it goes'),
    'G2-multi-agent-breakdown': ('G2 · multi-agent breakdown', 'failures of the organization, not the model'),
    'G3-tool-use-failures': ('G3 · tool-use failures', 'wrong tool, wrong arguments, no recovery'),
    'G4-failure-attribution': ('G4 · failure attribution', 'which step in the trace actually caused it'),
    'G5-deployment-conduct-envs': ('G5 · deployment-conduct sandboxes', 'score what an agent does with real stakes'),
    'G6-clarification-and-escalation': ('G6 · clarification & escalation', 'does it ask, or does it guess'),
    'G7-agentic-risk-foundations': ('G7 · agentic-risk foundations', 'the vocabulary for agentic harm'),
    'H1-judge-bias': ('H1 · judge bias', 'the grader has preferences of its own'),
    'H2-prompt-fragility': ('H2 · prompt fragility', 'the score moves with the prompt, not the model'),
    'H3-harness-validity': ('H3 · harness validity', 'does the instrument measure what it claims'),
    'H4-metric-meta-evaluation': ('H4 · metric meta-evaluation', 'does the metric track the failure it names'),
}
KINGS = list(KING_L)
by_family = collections.defaultdict(list)
for r in M:
    by_family[r['family']].append(r)
for f in by_family:
    by_family[f].sort(key=lambda r: (r['year'], r['short'].lower()))
FAMS_BY_KING = {k: [f for f in FAM_L if f[0] == k[0]] for k in KINGS}

# ---------------- charts ----------------
import charts_custom as cc
cc.bind(M, sc, dict(ELI=ELI, ELI_C=ELI_C, ELI_L=ELI_L, AWR=AWR, AWR_C=AWR_C, AWR_L=AWR_L,
                    KINGS=KINGS, KING_C=KING_C, KING_L=KING_L, FAM_L=FAM_L,
                    by_family=by_family, FAMS_BY_KING=FAMS_BY_KING, era=era, ERAS=ERAS))

charts = {}
charts['eliladder'] = cc.elicitation_ladder_svg()
charts['visibility'] = cc.visibility_svg()
charts['awareness'] = cc.awareness_svg()
charts['tree'] = cc.tree_skeleton_svg()
charts['eliwaves'] = sc.stacked_bars(era_eli, ELI, ELI_C, ELI_L, pct=True, legend_cols=3,
                                     x_label='share of new failure papers per era · how the failure was elicited')
charts['detwaves'] = sc.stacked_bars(era_det, DET, DET_C, DET_L, pct=True, legend_cols=3,
                                     x_label='share per era · what you would need to catch the failure in the wild')
charts['mitwaves'] = sc.stacked_bars(era_mit, MIT, MIT_C, MIT_L, pct=True, legend_cols=3,
                                     x_label='share per era · what the paper reports about defenses')
charts['locwaves'] = sc.stacked_bars(era_loc, LOC, LOC_C, LOC_L, pct=True, legend_cols=4,
                                     x_label='share per era · where in the stack the failure lives')
charts['harmwaves'] = sc.stacked_bars(era_hrm, HRM, HRM_C, HRM_L, pct=True, legend_cols=3,
                                      x_label='share per era · who bears the cost when it fails')
charts['heat_eli_det'] = sc.heatmap(ELI, DET, eli_det, ELI_L, DET_L, accent='#fb7185', pad_l=150)
charts['heat_eli_mit'] = sc.heatmap(ELI, MIT, eli_mit, ELI_L, MIT_L, accent='#a3e635', pad_l=150)
charts['heat_king_eli'] = sc.heatmap(KINGS, ELI, king_eli,
                                     {k: KING_L[k][0] for k in KINGS}, ELI_L,
                                     accent='#c084fc', pad_l=168)

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
    'eli': chip_counts(lambda r: r['elicitation'], ELI_L, ELI_C),
    'loc': chip_counts(lambda r: r['locus'], LOC_L, LOC_C),
    'evd': chip_counts(lambda r: r['evidence_mode'], EVD_L, EVD_C),
    'det': chip_counts(lambda r: r['detectability'], DET_L, DET_C),
    'mit': chip_counts(lambda r: r['mitigation_status'], MIT_L, MIT_C),
    'hrm': chip_counts(lambda r: r['harm_bearer'], HRM_L, HRM_C),
    'awr': chip_counts(lambda r: r['eval_awareness'], AWR_L, AWR_C),
}

# ---------------- facet cards ----------------
# Generated from one list so the ordinals, the card count and @@N_FACETS@@ cannot
# drift apart (a critique-round-1 note: the heading was tokenized but the cards were
# hand-numbered 1-7). Order here is the order stats_tokens.FACETS declares.
# (facet key, display name, question, chips key) — the key is carried so the assert
# below can check identity and order against stats_tokens.FACETS, not just the count.
FACET_CARDS = [
    ('elicitation', 'elicitation', 'How much of this failure did the researcher have to build before it appeared?', 'eli'),
    ('locus', 'locus', 'Where in the stack does the failure actually live?', 'loc'),
    ('evidence_mode', 'evidence mode', 'What kind of evidence is offered — a rate, a counterfactual, a proof, a synthesis?', 'evd'),
    ('detectability', 'detectability', 'What would you need in order to catch this failure in a real deployment?', 'det'),
    ('mitigation_status', 'mitigation status', 'Does anything actually work against it, as measured in the paper?', 'mit'),
    ('harm_bearer', 'harm bearer', 'Who eats the cost when it fails?', 'hrm'),
    ('eval_awareness', 'evaluation awareness', "Did anyone check whether the subject's belief that it was being tested moved the result?", 'awr'),
]
assert [k for k, _, _, _ in FACET_CARDS] == __import__('stats_tokens').FACETS, \
    'facet cards disagree with stats_tokens.FACETS (identity or order)'
facet_cards_html = ''.join(
    f"<div class='card'><div class='nm'>{i} · {html.escape(name)}</div>"
    f"<div class='q'>{q}</div><div class='chips'>{chips[ck]}</div></div>"
    for i, (_, name, q, ck) in enumerate(FACET_CARDS, start=1))

# ---------------- tree blocks ----------------
def tree_blocks():
    out = []
    for k in KINGS:
        col = KING_C[k]
        name, q = KING_L[k]
        kf = [f for f in FAMS_BY_KING[k] if by_family[f]]
        n = sum(len(by_family[f]) for f in kf)
        fams_html = []
        for f in kf:
            chips_h = ''.join(
                f"<a class='tchip' href='/papers/{r['slug']}.html' "
                f"title='{html.escape(r.get('placement_reason', ''), quote=True)}'>"
                f"{html.escape(r['short'])}<span>’{str(r['year'])[2:]}</span></a>"
                for r in by_family[f])
            lbl, dfn = FAM_L[f]
            fams_html.append(
                f"<div class='fam'><div class='fnm mono'>{html.escape(lbl)} "
                f"<span class='fdef'>— {html.escape(dfn)}</span>"
                f"<span class='fn'>{len(by_family[f])}</span></div>"
                f"<div class='tchips'>{chips_h}</div></div>")
        out.append(
            f"<div class='kingdom' style='--kc:{col}'><div class='khead'>"
            f"<span class='klet mono'>{k[0]}</span><div class='kt'><div class='knm'>{html.escape(name)}</div>"
            f"<div class='kq'>{html.escape(q)}</div></div><span class='kn mono'>{n}</span></div>"
            f"{''.join(fams_html)}</div>")
    return ''.join(out)

tree_blocks_html = tree_blocks()

# ---------------- table data ----------------
tbl = []
for r in sorted(M, key=lambda r: (-r['year'], r['short'].lower())):
    tbl.append({
        's': r['slug'], 'n': r['short'], 'y': r['year'],
        'e': r['elicitation'], 'l': r['locus'], 'v': r['evidence_mode'],
        'd': r['detectability'], 'm': r['mitigation_status'], 'h': r['harm_bearer'],
        'a': r['eval_awareness'], 'k': r['kingdom'], 'f': r['family'],
        'o': r['one_line'], 'q': r['key_number'],
    })
TABLE_JSON = json.dumps(tbl, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

ELI_OPTS = ''.join(f"<option value='{k}'>{ELI_L[k]}</option>" for k in ELI)
DET_OPTS = ''.join(f"<option value='{k}'>{DET_L[k]}</option>" for k in DET)
MIT_OPTS = ''.join(f"<option value='{k}'>{MIT_L[k]}</option>" for k in MIT)
KING_OPTS = ''.join(f"<option value='{k}'>{KING_L[k][0]}</option>" for k in KINGS)

JS_COLORS = json.dumps({'e': ELI_C, 'd': DET_C, 'm': MIT_C, 'k': KING_C,
                        'h': HRM_C, 'l': LOC_C, 'a': AWR_C}, separators=(',', ':'))
JS_LABELS = json.dumps({'e': ELI_L, 'd': DET_L, 'm': MIT_L, 'h': HRM_L, 'l': LOC_L,
                        'v': EVD_L, 'a': AWR_L,
                        'k': {k: KING_L[k][0] for k in KINGS},
                        'f': {f: FAM_L[f][0] for f in FAM_L}},
                       ensure_ascii=False, separators=(',', ':'))

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
            .replace('@@TREE_BLOCKS@@', tree_blocks_html)
            .replace('@@FACET_CARDS@@', facet_cards_html)
            .replace('@@ELI_OPTS@@', ELI_OPTS).replace('@@DET_OPTS@@', DET_OPTS)
            .replace('@@MIT_OPTS@@', MIT_OPTS).replace('@@KING_OPTS@@', KING_OPTS)
            .replace('@@JS_COLORS@@', JS_COLORS).replace('@@JS_LABELS@@', JS_LABELS))
for k, v in sorted(tokens.items(), key=lambda kv: -len(kv[0])):
    # paper-quoted figures can legitimately contain '<' or '>' ("<2%", ">= 0.9"), so
    # escape on the way in — an unescaped '<' is a latent parse bug on the page and a
    # real one in any downstream (LaTeX/XML) consumer of the same tokens dict.
    page = page.replace(f'@@{k}@@', html.escape(str(v), quote=False))

assert '@@' not in page, 'unresolved token: ' + page[page.index('@@'):page.index('@@') + 48]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page)
print(f'wrote {OUT} ({len(page) / 1024:.0f} KB) · {len(tokens)} tokens · {len(charts)} charts')
