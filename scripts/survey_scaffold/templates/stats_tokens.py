"""Compute every numeric token the survey prose cites, straight from the classified
corpus, so no number in the page is ever hand-typed. compute(M, era, ERAS) -> {TOKEN: value}.

Scaffolded by scripts/survey_scaffold/new_survey.py — see
scripts/evaluations_survey/stats_tokens.py for a fuller worked example (reward-readiness
class counts, per-era breakdowns, meta-eval shares, etc.)."""
import collections


def compute(M, era, ERAS):
    N = len(M)
    T = {}

    def pct(x):
        return round(100 * x / N) if N else 0

    # TODO(survey-author): compute every number your prose cites here, keyed by the
    # @@TOKEN@@ name used in survey_template.html. Example (delete once you have real
    # facets — see scripts/evaluations_survey/stats_tokens.py for the full pattern,
    # including per-era counts and cross-tab-derived tokens):
    c_example = collections.Counter(r.get('example_facet', 'value-a') for r in M)
    T['N_EXAMPLE_A'] = c_example['value-a']
    T['PCT_EXAMPLE_A'] = pct(T['N_EXAMPLE_A'])

    return T
