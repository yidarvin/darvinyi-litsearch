/* ---- timeline layout ------------------------------------------------------
   A time-ordered replacement for the old `cose` force layout. Papers flow
   left→right by publication date; because a paper can only cite *older* work,
   every edge then points leftward, which both organizes the map by time and
   un-tangles the force-directed hairball.

   How positions are computed:
     • x — papers are binned into period bands (quarters by default, halves as a
           one-line switch). Only NON-EMPTY bands get a column, and columns are
           spaced evenly (ordinal), not linearly in time: the data is bimodal
           (a sparse 2019–2024 tail vs. a dense 2025–26 head), so linear spacing
           would crush exactly the region that needs room. Labels still show the
           real period, so time stays legible.
     • y — within each column, nodes are ordered to minimize edge crossings with
           the classic barycenter heuristic (generalized to multi-band edges),
           then packed by their own diameter so large nodes don't overlap.

   Pure module: no DOM, no cytoscape. `sizeOf(p)` is injected so the size scale
   stays owned by main.js.
--------------------------------------------------------------------------- */

// fractional year, e.g. "2023-10" -> 2023.75 ; falls back to mid-year on `year`
export function timeOf(p) {
  const m = /^(\d{4})-(\d{2})$/.exec(p && p.date ? p.date : '');
  if (m) return Number(m[1]) + (Number(m[2]) - 1) / 12;
  return (p && Number.isFinite(p.year)) ? p.year + 0.5 : 0;
}

// band key + label for a paper, at quarter or half granularity
function bandOf(p, gran) {
  const m = /^(\d{4})-(\d{2})$/.exec(p && p.date ? p.date : '');
  const year = m ? Number(m[1]) : (Number.isFinite(p && p.year) ? p.year : 0);
  const month = m ? Number(m[2]) : 7; // mid-year when only a year is known
  if (gran === 'half') {
    const h = Math.min(1, Math.floor((month - 1) / 6));
    return { key: year * 2 + h, year, sub: `H${h + 1}`, label: `${year} H${h + 1}` };
  }
  const q = Math.min(3, Math.floor((month - 1) / 3));
  return { key: year * 4 + q, year, sub: `Q${q + 1}`, label: `${year} Q${q + 1}` };
}

/* compute {x,y} for every paper plus the band metadata the axis overlay draws.
   opts: { sizeOf(p)->px, band:'quarter'|'half', colGap, vGap, sweeps, centerSet }
   centerSet (optional Set<slug>): the "survey spine" view — those papers are
   packed at the vertical centre of every column and the rest fan out above and
   below, so the tagged subset reads as a bright horizontal spine through the map
   while the left→right time order is preserved. */
export function computeTimeline(papers, edges, opts = {}) {
  const sizeOf = opts.sizeOf || (() => 28);
  const gran   = opts.band   || 'quarter';
  const colGap = opts.colGap || 240;
  const vGap   = opts.vGap   || 26;
  const sweeps = opts.sweeps || 12;

  if (!papers.length) return { positions: new Map(), bands: [] };

  // undirected adjacency (crossing-minimization ignores edge direction)
  const present = new Set(papers.map(p => p.slug));
  const nbrs = new Map(papers.map(p => [p.slug, []]));
  edges.forEach(e => {
    if (present.has(e.from) && present.has(e.to)) {
      nbrs.get(e.from).push(e.to);
      nbrs.get(e.to).push(e.from);
    }
  });

  // bucket papers into non-empty bands, ordered chronologically
  const bandMap = new Map();
  papers.forEach(p => {
    const b = bandOf(p, gran);
    if (!bandMap.has(b.key)) bandMap.set(b.key, { ...b, items: [] });
    bandMap.get(b.key).items.push(p);
  });
  const cols = [...bandMap.values()].sort((a, b) => a.key - b.key);

  // seed each column's vertical order by size (big hubs first) for stable sweeps
  cols.forEach((c, i) => {
    c.x = i * colGap;
    c.order = c.items.slice().sort((a, b) => sizeOf(b) - sizeOf(a) || a.slug.localeCompare(b.slug));
  });

  const pos = new Map();
  // size-aware vertical packing: stack a column's ordered nodes, centered on y=0
  const packColumn = (c) => {
    let total = -vGap;
    c.order.forEach(p => { total += sizeOf(p) + vGap; });
    let cursor = -total / 2;
    c.order.forEach(p => {
      const r = sizeOf(p) / 2;
      cursor += r;
      pos.set(p.slug, { x: c.x, y: cursor });
      cursor += r + vGap;
    });
  };
  cols.forEach(packColumn);

  // barycenter sweeps: re-order each column by the mean y of each node's
  // neighbors, then re-pack. Nodes with no neighbors keep their place.
  for (let s = 0; s < sweeps; s++) {
    cols.forEach(c => {
      const bc = new Map();
      c.order.forEach(p => {
        const ns = nbrs.get(p.slug);
        if (!ns.length) { bc.set(p.slug, pos.get(p.slug).y); return; }
        let sum = 0;
        ns.forEach(id => { sum += pos.get(id).y; });
        bc.set(p.slug, sum / ns.length);
      });
      c.order = c.order
        .map((p, i) => [p, bc.get(p.slug), i])
        .sort((a, b) => (a[1] - b[1]) || (a[2] - b[2]))
        .map(t => t[0]);
    });
    cols.forEach(packColumn);
  }

  // survey "spine": re-pack so a tagged subset sits at each column's vertical
  // centre (centred on y=0), with the rest split evenly above and below. The
  // crossing-minimized order from the sweeps is preserved within each group.
  const centerSet = opts.centerSet;
  if (centerSet && centerSet.size) {
    cols.forEach(c => {
      const tagged = c.order.filter(p => centerSet.has(p.slug));
      if (!tagged.length) { packColumn(c); return; }   // no spine node here → normal stack
      const rest = c.order.filter(p => !centerSet.has(p.slug));
      // tagged block, centred on 0
      let h = -vGap; tagged.forEach(p => { h += sizeOf(p) + vGap; });
      let cursor = -h / 2;
      const topEdge = cursor;
      tagged.forEach(p => { const r = sizeOf(p) / 2; cursor += r; pos.set(p.slug, { x: c.x, y: cursor }); cursor += r + vGap; });
      const botEdge = cursor - vGap;
      // fan the rest out: first half upward from the band's top, second half downward
      const half = Math.ceil(rest.length / 2);
      const above = rest.slice(0, half), below = rest.slice(half);
      let up = topEdge - vGap;
      for (let k = above.length - 1; k >= 0; k--) { const p = above[k], r = sizeOf(p) / 2; up -= r; pos.set(p.slug, { x: c.x, y: up }); up -= r + vGap; }
      let dn = botEdge + vGap;
      for (let k = 0; k < below.length; k++) { const p = below[k], r = sizeOf(p) / 2; dn += r; pos.set(p.slug, { x: c.x, y: dn }); dn += r + vGap; }
    });
  }

  const bands = cols.map(c => ({ key: c.key, label: c.label, year: c.year, sub: c.sub, x: c.x }));
  return { positions: pos, bands };
}
