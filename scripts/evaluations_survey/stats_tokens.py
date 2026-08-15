"""Compute every numeric token the survey prose cites, straight from the classified corpus,
so no number in the page is ever hand-typed. compute(M, era, ERAS) -> {TOKEN: value}.

Rule of the file: if the page states a count, share, ranking, span, or superlative, it comes
from here. Prose that asserts an ordering ("the largest kingdom is X") gets both the name and
the number as tokens, so a re-tag that reorders the corpus rewrites the sentence too.
"""
import collections, json, pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent.parent

WORDS = {0: 'zero', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven',
         8: 'eight', 9: 'nine', 10: 'ten', 11: 'eleven', 12: 'twelve', 13: 'thirteen',
         14: 'fourteen', 15: 'fifteen', 16: 'sixteen', 17: 'seventeen', 18: 'eighteen',
         19: 'nineteen', 20: 'twenty', 21: 'twenty-one', 22: 'twenty-two', 23: 'twenty-three',
         24: 'twenty-four', 25: 'twenty-five', 26: 'twenty-six'}
ORD = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh',
       8: 'eighth', 9: 'ninth', 10: 'tenth'}

# facet keys the page claims to classify along (the "seven questions")
FACETS = ['verdict_engine', 'construct', 'reference_standard', 'signal_fidelity',
          'reward_readiness', 'validation_depth', 'grader_gap']

KING_NAME = {'S-scoring-metrics': 'scoring metrics', 'V-verification-harnesses': 'verification harnesses',
             'P-preference-courts': 'preference courts', 'I-behavioral-probes': 'behavioral probes',
             'M-process-surveillance': 'process surveillance', 'F-forensics-audits': 'forensics &amp; audits',
             'T-measurement-theory': 'measurement theory'}

# papers whose scoring machinery grades a model's *representations / inputs* rather than its
# outputs — the rubric's unresolved boundary, named in the corpus section.
REPR_SCORERS = ['lee-2018-mahalanobis-ood', 'liu-2020-energy-ood', 'wang-2020-alignment-uniformity']
# papers that borrow an existing instrument or ship no verdict of their own — the softer edge
BORROWED = ['lakshminarayanan-2016-deep-ensembles', 'lin-2023-agentsims']

MODEL_GRADED = ('model-judge', 'decomposed-judge', 'process-monitor')


def compute(M, era, ERAS):
    N = len(M)
    T = {}
    def pct(x, base=None): return round(100 * x / (base if base else N))
    def shorts(slugs):
        m = {r['slug']: r['short'].replace('&', '&amp;') for r in M}
        return ', '.join(m[s] for s in slugs if s in m)

    c_rwd = collections.Counter(r['reward_readiness'] for r in M)
    c_eng = collections.Counter(r['verdict_engine'] for r in M)
    c_gap = collections.Counter(r['grader_gap'] for r in M)
    c_val = collections.Counter(r['validation_depth'] for r in M)
    c_ref = collections.Counter(r['reference_standard'] for r in M)
    c_king = collections.Counter(r['kingdom'] for r in M)
    c_fam = collections.Counter(r['family'] for r in M)
    c_fid = collections.Counter(r['signal_fidelity'] for r in M)
    by_era = {e: [r for r in M if era(r['year']) == e] for e in ERAS}

    T['N'] = N
    T['N_METAEVAL'] = sum(1 for r in M if r['meta_eval'])
    T['PCT_METAEVAL'] = pct(T['N_METAEVAL'])
    T['N_NONMETA'] = N - T['N_METAEVAL']

    # ---------- span & shape ----------
    years = [r['year'] for r in M]
    T['YEAR_MIN'], T['YEAR_MAX'] = min(years), max(years)
    T['SPAN'] = f"{min(years)}–{max(years)}"
    first = min(M, key=lambda r: (r['date'], r['year']))
    T['EARLIEST_SHORT'], T['EARLIEST_YEAR'] = first['short'], first['year']
    T['N_FACETS'] = len(FACETS)
    T['N_FACETS_WORD'] = WORDS[len(FACETS)]
    T['N_ENGINES'] = len(set(r['verdict_engine'] for r in M))
    T['N_ENGINES_WORD'] = WORDS[T['N_ENGINES']]
    T['N_KINGDOMS'] = len(c_king)
    T['N_KINGDOMS_WORD'] = WORDS[len(c_king)]
    T['N_FAMILIES'] = len(c_fam)
    T['N_FAMILIES_WORD'] = WORDS[len(c_fam)]
    T['N_CONSTRUCTS'] = len(set(r['construct'] for r in M))
    T['N_HIGHCONF'] = sum(1 for r in M if r['confidence'] == 'high')
    T['N_MEDCONF'] = sum(1 for r in M if r['confidence'] == 'medium')
    T['PCT_HIGHCONF'] = pct(T['N_HIGHCONF'])

    # per-era sizes
    for e, tok in [('≤2018', 'PRE2019'), ('2019–21', 'E1921'), ('2022', 'E2022'),
                   ('2023', 'E2023'), ('2024', 'E2024'), ('2025', 'E2025'), ('2026', 'E2026')]:
        T[f'N_{tok}'] = len(by_era[e])
    T['N_2025'] = len(by_era['2025'])
    T['N_PRE2022'] = sum(1 for r in M if r['year'] < 2022)
    T['N_POST2022'] = N - T['N_PRE2022']

    # in-corpus citation graph (gravity is in-degree restricted to the tagged set)
    P = json.load(open(REPO / 'data' / 'papers.json'))
    slugs = set(r['slug'] for r in M)
    T['N_EDGES'] = len(set((e['from'], e['to']) for e in P['edges']
                           if e['from'] in slugs and e['to'] in slugs))
    T['N_BOTH_BENCH'] = sum(1 for p in P['papers']
                            if p['slug'] in slugs and 'benchmarks' in p.get('tags', []))

    # ---------- reward readiness (the load-bearing axis) ----------
    T['N_REWNATIVE'] = c_rwd['reward-native']
    T['N_REWADAPT'] = c_rwd['reward-adapted']
    T['N_DIAG'] = c_rwd['diagnostic-only']
    T['N_OPTFORBID'] = c_rwd['optimization-forbidden']
    T['PCT_OPTFORBID'] = pct(T['N_OPTFORBID'])
    T['N_TRAINSIG'] = c_rwd['reward-native'] + c_rwd['reward-adapted']
    T['PCT_TRAINSIG'] = pct(T['N_TRAINSIG'])
    T['PCT_DIAG'] = pct(T['N_DIAG'])
    T['N_POLES'] = T['N_TRAINSIG'] + T['N_OPTFORBID']
    T['PCT_POLES'] = pct(T['N_POLES'])

    ra = [r for r in M if r['reward_readiness'] == 'reward-adapted']
    T['REWADAPT_FIRST_YEAR'] = min(r['year'] for r in ra) if ra else '—'
    T['N_REWADAPT_2026'] = sum(1 for r in ra if r['year'] == 2026)
    of = [r for r in M if r['reward_readiness'] == 'optimization-forbidden']
    pre22 = [r for r in of if r['year'] < 2022]
    T['N_OPTFORBID_PRE2022'] = len(pre22)
    T['PCT_OPTFORBID_PRE2022'] = pct(len(pre22), T['N_PRE2022'])
    T['N_OPTFORBID_POST2022'] = len(of) - len(pre22)
    T['PCT_OPTFORBID_POST2022'] = pct(len(of) - len(pre22), T['N_POST2022'])
    of_first = min(of, key=lambda r: (r['year'], r['short']))
    T['OPTFORBID_FIRST_SHORT'], T['OPTFORBID_FIRST_YEAR'] = of_first['short'], of_first['year']
    T['N_OPTFORBID_ADVROB'] = sum(1 for r in of if r['family'] == 'I3-adversarial-robustness')
    T['N_OPTFORBID_2025'] = sum(1 for r in by_era['2025'] if r['reward_readiness'] == 'optimization-forbidden')
    T['PCT_OPTFORBID_2025'] = pct(T['N_OPTFORBID_2025'], T['N_2025'])
    T['N_OPTFORBID_2024'] = sum(1 for r in by_era['2024'] if r['reward_readiness'] == 'optimization-forbidden')
    T['N_DIAG_2025'] = sum(1 for r in by_era['2025'] if r['reward_readiness'] == 'diagnostic-only')
    T['PCT_DIAG_2025'] = pct(T['N_DIAG_2025'], T['N_2025'])
    T['N_OPTFORBID_M'] = sum(1 for r in of if r['kingdom'] == 'M-process-surveillance')
    T['N_OPTFORBID_M_2025'] = sum(1 for r in of if r['kingdom'] == 'M-process-surveillance' and r['year'] == 2025)
    T['N_OPTFORBID_I'] = sum(1 for r in of if r['kingdom'] == 'I-behavioral-probes')
    T['N_OPTFORBID_F'] = sum(1 for r in of if r['kingdom'] == 'F-forensics-audits')

    # ---------- engines ----------
    for k, tok in [('lexical-overlap', 'LEXICAL'), ('execution-oracle', 'EXEC'), ('model-judge', 'MODELJUDGE'),
                   ('decomposed-judge', 'DECOMP'), ('process-monitor', 'PROCMON'), ('statistical-protocol', 'STATPROT'),
                   ('human-grading', 'HUMANGRADE'), ('learned-metric', 'LEARNED')]:
        T[f'N_ENG_{tok}'] = c_eng[k]
    T['PCT_ENG_STATPROT'] = pct(c_eng['statistical-protocol'])
    T['N_EXEC_POST2022'] = sum(1 for r in M if r['verdict_engine'] == 'execution-oracle' and r['year'] >= 2023)
    eng_rank = [k for k, _ in c_eng.most_common()]
    T['ENG_TOP'] = eng_rank[0].replace('-', ' ')
    T['N_ENG_TOP'] = c_eng[eng_rank[0]]

    pm = [r for r in M if r['verdict_engine'] == 'process-monitor']
    pm_years = sorted(set(r['year'] for r in pm))
    T['PROCMON_YEARS'] = '/'.join(str(y) for y in pm_years) if pm_years else '—'
    T['PROCMON_YEAR_LAST'] = pm_years[-1] if pm_years else '—'
    T['PROCMON_YEAR_FIRST'] = pm_years[0] if pm_years else '—'
    T['N_PROCMON_2025'] = sum(1 for r in pm if r['year'] == 2025)
    T['N_PROCMON_OPTFORBID'] = sum(1 for r in pm if r['reward_readiness'] == 'optimization-forbidden')

    # item-graders: everything except the statistical protocols, which design aggregation, not verdicts
    item = [r for r in M if r['verdict_engine'] != 'statistical-protocol']
    T['N_ITEMGRADERS'] = len(item)
    pre19 = by_era['≤2018']
    pre19_item = [r for r in pre19 if r['verdict_engine'] != 'statistical-protocol']
    T['N_PRE2019_ITEM'] = len(pre19_item)
    T['N_PRE2019_ITEM_LEXICAL'] = sum(1 for r in pre19_item if r['verdict_engine'] == 'lexical-overlap')
    T['PCT_PRE2019_ITEM_LEXICAL'] = pct(T['N_PRE2019_ITEM_LEXICAL'], max(len(pre19_item), 1))
    T['N_PRE2019'] = len(pre19)
    T['N_PRE2019_LEXICAL'] = sum(1 for r in pre19 if r['verdict_engine'] == 'lexical-overlap')
    T['N_PRE2019_STATPROT'] = sum(1 for r in pre19 if r['verdict_engine'] == 'statistical-protocol')
    T['PCT_PRE2019_STATPROT'] = pct(T['N_PRE2019_STATPROT'], len(pre19))

    mg = [r for r in M if r['verdict_engine'] in MODEL_GRADED]
    T['N_MODELGRADED'] = len(mg)
    T['PCT_MODELGRADED'] = pct(len(mg))
    T['N_MODELGRADED_PRE2019'] = sum(1 for r in pre19 if r['verdict_engine'] in MODEL_GRADED)
    T['PCT_MODELGRADED_PRE2019'] = pct(T['N_MODELGRADED_PRE2019'], len(pre19))
    T['N_MODELGRADED_2025'] = sum(1 for r in by_era['2025'] if r['verdict_engine'] in MODEL_GRADED)
    T['PCT_MODELGRADED_2025'] = pct(T['N_MODELGRADED_2025'], T['N_2025'])
    T['N_MODELJUDGE_2324'] = sum(1 for r in M if r['verdict_engine'] == 'model-judge' and r['year'] in (2023, 2024))
    T['N_DECOMP_2025'] = sum(1 for r in by_era['2025'] if r['verdict_engine'] == 'decomposed-judge')
    T['PCT_DECOMP_2025'] = pct(T['N_DECOMP_2025'], T['N_2025'])
    T['N_STATPROT_2025'] = sum(1 for r in by_era['2025'] if r['verdict_engine'] == 'statistical-protocol')
    T['PCT_STATPROT_2025'] = pct(T['N_STATPROT_2025'], T['N_2025'])

    # ---------- reference standard ----------
    T['N_PRE2019_GOLDREF'] = sum(1 for r in pre19 if r['reference_standard'] == 'gold-reference')
    T['PCT_PRE2019_GOLDREF'] = pct(T['N_PRE2019_GOLDREF'], len(pre19))
    T['N_REF_MODELPROCESS'] = c_ref['model-process']
    T['N_REF_JUDGEPRIOR'] = c_ref['judge-prior']
    T['N_REF_GOLDREF'] = c_ref['gold-reference']
    T['N_REF_TESTORACLE'] = c_ref['test-oracle']
    T['N_REF_EXPERTRUBRIC'] = c_ref['expert-rubric']
    T['N_REF_HUMANPREF'] = c_ref['human-preference']
    T['N_REF_SELFREF'] = c_ref['none-self-referential']
    T['PCT_REF_GOLDREF'] = pct(c_ref['gold-reference'])
    T['N_GOLDREF_2025'] = sum(1 for r in by_era['2025'] if r['reference_standard'] == 'gold-reference')
    T['PCT_GOLDREF_2025'] = pct(T['N_GOLDREF_2025'], T['N_2025'])
    T['N_EXPERTRUBRIC_2025'] = sum(1 for r in by_era['2025'] if r['reference_standard'] == 'expert-rubric')
    T['PCT_EXPERTRUBRIC_2025'] = pct(T['N_EXPERTRUBRIC_2025'], T['N_2025'])
    mproc_years = sorted(set(r['year'] for r in M if r['reference_standard'] == 'model-process'))
    T['MODELPROCESS_YEARS'] = '/'.join(str(y) for y in mproc_years) if mproc_years else '—'
    T['N_MODELPROCESS_2025'] = sum(1 for r in by_era['2025'] if r['reference_standard'] == 'model-process')
    ref_rank_2025 = collections.Counter(r['reference_standard'] for r in by_era['2025']).most_common()
    T['REF_TOP_2025'] = ref_rank_2025[0][0].replace('-', ' ')
    T['N_REFS_USED'] = len(c_ref)
    T['N_REFS_ALT'] = len(c_ref) - 1
    T['N_REFS_ALT_WORD'] = WORDS[len(c_ref) - 1]
    mj = [r for r in M if r['verdict_engine'] == 'model-judge']
    T['N_MODELJUDGE_PRIOR'] = sum(1 for r in mj if r['reference_standard'] == 'judge-prior')
    T['N_MODELJUDGE_ANCHORED'] = len(mj) - T['N_MODELJUDGE_PRIOR']

    # ---------- grader gap ----------
    T['N_GAP_NOMODEL'] = c_gap['no-model']
    T['N_GAP_PEER'] = c_gap['peer-or-stronger']
    T['N_GAP_WEAKER'] = c_gap['weaker-ok']
    T['N_GAP_HUMAN'] = c_gap['human-anchored']
    T['N_GAP_BIMODAL'] = c_gap['no-model'] + c_gap['peer-or-stronger']
    T['PCT_GAP_BIMODAL'] = pct(T['N_GAP_BIMODAL'])
    T['PCT_GAP_WEAKER'] = pct(c_gap['weaker-ok'])
    T['PCT_GAP_NOMODEL'] = pct(c_gap['no-model'])
    T['PCT_GAP_PEER'] = pct(c_gap['peer-or-stronger'])
    wk = [r for r in M if r['grader_gap'] == 'weaker-ok']
    T['N_WEAKER_SCORERS'] = sum(1 for r in wk if r['kingdom'] == 'S-scoring-metrics')
    T['N_WEAKER_OVERSIGHT'] = sum(1 for r in wk if r['kingdom'] in ('M-process-surveillance', 'V-verification-harnesses'))
    T['N_WEAKER_2023P'] = sum(1 for r in wk if r['year'] >= 2023)
    T['N_NOMODEL_PRE2019'] = sum(1 for r in pre19 if r['grader_gap'] == 'no-model')
    T['PCT_NOMODEL_PRE2019'] = pct(T['N_NOMODEL_PRE2019'], len(pre19))
    for key, tok in [('no-model', 'NOMODEL'), ('peer-or-stronger', 'PEER'), ('weaker-ok', 'WEAKER'),
                     ('human-anchored', 'HUMANANCH')]:
        n = sum(1 for r in by_era['2025'] if r['grader_gap'] == key)
        T[f'N_{tok}_2025'] = n
        T[f'PCT_{tok}_2025'] = pct(n, T['N_2025'])

    # ---------- validation depth ----------
    T['N_VAL_NONE'] = c_val['none']
    T['N_VAL_AGREE'] = c_val['human-agreement']
    T['N_VAL_BIAS'] = c_val['bias-audited']
    T['N_VAL_ADV'] = c_val['adversarial-stress']
    T['N_VAL_SHALLOW'] = c_val['none'] + c_val['human-agreement']
    T['PCT_VAL_SHALLOW'] = pct(T['N_VAL_SHALLOW'])
    meta = [r for r in M if r['meta_eval']]
    nonmeta = [r for r in M if not r['meta_eval']]
    T['N_META_DEEP'] = sum(1 for r in meta if r['validation_depth'] in ('bias-audited', 'adversarial-stress'))
    T['N_META'] = len(meta)
    T['PCT_META_DEEP'] = pct(T['N_META_DEEP'], len(meta))
    T['N_NONMETA_DEEP'] = sum(1 for r in nonmeta if r['validation_depth'] in ('bias-audited', 'adversarial-stress'))
    T['PCT_NONMETA_DEEP'] = pct(T['N_NONMETA_DEEP'], len(nonmeta))
    T['RATIO_META_DEEP'] = round(T['PCT_META_DEEP'] / max(T['PCT_NONMETA_DEEP'], 1), 1)
    T['N_NONMETA_SHALLOW'] = sum(1 for r in nonmeta if r['validation_depth'] in ('none', 'human-agreement'))
    T['PCT_NONMETA_SHALLOW'] = pct(T['N_NONMETA_SHALLOW'], len(nonmeta))
    T['N_NONMETA_TOT'] = len(nonmeta)

    # ---------- signal fidelity ----------
    T['N_FID_SURFACE'] = c_fid['surface-correlate']
    T['N_FID_SURFACE_DIAG'] = sum(1 for r in M if r['signal_fidelity'] == 'surface-correlate'
                                  and r['reward_readiness'] == 'diagnostic-only')
    T['N_FID_PROCTRANS'] = c_fid['process-transparency']
    T['N_FID_PROCTRANS_OPTFORBID'] = sum(1 for r in M if r['signal_fidelity'] == 'process-transparency'
                                         and r['reward_readiness'] == 'optimization-forbidden')
    T['N_FID_DIRECT'] = c_fid['direct-outcome']
    T['N_FID_DECOMP'] = c_fid['decomposed-proxy']
    T['N_FID_DIRECT_TRAINSIG'] = sum(1 for r in M if r['signal_fidelity'] == 'direct-outcome'
                                     and r['reward_readiness'] in ('reward-native', 'reward-adapted'))
    T['N_FID_DECOMP_TRAINSIG'] = sum(1 for r in M if r['signal_fidelity'] == 'decomposed-proxy'
                                     and r['reward_readiness'] in ('reward-native', 'reward-adapted'))

    # ---------- kingdoms & families ----------
    for k, tok in [('F-forensics-audits', 'FORENSICS'), ('V-verification-harnesses', 'VERIFY'),
                   ('I-behavioral-probes', 'PROBES'), ('M-process-surveillance', 'PROCESS'),
                   ('S-scoring-metrics', 'SCORING'), ('T-measurement-theory', 'THEORY'),
                   ('P-preference-courts', 'PREF')]:
        T[f'N_KING_{tok}'] = c_king[k]
    king_rank = c_king.most_common()
    T['KING_TOP_NAME'] = KING_NAME[king_rank[0][0]]
    T['N_KING_TOP'] = king_rank[0][1]
    T['PCT_KING_TOP'] = pct(king_rank[0][1])
    T['KING_2_NAME'] = KING_NAME[king_rank[1][0]]
    T['KING_SMALLEST_NAME'] = KING_NAME[king_rank[-1][0]]

    fam_rank = c_fam.most_common()
    T['N_FAM_TOP'] = fam_rank[0][1]
    T['PCT_FAM_TOP'] = pct(fam_rank[0][1])
    for f, tok in [('F1-contamination-forensics', 'F1'), ('F2-judge-bias-audits', 'F2'),
                   ('F3-metric-construct-critiques', 'F3'), ('F4-reward-hacking-forensics', 'F4'),
                   ('F5-benchmark-rigor-standards', 'F5'), ('V2-rubric-verifiers', 'V2'),
                   ('S3-reference-free-scorers', 'S3'), ('I3-adversarial-robustness', 'I3'),
                   ('T1-holistic-frameworks', 'T1'), ('T2-capability-axis-instruments', 'T2')]:
        T[f'N_FAM_{tok}'] = c_fam[f]
    T['PCT_FAM_F3'] = pct(c_fam['F3-metric-construct-critiques'])
    f3 = [r for r in M if r['family'] == 'F3-metric-construct-critiques']
    T['N_F3_FAIR'] = sum(1 for r in f3 if r['construct'] == 'fairness')
    T['N_F3_MEASINT'] = sum(1 for r in f3 if r['construct'] == 'measurement-integrity')
    T['N_F3_STATPROT'] = sum(1 for r in f3 if r['verdict_engine'] == 'statistical-protocol')
    T['F3_YEAR_MIN'] = min(r['year'] for r in f3)
    T['F3_YEAR_MAX'] = max(r['year'] for r in f3)
    fair = [r for r in f3 if r['construct'] == 'fairness']
    T['F3_FAIR_SPAN'] = f"{min(r['year'] for r in fair)}–{max(r['year'] for r in fair)}"
    T['N_F3_METAEVAL'] = sum(1 for r in f3 if r['meta_eval'])
    v2 = [r for r in M if r['family'] == 'V2-rubric-verifiers']
    T['N_FAM_V2_REWARD'] = sum(1 for r in v2 if r['reward_readiness'] in ('reward-native', 'reward-adapted'))
    T['N_FAM_V2_2025P'] = sum(1 for r in v2 if r['year'] >= 2025)
    m12 = [r for r in M if r['family'] in ('M1-cot-monitoring', 'M2-faithfulness-tests')]
    T['N_M1M2'] = len(m12)
    T['N_M1M2_WORD'] = WORDS[len(m12)]
    T['N_M1M2_OPTFORBID'] = sum(1 for r in m12 if r['reward_readiness'] == 'optimization-forbidden')

    # ---------- gravity hubs ----------
    grav = {r['slug']: r.get('gravity', 0) for r in M}
    T['GRAV_HUMANEVAL'] = grav.get('chen-2021-codex', 0)
    T['GRAV_MTBENCH'] = grav.get('zheng-2023-mt-bench', 0)
    T['GRAV_BLEU'] = grav.get('papineni-2002-bleu', 0)
    T['GRAV_SWEBENCH'] = grav.get('jimenez-2023-swe-bench', 0)
    T['GRAV_BIGBENCH'] = grav.get('srivastava-2022-big-bench', 0)
    T['GRAV_AICONTROL'] = grav.get('greenblatt-2023-ai-control', 0)
    ranked = sorted(M, key=lambda r: (-r.get('gravity', 0), r['slug']))
    T['GRAV_TOP_NAME'] = ranked[0]['short']
    T['GRAV_TOP_N'] = ranked[0].get('gravity', 0)
    T['GRAV_2_NAME'] = ranked[1]['short']
    order = [r['slug'] for r in ranked]
    def rank(slug): return order.index(slug) + 1 if slug in order else 0
    T['GRAV_RANK_HUMANEVAL'] = rank('chen-2021-codex')
    T['GRAV_RANK_HUMANEVAL_WORD'] = ORD.get(rank('chen-2021-codex'), str(rank('chen-2021-codex')))
    T['GRAV_RANK_MTBENCH_WORD'] = ORD.get(rank('zheng-2023-mt-bench'), str(rank('zheng-2023-mt-bench')))
    # biggest well inside the verification kingdom
    vk = [r for r in ranked if r['kingdom'] == 'V-verification-harnesses']
    T['GRAV_TOP_V_NAME'] = vk[0]['short']
    T['GRAV_TOP_V_N'] = vk[0].get('gravity', 0)
    # how much of HumanEval's pull is forensic
    P_edges = [(e['from'], e['to']) for e in P['edges']]
    he_citers = [f for f, t in P_edges if t == 'chen-2021-codex' and f in slugs]
    recs = {r['slug']: r for r in M}
    T['N_HUMANEVAL_CITERS'] = len(he_citers)
    T['N_HUMANEVAL_CITERS_F'] = sum(1 for s in he_citers if recs[s]['kingdom'] == 'F-forensics-audits')
    # who attracts the most forensic attention
    f_citers = collections.Counter(t for f, t in set(P_edges)
                                   if f in slugs and t in slugs and recs[f]['kingdom'] == 'F-forensics-audits')
    T['N_MTBENCH_CITERS_F'] = f_citers['zheng-2023-mt-bench']
    T['AUDITED_TOP_NAME'] = recs[f_citers.most_common(1)[0][0]]['short'] if f_citers else '—'
    ac_citers = [f for f, t in P_edges if t == 'greenblatt-2023-ai-control' and f in slugs]
    T['N_AICONTROL_CITERS_M'] = WORDS[sum(1 for s in ac_citers if recs[s]['kingdom'] == 'M-process-surveillance')]
    T['N_AICONTROL_CITERS_I'] = WORDS[sum(1 for s in ac_citers if recs[s]['kingdom'] == 'I-behavioral-probes')]

    # ---------- the rubric's unresolved boundary ----------
    present = [s for s in REPR_SCORERS if s in slugs]
    T['N_REPR_SCORERS'] = len(present)
    T['N_REPR_SCORERS_WORD'] = WORDS[len(present)]
    T['REPR_SCORERS_NAMES'] = shorts(present)
    borrowed = [s for s in BORROWED if s in slugs]
    T['N_BORROWED'] = len(borrowed)
    T['N_BORROWED_WORD'] = WORDS[len(borrowed)]
    T['BORROWED_NAMES'] = shorts(borrowed)
    T['N_BOUNDARY'] = len(present) + len(borrowed)
    T['N_BOUNDARY_WORD'] = WORDS[T['N_BOUNDARY']]

    # sentence-initial variants of every spelled-out number
    for k in [k for k in T if k.endswith('_WORD')]:
        T[k + '_CAP'] = str(T[k])[:1].upper() + str(T[k])[1:]
    return {k: v for k, v in T.items()}
