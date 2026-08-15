"""Custom inline-SVG charts for the failure-modes survey page. bind() injects the corpus
and vocab so the module-level chart fns can close over them. All return SVG strings.

Mirrors scripts/evaluations_survey/charts_custom.py; the shared primitives
(stacked_bars / heatmap / colours / MONO) come from scripts/survey_common/svgcharts.py
and are not duplicated here.
"""
import collections

M = None
sc = None
V = {}


def bind(corpus, svgcharts, vocab):
    global M, sc, V
    M, sc, V = corpus, svgcharts, vocab


def _wrap(out, s, x, y, fs, col, width, line_h=11, font=None):
    """Greedy character-count wrap — SVG has no text flow."""
    font = font or sc.SANS
    words, line, yy = s.split(' '), '', y
    for w in words:
        if line and len(line) + len(w) + 1 > width:
            out.append(f"<text x='{x}' y='{yy}' font-size='{fs}' fill='{col}' {font}>{sc.esc(line)}</text>")
            line, yy = w, yy + line_h
        else:
            line = (line + ' ' + w).strip()
    if line:
        out.append(f"<text x='{x}' y='{yy}' font-size='{fs}' fill='{col}' {font}>{sc.esc(line)}</text>")
    return yy


# ───────────────────────── the elicitation ladder (the novel axis) ────────────
def elicitation_ladder_svg():
    """Six rungs of 'how much of this failure did the researcher build?', each carrying
    the two derived numbers that make the axis load-bearing: what share of the rung's
    failures are visible from output alone, and how its defense record splits."""
    ELI, ELI_C, ELI_L = V['ELI'], V['ELI_C'], V['ELI_L']
    cnt = collections.Counter(r['elicitation'] for r in M)
    out_alone = {k: sum(1 for r in M if r['elicitation'] == k and r['detectability'] == 'output-alone')
                 for k in ELI}
    fails = {k: sum(1 for r in M if r['elicitation'] == k and r['mitigation_status'] == 'defenses-fail')
             for k in ELI}
    partial = {k: sum(1 for r in M if r['elicitation'] == k and r['mitigation_status'] == 'partial-mitigation')
               for k in ELI}
    BUILT = {
        'spontaneous': ('nothing', 'ran the system normally and the failure was already there'),
        'prompted': ('an input', 'hand-written prompts, templates, adversarial questions'),
        'optimized': ('a search', 'a gradient or an attacker LLM produced the input for you'),
        'constructed-scenario': ('a world', 'a staged situation with stakes, roles and a temptation'),
        'trained-in': ('the model', 'fine-tuning, poisoning, or an RL run installed the failure'),
        'not-elicited': ('no experiment', 'taxonomy, survey, or proof — nothing was run at all'),
    }
    EXAMPLES = {
        'spontaneous': 'Lost in the Middle · FActScore · Vending-Bench',
        'prompted': 'TruthfulQA · Jailbroken · SycEval',
        'optimized': 'GCG · PAIR · TAP · AutoDAN',
        'constructed-scenario': 'Alignment Faking · ToolEmu · Agentic Misalignment',
        'trained-in': 'Sleeper Agents · Reversal Curse · CoT Obfuscation',
        'not-elicited': 'Concrete Problems · Hallucination Survey',
    }
    W = 960
    x0, gap, y0 = 16, 8, 96
    bw = (W - 2 * x0 - gap * (len(ELI) - 1)) / len(ELI)
    bh = 150
    H = y0 + bh + 108
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]

    # brackets: what object was manufactured
    b1w = 3 * (bw + gap) - gap
    out.append(f"<path d='M{x0} 66 v-10 h{b1w:.0f} v10' fill='none' stroke='#4ade80' stroke-width='1.3'/>")
    out.append(f"<text x='{x0 + b1w / 2:.0f}' y='46' text-anchor='middle' font-size='11' fill='#4ade80' {sc.MONO}>the manufactured object is the INPUT, or nothing at all — the failure lands in the output</text>")
    bx = x0 + 3 * (bw + gap)
    b2w = 2 * (bw + gap) - gap
    out.append(f"<path d='M{bx:.0f} 66 v-10 h{b2w:.0f} v10' fill='none' stroke='#f87171' stroke-width='1.3'/>")
    out.append(f"<text x='{bx + b2w / 2:.0f}' y='46' text-anchor='middle' font-size='11' fill='#f87171' {sc.MONO}>the manufactured object is the CONTEXT or the WEIGHTS — the output looks clean</text>")
    bx3 = x0 + 5 * (bw + gap)
    out.append(f"<path d='M{bx3:.0f} 66 v-10 h{bw:.0f} v10' fill='none' stroke='{sc.MUTED}' stroke-width='1.3'/>")
    out.append(f"<text x='{bx3 + bw / 2:.0f}' y='46' text-anchor='middle' font-size='11' fill='{sc.MUTED}' {sc.MONO}>off the ladder</text>")

    for i, k in enumerate(ELI):
        x = x0 + i * (bw + gap)
        col = ELI_C[k]
        n = cnt[k]
        out.append(f"<rect x='{x:.0f}' y='{y0}' width='{bw:.0f}' height='{bh}' rx='9' fill='{col}' fill-opacity='0.13' stroke='{col}' stroke-width='1.5'/>")
        out.append(f"<text x='{x + 11:.0f}' y='{y0 + 26}' font-size='20' font-weight='700' fill='{col}' {sc.MONO}>{n}</text>")
        lbl = ELI_L[k]
        _wrap(out, lbl, x + 48, y0 + 18, 11, col, 17, 12, sc.MONO)
        out.append(f"<text x='{x + 11:.0f}' y='{y0 + 48}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>built: {sc.esc(BUILT[k][0])}</text>")
        yy = _wrap(out, BUILT[k][1], x + 11, y0 + 65, 9.4, sc.DIM, 25, 11)
        _wrap(out, EXAMPLES[k], x + 11, yy + 18, 8.8, sc.MUTED, 26, 10, sc.MONO)
        # derived stat 1: visible from output alone
        pct = round(100 * out_alone[k] / n) if n else 0
        barw = (bw - 22)
        out.append(f"<rect x='{x + 11:.0f}' y='{y0 + bh - 30}' width='{barw:.0f}' height='7' rx='3.5' fill='{sc.LINE}'/>")
        if pct:
            out.append(f"<rect x='{x + 11:.0f}' y='{y0 + bh - 30}' width='{barw * pct / 100:.1f}' height='7' rx='3.5' fill='{col}'/>")
        out.append(f"<text x='{x + 11:.0f}' y='{y0 + bh - 12}' font-size='9' fill='{sc.DIM}' {sc.MONO}>{pct}% visible from output ({out_alone[k]}/{n})</text>")
        # derived stat 2: defense record
        sign = '&gt;' if fails[k] > partial[k] else ('=' if fails[k] == partial[k] else '&lt;')
        dcol = '#f87171' if fails[k] > partial[k] else sc.MUTED
        out.append(f"<text x='{x + 11:.0f}' y='{y0 + bh + 20}' font-size='9.5' fill='{dcol}' {sc.MONO}>defenses fail {fails[k]} {sign} {partial[k]} partial</text>")
        if i < len(ELI) - 1:
            out.append(f"<text x='{x + bw + gap / 2:.0f}' y='{y0 + bh / 2 + 4:.0f}' text-anchor='middle' font-size='13' fill='{sc.MUTED}'>›</text>")

    out.append(f"<line x1='{x0}' y1='{H - 46}' x2='{W - x0}' y2='{H - 46}' stroke='{sc.LINE}' stroke-width='1'/>")
    out.append(f"<text x='{x0}' y='{H - 28}' font-size='10.5' fill='{sc.DIM}' {sc.MONO}>← how much of the failure the researcher had to build, left to right →</text>")
    out.append(f"<text x='{x0}' y='{H - 11}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>an axis about the experiment, not the failure — it cuts across every kingdom of the tree, and it is what bounds each paper's claim</text>")
    out.append('</svg>')
    return ''.join(out)


# ───────────────────────── the visibility inversion ──────────────────────────
def visibility_svg():
    """Per-rung share of failures catchable from output alone, drawn as a curve that
    peaks in the middle and hits zero on both deep rungs."""
    ELI, ELI_C, ELI_L = V['ELI'], V['ELI_C'], V['ELI_L']
    cnt = collections.Counter(r['elicitation'] for r in M)
    vals = []
    for k in ELI:
        n = cnt[k]
        o = sum(1 for r in M if r['elicitation'] == k and r['detectability'] == 'output-alone')
        vals.append((k, o, n, (100 * o / n) if n else 0))
    W, H = 880, 320
    pad_l, pad_r, pad_t, pad_b = 52, 20, 26, 84
    plot_w, plot_h = W - pad_l - pad_r, H - pad_t - pad_b
    n = len(vals)
    step = plot_w / n
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    for i in range(5):
        v = 100 * i / 4
        y = pad_t + plot_h * (1 - i / 4)
        out.append(f"<line x1='{pad_l}' y1='{y:.1f}' x2='{W - pad_r}' y2='{y:.1f}' stroke='{sc.LINE}' stroke-width='1'/>")
        out.append(f"<text x='{pad_l - 8}' y='{y + 3.5:.1f}' text-anchor='end' font-size='10.5' fill='{sc.MUTED}' {sc.MONO}>{int(v)}%</text>")
    pts = []
    for i, (k, o, tot, p) in enumerate(vals):
        cx = pad_l + i * step + step / 2
        y = pad_t + plot_h * (1 - p / 100)
        pts.append((cx, y))
        bw = step * 0.42
        out.append(f"<rect x='{cx - bw / 2:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{pad_t + plot_h - y:.1f}' rx='3' fill='{ELI_C[k]}' fill-opacity='0.55'><title>{sc.esc(ELI_L[k])}: {o} of {tot} detectable from output alone</title></rect>")
        out.append(f"<text x='{cx:.1f}' y='{y - 9:.1f}' text-anchor='middle' font-size='12.5' font-weight='700' fill='{ELI_C[k]}' {sc.MONO}>{round(p)}%</text>")
        out.append(f"<text x='{cx:.1f}' y='{pad_t + plot_h + 17:.1f}' text-anchor='middle' font-size='10' fill='{sc.DIM}' {sc.MONO}>{sc.esc(ELI_L[k])}</text>")
        out.append(f"<text x='{cx:.1f}' y='{pad_t + plot_h + 31:.1f}' text-anchor='middle' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>{o} / {tot}</text>")
    path = ' '.join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    out.append(f"<path d='{path}' fill='none' stroke='{sc.FG}' stroke-width='1.6' stroke-dasharray='4 3' opacity='0.5'/>")
    for x, y in pts:
        out.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3.4' fill='{sc.BG}' stroke='{sc.FG}' stroke-width='1.6'/>")
    out.append(f"<text x='{pad_l}' y='{H - 30}' font-size='10.5' fill='{sc.DIM}' {sc.MONO}>share of each rung's papers whose failure is catchable from the model's output alone</text>")
    out.append(f"<text x='{pad_l}' y='{H - 13}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>visibility peaks where the manufactured object is the input, and falls to zero the moment it is the context or the weights</text>")
    out.append('</svg>')
    return ''.join(out)


# ───────────────────────── the evaluation-awareness waffle ───────────────────
def awareness_svg():
    """One cell per paper, grouped by whether anyone checked that the subject's belief
    about being evaluated moved the result. The five that checked sit last, named."""
    AWR_C, AWR_L = V['AWR_C'], V['AWR_L']
    order = ['n-a', 'not-tested', 'shown-sensitive']
    cells = []
    for a in order:
        for r in sorted([x for x in M if x['eval_awareness'] == a], key=lambda x: (x['year'], x['short'])):
            cells.append((a, r))
    cols = 19
    cell, gap = 38, 6
    per = cell + gap
    rows = (len(cells) + cols - 1) // cols
    W = 960
    x0, y0 = 18, 96
    H = y0 + rows * per + 148
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    # legend
    lx = x0
    for a in order:
        n = sum(1 for c in cells if c[0] == a)
        out.append(f"<rect x='{lx}' y='34' width='13' height='13' rx='3' fill='{AWR_C[a]}'/>")
        out.append(f"<text x='{lx + 20}' y='45' font-size='11' fill='{sc.DIM}' {sc.MONO}>{sc.esc(AWR_L[a])} — {n}</text>")
        lx += 26 + 8.2 * len(AWR_L[a] + f' — {n}')
    out.append(f"<text x='{x0}' y='72' font-size='11' fill='{sc.MUTED}' {sc.MONO}>one square per paper · {len(cells)} squares</text>")
    sens_pos = []
    for i, (a, r) in enumerate(cells):
        cx = x0 + (i % cols) * per
        cy = y0 + (i // cols) * per
        op = '0.55' if a != 'shown-sensitive' else '1'
        out.append(f"<rect x='{cx}' y='{cy}' width='{cell}' height='{cell}' rx='6' fill='{AWR_C[a]}' fill-opacity='{op}' stroke='{AWR_C[a]}' stroke-opacity='0.5'><title>{sc.esc(r['short'])} ({r['year']}) — {sc.esc(AWR_L[a])}</title></rect>")
        if a == 'shown-sensitive':
            sens_pos.append((cx, cy, r))
    # bracket + names under the five that checked
    if sens_pos:
        bx0 = min(p[0] for p in sens_pos)
        bx1 = max(p[0] for p in sens_pos) + cell
        by = max(p[1] for p in sens_pos) + cell
        out.append(f"<path d='M{bx0} {by + 6} v8 h{bx1 - bx0} v-8' fill='none' stroke='#f87171' stroke-width='1.4'/>")
        out.append(f"<text x='{bx1}' y='{by + 34}' text-anchor='end' font-size='11' fill='#f87171' {sc.MONO}>the {len(sens_pos)} papers that measured it</text>")
        ty = by + 52
        for _, _, r in sorted(sens_pos, key=lambda p: p[2]['year']):
            out.append(f"<text x='{bx1}' y='{ty}' text-anchor='end' font-size='10' fill='{sc.DIM}' {sc.MONO}>{sc.esc(r['short'])} ’{str(r['year'])[2:]} — every one found the belief moved the number</text>")
            ty += 14
    out.append(f"<text x='{x0}' y='{H - 14}' font-size='10' fill='{sc.MUTED}' {sc.MONO}>zero papers in this corpus report a null evaluation-awareness result — the vocabulary has no slot for one because nothing filled it</text>")
    out.append('</svg>')
    return ''.join(out)


# ───────────────────────── the tree skeleton ─────────────────────────────────
def tree_skeleton_svg():
    KINGS, KING_C, KING_L = V['KINGS'], V['KING_C'], V['KING_L']
    FAM_L, by_family, FAMS_BY_KING = V['FAM_L'], V['by_family'], V['FAMS_BY_KING']
    fams = [f for k in KINGS for f in FAMS_BY_KING[k] if by_family[f]]
    row_h, top = 22, 16
    W = 900
    H = top + len(fams) * row_h + 20
    kx, fx = 250, 420
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    rooty = top + len(fams) * row_h / 2
    out.append(f"<text x='16' y='{rooty + 4:.0f}' font-size='12.5' font-weight='700' fill='{sc.FG}' {sc.MONO}>{len(M)}</text>")
    out.append(f"<text x='16' y='{rooty + 20:.0f}' font-size='9' fill='{sc.MUTED}' {sc.MONO}>papers</text>")
    y = top
    for k in KINGS:
        kf = [f for f in FAMS_BY_KING[k] if by_family[f]]
        if not kf:
            continue
        n = sum(len(by_family[f]) for f in kf)
        y0, y1 = y, y + len(kf) * row_h
        ky = (y0 + y1) / 2
        col = KING_C[k]
        out.append(f"<path d='M56 {rooty:.0f} C 120 {rooty:.0f} 120 {ky:.0f} {kx - 130} {ky:.0f}' fill='none' stroke='{sc.LINE}' stroke-width='1.4'/>")
        out.append(f"<text x='{kx - 122}' y='{ky + 4:.0f}' font-size='11.5' font-weight='700' fill='{col}' {sc.MONO}>{sc.esc(KING_L[k][0])}</text>")
        out.append(f"<text x='{kx - 4}' y='{ky + 4:.0f}' font-size='10' fill='{sc.MUTED}' {sc.MONO}>{n}</text>")
        for f in kf:
            fy = y + row_h / 2
            out.append(f"<path d='M{kx + 16} {ky:.0f} C {kx + 66} {ky:.0f} {kx + 66} {fy:.0f} {fx - 12} {fy:.0f}' fill='none' stroke='{sc.LINE}' stroke-width='1'/>")
            c = len(by_family[f])
            out.append(f"<text x='{fx}' y='{fy + 3.5:.0f}' font-size='10.5' fill='{sc.DIM}' {sc.MONO}>{sc.esc(FAM_L[f][0])}</text>")
            out.append(f"<rect x='{fx + 268}' y='{fy - 5:.0f}' width='{c * 14:.0f}' height='10' rx='2.5' fill='{col}' fill-opacity='0.55'/>")
            out.append(f"<text x='{fx + 276 + c * 14:.0f}' y='{fy + 3.5:.0f}' font-size='9.5' fill='{sc.MUTED}' {sc.MONO}>{c}</text>")
            y += row_h
    out.append('</svg>')
    return ''.join(out)
