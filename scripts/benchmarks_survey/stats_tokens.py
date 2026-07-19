"""Compute every corpus-statistic token the benchmarks-survey prose cites, straight from the
classified taxonomy, so no number on the page is ever hand-typed. compute(merged, era, ERAS)
-> {TOKEN: value}. Mirrors the evaluations_survey/stats_tokens.py pattern.

Scope: only *live corpus* statistics (paper counts, era pool sizes, membership counts,
percentages, span) are tokenised here. Deliberately NOT tokenised (see build_survey_page.py /
survey_template.html): (a) taxonomy *vocabulary* sizes fixed by the schema and immune to corpus
growth — 8 facets, 6 grading families, 5 horizon buckets, 7 kingdoms, 25 families, 9 connections;
(b) analysis-provenance numbers frozen at the pre-growth 126-paper snapshot the connections and
tree placements were mined from (the 598-edge/126-node graph, the two-pass agreement stats) —
these are not recomputable from `merged`; (c) numbers quoted from individual papers (e.g.
MT-Bench's 85% judge/human agreement). The connection-08 HumanEval/APPS in-corpus gravity-well
citation counts (GRAV_HUMANEVAL / GRAV_APPS) ARE live and recomputed here each build from
data/papers.json's edge list, restricted to the 139-paper tagged-benchmarks subgraph."""
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

    # ---- corpus-wide ----
    T['N'] = N
    yrs = [r['year'] for r in M]
    T['SPAN'] = f'{min(yrs)}–{max(yrs)}'
    T['N_EVALS_TAG'] = cnt(M, lambda r: r['evals_tag'])

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
    T['N_SAT_PRE2021'] = cnt(upto2020, lambda r: r['saturation'] == 'saturated')
    T['PCT_SAT_PRE2021'] = share(T['N_SAT_PRE2021'], len(upto2020))
    T['PCT_SAT_CORPUS'] = share(cnt(M, lambda r: r['saturation'] == 'saturated'), N)

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

    # ---- finding 01: grading waves ----
    T['N_EM_UPTO2020'] = cnt(upto2020, lambda r: r['grading_primary'] == 'exact-match')
    T['N_PROG_2023'] = cnt(e2023, lambda r: r['grading_primary'] == 'programmatic')
    T['N_RUB_2025'] = cnt(e2025, lambda r: r['grading_primary'] == 'rubric-judge')
    T['PCT_RUB_2025'] = share(T['N_RUB_2025'], len(e2025))
    T['N_RUB_PRE2025'] = cnt(M, lambda r: r['grading_primary'] == 'rubric-judge' and r['year'] < 2025)

    # ---- finding 02: verifiability frontier ----
    l1 = [r for r in M if r['complexity'] == 'L1-seconds']
    l3 = [r for r in M if r['complexity'] == 'L3-hours']
    T['N_L1'] = len(l1)
    T['N_EM_L1'] = cnt(l1, lambda r: r['grading_primary'] == 'exact-match')
    T['N_EM_L3'] = cnt(l3, lambda r: r['grading_primary'] == 'exact-match')

    # ---- finding 03: the horizon climb ----
    def l3plus_share(rows):
        return share(cnt(rows, lambda r: r['complexity'] in L3PLUS), len(rows))
    T['PCT_L3_2023'] = l3plus_share(e2023)
    T['PCT_L3_2024'] = l3plus_share(in_era('2024'))
    T['PCT_L3_2025'] = l3plus_share(e2025)
    T['N_L3PLUS_2026'] = cnt(e2026, lambda r: r['complexity'] in L3PLUS)
    T['N_L4'] = cnt(M, lambda r: r['complexity'] == 'L4-days')

    def mean_rung(rows):
        return f"{sum(LEVNUM[r['complexity']] for r in rows) / len(rows):.1f}"
    T['MEAN_RUNG_LE2018'] = mean_rung(e18)
    T['MEAN_RUNG_2026'] = mean_rung(e2026)

    # ---- finding 04: task shape ----
    T['N_IE_2025'] = cnt(e2025, lambda r: r['task_shape'] == 'interactive-env')
    T['PCT_IE_2025'] = share(T['N_IE_2025'], len(e2025))
    T['N_IE_2026'] = cnt(e2026, lambda r: r['task_shape'] == 'interactive-env')
    T['PCT_SINGLE_THRU2020'] = share(cnt(upto2020, lambda r: r['task_shape'] == 'single-turn'), len(upto2020))
    T['N_MULTITURN'] = cnt(M, lambda r: r['task_shape'] == 'multi-turn')
    T['PCT_MULTITURN_MAX'] = max(share(cnt(in_era(e), lambda r: r['task_shape'] == 'multi-turn'), len(in_era(e)))
                                 for e in ERAS)

    # ---- finding 05: provenance ----
    T['N_CROWDEXAM_2018'] = cnt(e18, lambda r: r['provenance'] in ('crowdsourced', 'exam-derived'))
    T['PCT_EXPERT_2025'] = share(cnt(e2025, lambda r: r['provenance'] == 'expert-authored'), len(e2025))
    T['PCT_RWM_2025'] = share(cnt(e2025, lambda r: r['provenance'] == 'real-work-mined'), len(e2025))

    # ---- finding 06: contamination defenses ----
    T['N_PRIVHOLD_2018'] = cnt(e18, lambda r: r['contamination_defense'] == 'private-holdout')
    T['N_NONPUB_2122'] = cnt(in_era('2021–22'), lambda r: r['contamination_defense'] == 'none-public')
    T['N_PRIVHOLD_2025'] = cnt(e2025, lambda r: r['contamination_defense'] == 'private-holdout')
    T['N_DEF_2026'] = cnt(e2026, lambda r: r['contamination_defense'] != 'none-public')
    T['N_LIVEREFRESH'] = cnt(M, lambda r: r['contamination_defense'] == 'live-refresh')

    # ---- finding 07: saturation by horizon ----
    def sat_share(level_pred):
        rows = [r for r in M if level_pred(r['complexity'])]
        return share(cnt(rows, lambda r: r['saturation'] == 'saturated'), len(rows))
    T['PCT_SAT_L1'] = sat_share(lambda c: c == 'L1-seconds')
    T['PCT_SAT_L2'] = sat_share(lambda c: c == 'L2-minutes')
    T['PCT_SAT_L3PLUS'] = sat_share(lambda c: c in L3PLUS)

    # ---- connection-08: in-corpus citation gravity (HumanEval vs APPS) ----
    # Both endpoints must be in the tagged-benchmarks subgraph (the `merged` taxonomy rows),
    # not the full papers.json graph, so this tracks the corpus this page is actually about.
    tagged_slugs = {r['slug'] for r in M}
    papers_path = pathlib.Path(__file__).resolve().parent.parent.parent / 'data' / 'papers.json'
    graph = json.load(open(papers_path))
    in_corpus_indeg = collections.Counter(
        e['to'] for e in graph['edges'] if e['from'] in tagged_slugs and e['to'] in tagged_slugs)
    T['GRAV_HUMANEVAL'] = in_corpus_indeg['chen-2021-codex']
    T['GRAV_APPS'] = in_corpus_indeg['hendrycks-2021-apps']

    return T
