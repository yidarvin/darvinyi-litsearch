"""Custom inline-SVG charts for the evaluations survey page. bind() injects the corpus
and vocab so the module-level chart fns can close over them. All return SVG strings."""
import collections, html

M = None; sc = None; V = {}

def bind(corpus, svgcharts, vocab):
    global M, sc, V
    M, sc, V = corpus, svgcharts, vocab

def _n(engine):
    return sum(1 for r in M if r['verdict_engine'] == engine)

# -------- the verdict-engine ladder (cost per verdict rises, generality rises) --------
def engine_ladder_svg():
    ENG, ENG_C, ENG_L = V['ENG'], V['ENG_C'], V['ENG_L']
    rows = [
        ('lexical-overlap', 'n-gram / LCS vs references', '≈ free', 'BLEU, ROUGE — no longer trusted'),
        ('learned-metric', 'trained neural scalar', '≈ free at run', 'BLEURT: learn the metric'),
        ('execution-oracle', 'tests · checkers · env state', 'build a harness once', 'HumanEval, SWE-bench'),
        ('human-grading', 'expert / crowd verdict', 'human-hours per item', 'GDPval: >1 h per grade'),
        ('model-judge', 'holistic model opinion', 'one model call', 'MT-Bench: 85% human agree'),
        ('decomposed-judge', 'per-item rubric / atomic facts', 'experts author criteria', 'PaperBench: 8,316 leaves'),
        ('process-monitor', 'read the subject’s reasoning', 'one monitor call', 'breaks under optimization'),
        ('statistical-protocol', 'estimator / design / aggregation', 'design, not grade', 'pass@k, Elo, time-horizon'),
    ]
    W = 880
    bw, gap, x0, y0, bh = 100, 5, 20, 92, 118
    per = bw + gap
    H = y0 + bh + 84
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    # verifiable / mechanical bracket over first three
    out.append(f"<path d='M{x0} 60 v-10 h{3*per-gap} v10' fill='none' stroke='#4ade80' stroke-width='1.3'/>")
    out.append(f"<text x='{x0 + (3*per-gap)/2}' y='40' text-anchor='middle' font-size='10.5' fill='#4ade80' {sc.MONO}>mechanically checkable → reusable as an RL reward</text>")
    bx = x0 + 4*per
    out.append(f"<path d='M{bx} 60 v-10 h{3*per-gap} v10' fill='none' stroke='#f472b6' stroke-width='1.3'/>")
    out.append(f"<text x='{bx + (3*per-gap)/2}' y='40' text-anchor='middle' font-size='10.5' fill='#f472b6' {sc.MONO}>model-graded → who grades the grader?</text>")
    for i, (k, sub, cost, note) in enumerate(rows):
        x = x0 + i * per
        col = ENG_C[k]
        out.append(f"<rect x='{x}' y='{y0}' width='{bw}' height='{bh}' rx='8' fill='{col}' fill-opacity='0.13' stroke='{col}' stroke-width='1.4'/>")
        # wrap label into two lines
        lbl = ENG_L[k]
        parts = lbl.split(' ')
        if len(parts) > 1:
            l1, l2 = parts[0], ' '.join(parts[1:])
        else:
            l1, l2 = lbl, ''
        out.append(f"<text x='{x + 9}' y='{y0 + 19}' font-size='11' font-weight='700' fill='{col}' {sc.MONO}>{l1}</text>")
        if l2:
            out.append(f"<text x='{x + 9}' y='{y0 + 32}' font-size='11' font-weight='700' fill='{col}' {sc.MONO}>{l2}</text>")
        out.append(f"<text x='{x + 9}' y='{y0 + 52}' font-size='8.6' fill='{sc.DIM}' {sc.SANS}>{sc.esc(sub)}</text>" if len(sub) < 30 else _wrap(out, sub, x+9, y0+52, 8.6, sc.DIM, 14, sc))
        out.append(f"<text x='{x + 9}' y='{y0 + bh - 26}' font-size='8.6' fill='{sc.MUTED}' {sc.SANS}>{sc.esc(cost)}</text>")
        out.append(f"<text x='{x + bw/2}' y='{y0 + bh + (18 if i % 2 == 0 else 34)}' text-anchor='middle' font-size='8.4' fill='{sc.MUTED}' {sc.SANS}>{sc.esc(note)}</text>")
        out.append(f"<text x='{x + bw - 9}' y='{y0 + 19}' text-anchor='end' font-size='10.5' fill='{sc.MUTED}' {sc.MONO}>{_n(k)}</text>")
        if i < len(rows) - 1:
            out.append(f"<text x='{x + bw + gap/2}' y='{y0 + bh/2}' text-anchor='middle' font-size='12' fill='{sc.MUTED}'>›</text>")
    out.append(f"<line x1='{x0}' y1='{H - 26}' x2='{W - 20}' y2='{H - 26}' stroke='{sc.LINE}' stroke-width='1'/>")
    out.append(f"<text x='{x0}' y='{H - 9}' font-size='10' fill='{sc.MUTED}' {sc.MONO}>cost to produce one verdict, and generality, rise left → right   ·   n = papers whose headline engine is this</text>")
    out.append('</svg>')
    return ''.join(out)

def _wrap(out, s, x, y, fs, col, width, sc):
    words = s.split(' '); line = ''; yy = y
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(f"<text x='{x}' y='{yy}' font-size='{fs}' fill='{col}' {sc.SANS}>{sc.esc(line)}</text>")
            line = w; yy += 11
        else:
            line = (line + ' ' + w).strip()
    if line:
        out.append(f"<text x='{x}' y='{yy}' font-size='{fs}' fill='{col}' {sc.SANS}>{sc.esc(line)}</text>")
    return ''

# -------- the reward-readiness ladder (the novel axis) --------
def reward_ladder_svg():
    RWD, RWD_C, RWD_L = V['RWD'], V['RWD_C'], V['RWD_L']
    cnt = collections.Counter(r['reward_readiness'] for r in M)
    rows = [
        ('reward-native', 'already a standard training signal', 'execution tests → RLVR; preference votes → RLHF',
         'Goodhart risk is priced in from day one'),
        ('reward-adapted', 'wired in as a reward, with a documented cost', 'LLM judge → RLAIF; rubric → RaR',
         'reward hacking measured, not hypothetical'),
        ('diagnostic-only', 'too slow / situated to be a gradient', 'expert panels, arenas, holistic frameworks',
         'reads the model; never trains it'),
        ('optimization-forbidden', 'validity DEPENDS on not training against it', 'CoT monitors, private twins, propensity traps',
         'optimize it and you destroy the instrument'),
    ]
    W, H = 880, 250
    bw, gap, x0, y0, bh = 208, 10, 20, 30, 96
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    for i, (k, sub, ex, note) in enumerate(rows):
        x = x0 + i * (bw + gap)
        col = RWD_C[k]
        out.append(f"<rect x='{x}' y='{y0}' width='{bw}' height='{bh}' rx='9' fill='{col}' fill-opacity='0.14' stroke='{col}' stroke-width='1.5'/>")
        out.append(f"<text x='{x + 40}' y='{y0 + 23}' font-size='11.5' font-weight='700' fill='{col}' {sc.MONO}>{RWD_L[k]}</text>")
        out.append(f"<text x='{x + 24}' y='{y0 + 26}' text-anchor='middle' font-size='19' font-weight='700' fill='{col}' {sc.MONO}>{cnt.get(k,0)}</text>")
        _wrap(out, sub, x + 12, y0 + 44, 10.5, sc.DIM, 34, sc)
        _wrap(out, ex, x + 12, y0 + 72, 9.5, sc.MUTED, 40, sc)
        out.append(f"<text x='{x + bw/2}' y='{y0 + bh + 22}' text-anchor='middle' font-size='9.5' fill='{sc.MUTED}' {sc.SANS} font-style='italic'>{sc.esc(note)}</text>")
        if i < len(rows) - 1:
            out.append(f"<text x='{x + bw + gap/2}' y='{y0 + bh/2 + 4}' text-anchor='middle' font-size='14' fill='{sc.MUTED}'>→</text>")
    out.append(f"<line x1='{x0}' y1='{H - 40}' x2='{W - 20}' y2='{H - 40}' stroke='{sc.LINE}' stroke-width='1'/>")
    out.append(f"<text x='{x0}' y='{H - 22}' font-size='10.5' fill='{sc.DIM}' {sc.MONO}>← distance from the training loop grows →</text>")
    out.append(f"<text x='{x0}' y='{H - 7}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>the left two are optimization targets; the right two are protected instruments — an axis no prior eval survey names</text>")
    out.append('</svg>')
    return ''.join(out)

# -------- tree skeleton --------
def tree_skeleton_svg():
    KINGS, KING_C, KING_L, FAM_L, by_family = V['KINGS'], V['KING_C'], V['KING_L'], V['FAM_L'], V['by_family']
    FAMS_BY_KING = V['FAMS_BY_KING']
    fams = [f for k in KINGS for f in FAMS_BY_KING[k] if by_family[f]]
    row_h, top = 25, 16
    H = top + len(fams) * row_h + 18
    W = 880
    kx, fx = 250, 430
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    rooty = top + len(fams) * row_h / 2
    out.append(f"<text x='16' y='{rooty + 4:.0f}' font-size='12.5' font-weight='700' fill='{sc.FG}' {sc.MONO}>{len(M)}</text>")
    out.append(f"<text x='16' y='{rooty + 20:.0f}' font-size='9' fill='{sc.MUTED}' {sc.MONO}>methods</text>")
    y = top
    for k in KINGS:
        kf = [f for f in FAMS_BY_KING[k] if by_family[f]]
        if not kf:
            continue
        n = sum(len(by_family[f]) for f in kf)
        y0, y1 = y, y + len(kf) * row_h
        ky = (y0 + y1) / 2
        col = KING_C[k]
        out.append(f"<path d='M56 {rooty:.0f} C 120 {rooty:.0f} 120 {ky:.0f} {kx - 120} {ky:.0f}' fill='none' stroke='{sc.LINE}' stroke-width='1.4'/>")
        out.append(f"<text x='{kx - 112}' y='{ky + 4:.0f}' font-size='11.5' font-weight='700' fill='{col}' {sc.MONO}>{KING_L[k][0]}</text>")
        out.append(f"<text x='{kx - 4}' y='{ky + 4:.0f}' font-size='10' fill='{sc.MUTED}' {sc.MONO}>{n}</text>")
        for f in kf:
            fy = y + row_h / 2
            out.append(f"<path d='M{kx + 20} {ky:.0f} C {kx + 70} {ky:.0f} {kx + 70} {fy:.0f} {fx - 12} {fy:.0f}' fill='none' stroke='{sc.LINE}' stroke-width='1'/>")
            cnt = len(by_family[f])
            out.append(f"<text x='{fx}' y='{fy + 3.5:.0f}' font-size='10.5' fill='{sc.DIM}' {sc.MONO}>{FAM_L[f][0]}</text>")
            out.append(f"<rect x='{fx + 250}' y='{fy - 5:.0f}' width='{cnt * 12:.0f}' height='10' rx='2.5' fill='{col}' fill-opacity='0.55'/>")
            out.append(f"<text x='{fx + 256 + cnt * 12:.0f}' y='{fy + 3.5:.0f}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>{cnt}</text>")
            y += row_h
    out.append('</svg>')
    return ''.join(out)

# -------- absorption-cycle timeline: engine proven → engine as reward → hack documented --------
def absorption_svg():
    # verified from digests; each row = a verdict engine and the papers marking the three stages
    ROWS = [
        ('lexical overlap', 'BLEU ’02', 2002, 'built to “iterate against”', 2002, 'ROUGE Goodharted', 2004),
        ('execution oracle', 'HumanEval ’21', 2021, 'RLVR / verifier’s law', 2024, 'SWE public→private −25pt', 2025),
        ('repeated sampling', 'pass@k ’24', 2024, 'reasoning-RL target', 2024, '(coverage≠selection)', 2024),
        ('human preference', 'AlpacaFarm ’23', 2023, 'RLAIF reward models', 2023, 'over-optimization sim', 2023),
        ('model judge', 'MT-Bench ’23', 2023, 'judge-as-reward', 2024, 'self-preference / bias', 2024),
        ('rubric judge', 'PaperBench ’25', 2025, 'rubrics-as-rewards', 2025, 'rubric reward hacking ’26', 2026),
    ]
    W = 960
    row_h, top, pad_l, pad_r = 30, 44, 150, 30
    H = top + len(ROWS) * row_h + 42
    y0, y1 = 2001.5, 2026.5
    def X(yr):
        return pad_l + (yr - y0) / (y1 - y0) * (W - pad_l - pad_r)
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    for yr in range(2002, 2027, 3):
        x = X(yr)
        out.append(f"<line x1='{x:.0f}' y1='{top - 12}' x2='{x:.0f}' y2='{H - 30}' stroke='{sc.LINE}' stroke-width='1'/>")
        out.append(f"<text x='{x:.0f}' y='{top - 18}' text-anchor='middle' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>{yr}</text>")
    # stage legend
    for lbl, cx, col in [('① engine proven', pad_l, '#4ade80'), ('② becomes a reward', pad_l + 190, '#c084fc'), ('③ hack documented', pad_l + 400, '#f87171')]:
        out.append(f"<circle cx='{cx}' cy='{top - 30}' r='4' fill='{col}'/>")
        out.append(f"<text x='{cx + 10}' y='{top - 26}' font-size='9.5' fill='{sc.DIM}' {sc.MONO}>{lbl}</text>")
    for i, (fam, p1, y_1, p2, y_2, p3, y_3) in enumerate(ROWS):
        y = top + i * row_h + row_h / 2
        out.append(f"<text x='{pad_l - 12}' y='{y + 3.5:.0f}' text-anchor='end' font-size='10' fill='{sc.DIM}' {sc.MONO}>{fam}</text>")
        xs = [(X(y_1), '#4ade80', p1), (X(y_2), '#c084fc', p2), (X(y_3), '#f87171', p3)]
        x_start = min(x for x, _, _ in xs)
        x_end = max(x for x, _, _ in xs)
        out.append(f"<line x1='{x_start:.0f}' y1='{y:.0f}' x2='{x_end:.0f}' y2='{y:.0f}' stroke='{sc.LINE}' stroke-width='1.3'/>")
        # place labels alternating above/below to avoid overlap
        for j, (x, col, lab) in enumerate(xs):
            out.append(f"<circle cx='{x:.0f}' cy='{y:.0f}' r='4' fill='{col}'/>")
            dy = -8 if j != 1 else 15
            anchor = 'start' if j == 0 else ('end' if j == 2 else 'middle')
            out.append(f"<text x='{x:.0f}' y='{y + dy:.0f}' text-anchor='{anchor}' font-size='8.6' fill='{sc.MUTED}' {sc.MONO}>{sc.esc(lab)}</text>")
    out.append(f"<text x='{pad_l}' y='{H - 10}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>every verdict engine that proved cheap enough was absorbed as a training reward — and each absorption grew its own reward-hacking literature</text>")
    out.append('</svg>')
    return ''.join(out)
