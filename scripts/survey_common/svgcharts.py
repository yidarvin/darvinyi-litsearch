"""Dark-theme inline-SVG chart helpers for the benchmark survey page.
All functions return SVG strings (viewBox-scaled, no fixed px width) so they
shrink cleanly on mobile inside a max-width:100% container."""

FG = '#ececee'; DIM = '#c7c7cf'; MUTED = '#82828c'; LINE = '#27272e'
PANEL = '#141417'; ELEV = '#1b1b20'; BG = '#0a0a0b'
MONO = "font-family='JetBrains Mono,monospace'"
SANS = "font-family='Inter,system-ui,sans-serif'"


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def stacked_bars(series_by_x, order, colors, labels, W=860, H=380, pad_l=46, pad_r=10,
                 pad_t=14, pad_b=88, pct=False, x_label='', bar_gap=6, legend_cols=3):
    """series_by_x: {x_key: {cat: count}} ordered dict; order: category draw order."""
    xs = list(series_by_x.keys())
    n = len(xs)
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    bw = plot_w / n - bar_gap
    totals = {x: sum(series_by_x[x].values()) or 1 for x in xs}
    maxy = 1.0 if pct else max(totals.values())
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    # y gridlines
    steps = 4
    for i in range(steps + 1):
        v = maxy * i / steps
        y = pad_t + plot_h * (1 - i / steps)
        lbl = f'{int(round(v * 100))}%' if pct else f'{int(round(v))}'
        out.append(f"<line x1='{pad_l}' y1='{y:.1f}' x2='{W - pad_r}' y2='{y:.1f}' stroke='{LINE}' stroke-width='1'/>")
        out.append(f"<text x='{pad_l - 7}' y='{y + 3.5:.1f}' text-anchor='end' font-size='10.5' fill='{MUTED}' {MONO}>{lbl}</text>")
    # bars
    for i, x in enumerate(xs):
        bx = pad_l + i * (plot_w / n) + bar_gap / 2
        y0 = pad_t + plot_h
        tot = totals[x]
        for cat in order:
            c = series_by_x[x].get(cat, 0)
            if not c:
                continue
            frac = (c / tot) if pct else (c / maxy)
            h = plot_h * frac
            y0 -= h
            out.append(f"<rect x='{bx:.1f}' y='{y0:.1f}' width='{bw:.1f}' height='{max(h - 1, 0.5):.1f}' rx='1.5' fill='{colors[cat]}'><title>{esc(x)} · {esc(labels.get(cat, cat))}: {c}</title></rect>")
        out.append(f"<text x='{bx + bw / 2:.1f}' y='{pad_t + plot_h + 16}' text-anchor='middle' font-size='10.5' fill='{MUTED}' {MONO}>{esc(x)}</text>")
        if not pct:
            out.append(f"<text x='{bx + bw / 2:.1f}' y='{pad_t + plot_h - totals[x] / maxy * plot_h - 5:.1f}' text-anchor='middle' font-size='9.5' fill='{MUTED}' {MONO}>{totals[x]}</text>")
    # legend under axis
    lx, ly = pad_l, pad_t + plot_h + 34
    col_w = (W - pad_l - pad_r) / legend_cols
    for j, cat in enumerate(order):
        cx = lx + (j % legend_cols) * col_w
        cy = ly + (j // legend_cols) * 16
        out.append(f"<rect x='{cx}' y='{cy - 8}' width='9' height='9' rx='2' fill='{colors[cat]}'/>")
        out.append(f"<text x='{cx + 14}' y='{cy}' font-size='10.5' fill='{DIM}' {MONO}>{esc(labels.get(cat, cat))}</text>")
    if x_label:
        out.append(f"<text x='{W / 2}' y='{H - 6}' text-anchor='middle' font-size='10' fill='{MUTED}' {MONO}>{esc(x_label)}</text>")
    out.append('</svg>')
    return ''.join(out)


def heatmap(rows, cols, grid, row_labels, col_labels, accent='#ffd166',
            W=860, H=None, pad_l=118, pad_t=64, cell_h=44, note_cells=None):
    """grid[r][c] = count. Color intensity by count; zero cells drawn hollow."""
    n_r, n_c = len(rows), len(cols)
    H = H or pad_t + n_r * cell_h + 16
    cell_w = (W - pad_l - 14) / n_c
    mx = max((grid[r].get(c, 0) for r in rows for c in cols), default=1) or 1
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    for j, c in enumerate(cols):
        out.append(f"<text x='{pad_l + j * cell_w + cell_w / 2:.1f}' y='{pad_t - 34}' text-anchor='middle' font-size='10.5' fill='{DIM}' {MONO} transform='rotate(0)'>{esc(col_labels.get(c, c))}</text>")
    for i, r in enumerate(rows):
        y = pad_t + i * cell_h
        out.append(f"<text x='{pad_l - 10}' y='{y + cell_h / 2 + 3.5:.1f}' text-anchor='end' font-size='10.5' fill='{DIM}' {MONO}>{esc(row_labels.get(r, r))}</text>")
        for j, c in enumerate(cols):
            v = grid[r].get(c, 0)
            x = pad_l + j * cell_w
            if v:
                alpha = 0.16 + 0.84 * (v / mx) ** 0.7
                out.append(f"<rect x='{x + 2:.1f}' y='{y + 2}' width='{cell_w - 4:.1f}' height='{cell_h - 4}' rx='6' fill='{accent}' fill-opacity='{alpha:.2f}'><title>{esc(row_labels.get(r, r))} × {esc(col_labels.get(c, c))}: {v}</title></rect>")
                tcol = BG if alpha > 0.55 else FG
                out.append(f"<text x='{x + cell_w / 2:.1f}' y='{y + cell_h / 2 + 4}' text-anchor='middle' font-size='12.5' font-weight='600' fill='{tcol}' {MONO}>{v}</text>")
            else:
                out.append(f"<rect x='{x + 2:.1f}' y='{y + 2}' width='{cell_w - 4:.1f}' height='{cell_h - 4}' rx='6' fill='none' stroke='{LINE}' stroke-width='1'/>")
            if note_cells and (r, c) in note_cells:
                out.append(f"<text x='{x + cell_w - 8:.1f}' y='{y + 14}' text-anchor='end' font-size='9' fill='{MUTED}' {MONO}>{esc(note_cells[(r, c)])}</text>")
    out.append('</svg>')
    return ''.join(out)


def line_chart(points, W=860, H=300, pad_l=46, pad_r=14, pad_t=16, pad_b=40,
               color='#ffd166', y_max=None, y_ticks=None, y_fmt=str, dot_labels=None):
    """points: [(x_label, y)] — categorical x axis."""
    n = len(points)
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    ymax = y_max or max(p[1] for p in points) * 1.15
    xstep = plot_w / max(n - 1, 1)
    out = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"]
    ticks = y_ticks or [ymax * i / 4 for i in range(5)]
    for v in ticks:
        y = pad_t + plot_h * (1 - v / ymax)
        out.append(f"<line x1='{pad_l}' y1='{y:.1f}' x2='{W - pad_r}' y2='{y:.1f}' stroke='{LINE}' stroke-width='1'/>")
        out.append(f"<text x='{pad_l - 7}' y='{y + 3.5:.1f}' text-anchor='end' font-size='10.5' fill='{MUTED}' {MONO}>{esc(y_fmt(v))}</text>")
    path = []
    for i, (xl, yv) in enumerate(points):
        x = pad_l + i * xstep
        y = pad_t + plot_h * (1 - yv / ymax)
        path.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")
    out.append(f"<path d='{' '.join(path)}' fill='none' stroke='{color}' stroke-width='2.5' stroke-linejoin='round'/>")
    for i, (xl, yv) in enumerate(points):
        x = pad_l + i * xstep
        y = pad_t + plot_h * (1 - yv / ymax)
        out.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{BG}' stroke='{color}' stroke-width='2'><title>{esc(xl)}: {yv}</title></circle>")
        out.append(f"<text x='{x:.1f}' y='{pad_t + plot_h + 16}' text-anchor='middle' font-size='10.5' fill='{MUTED}' {MONO}>{esc(xl)}</text>")
        if dot_labels:
            out.append(f"<text x='{x:.1f}' y='{y - 10:.1f}' text-anchor='middle' font-size='10' fill='{DIM}' {MONO}>{esc(dot_labels(yv))}</text>")
    out.append('</svg>')
    return ''.join(out)
