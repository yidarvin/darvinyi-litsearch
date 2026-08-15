"""Compute every numeric token the survey prose cites, straight from the classified
corpus, so no number in the page is ever hand-typed. compute(M, era, ERAS) -> {TOKEN: value}.

Two kinds of token live here:

  * **corpus statistics** — counts, shares and cross-tab cells derived from the 114
    classified records (``N_ELI_OPT``, ``PCT_OPT_OUTPUT``, …);
  * **paper-quoted figures** — the individual numbers the prose quotes from a specific
    paper. These are *not* hand-typed either: each is pulled out of that paper's
    ``key_number`` field in data/failure-modes-taxonomy.json by an anchored regex that
    asserts on a miss, so re-classifying a paper either keeps the quote correct or
    breaks the build loudly. See QUOTES below.

Mirrors scripts/evaluations_survey/stats_tokens.py's role in that survey's builder.
"""
import collections
import re


# ---------------------------------------------------------------- facet vocab
ELI = ['spontaneous', 'prompted', 'optimized', 'constructed-scenario',
       'trained-in', 'not-elicited']
DET = ['output-alone', 'needs-ground-truth', 'needs-trace', 'needs-counterfactual',
       'needs-internals', 'undetectable-in-practice']
MIT = ['effective-mitigation', 'partial-mitigation', 'defenses-fail',
       'proposed-untested', 'none-proposed']
AWR = ['shown-sensitive', 'not-tested', 'n-a']
LOC = ['weights-prior', 'context-window', 'reasoning-trace', 'agent-trajectory',
       'multi-agent-system', 'training-loop', 'eval-harness', 'deployment-system']
EVD = ['behavioural-rate', 'controlled-counterfactual', 'internals-probe',
       'formal-proof', 'case-demonstration', 'corpus-synthesis']
HRM = ['user', 'operator', 'third-party', 'society', 'research-integrity']

# The facets the page presents as its closed-vocabulary question set. len() of this is
# the "seven facets" the prose claims, so the claim can't drift from the design.
FACETS = ['elicitation', 'locus', 'evidence_mode', 'detectability',
          'mitigation_status', 'harm_bearer', 'eval_awareness']

# The rungs where the researcher had to build more than the input: a staged world, a
# poisoned training run, or nothing at all (no experiment). Used repeatedly below.
DEEP_ELI = ['constructed-scenario', 'trained-in', 'not-elicited']

# --------------------------------------------------- paper-quoted figures (see above)
# TOKEN: (slug, regex over that record's key_number, group index)
QUOTES = {
    # kingdom E — the evaluation-awareness cluster
    'Q_AM_BLACKMAIL':   ('lynch-2025-agentic-misalignment', r'^(\d+%) blackmail'),
    'Q_AM_REAL':        ('lynch-2025-agentic-misalignment', r'([\d.]+%) vs [\d.]+% real-vs-evaluation'),
    'Q_AM_EVAL':        ('lynch-2025-agentic-misalignment', r'[\d.]+% vs ([\d.]+%) real-vs-evaluation'),
    'Q_AF_GAP':         ('greenblatt-2024-alignment-faking', r'([\d.]+%) compliance gap'),
    'Q_AF_PRERLHF':     ('greenblatt-2024-alignment-faking', r'alignment-faking reasoning (\d+%) ->'),
    'Q_AF_POSTRLHF':    ('greenblatt-2024-alignment-faking', r'alignment-faking reasoning \d+% -> (\d+%) after actual RLHF'),
    'Q_AF_POSTGAP':     ('greenblatt-2024-alignment-faking', r'compliance gap shrinks to ([\d.]+%) on the exact training prompt'),
    # The scope travels with the figure: 6.9% is true only on the training prompt, and
    # the paper's actual finding is that the gap is recoverable. Pairing the two tokens
    # makes them as hard to drift apart as the 12%/78% pair (critique round 2, B8).
    'Q_AF_POSTGAP_RECOVERED': ('greenblatt-2024-alignment-faking', r'returns to ([\d.]+%) under a one-word prompt edit'),
    'Q_SA_BEFORE':      ('hubinger-2024-sleeper-agents', r'trigger rate (\d+%) ->'),
    'Q_SA_AFTER_RL':    ('hubinger-2024-sleeper-agents', r'-> (\d+%) \(RL\)'),
    'Q_SA_HELDOUT':     ('hubinger-2024-sleeper-agents', r'leaves (\d+%) held-out defection'),
    'Q_ICS_EVALS':      ('meinke-2024-in-context-scheming', r'o1 schemes on (\d+/\d+) evaluations'),
    'Q_ICS_SANDBAG_HI': ('meinke-2024-in-context-scheming', r'sandbags ([\d.]+) ->'),
    'Q_ICS_SANDBAG_LO': ('meinke-2024-in-context-scheming', r'sandbags [\d.]+ -> ([\d.]+)'),
    'Q_W2S_UNAWARE':    ('kale-2025-weak-to-strong-monitoring', r'AUC (>= [\d.]+) against unaware'),
    'Q_W2S_HIJACK':     ('kale-2025-weak-to-strong-monitoring', r'falls below ([\d.]+) AUC under monitor hijacking'),

    # the optimized-jailbreak arms race
    'Q_GCG_ASR':        ('zou-2023-gcg', r'^(\d+%) white-box ASR'),
    'Q_GCG_TRANSFER':   ('zou-2023-gcg', r'; ([\d.]+%) / [\d.]+% / [\d.]+% ensembled transfer to GPT-3.5'),
    'Q_GCG_TRANSFER_GPT4': ('zou-2023-gcg', r'; [\d.]+% / ([\d.]+%) / [\d.]+% ensembled transfer to GPT-3.5 / GPT-4'),
    'Q_PAIR_QUERIES':   ('chao-2023-pair', r'(~\d+) queries vs GCG'),
    'Q_TAP_GPT4O':      ('mehrotra-2023-tap', r'^(\d+%) vs PAIR'),
    'Q_BASE_PPL':       ('jain-2023-baseline-defenses', r'PPL-filter pass rate ([\d.]+)'),
    'Q_BASE_PARA_HI':   ('jain-2023-baseline-defenses', r'paraphrase ASR ([\d.]+) ->'),
    'Q_BASE_PARA_LO':   ('jain-2023-baseline-defenses', r'paraphrase ASR [\d.]+ -> ([\d.]+)'),
    'Q_AUTODAN_ASR':    ('liu-2023-autodan', r'^([\d.]+%) vs GCG'),
    'Q_AUTODAN_GCG':    ('liu-2023-autodan', r"^[\d.]+% vs GCG's ([\d.]+%)"),
    'Q_AUTODAN_FILTER': ('liu-2023-autodan', r'ASR under perplexity filter: GCG ([\d.]+%)'),
    'Q_MHJ_HUMAN':      ('li-2024-multiturn-jailbreaks', r'human ASR ([\d.]+%) \(RR\)'),
    'Q_MHJ_AUTO':       ('li-2024-multiturn-jailbreaks', r'vs automated-ensemble ASR ([\d.]+%) /'),
    'Q_J2_ASR':         ('kritz-2025-j2', r'^([\d.]+) ASR on GPT-4o'),
    'Q_J2_HUMAN':       ('kritz-2025-j2', r'human red teamers ([\d.]+)\)'),

    # the injection lineage
    'Q_IPI_RATES':      ('greshake-2023-indirect-prompt-injection', r'^(\d+) success rates reported'),
    'Q_PI_HIJACK':      ('perez-2022-ignore-previous-prompt', r'^([\d.]+%) \+/- [\d.]+ goal hijacking'),
    'Q_STRUQ_HI':       ('chen-2024-struq', r'Completion-Real (\d+%) ->'),
    'Q_STRUQ_LO':       ('chen-2024-struq', r'Completion-Real \d+% -> (\d+%)'),
    'Q_STRUQ_GCG':      ('chen-2024-struq', r'GCG residual (\d+%)'),
    'Q_SPOT_LO':        ('hines-2024-spotlighting', r'ASR >50% -> <(\d+%)'),
    'Q_ASPI_O3_LO':     ('sehwag-2026-aspi', r'o3 ([\d.]+%) ->'),
    'Q_ASPI_O3_HI':     ('sehwag-2026-aspi', r'o3 [\d.]+% -> ([\d.]+%)'),
    'Q_ASPI_KIMI_HI':   ('sehwag-2026-aspi', r'Kimi K2.5 [\d.]+% -> ([\d.]+%)'),

    # trained-in
    'Q_FT_BEFORE':      ('qi-2023-finetuning-compromises-safety', r'^([\d.]+%) ->'),
    'Q_FT_AFTER':       ('qi-2023-finetuning-compromises-safety', r'^[\d.]+% -> ([\d.]+%)'),
    'Q_FT_COST':        ('qi-2023-finetuning-compromises-safety', r'\((<\$[\d.]+)\)'),
    'Q_FT_EXAMPLES':    ('qi-2023-finetuning-compromises-safety', r'from (\d+ examples)'),
    'Q_FT_MOD':         ('qi-2023-finetuning-compromises-safety', r'moderation caught (\d+ of \d+)'),
    'Q_BIO_STEPS':      ('wei-2025-bioriskeval', r'^(\d+) fine-tuning steps'),
    'Q_BIO_HOURS':      ('wei-2025-bioriskeval', r'/ ([\d.]+) H100 GPU-hours'),
    'Q_RRH_LO':         ('mahmoud-2026-reward-hacking', r'exploitation (\d+%) ->'),
    'Q_RRH_HI':         ('mahmoud-2026-reward-hacking', r'exploitation \d+% -> (\d+%)'),
    'Q_REV_BACK':       ('berglund-2023-reversal-curse', r'^([\d.]+% \+/- [\d.]+) reverse-direction'),
    'Q_REV_FWD':        ('berglund-2023-reversal-curse', r'vs ([\d.]+%) forward'),
    'Q_RM_CAUSED':      ('pan-2022-reward-misspecification', r'^(\d+ of \d+) misspecifications'),
    'Q_RM_AUROC':       ('pan-2022-reward-misspecification', r'below (\d+% AUROC)'),
    'Q_VFT_VFT':        ('turpin-2025-vft', r'rate (\d+%) \(VFT\)'),
    'Q_VFT_RL':         ('turpin-2025-vft', r'vs (\d+%) \(RL\)'),
    'Q_VFT_BCT':        ('turpin-2025-vft', r'vs (\d+%) \(BCT\)'),
    'Q_VFT_CUE':        ('turpin-2025-vft', r'cue influence (~\d+%) for all methods'),
    'Q_OBF_COT':        ('baker-2025-monitoring-reasoning', r'CoT monitor (\d+%) joint recall'),
    'Q_OBF_ACTION':     ('baker-2025-monitoring-reasoning', r'action monitor (\d+%)'),
    'Q_EVADE_EPISODES': ('emmons-2025-cot-evade-monitors', r'evasion requires (~[\d.]+M) RL episodes'),

    # spontaneous / agentic
    # Anchored through "attack success" so the metric name cannot be dropped from the
    # record without breaking the build — the neutral form let the prose attach the
    # opposite verb (critique round 3, B9).
    'Q_BART_CHAT':      ('kumar-2024-browserart', r'GPT-4o attack success (\d+%) \(chat\)'),
    'Q_BART_AGENT':     ('kumar-2024-browserart', r'GPT-4o attack success \d+% \(chat\) -> (\d+%) \(agent\)'),
    'Q_BART_JB':        ('kumar-2024-browserart', r'GPT-4o attack success \d+% \(chat\) -> \d+% \(agent\) -> (\d+%) \(with transferred jailbreaks\)'),
    'Q_VEND_WORST':     ('backlund-2025-vending-bench', r'worst run (\$[\d,.]+)'),
    'Q_WW_AGENT':       ('zhang-2025-failure-attribution', r'^([\d.]+%) agent-level'),
    'Q_WW_STEP':        ('zhang-2025-failure-attribution', r'/ ([\d.]+%) step-level'),
    'Q_TRAIL_JOINT':    ('deshpande-2025-trail', r'^(\d+%) joint accuracy'),
    'Q_HIL_FULL':       ('elfeki-2026-hil-bench', r'^([\d-]+%) full-info'),
    'Q_HIL_BLOCKED':    ('elfeki-2026-hil-bench', r'-> ([\d-]+%) blocked'),
    'Q_LHAW_OPUS_HI':   ('pu-2026-lhaw', r'outcome-critical Opus-4.5 ([\d.]+) ->'),
    'Q_LHAW_OPUS_LO':   ('pu-2026-lhaw', r'outcome-critical Opus-4.5 [\d.]+ -> ([\d.]+)'),
    'Q_LITM_GAP':       ('liu-2023-lost-in-the-middle', r'^(>\d+-point) best-vs-worst'),
    'Q_MCP_COGNITIVE':  ('bandi-2026-mcp-atlas', r'([\d.]+%) of failures cognitive'),

    # not-elicited / measurement integrity
    'Q_CP_MODES':       ('amodei-2016-concrete-problems', r'^(\d+) failure modes'),
    'Q_CP_EXPERIMENTS': ('amodei-2016-concrete-problems', r'(\d+) experiments'),
    'Q_GM_ELICITED':    ('shah-2022-goal-misgeneralization', r'Limitations, (\d+) were built to elicit'),
    'Q_GM_EXAMPLES':    ('shah-2022-goal-misgeneralization', r'^(\d+) examples in Table 1'),
    'Q_AH_AUTHORS':     ('chan-2023-agentic-harms', r'(\d+) authors'),
    'Q_AH_MEASURE':     ('chan-2023-agentic-harms', r'(\d+) measurements'),
    'Q_SYC_MISATTR':    ('malmqvist-2024-sycophancy-survey', r'^\d+ references; (\d+) misattributed'),
    'Q_SYC_ORIGINAL':   ('malmqvist-2024-sycophancy-survey', r'(\d+) original measurements'),
    'Q_ABC_TASK':       ('zhu-2025-agentic-benchmarks', r'^(\d+/\d+) violate task validity'),
    'Q_ABC_REPORT':     ('zhu-2025-agentic-benchmarks', r'(\d+/\d+) have reporting limitations'),
    'Q_SELFREC_PREF':   ('panickssery-2024-self-recognition', r'GPT-4 self-preference ([\d.]+)/'),
    'Q_TQA_BEST':       ('lin-2021-truthfulqa', r'^(\d+%) truthful'),
    'Q_TQA_HUMAN':      ('lin-2021-truthfulqa', r'vs (\d+%) human'),
    'Q_HALLU_INEV':     ('xu-2024-hallucination-inevitable', r'^(existence-level impossibility)'),
    'Q_WHY_BINARY':     ('kalai-2025-why-lms-hallucinate', r'^(\d+ of \d+) surveyed benchmarks'),
    'Q_STYLE_HI':       ('wu-2025-style-over-substance', r'^(\d+) Elo'),
    'Q_STYLE_LO':       ('wu-2025-style-over-substance', r'vs (\d+) \(correct but short\)'),
}


def _quote(by, slug, rx, tok):
    rec = by.get(slug)
    assert rec is not None, f'{tok}: no taxonomy record for {slug!r}'
    m = re.search(rx, rec['key_number'])
    assert m, (f'{tok}: key_number for {slug} no longer matches {rx!r} — '
               f'got {rec["key_number"]!r}')
    return m.group(1)


def compute(M, era, ERAS):
    N = len(M)
    T = {}
    by = {r['slug']: r for r in M}

    def pct(x, of=None):
        d = N if of is None else of
        return round(100 * x / d) if d else 0

    c_eli = collections.Counter(r['elicitation'] for r in M)
    c_det = collections.Counter(r['detectability'] for r in M)
    c_mit = collections.Counter(r['mitigation_status'] for r in M)
    c_awr = collections.Counter(r['eval_awareness'] for r in M)
    c_loc = collections.Counter(r['locus'] for r in M)
    c_evd = collections.Counter(r['evidence_mode'] for r in M)
    c_hrm = collections.Counter(r['harm_bearer'] for r in M)
    c_king = collections.Counter(r['kingdom'] for r in M)

    # ------------------------------------------------------------ corpus shape
    T['N'] = N
    T['YEAR_MIN'] = min(r['year'] for r in M)
    T['YEAR_MAX'] = max(r['year'] for r in M)
    T['N_FACETS'] = len(FACETS)
    T['N_FACETS_OTHER'] = len(FACETS) - 1
    T['N_KINGDOMS'] = len(c_king)
    T['N_KINGDOMS_OTHER'] = len(c_king) - 1
    T['N_FAMILIES'] = len(set(r['family'] for r in M))
    T['N_EDGES'] = sum(len(r['lineage']) for r in M)
    T['N_EDGES_CROSS'] = sum(1 for r in M for e in r['lineage']
                             if by[e['parent']]['kingdom'] != r['kingdom'])
    T['N_ROOTS'] = sum(1 for r in M if not r['lineage'])
    T['N_CONF_HIGH'] = sum(1 for r in M if r['confidence'] == 'high')
    T['N_CONF_MED'] = sum(1 for r in M if r['confidence'] == 'medium')
    for e in ERAS:
        T['N_ERA_' + re.sub(r'\W', '', e).upper()] = sum(1 for r in M if era(r['year']) == e)
    T['N_2025'] = sum(1 for r in M if r['year'] == 2025)
    T['N_2024'] = sum(1 for r in M if r['year'] == 2024)
    T['N_SINCE_2023'] = sum(1 for r in M if r['year'] >= 2023)
    T['PCT_SINCE_2023'] = pct(T['N_SINCE_2023'])

    # ------------------------------------------------------------- elicitation
    ELI_TOK = {'spontaneous': 'SPON', 'prompted': 'PROMPT', 'optimized': 'OPT',
               'constructed-scenario': 'SCEN', 'trained-in': 'TRAIN',
               'not-elicited': 'NONE'}
    for k, tok in ELI_TOK.items():
        T[f'N_ELI_{tok}'] = c_eli[k]
        T[f'PCT_ELI_{tok}'] = pct(c_eli[k])
    T['N_MANUFACTURED'] = sum(c_eli[k] for k in ELI if k not in ('spontaneous', 'not-elicited'))
    T['PCT_MANUFACTURED'] = pct(T['N_MANUFACTURED'])
    T['N_ELICITED'] = N - c_eli['not-elicited']
    T['N_DEEP_ELI'] = sum(c_eli[k] for k in DEEP_ELI)
    T['PCT_DEEP_ELI'] = pct(T['N_DEEP_ELI'])

    # orthogonality: how many families / kingdoms hold more than one elicitation value
    fam_eli = collections.defaultdict(set)
    king_eli = collections.defaultdict(set)
    for r in M:
        fam_eli[r['family']].add(r['elicitation'])
        king_eli[r['kingdom']].add(r['elicitation'])
    T['N_FAM_SPLIT'] = sum(1 for v in fam_eli.values() if len(v) > 1)
    T['N_KING_SPLIT'] = sum(1 for v in king_eli.values() if len(v) > 1)
    T['N_FAM_MULTI'] = sum(1 for f, v in fam_eli.items()
                           if len([r for r in M if r['family'] == f]) > 1)

    # --- how strongly elicitation is associated with the tree ------------------
    # Round 1 of critique correctly killed the word "orthogonal": elicitation and
    # kingdom are strongly associated. The honest claim is that the axis is
    # cross-cutting and not *reducible* to the tree, and these numbers are what let
    # the prose say so without hand-waving. Cramer's V over the kingdom x elicitation
    # contingency table, plus how well a majority-vote baseline predicts a paper's
    # elicitation from its placement.
    kings = sorted(c_king)
    obs = {k: collections.Counter() for k in kings}
    for r in M:
        obs[r['kingdom']][r['elicitation']] += 1
    chi2 = 0.0
    for k in kings:
        for e in ELI:
            exp = c_king[k] * c_eli[e] / N
            if exp:
                chi2 += (obs[k][e] - exp) ** 2 / exp
    dof = min(len(kings) - 1, len(ELI) - 1)
    T['CHI2_KING_ELI'] = round(chi2, 1)
    T['CRAMERS_V'] = round((chi2 / (N * dof)) ** 0.5, 2)

    def majority_accuracy(key):
        groups = collections.defaultdict(collections.Counter)
        for r in M:
            groups[r[key]][r['elicitation']] += 1
        modal = {g: c.most_common(1)[0][0] for g, c in groups.items()}
        return pct(sum(1 for r in M if modal[r[key]] == r['elicitation']))

    T['PCT_KING_MAJORITY'] = majority_accuracy('kingdom')
    T['PCT_FAM_MAJORITY'] = majority_accuracy('family')
    T['PCT_ELI_BASERATE'] = pct(max(c_eli.values()))

    # --- the input / world split (the thesis) ----------------------------------
    # What predicts visibility is which object was manufactured, not what it cost to
    # make. INPUT rungs = the researcher wrote or searched for a string (spontaneous
    # sits here too: nothing was built, so the artifact is still an ordinary output).
    # WORLD rungs = the researcher built the context around the model or the weights
    # inside it. `not-elicited` is off the ladder entirely — no run, so no output.
    INPUT_ELI = ['spontaneous', 'prompted', 'optimized']
    WORLD_ELI = ['constructed-scenario', 'trained-in']
    T['N_INPUT_ELI'] = sum(c_eli[k] for k in INPUT_ELI)
    T['N_WORLD_ELI'] = sum(c_eli[k] for k in WORLD_ELI)
    T['N_INPUT_OUTPUT'] = sum(1 for r in M if r['elicitation'] in INPUT_ELI
                              and r['detectability'] == 'output-alone')
    T['N_WORLD_OUTPUT'] = sum(1 for r in M if r['elicitation'] in WORLD_ELI
                              and r['detectability'] == 'output-alone')
    T['PCT_WORLD_ELI'] = pct(T['N_WORLD_ELI'])

    # --- kingdoms with no spontaneous member (B2) ------------------------------
    no_spon = [k for k in kings if obs[k]['spontaneous'] == 0]
    T['N_KING_NO_SPON'] = len(no_spon)
    T['KING_NO_SPON_OTHERS'] = ' and '.join(
        k[2:].replace('-', ' ') for k in no_spon if k != 'F-adversarial-breach')

    # --- when the constructed-scenario rung actually arrives (B1) --------------
    scen_years = sorted(r['year'] for r in M if r['elicitation'] == 'constructed-scenario')
    T['YEAR_SCEN_FIRST'] = scen_years[0] if scen_years else '—'
    T['N_SCEN_FIRST_YEAR'] = sum(1 for y in scen_years if y == scen_years[0]) if scen_years else 0
    T['N_SCEN_AFTER_FIRST'] = sum(1 for y in scen_years if y > scen_years[0]) if scen_years else 0

    # ------------------------------------------------------------ detectability
    DET_TOK = {'output-alone': 'OUTPUT', 'needs-ground-truth': 'GT', 'needs-trace': 'TRACE',
               'needs-counterfactual': 'CF', 'needs-internals': 'INT',
               'undetectable-in-practice': 'UNDET'}
    for k, tok in DET_TOK.items():
        T[f'N_DET_{tok}'] = c_det[k]
        T[f'PCT_DET_{tok}'] = pct(c_det[k])
    T['N_DET_BEYOND_OUTPUT'] = N - c_det['output-alone']
    T['PCT_DET_BEYOND_OUTPUT'] = pct(T['N_DET_BEYOND_OUTPUT'])

    # the visibility inversion — output-alone rate per elicitation rung
    for k, tok in ELI_TOK.items():
        sub = [r for r in M if r['elicitation'] == k]
        n_out = sum(1 for r in sub if r['detectability'] == 'output-alone')
        T[f'N_{tok}_OUTPUT'] = n_out
        T[f'PCT_{tok}_OUTPUT'] = pct(n_out, len(sub))
    deep = [r for r in M if r['elicitation'] in DEEP_ELI]
    T['N_DEEP_OUTPUT'] = sum(1 for r in deep if r['detectability'] == 'output-alone')
    T['N_SPON_PROMPT_OPT'] = sum(c_eli[k] for k in ('spontaneous', 'prompted', 'optimized'))
    T['N_SPON_PROMPT_OPT_OUTPUT'] = sum(
        1 for r in M if r['elicitation'] in ('spontaneous', 'prompted', 'optimized')
        and r['detectability'] == 'output-alone')
    T['PCT_SPON_PROMPT_OPT_OUTPUT'] = pct(T['N_SPON_PROMPT_OPT_OUTPUT'], T['N_SPON_PROMPT_OPT'])
    T['RATIO_OPT_VS_SPON_OUTPUT'] = round(
        (T['PCT_OPT_OUTPUT'] / T['PCT_SPON_OUTPUT']) if T['PCT_SPON_OUTPUT'] else 0, 1)

    # trace detection over time
    T['N_TRACE_2025'] = sum(1 for r in M if r['year'] == 2025 and r['detectability'] == 'needs-trace')
    T['N_TRACE_PRE2025'] = sum(1 for r in M if r['year'] < 2025 and r['detectability'] == 'needs-trace')
    T['N_TRACE_2025PLUS'] = sum(1 for r in M if r['year'] >= 2025 and r['detectability'] == 'needs-trace')
    T['PCT_TRACE_2025'] = pct(T['N_TRACE_2025'], T['N_2025'])

    # --------------------------------------------------------------- mitigation
    MIT_TOK = {'effective-mitigation': 'EFFECTIVE', 'partial-mitigation': 'PARTIAL',
               'defenses-fail': 'FAIL', 'proposed-untested': 'UNTESTED',
               'none-proposed': 'NONE'}
    for k, tok in MIT_TOK.items():
        T[f'N_MIT_{tok}'] = c_mit[k]
        T[f'PCT_MIT_{tok}'] = pct(c_mit[k])
    T['N_MIT_NOTHING'] = c_mit['defenses-fail'] + c_mit['proposed-untested'] + c_mit['none-proposed']
    T['PCT_MIT_NOTHING'] = pct(T['N_MIT_NOTHING'])
    T['N_MIT_SOMETHING'] = c_mit['effective-mitigation'] + c_mit['partial-mitigation']
    T['PCT_MIT_SOMETHING'] = pct(T['N_MIT_SOMETHING'])
    T['RATIO_FAIL_EFFECTIVE'] = round(c_mit['defenses-fail'] / c_mit['effective-mitigation'], 1) \
        if c_mit['effective-mitigation'] else 0

    # per-rung defense record; trained-in is the only inversion
    for k, tok in ELI_TOK.items():
        sub = [r for r in M if r['elicitation'] == k]
        T[f'N_{tok}_FAIL'] = sum(1 for r in sub if r['mitigation_status'] == 'defenses-fail')
        T[f'N_{tok}_PARTIAL'] = sum(1 for r in sub if r['mitigation_status'] == 'partial-mitigation')
        T[f'N_{tok}_EFFECTIVE'] = sum(1 for r in sub if r['mitigation_status'] == 'effective-mitigation')
    T['N_ELI_INVERTED'] = sum(1 for k in ELI
                              if T[f'N_{ELI_TOK[k]}_FAIL'] > T[f'N_{ELI_TOK[k]}_PARTIAL'])
    T['N_ELI_WITH_VERDICT'] = sum(1 for k in ELI
                                  if T[f'N_{ELI_TOK[k]}_FAIL'] + T[f'N_{ELI_TOK[k]}_PARTIAL'])

    # ---------------------------------------------------- evaluation awareness
    AWR_TOK = {'shown-sensitive': 'SENSITIVE', 'not-tested': 'NOTTESTED', 'n-a': 'NA'}
    for k, tok in AWR_TOK.items():
        T[f'N_AWR_{tok}'] = c_awr[k]
        T[f'PCT_AWR_{tok}'] = pct(c_awr[k])
    T['N_AWR_NULL'] = 0  # the point: no paper in this corpus reports a null effect
    T['N_AWR_VALUES'] = len(AWR)
    T['N_ELI_RUNGS'] = len(ELI)
    T['N_AWR_TESTED'] = c_awr['shown-sensitive'] + T['N_AWR_NULL']
    T['PCT_AWR_TESTED'] = pct(T['N_AWR_TESTED'])
    T['N_AWR_APPLICABLE'] = N - c_awr['n-a']
    T['PCT_AWR_TESTED_OF_APPLICABLE'] = pct(T['N_AWR_TESTED'], T['N_AWR_APPLICABLE'])
    sens = [r for r in M if r['eval_awareness'] == 'shown-sensitive']
    T['N_AWR_KINGDOMS'] = len(set(r['kingdom'] for r in sens))
    T['N_AWR_KING_LABEL'] = sorted(set(r['kingdom'] for r in sens))[0][2:].replace('-', ' ') \
        if sens else '—'
    king_of_sens = sorted(set(r['kingdom'] for r in sens))[0] if sens else None
    T['N_KING_AWR_TOTAL'] = c_king[king_of_sens] if king_of_sens else 0
    T['N_OTHER_KINGDOM_PAPERS'] = N - T['N_KING_AWR_TOTAL']
    T['N_AWR_SCEN'] = sum(1 for r in sens if r['elicitation'] == 'constructed-scenario')
    T['N_AWR_TRAIN'] = sum(1 for r in sens if r['elicitation'] == 'trained-in')
    # where the confound is live and unmeasured
    nt = [r for r in M if r['eval_awareness'] == 'not-tested']
    for k, tok in ELI_TOK.items():
        T[f'N_NOTTESTED_{tok}'] = sum(1 for r in nt if r['elicitation'] == k)
    T['N_NOTTESTED_PROMPT_OPT'] = T['N_NOTTESTED_PROMPT'] + T['N_NOTTESTED_OPT']
    T['PCT_NOTTESTED_PROMPT_OPT'] = pct(T['N_NOTTESTED_PROMPT_OPT'], len(nt))
    T['N_SCEN_APPLICABLE'] = sum(1 for r in M if r['elicitation'] == 'constructed-scenario'
                                 and r['eval_awareness'] != 'n-a')
    T['N_PROMPT_APPLICABLE'] = sum(1 for r in M if r['elicitation'] == 'prompted'
                                   and r['eval_awareness'] != 'n-a')
    T['PCT_SCEN_TESTED'] = pct(T['N_AWR_SCEN'], T['N_SCEN_APPLICABLE'])

    # ------------------------------------------------------------------ locus
    LOC_TOK = {'weights-prior': 'WEIGHTS', 'context-window': 'CONTEXT',
               'reasoning-trace': 'REASONING', 'agent-trajectory': 'TRAJECTORY',
               'multi-agent-system': 'MULTIAGENT', 'training-loop': 'TRAINING',
               'eval-harness': 'HARNESS', 'deployment-system': 'DEPLOY'}
    for k, tok in LOC_TOK.items():
        T[f'N_LOC_{tok}'] = c_loc[k]
        T[f'PCT_LOC_{tok}'] = pct(c_loc[k])
    T['N_LOC_AGENTIC'] = c_loc['agent-trajectory'] + c_loc['multi-agent-system']
    T['N_LOC_AGENTIC_2025PLUS'] = sum(1 for r in M if r['year'] >= 2025 and
                                      r['locus'] in ('agent-trajectory', 'multi-agent-system'))
    T['N_2025PLUS'] = sum(1 for r in M if r['year'] >= 2025)
    T['PCT_LOC_AGENTIC_2025PLUS'] = pct(T['N_LOC_AGENTIC_2025PLUS'], T['N_2025PLUS'])
    T['N_LOC_WEIGHTS_PRE2025'] = sum(1 for r in M if r['year'] < 2025 and r['locus'] == 'weights-prior')
    T['N_PRE2025'] = sum(1 for r in M if r['year'] < 2025)
    T['PCT_LOC_WEIGHTS_PRE2025'] = pct(T['N_LOC_WEIGHTS_PRE2025'], T['N_PRE2025'])
    T['N_LOC_REASONING_2025PLUS'] = sum(1 for r in M if r['year'] >= 2025 and r['locus'] == 'reasoning-trace')

    # --------------------------------------------------------- evidence & harm
    EVD_TOK = {'behavioural-rate': 'RATE', 'controlled-counterfactual': 'CF',
               'internals-probe': 'PROBE', 'formal-proof': 'PROOF',
               'case-demonstration': 'CASE', 'corpus-synthesis': 'SYNTH'}
    for k, tok in EVD_TOK.items():
        T[f'N_EVD_{tok}'] = c_evd[k]
        T[f'PCT_EVD_{tok}'] = pct(c_evd[k])
    T['N_EVD_EMPIRICAL'] = c_evd['behavioural-rate'] + c_evd['controlled-counterfactual']
    T['PCT_EVD_EMPIRICAL'] = pct(T['N_EVD_EMPIRICAL'])
    T['N_EVD_NOEXPERIMENT'] = c_evd['corpus-synthesis'] + c_evd['formal-proof']

    HRM_TOK = {'user': 'USER', 'operator': 'OPERATOR', 'third-party': 'THIRD',
               'society': 'SOCIETY', 'research-integrity': 'RESEARCH'}
    for k, tok in HRM_TOK.items():
        T[f'N_HRM_{tok}'] = c_hrm[k]
        T[f'PCT_HRM_{tok}'] = pct(c_hrm[k])
    T['N_HRM_PRINCIPALS'] = c_hrm['user'] + c_hrm['operator']
    T['PCT_HRM_PRINCIPALS'] = pct(T['N_HRM_PRINCIPALS'])
    T['N_HRM_BYSTANDERS'] = c_hrm['third-party'] + c_hrm['society']
    T['PCT_HRM_BYSTANDERS'] = pct(T['N_HRM_BYSTANDERS'])

    # --------------------------------------------------------------- kingdoms
    KING_TOK = {'A-objective-corruption': 'A', 'B-competence-cliffs': 'B',
                'C-truthfulness-breakdown': 'C', 'D-interaction-failure': 'D',
                'E-oversight-erosion': 'E', 'F-adversarial-breach': 'F',
                'G-agentic-breakdown': 'G', 'H-measurement-integrity': 'H'}
    for k, tok in KING_TOK.items():
        T[f'N_KING_{tok}'] = c_king[k]
        T[f'PCT_KING_{tok}'] = pct(c_king[k])
    f_papers = [r for r in M if r['kingdom'] == 'F-adversarial-breach']
    T['N_KING_F_SPONTANEOUS'] = sum(1 for r in f_papers if r['elicitation'] == 'spontaneous')
    T['N_KING_F_MANUFACTURED'] = sum(1 for r in f_papers
                                     if r['elicitation'] in ('prompted', 'optimized'))
    T['N_KING_F_FAIL'] = sum(1 for r in f_papers if r['mitigation_status'] == 'defenses-fail')
    T['PCT_KING_F_FAIL_SHARE'] = pct(T['N_KING_F_FAIL'], c_mit['defenses-fail'])
    h_papers = [r for r in M if r['kingdom'] == 'H-measurement-integrity']
    T['N_KING_H_SPONTANEOUS'] = sum(1 for r in h_papers if r['elicitation'] == 'spontaneous')
    g_papers = [r for r in M if r['kingdom'] == 'G-agentic-breakdown']
    T['N_KING_G_SPONTANEOUS'] = sum(1 for r in g_papers if r['elicitation'] == 'spontaneous')
    T['N_KING_G_SCEN'] = sum(1 for r in g_papers if r['elicitation'] == 'constructed-scenario')
    a_papers = [r for r in M if r['kingdom'] == 'A-objective-corruption']
    T['N_KING_A_TRAIN'] = sum(1 for r in a_papers if r['elicitation'] == 'trained-in')
    T['N_KING_A_NONE'] = sum(1 for r in a_papers if r['elicitation'] == 'not-elicited')
    T['RATIO_F_OVER_D'] = round(c_king['F-adversarial-breach'] / c_king['D-interaction-failure'], 1) \
        if c_king['D-interaction-failure'] else 0

    # ------------------------------------------------------------ lineage hubs
    indeg = collections.Counter()
    for r in M:
        for e in r['lineage']:
            indeg[e['parent']] += 1
    T['N_HUB_IPI'] = indeg['greshake-2023-indirect-prompt-injection']
    T['N_HUB_GCG'] = indeg['zou-2023-gcg']
    T['N_HUB_ICS'] = indeg['meinke-2024-in-context-scheming']
    T['N_HUB_UNFAITHFUL'] = indeg['turpin-2023-unfaithful-cot']
    T['N_HUB_OBFUSCATION'] = indeg['baker-2025-monitoring-reasoning']
    T['N_DEFENDS_EDGES'] = sum(1 for r in M for e in r['lineage']
                               if e['relation'] == 'defends-against')
    T['N_DEFENDS_TARGETS'] = len(set(e['parent'] for r in M for e in r['lineage']
                                     if e['relation'] == 'defends-against'))
    T['N_AM_PARENTS'] = len(by['lynch-2025-agentic-misalignment']['lineage'])

    def _months(d):
        y, m = d.split('-')
        return int(y) * 12 + int(m)
    T['MONTHS_BD_AUTODAN'] = abs(_months(by['liu-2023-autodan']['date'])
                                 - _months(by['jain-2023-baseline-defenses']['date']))
    T['N_DEFENDS_AT_IPI'] = sum(1 for r in M for e in r['lineage']
                                if e['relation'] == 'defends-against'
                                and e['parent'] == 'greshake-2023-indirect-prompt-injection')
    T['N_RESPONDS_EDGES'] = sum(1 for r in M for e in r['lineage']
                                if e['relation'] == 'responds-to')

    # ------------------------------------------------ paper-quoted figures
    for tok, (slug, rx) in QUOTES.items():
        T[tok] = _quote(by, slug, rx, tok)
    # derived from two quoted figures (still not hand-typed: read, then divided)
    T['Q_AM_SWING'] = round(float(T['Q_AM_REAL'].rstrip('%')) / float(T['Q_AM_EVAL'].rstrip('%')), 1)

    return T
