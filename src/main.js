import cytoscape from 'cytoscape';
import data from '../data/papers.json';
import { computeTimeline } from './timeline.js';
import './style.css';

/* ---- data ----------------------------------------------------------------
   Built at build time from data/papers.json (see CLAUDE.md for the shape):
     node id      = slug
     label        = short
     size         = sqrt(citation_count)
     color dims   = topic / author_group / venue
     edges        = data.edges  ({from,to}  ->  cytoscape {source,target})
--------------------------------------------------------------------------- */
const PAPERS = Array.isArray(data.papers) ? data.papers : [];
const EDGES  = Array.isArray(data.edges)  ? data.edges  : [];
const byId   = new Map(PAPERS.map(p => [p.slug, p]));

// outgoing citations per node: slug -> [cited slug, …]
const citesOf = new Map(PAPERS.map(p => [p.slug, []]));
EDGES.forEach(e => {
  if (byId.has(e.from) && byId.has(e.to)) citesOf.get(e.from).push(e.to);
});

/* ---- color dimensions ----------------------------------------------------
   Colors are assigned from a fixed palette in the order values first appear
   in the data, so the legend stays correct as the graph grows. The three
   switchable dimensions map onto these paper fields:                        */
const DIM_FIELD = { topic: 'topic', group: 'author_group', venue: 'venue' };

// literal hex (canvas can't read CSS vars) — distinct from the teal UI accent
const PAL = ['#60a5fa','#f59e0b','#4ade80','#a78bfa','#f472b6','#22d3ee','#fb923c','#a3e635','#e879f9','#f87171'];
const SLATE = '#8b96a8';
const ACCENT = '#2dd4bf';

function buildDim(field){
  const vals = [...new Set(PAPERS.map(p => p[field]).filter(Boolean))];
  const colors = {};
  vals.forEach((v, i) => { colors[v] = PAL[i % PAL.length]; });
  return { vals, colors };
}
const DIMS = { topic: buildDim('topic'), group: buildDim('author_group'), venue: buildDim('venue') };
const valOf = (p, dim) => p[DIM_FIELD[dim]];
function colorFor(dim, val){ const d = DIMS[dim]; return (d && d.colors[val]) || SLATE; }
// sqrt(citation_count), but capped so the ~26k-citation foundational nodes
// (T5, CoT) don't blow out a whole timeline column. Range ≈ 14–60px.
function size(c){ return Math.min(60, Math.round(14 + Math.sqrt(Math.max(0, c || 0)) * 1.4)); }

/* ---- empty state ---------------------------------------------------------
   papers.json starts empty; show a friendly message instead of a blank canvas. */
const datanote = document.getElementById('datanote');
if (!PAPERS.length){
  document.getElementById('empty').hidden = false;
  document.getElementById('hint').style.display = 'none';
  document.getElementById('legend').style.display = 'none';
  datanote.textContent = '/* no explainers yet */';
} else {
  datanote.textContent = `/* ${PAPERS.length} paper${PAPERS.length === 1 ? '' : 's'} · ${EDGES.length} edge${EDGES.length === 1 ? '' : 's'} */`;
  initGraph();
}

function initGraph(){
  // time-ordered positions: papers flow left→right by publication date, with
  // each column ordered to minimize edge crossings (see timeline.js).
  const { positions, bands } = computeTimeline(PAPERS, EDGES, {
    sizeOf: p => size(p.citation_count), band: 'quarter', colGap: 185, vGap: 30,
  });

  const elements = [];
  PAPERS.forEach(p => elements.push({
    data: {
      id: p.slug, short: p.short || p.slug,
      size: size(p.citation_count),
      bg: colorFor('topic', valOf(p, 'topic')),
      topicC: colorFor('topic', valOf(p, 'topic')),
      groupC: colorFor('group', valOf(p, 'group')),
      venueC: colorFor('venue', valOf(p, 'venue')),
    },
    position: positions.get(p.slug),
  }));
  EDGES.forEach(e => {
    if (byId.has(e.from) && byId.has(e.to))
      elements.push({ data: { id: `${e.from}__${e.to}`, source: e.from, target: e.to } });
  });

  const cy = cytoscape({
    container: document.getElementById('cy'), elements, minZoom: .16, maxZoom: 2.5, wheelSensitivity: .25,
    style: [
      { selector: 'node', style: {
        'background-color': 'data(bg)', 'width': 'data(size)', 'height': 'data(size)',
        'label': 'data(short)', 'font-family': 'JetBrains Mono, monospace', 'font-size': '9.5px',
        'color': '#cfcfd6', 'text-margin-y': 6, 'text-valign': 'bottom', 'min-zoomed-font-size': 7,
        'text-outline-width': 2.5, 'text-outline-color': '#0a0a0b',
        'border-width': 1.5, 'border-color': '#0a0a0b' }},
      // edges sit dim by default (a timeline of 170+ citations would be a hairball
      // at full opacity); a node's edges brighten on hover/selection.
      { selector: 'edge', style: {
        'width': 1.1, 'line-color': '#3a3a44', 'target-arrow-color': '#3a3a44',
        'target-arrow-shape': 'triangle', 'arrow-scale': .8, 'curve-style': 'bezier', 'opacity': .13 }},
      { selector: '.faded', style: { 'opacity': .06 }},
      { selector: 'node.sel', style: { 'border-width': 3, 'border-color': ACCENT, 'border-style': 'dashed' }},
      { selector: 'edge.hl', style: { 'line-color': ACCENT, 'target-arrow-color': ACCENT, 'opacity': 1, 'width': 2.4, 'z-index': 9 }},
    ],
    layout: { name: 'preset' },
  });
  if (import.meta.env?.DEV) window.cy = cy; // dev-only handle for debugging/tests

  /* ---- color-by switch + legend ---- */
  let curDim = 'topic';
  function applyColor(dim){
    curDim = dim;
    cy.nodes().forEach(n => n.data('bg', n.data(dim === 'topic' ? 'topicC' : dim === 'group' ? 'groupC' : 'venueC')));
    document.querySelectorAll('#seg button').forEach(b => b.classList.toggle('on', b.dataset.dim === dim));
    renderLegend();
  }
  document.getElementById('seg').addEventListener('click', e => {
    const b = e.target.closest('button'); if (b) applyColor(b.dataset.dim);
  });

  function renderLegend(){
    const present = [...new Set(PAPERS.map(p => valOf(p, curDim)).filter(Boolean))];
    const ordered = DIMS[curDim].vals.filter(v => present.includes(v));
    const el = document.getElementById('legend');
    el.innerHTML = '<h4>// ' + (curDim === 'group' ? 'author group' : curDim) + '</h4>' +
      ordered.map(v => `<div class="row" data-val="${v}"><span class="sw" style="background:${colorFor(curDim, v)}"></span>${v}</div>`).join('');
    el.querySelectorAll('.row').forEach(r => {
      r.onmouseenter = () => highlightCategory(r.dataset.val);
      r.onmouseleave = clearHighlight;
    });
  }
  function highlightCategory(val){
    cy.batch(() => {
      cy.elements().addClass('faded');
      cy.nodes().filter(n => { const p = byId.get(n.id()); return p && valOf(p, curDim) === val; }).removeClass('faded');
    });
  }
  function clearHighlight(){ if (!cy.$('node.sel').length) cy.elements().removeClass('faded'); }

  /* ---- side panel ---- */
  const panel = document.getElementById('panel'), pbody = document.getElementById('pbody');
  function openPaper(p){
    cy.batch(() => {
      cy.elements().removeClass('sel hl').addClass('faded');
      const n = cy.$id(p.slug);
      n.closedNeighborhood().removeClass('faded');
      n.addClass('sel');
      n.connectedEdges().addClass('hl').removeClass('faded');
    });

    const tags = [
      [valOf(p, 'topic'), colorFor('topic', valOf(p, 'topic'))],
      [valOf(p, 'group'), colorFor('group', valOf(p, 'group'))],
      [valOf(p, 'venue'), colorFor('venue', valOf(p, 'venue'))],
    ].filter(t => t[0]);

    const cited = (citesOf.get(p.slug) || []).map(id => byId.get(id));
    const venue = p.venue || 'arXiv';
    const cc = (p.citation_count ?? null);
    const href = p.explainer ? `/${p.explainer}` : null;

    pbody.innerHTML = `
      <div class="kick">${p.year ?? ''} · ${venue.toLowerCase()}</div>
      <h2>${p.title}</h2>
      <div class="meta">${p.authors || ''}</div>
      <div class="cites"><b>${cc === null ? '—' : cc.toLocaleString()}</b><span>citations</span></div>
      <div class="chips">${tags.map(t => `<span class="chip"><span class="d" style="background:${t[1]}"></span>${t[0]}</span>`).join('')}</div>
      <div class="abstract">${p.abstract || '<em>No abstract yet.</em>'}</div>
      ${href
        ? `<a class="go" href="${href}">read the explainer&nbsp;→</a>`
        : `<span class="go disabled">explainer pending</span>`}
      <div class="refs"><h4>// cites (${cited.length})</h4>${
        cited.length
          ? cited.map(q => `<a data-id="${q.slug}">${q.title}</a>`).join('')
          : '<div class="meta">— no outgoing citations in the graph —</div>'}</div>`;

    pbody.querySelectorAll('.refs a').forEach(a => a.onclick = () => {
      const q = byId.get(a.dataset.id);
      cy.animate({ center: { eles: cy.$id(q.slug) }, zoom: 1.1 }, { duration: 300 });
      openPaper(q);
    });
    panel.classList.add('open');
  }

  cy.on('tap', 'node', e => openPaper(byId.get(e.target.id())));
  cy.on('tap', e => { if (e.target === cy){ panel.classList.remove('open'); cy.elements().removeClass('sel hl faded'); }});
  document.getElementById('close').onclick = () => { panel.classList.remove('open'); cy.elements().removeClass('sel hl faded'); };

  /* ---- search ---- */
  document.getElementById('q').addEventListener('input', e => {
    const v = e.target.value.trim().toLowerCase();
    if (!v){ if (!cy.$('node.sel').length) cy.elements().removeClass('faded'); return; }
    cy.batch(() => {
      cy.elements().addClass('faded');
      cy.nodes().filter(n => {
        const p = byId.get(n.id());
        return p && (
          (p.title || '').toLowerCase().includes(v) ||
          (p.short || '').toLowerCase().includes(v) ||
          (p.authors || '').toLowerCase().includes(v));
      }).removeClass('faded');
    });
  });

  /* ---- hover: brighten a node's citations ---- */
  const qEl = document.getElementById('q');
  cy.on('mouseover', 'node', e => {
    if (cy.$('node.sel').length || qEl.value.trim()) return; // selection/search win
    const n = e.target;
    cy.batch(() => {
      cy.elements().addClass('faded');
      n.closedNeighborhood().removeClass('faded');
      n.connectedEdges().addClass('hl').removeClass('faded');
    });
  });
  cy.on('mouseout', 'node', () => {
    if (cy.$('node.sel').length || qEl.value.trim()) return; // don't clobber those states
    cy.batch(() => { cy.elements().removeClass('faded'); cy.edges().removeClass('hl'); });
  });

  /* ---- time axis: a vertical tick + period label per band, kept in sync with
     pan/zoom. Cytoscape has no native axis, so this is a DOM overlay. ---- */
  const axisEl = document.getElementById('axis');
  const ticks = bands.map((b, i) => {
    const showYear = i === 0 || b.year !== bands[i - 1].year;
    const t = document.createElement('div');
    t.className = 'tick' + (showYear ? ' yr' : '');
    t.innerHTML = `<span class="ln"></span><span class="lb">${showYear ? `<b>${b.year}</b> ` : ''}${b.sub}</span>`;
    axisEl.appendChild(t);
    return { x: b.x, el: t };
  });
  function placeAxis(){
    const z = cy.zoom(), px = cy.pan().x;
    ticks.forEach(t => { t.el.style.transform = `translateX(${(t.x * z + px).toFixed(1)}px)`; });
  }
  cy.on('pan zoom resize', placeAxis);

  applyColor('topic');
  cy.ready(() => { cy.fit(undefined, 70); placeAxis(); });
}
