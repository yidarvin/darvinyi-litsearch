"""Compute every numeric token the survey prose cites, straight from the classified corpus,
so no number in the page is ever hand-typed. compute(M, era, ERAS) -> {TOKEN: value}."""
import collections

def compute(M, era, ERAS):
    N = len(M)
    T = {}
    def pct(x): return round(100 * x / N)
    c_rwd = collections.Counter(r['reward_readiness'] for r in M)
    c_eng = collections.Counter(r['verdict_engine'] for r in M)
    c_gap = collections.Counter(r['grader_gap'] for r in M)
    c_val = collections.Counter(r['validation_depth'] for r in M)
    c_ref = collections.Counter(r['reference_standard'] for r in M)
    c_king = collections.Counter(r['kingdom'] for r in M)

    T['N'] = N
    T['N_METAEVAL'] = sum(1 for r in M if r['meta_eval'])
    T['PCT_METAEVAL'] = pct(T['N_METAEVAL'])
    T['N_NONMETA'] = N - T['N_METAEVAL']

    # reward readiness
    T['N_REWNATIVE'] = c_rwd['reward-native']
    T['N_REWADAPT'] = c_rwd['reward-adapted']
    T['N_DIAG'] = c_rwd['diagnostic-only']
    T['N_OPTFORBID'] = c_rwd['optimization-forbidden']
    T['PCT_OPTFORBID'] = pct(T['N_OPTFORBID'])
    T['N_TRAINSIG'] = c_rwd['reward-native'] + c_rwd['reward-adapted']
    T['PCT_TRAINSIG'] = pct(T['N_TRAINSIG'])
    T['PCT_DIAG'] = pct(T['N_DIAG'])

    # optimization-forbidden timeline
    pre22 = sum(1 for r in M if r['reward_readiness'] == 'optimization-forbidden' and r['year'] < 2022)
    T['N_OPTFORBID_PRE2022'] = pre22
    of25 = [r for r in M if era(r['year']) == '2025']
    T['N_OPTFORBID_2025'] = sum(1 for r in of25 if r['reward_readiness'] == 'optimization-forbidden')
    T['N_2025'] = len(of25)

    # engine counts
    for k, tok in [('lexical-overlap', 'LEXICAL'), ('execution-oracle', 'EXEC'), ('model-judge', 'MODELJUDGE'),
                   ('decomposed-judge', 'DECOMP'), ('process-monitor', 'PROCMON'), ('statistical-protocol', 'STATPROT'),
                   ('human-grading', 'HUMANGRADE'), ('learned-metric', 'LEARNED')]:
        T[f'N_ENG_{tok}'] = c_eng[k]
    # process-monitor all one year?
    pm_years = set(r['year'] for r in M if r['verdict_engine'] == 'process-monitor')
    T['PROCMON_YEARS'] = '/'.join(str(y) for y in sorted(pm_years)) if pm_years else '—'
    T['N_PROCMON_2025'] = sum(1 for r in M if r['verdict_engine'] == 'process-monitor' and r['year'] == 2025)
    # lexical share pre-2019
    pre19 = [r for r in M if r['year'] <= 2018]
    T['N_PRE2019'] = len(pre19)
    T['N_PRE2019_LEXICAL'] = sum(1 for r in pre19 if r['verdict_engine'] == 'lexical-overlap')

    # reference standard
    T['N_PRE2019_GOLDREF'] = sum(1 for r in pre19 if r['reference_standard'] == 'gold-reference')
    T['N_REF_MODELPROCESS'] = c_ref['model-process']
    T['N_REF_JUDGEPRIOR'] = c_ref['judge-prior']
    T['N_REF_GOLDREF'] = c_ref['gold-reference']

    # grader gap
    T['N_GAP_NOMODEL'] = c_gap['no-model']
    T['N_GAP_PEER'] = c_gap['peer-or-stronger']
    T['N_GAP_WEAKER'] = c_gap['weaker-ok']
    T['N_GAP_HUMAN'] = c_gap['human-anchored']
    T['N_GAP_BIMODAL'] = c_gap['no-model'] + c_gap['peer-or-stronger']
    T['PCT_GAP_WEAKER'] = pct(c_gap['weaker-ok'])

    # validation depth
    T['N_VAL_NONE'] = c_val['none']
    T['N_VAL_AGREE'] = c_val['human-agreement']
    T['N_VAL_BIAS'] = c_val['bias-audited']
    T['N_VAL_ADV'] = c_val['adversarial-stress']
    T['N_VAL_SHALLOW'] = c_val['none'] + c_val['human-agreement']
    T['PCT_VAL_SHALLOW'] = pct(T['N_VAL_SHALLOW'])
    # deep validation concentrated in meta papers
    meta = [r for r in M if r['meta_eval']]
    nonmeta = [r for r in M if not r['meta_eval']]
    T['N_META_DEEP'] = sum(1 for r in meta if r['validation_depth'] in ('bias-audited', 'adversarial-stress'))
    T['N_META'] = len(meta)
    T['N_NONMETA_DEEP'] = sum(1 for r in nonmeta if r['validation_depth'] in ('bias-audited', 'adversarial-stress'))
    T['N_NONMETA_SHALLOW'] = sum(1 for r in nonmeta if r['validation_depth'] in ('none', 'human-agreement'))
    T['N_NONMETA_TOT'] = len(nonmeta)

    # kingdoms
    T['N_KING_FORENSICS'] = c_king['F-forensics-audits']
    T['N_KING_VERIFY'] = c_king['V-verification-harnesses']
    T['N_KING_PROBES'] = c_king['I-behavioral-probes']
    T['N_KING_PROCESS'] = c_king['M-process-surveillance']

    # gravity hubs
    grav = {r['slug']: r.get('gravity', 0) for r in M}
    T['GRAV_HUMANEVAL'] = grav.get('chen-2021-codex', 0)
    T['GRAV_MTBENCH'] = grav.get('zheng-2023-mt-bench', 0)
    T['GRAV_BLEU'] = grav.get('papineni-2002-bleu', 0)
    T['GRAV_SWEBENCH'] = grav.get('jimenez-2023-swe-bench', 0)
    T['GRAV_BIGBENCH'] = grav.get('srivastava-2022-big-bench', 0)

    # edges in corpus (for connections framing)
    return {k: v for k, v in T.items()}
