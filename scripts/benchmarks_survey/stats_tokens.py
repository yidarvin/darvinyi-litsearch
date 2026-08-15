"""Compute every corpus-statistic token the benchmarks-survey prose cites, straight from the
classified taxonomy, so no number on the page is ever hand-typed. compute(merged, era, ERAS)
-> {TOKEN: value}. Mirrors the evaluations_survey/stats_tokens.py pattern.

Scope: only *live corpus* statistics (paper counts, era pool sizes, membership counts,
percentages, span, and the in-corpus citation graph) are tokenised here. Deliberately NOT
tokenised (see build_survey_page.py / survey_template.html): (a) taxonomy *vocabulary* sizes
fixed by the schema and immune to corpus growth — 8 facets, 6 grading families, 5 horizon
buckets, 7 kingdoms, 25 families, 9 connections; (b) analysis-provenance numbers frozen at the
pre-growth snapshot the tree-placement QA was actually run against (the independent second
pass's coverage and disagreement counts, the 139/230 split of the 2026-08 backfill) — these
describe one-time historical events, not live properties of `merged`, and are worded in the
prose to name the corpus they were run against rather than silently inflate to the current N;
(c) numbers quoted from individual papers (e.g. MT-Bench's 85% judge/human agreement).

Everything that tracks the corpus IS live here, including things prose usually hand-types:
superlatives and extremes (EARLIEST_/LATEST_ endpoints, GRAV_TOP, FAM_TOP, ERA_*_PEAK), the
*names* the prose enumerates (EM_L3_LIST, L4_LIST, RUB_PRE2025_LIST, SAT_L3PLUS_LIST,
PRE2021_L3PLUS_LIST, …, and the *_EX example lists, which are chosen by gravity rather than by
hand), and the two graphs — the in-corpus citation subgraph (N_EDGES, the gravity-well
in-degrees) read from data/papers.json restricted to the `merged` rows, and the taxonomy's own
typed lineage graph (N_LINEAGE, the audit-lag statistics, N_TOP20_AUDITED). A hand-typed name or
superlative drifts exactly as silently as a hand-typed number: at 139 papers the hero dek said
the corpus began at ImageNet (2009), which the 369-paper corpus falsified.

Era labels that reach a token value are written ASCII-safe ('2018 and earlier', not '≤2018')
because these same values are emitted as LaTeX macros for the PDF, and the default font has no
text-mode glyph for '≤' (scripts/survey_scaffold/latex_utils.py documents the failure mode)."""
import collections
import json
import pathlib

LEV = ['L1-seconds', 'L2-minutes', 'L3-hours', 'L4-days', 'L5-weeks']
LEVNUM = {l: i + 1 for i, l in enumerate(LEV)}
L3PLUS = ('L3-hours', 'L4-days', 'L5-weeks')


def compute(merged, era, ERAS):
    M = merged
    N = len(M)
    T = {}

    def rnd(x):  # match the build script's round() (banker's rounding, like the charts)
        return round(x)

    def share(sub, tot):
        return rnd(100 * sub / tot) if tot else 0

    def in_era(e):
        return [r for r in M if era(r['year']) == e]

    def cnt(rows, pred):
        return sum(1 for r in rows if pred(r))

    def namelist(rows, years=False):
        """'A, B and C' — computed so the prose never hand-enumerates corpus membership."""
        rows = sorted(rows, key=lambda r: (r['year'], r['short'].lower()))
        names = [f"{r['short']} ({r['year']})" if years else r['short'] for r in rows]
        if not names:
            return 'none'
        if len(names) == 1:
            return names[0]
        return ', '.join(names[:-1]) + ' and ' + names[-1]

    def examples(rows, k=3):
        """The k most-cited members of a set — an example list chosen by the graph, not by hand."""
        return namelist(sorted(rows, key=lambda r: (-r['gravity'], r['short'].lower()))[:k])

    ERA_ASCII = {'≤2018': '2018 and earlier', '2019–20': '2019–20', '2021–22': '2021–22'}

    def peak_era(pred):
        """Era with the largest share of rows satisfying pred (ties -> earliest era)."""
        best, best_share = None, -1
        for e in ERAS:
            rows = in_era(e)
            s = share(cnt(rows, pred), len(rows))
            if s > best_share:
                best, best_share = e, s
        return ERA_ASCII.get(best, best)

    # ---- corpus-wide ----
    T['N'] = N
    yrs = [r['year'] for r in M]
    T['SPAN'] = f'{min(yrs)}–{max(yrs)}'
    T['SPAN_YEARS'] = max(yrs) - min(yrs)
    # hero dek endpoints: the corpus's actual first and last paper by preprint month.
    first = min(M, key=lambda r: (r['date'], r['short'].lower()))
    last = max(M, key=lambda r: (r['date'], r['short'].lower()))
    T['EARLIEST_SHORT'], T['EARLIEST_YEAR'] = first['short'], first['year']
    T['LATEST_SHORT'], T['LATEST_YEAR'] = last['short'], last['year']
    T['N_DOMAINS'] = len({r['domain_primary'] for r in M})
    # the `evaluations` cross-tag is read from papers.json (the tag's home) rather than the
    # taxonomy's frozen evals_tag field, which drifts as papers are re-tagged.
    papers_path = pathlib.Path(__file__).resolve().parent.parent.parent / 'data' / 'papers.json'
    graph = json.load(open(papers_path))
    tags = {p['slug']: p.get('tags', []) for p in graph['papers']}
    T['N_EVALS_TAG'] = cnt(M, lambda r: 'evaluations' in tags.get(r['slug'], []))

    # ---- era pool sizes (finding-01 figcap; reused as denominators everywhere) ----
    T['N_ERA_LE2018'] = len(in_era('≤2018'))
    T['N_ERA_1920'] = len(in_era('2019–20'))
    T['N_ERA_2122'] = len(in_era('2021–22'))
    T['N_2023'] = len(in_era('2023'))
    T['N_2024'] = len(in_era('2024'))
    T['N_2025'] = len(in_era('2025'))
    T['N_2026'] = len(in_era('2026'))

    e18 = in_era('≤2018')
    e2023, e2025, e2026 = in_era('2023'), in_era('2025'), in_era('2026')
    upto2020 = [r for r in M if r['year'] <= 2020]      # ≤2018 + 2019–20 pools

    # ---- prior work: pre-2021 saturation vs corpus-wide ----
    T['N_PRE2021'] = len(upto2020)
    T['PCT_PRE2021'] = share(len(upto2020), N)
    T['N_SAT'] = cnt(M, lambda r: r['saturation'] == 'saturated')
    T['N_SAT_PRE2021'] = cnt(upto2020, lambda r: r['saturation'] == 'saturated')
    T['PCT_SAT_PRE2021'] = share(T['N_SAT_PRE2021'], len(upto2020))
    T['PCT_SAT_CORPUS'] = share(T['N_SAT'], N)
    pre21_long = [r for r in upto2020 if r['complexity'] in L3PLUS]
    T['N_PRE2021_L3PLUS'] = len(pre21_long)
    T['PRE2021_L3PLUS_LIST'] = namelist(pre21_long, years=True)

    # ---- the tree: kingdom membership ----
    king = collections.Counter(r['kingdom'] for r in M)
    T['N_KING_CAP'] = king['A-capability']
    T['PCT_KING_CAP'] = share(king['A-capability'], N)
    T['N_KING_AUDIT'] = king['B-audit']
    T['N_KING_DEPLOY'] = king['D-deployment']
    T['N_KING_HAZARD'] = king['E-hazard']
    T['N_KING_WALLS'] = king['C-frontier-walls']
    T['N_KING_REWARD'] = king['F-reward-factories']
    T['N_KING_META'] = king['G-meta-evaluation']
    T['PCT_CAP_PRE2021'] = share(cnt(upto2020, lambda r: r['kingdom'] == 'A-capability'), len(upto2020))
    e2425 = [r for r in M if r['year'] in (2024, 2025)]
    T['PCT_CAP_2425'] = share(cnt(e2425, lambda r: r['kingdom'] == 'A-capability'), len(e2425))
    T['PCT_CAP_2025'] = share(cnt(e2025, lambda r: r['kingdom'] == 'A-capability'), len(e2025))
    T['N_NONCAP'] = N - king['A-capability']
    T['PCT_NONCAP'] = share(T['N_NONCAP'], N)
    fam = collections.Counter(r['family'] for r in M)
    top_fam, top_fam_n = fam.most_common(1)[0]
    T['FAM_TOP'] = top_fam
    T['N_FAM_TOP'] = top_fam_n
    T['N_FAM_A5'] = fam['A5-embodied-operation']
    min_fam, min_fam_n = fam.most_common()[-1]
    T['FAM_MIN'] = min_fam
    T['N_FAM_MIN'] = min_fam_n
    T['N_FAM_SMALL'] = sum(1 for v in fam.values() if v < 5)

    # ---- finding 01: grading waves ----
    def gr_cnt(rows, g):
        return cnt(rows, lambda r: r['grading_primary'] == g)
    T['N_EM_UPTO2020'] = gr_cnt(upto2020, 'exact-match')
    T['PCT_EM_LE2018'] = share(gr_cnt(e18, 'exact-match'), len(e18))
    T['PCT_EM_2025'] = share(gr_cnt(e2025, 'exact-match'), len(e2025))
    T['N_PROG_2023'] = gr_cnt(e2023, 'programmatic')
    e2122 = in_era('2021–22')
    T['N_PROG_2122'] = gr_cnt(e2122, 'programmatic')
    T['PCT_PROG_2122'] = share(T['N_PROG_2122'], len(e2122))
    T['N_PROG_2025'] = gr_cnt(e2025, 'programmatic')
    T['PCT_PROG_2025'] = share(T['N_PROG_2025'], len(e2025))
    T['N_LLMJ_2024'] = gr_cnt(in_era('2024'), 'llm-judge')
    T['PCT_LLMJ_2024'] = share(T['N_LLMJ_2024'], len(in_era('2024')))
    T['ERA_LLMJ_PEAK'] = peak_era(lambda r: r['grading_primary'] == 'llm-judge')
    # the largest grading family among a year's new benchmarks — a superlative the prose used to
    # hand-assert ("rubric judging became the single largest"), true at 139 papers, false at 369.
    gr2025 = collections.Counter(r['grading_primary'] for r in e2025)
    top_gr, top_gr_n = gr2025.most_common(1)[0]
    T['GR_TOP_2025'] = top_gr
    T['GR_TOP_2025_N'] = top_gr_n
    T['GR_TOP_2025_PCT'] = share(top_gr_n, len(e2025))
    T['N_RUB_2025'] = gr_cnt(e2025, 'rubric-judge')
    T['PCT_RUB_2025'] = share(T['N_RUB_2025'], len(e2025))
    rub_pre25 = [r for r in M if r['grading_primary'] == 'rubric-judge' and r['year'] < 2025]
    T['N_RUB_PRE2025'] = len(rub_pre25)
    T['RUB_PRE2025_LIST'] = namelist(rub_pre25, years=True)
    rub26 = [r for r in e2026 if r['grading_primary'] == 'rubric-judge']
    T['N_RUB_2026'] = len(rub26)
    T['RUB_2026_LIST'] = namelist(rub26)
    T['RUB_2025_EX'] = examples([r for r in e2025 if r['grading_primary'] == 'rubric-judge'], 4)

    # ---- finding 02: verifiability frontier ----
    l1 = [r for r in M if r['complexity'] == 'L1-seconds']
    l3 = [r for r in M if r['complexity'] == 'L3-hours']
    l4 = [r for r in M if r['complexity'] == 'L4-days']
    T['N_L1'] = len(l1)
    T['N_L3'] = len(l3)
    T['N_EM_L1'] = cnt(l1, lambda r: r['grading_primary'] == 'exact-match')
    em_l3 = [r for r in l3 if r['grading_primary'] == 'exact-match']
    T['N_EM_L3'] = len(em_l3)
    T['EM_L3_LIST'] = namelist(em_l3)
    T['N_PROG_L3'] = gr_cnt(l3, 'programmatic')
    T['N_PROG_L4'] = gr_cnt(l4, 'programmatic')
    T['N_HUMAN_L4'] = gr_cnt(l4, 'human')
    T['N_RUB_L4'] = gr_cnt(l4, 'rubric-judge')

    # ---- finding 03: the horizon climb ----
    def l3plus_share(rows):
        return share(cnt(rows, lambda r: r['complexity'] in L3PLUS), len(rows))
    T['PCT_L3_2023'] = l3plus_share(e2023)
    T['PCT_L3_2024'] = l3plus_share(in_era('2024'))
    T['PCT_L3_2025'] = l3plus_share(e2025)
    T['PCT_L3_2026'] = l3plus_share(e2026)
    T['N_L3PLUS_2026'] = cnt(e2026, lambda r: r['complexity'] in L3PLUS)
    T['N_L4'] = len(l4)
    T['L4_LIST'] = namelist(l4)
    l4yrs = sorted({r['year'] for r in l4})
    T['L4_YEARS'] = str(l4yrs[0]) if len(l4yrs) == 1 else f'{l4yrs[0]}–{l4yrs[-1]}'
    T['N_L5'] = cnt(M, lambda r: r['complexity'] == 'L5-weeks')

    def mean_rung(rows):
        return f"{sum(LEVNUM[r['complexity']] for r in rows) / len(rows):.1f}"
    T['MEAN_RUNG_LE2018'] = mean_rung(e18)
    T['MEAN_RUNG_2026'] = mean_rung(e2026)

    # ---- finding 04: task shape ----
    def sh(rows, s):
        return cnt(rows, lambda r: r['task_shape'] == s)
    ie = [r for r in M if r['task_shape'] == 'interactive-env']
    T['N_IE'] = len(ie)
    first_ie = min(ie, key=lambda r: (r['date'], r['short'].lower()))
    T['FIRST_IE_SHORT'], T['FIRST_IE_YEAR'] = first_ie['short'], first_ie['year']
    T['N_IE_1920'] = sh(in_era('2019–20'), 'interactive-env')
    T['PCT_IE_LE2018'] = share(sh(e18, 'interactive-env'), len(e18))
    T['PCT_IE_1920'] = share(T['N_IE_1920'], len(in_era('2019–20')))
    T['PCT_IE_2122'] = share(sh(e2122, 'interactive-env'), len(e2122))
    T['PCT_IE_2023'] = share(sh(e2023, 'interactive-env'), len(e2023))
    T['PCT_IE_2024'] = share(sh(in_era('2024'), 'interactive-env'), len(in_era('2024')))
    T['IE_1920_EX'] = examples([r for r in in_era('2019–20') if r['task_shape'] == 'interactive-env'], 4)
    T['N_IE_2025'] = sh(e2025, 'interactive-env')
    T['PCT_IE_2025'] = share(T['N_IE_2025'], len(e2025))
    T['N_IE_2026'] = sh(e2026, 'interactive-env')
    T['PCT_IE_2026'] = share(T['N_IE_2026'], len(e2026))
    T['PCT_SINGLE_THRU2020'] = share(sh(upto2020, 'single-turn'), len(upto2020))
    T['PCT_SINGLE_2026'] = share(sh(e2026, 'single-turn'), len(e2026))
    T['N_MULTITURN'] = sh(M, 'multi-turn')
    T['PCT_MULTITURN_MAX'] = max(share(sh(in_era(e), 'multi-turn'), len(in_era(e))) for e in ERAS)
    T['ERA_MT_PEAK'] = peak_era(lambda r: r['task_shape'] == 'multi-turn')
    T['N_MT_PRE2021'] = sh(upto2020, 'multi-turn')
    T['MT_PRE2021_EX'] = examples([r for r in upto2020 if r['task_shape'] == 'multi-turn'], 4)
    T['PCT_MT_2024'] = share(sh(in_era('2024'), 'multi-turn'), len(in_era('2024')))
    T['PCT_MT_2025'] = share(sh(e2025, 'multi-turn'), len(e2025))
    T['N_MT_2026'] = sh(e2026, 'multi-turn')

    # ---- finding 05: provenance ----
    T['N_CROWDEXAM_2018'] = cnt(e18, lambda r: r['provenance'] in ('crowdsourced', 'exam-derived'))
    T['PCT_CROWDEXAM_LE2018'] = share(T['N_CROWDEXAM_2018'], len(e18))
    T['PCT_EXPERT_2025'] = share(cnt(e2025, lambda r: r['provenance'] == 'expert-authored'), len(e2025))
    T['PCT_RWM_2025'] = share(cnt(e2025, lambda r: r['provenance'] == 'real-work-mined'), len(e2025))
    T['PCT_CROWD_2025'] = share(cnt(e2025, lambda r: r['provenance'] == 'crowdsourced'), len(e2025))

    # ---- finding 06: contamination defenses ----
    def def_share(rows):
        return share(cnt(rows, lambda r: r['contamination_defense'] != 'none-public'), len(rows))
    privhold18 = [r for r in e18 if r['contamination_defense'] == 'private-holdout']
    T['N_PRIVHOLD_2018'] = len(privhold18)
    T['PCT_PRIVHOLD_LE2018'] = share(len(privhold18), len(e18))
    T['PRIVHOLD_LE2018_EX'] = examples(privhold18, 4)
    nonpub2122 = [r for r in e2122 if r['contamination_defense'] == 'none-public']
    T['N_NONPUB_2122'] = len(nonpub2122)
    T['NONPUB_2122_EX'] = examples(nonpub2122, 4)
    T['N_PRIVHOLD_2025'] = cnt(e2025, lambda r: r['contamination_defense'] == 'private-holdout')
    T['PCT_PRIVHOLD_2025'] = share(T['N_PRIVHOLD_2025'], len(e2025))
    T['N_DEF_2026'] = cnt(e2026, lambda r: r['contamination_defense'] != 'none-public')
    T['PCT_DEF_LE2018'] = def_share(e18)
    T['PCT_DEF_1920'] = def_share(in_era('2019–20'))
    T['PCT_DEF_2122'] = def_share(e2122)
    T['PCT_DEF_2023'] = def_share(e2023)
    T['PCT_DEF_2024'] = def_share(in_era('2024'))
    T['PCT_DEF_2025'] = def_share(e2025)
    T['PCT_DEF_2026'] = def_share(e2026)
    T['PCT_DEF_MAX'] = max(def_share(in_era(e)) for e in ERAS)
    live = [r for r in M if r['contamination_defense'] == 'live-refresh']
    T['N_LIVEREFRESH'] = len(live)
    T['N_SAT_LIVEREFRESH'] = cnt(live, lambda r: r['saturation'] == 'saturated')
    ph = [r for r in M if r['contamination_defense'] == 'private-holdout']
    T['PCT_SAT_PRIVHOLD'] = share(cnt(ph, lambda r: r['saturation'] == 'saturated'), len(ph))

    # ---- finding 07: saturation by horizon ----
    def sat_share(level_pred):
        rows = [r for r in M if level_pred(r['complexity'])]
        return share(cnt(rows, lambda r: r['saturation'] == 'saturated'), len(rows))
    T['PCT_SAT_L1'] = sat_share(lambda c: c == 'L1-seconds')
    T['PCT_SAT_L2'] = sat_share(lambda c: c == 'L2-minutes')
    T['PCT_SAT_L3PLUS'] = sat_share(lambda c: c in L3PLUS)
    sat_long = [r for r in M if r['saturation'] == 'saturated' and r['complexity'] in L3PLUS]
    T['N_SAT_L3PLUS'] = len(sat_long)
    T['SAT_L3PLUS_LIST'] = namelist(sat_long, years=True)
    l2 = [r for r in M if r['complexity'] == 'L2-minutes']
    T['N_L2'] = len(l2)
    T['PCT_CLOSING_L2'] = share(cnt(l2, lambda r: r['saturation'] == 'closing'), len(l2))
    T['PCT_OPEN_L3PLUS'] = share(cnt([r for r in M if r['complexity'] in L3PLUS],
                                     lambda r: r['saturation'] == 'open'),
                                 cnt(M, lambda r: r['complexity'] in L3PLUS))

    # ---- in-corpus citation graph: edge count + gravity wells ----
    # Restricted to the classified corpus (the `merged` taxonomy rows), not the full
    # papers.json graph, so every graph statistic tracks the corpus this page is about —
    # the same subgraph N, the table, and the charts all describe. Deduplicated on
    # (from, to) so a doubled edge in papers.json can't inflate the count.
    corpus_slugs = {r['slug'] for r in M}
    in_corpus_edges = {(e['from'], e['to']) for e in graph['edges']
                       if e['from'] in corpus_slugs and e['to'] in corpus_slugs}
    T['N_EDGES'] = len(in_corpus_edges)
    in_corpus_indeg = collections.Counter(t for _, t in in_corpus_edges)
    T['GRAV_HUMANEVAL'] = in_corpus_indeg['chen-2021-codex']
    T['GRAV_APPS'] = in_corpus_indeg['hendrycks-2021-apps']
    by_slug = {r['slug']: r for r in M}
    # finding 04: do the two generations of interactive environments (pre-2021 deep-RL /
    # robotics vs the LLM-agent era) actually touch, or are they separate inventions?
    ie_old = {r['slug'] for r in M if r['task_shape'] == 'interactive-env' and r['year'] <= 2020}
    ie_new = {r['slug'] for r in M if r['task_shape'] == 'interactive-env' and r['year'] >= 2022}
    T['N_IE_CROSS'] = sum(1 for a, b in in_corpus_edges
                          if (a in ie_new and b in ie_old) or (a in ie_old and b in ie_new))
    ranked = sorted(M, key=lambda r: (-in_corpus_indeg[r['slug']], r['short'].lower()))
    T['GRAV_TOP'] = ranked[0]['short']
    T['GRAV_TOP_N'] = in_corpus_indeg[ranked[0]['slug']]
    T['GRAV_RUNNERUP'] = ranked[1]['short']
    T['GRAV_RUNNERUP_N'] = in_corpus_indeg[ranked[1]['slug']]

    # ---- the taxonomy's typed lineage graph: the audit shadow ----
    # Corrective descent only — a child that audits, de-saturates, or hardens the grader of its
    # parent. (`descends-from` / `responds-to` / `ports-to-new-domain` are extension, not
    # correction, and the difference is finding-bearing: see connection 02.)
    CORRECTIVE = ('audits', 'de-saturates', 'hardens-grader-of')
    lineage = [(r, l) for r in M for l in r.get('lineage', []) if l['parent'] in by_slug]
    T['N_LINEAGE'] = len(lineage)
    corrections = [(by_slug[l['parent']], r, l['relation'])
                   for r, l in lineage if l['relation'] in CORRECTIVE]
    T['N_CORRECTIONS'] = len(corrections)
    # first correction per parent = that benchmark's unaudited lifetime
    firsts = {}
    for p, c, rel in corrections:
        key = p['slug']
        if key not in firsts or (c['year'], c['short']) < (firsts[key][1]['year'], firsts[key][1]['short']):
            firsts[key] = (p, c, rel)
    lags = {s: v[1]['year'] - v[0]['year'] for s, v in firsts.items()}

    def lag_stats(pred, suffix):
        vals = sorted(lag for s, lag in lags.items() if pred(by_slug[s]['year']))
        if not vals:
            T[f'LAG_MED_{suffix}'] = T[f'LAG_MAX_{suffix}'] = 0
            return
        mid = len(vals) // 2
        med = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2
        T[f'LAG_MED_{suffix}'] = f'{med:g}'
        T[f'LAG_MAX_{suffix}'] = vals[-1]
    lag_stats(lambda y: y <= 2018, 'LE2018')
    lag_stats(lambda y: 2019 <= y <= 2020, '1920')
    lag_stats(lambda y: 2021 <= y <= 2022, '2122')
    lag_stats(lambda y: y >= 2023, '2324')
    T['N_AUDITED'] = len(firsts)
    worst = sorted(firsts.values(),
                   key=lambda v: (-(v[1]['year'] - v[0]['year']), -v[0]['gravity'],
                                  v[1]['short'].lower()))[0]
    T['LAG_MAX'] = worst[1]['year'] - worst[0]['year']
    T['LAG_MAX_PAIR'] = f"{worst[0]['short']} → {worst[1]['short']}"
    top20 = ranked[:20]
    T['N_TOP20_AUDITED'] = sum(1 for r in top20 if r['slug'] in firsts)
    T['TOP20_UNAUDITED_EX'] = examples([r for r in top20 if r['slug'] not in firsts], 4)
    # connection 08: SWE-Lancer's descendants (a graph claim the prose used to hand-assert)
    swel = 'miserendino-2025-swe-lancer'
    swel_desc = [r for r, l in lineage if l['parent'] == swel and l['relation'] == 'descends-from']
    T['SWEL_DESC_LIST'] = namelist(swel_desc)
    T['N_SWEL_DESC_CODING'] = sum(1 for r in swel_desc if r['domain_primary'] == 'coding')

    # ---- classification provenance that is live rather than frozen ----
    T['N_CONF_MED'] = cnt(M, lambda r: r['confidence'] == 'medium')

    return T
