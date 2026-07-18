import cytoscape from 'cytoscape';
import data from '../data/papers.json';
import surveyData from '../data/surveys.json';
import { computeTimeline } from './timeline.js';
import './style.css';

/* ---- data ----------------------------------------------------------------
   Built at build time from data/papers.json (see CLAUDE.md for the shape):
     node id      = slug
     label        = short
     size         = log10(citation_count), capped (see `size()` below)
     color dims   = topic / institution (derived) / venue (derived)
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

/* ---- surveys (tag overlays) ----------------------------------------------
   A survey is a named tag defined in data/surveys.json; each paper node carries
   a `tags` array of survey ids. Surveys are ORTHOGONAL to the color-by dims:
   selecting one pulls its tagged papers into a centred horizontal spine (the
   timeline `centerSet`) and rings them in the survey colour — deliberately
   minimal, no dimming and no edge colouring, so the rest of the map is left
   exactly as-is. `none` restores the normal (uncentred) map.                */
const SURVEYS = Array.isArray(surveyData?.surveys) ? surveyData.surveys : [];
const surveyById = new Map(SURVEYS.map(s => [s.id, s]));
const surveyMembers = new Map(SURVEYS.map(s =>
  [s.id, new Set(PAPERS.filter(p => Array.isArray(p.tags) && p.tags.includes(s.id)).map(p => p.slug))]));

/* ---- color dimensions ----------------------------------------------------
   Three switchable color dims: topic / institution / venue. `topic` is a raw
   field, but `institution` and `venue` are DERIVED — the raw paper fields are
   too fine-grained (author_group encodes every collaboration combo, venue
   carries the year + track), which blew the legend up to ~90 / ~54 swatches.
   We collapse both, then assign palette colors by descending paper count so
   the most common categories read first.                                    */

// literal hex (canvas can't read CSS vars) — distinct from the teal UI accent
const PAL = ['#60a5fa','#f59e0b','#4ade80','#a78bfa','#f472b6','#22d3ee','#fb923c','#a3e635','#e879f9','#f87171'];
const SLATE = '#8b96a8';
const ACCENT = '#2dd4bf';
// the two long-tail catch-alls get fixed greys (and always sort last)
const OTHER_COLOR = { 'Other (industry)': '#6b7280', 'Other (academia)': '#475569' };

/* institution — collapse author_group ("A / B / …") to ONE institution: each
   token is normalized to a canonical name, and the highest-prominence partner
   wins, so "UMass Amherst / Meta" → Meta. Institutions with < MIN_NAMED papers
   then fall into an industry/academia catch-all so the legend stays short. */
const INST_ALIAS = {
  'Google':'Google','Google DeepMind':'Google','DeepMind':'Google',
  'Meta AI (FAIR)':'Meta','Meta AI':'Meta','Meta':'Meta','Meta Superintelligence Labs':'Meta',
  'Microsoft':'Microsoft','Microsoft Research':'Microsoft','DeepSeek-AI':'DeepSeek',
  'AI2':'AI2','Ai2':'AI2','Princeton NLP':'Princeton','Princeton':'Princeton',
  'UC Berkeley':'UC Berkeley','Berkeley':'UC Berkeley','LMSYS':'UC Berkeley',
  'MIT Media Lab':'MIT','MIT':'MIT','USC ISI':'USC','UMass Amherst':'UMass','UMass':'UMass',
  'OSU NLP':'Ohio State','GAIR Lab':'SJTU','SJTU':'SJTU','OpenBMB':'Tsinghua','Tsinghua':'Tsinghua',
  'Renmin University of China':'Renmin University','Renmin University':'Renmin University',
  'National Taiwan University':'NTU','UKP Lab (TU Darmstadt)':'TU Darmstadt','KAIST AI':'KAIST',
  'Inclusion AI':'Ant Group','Ant Group':'Ant Group','ByteDance Seed':'ByteDance',
  'Tencent AI Lab':'Tencent','Alibaba DAMO':'Alibaba','Salesforce AI Research':'Salesforce',
};
const INST_WEIGHT = {};
['OpenAI','Google','Meta','Microsoft','Anthropic','Amazon','Apple','IBM','Bloomberg',
 'ByteDance','Tencent','Alibaba','Salesforce','J.P. Morgan'].forEach(n => { INST_WEIGHT[n] = 100; });
['Scale AI','DeepSeek','Ant Group','Zhipu AI','Shanghai AI Lab','MBZUAI','AI2'].forEach(n => { INST_WEIGHT[n] = 90; });
['Stanford','MIT','UC Berkeley','CMU','Princeton','Oxford','ETH Zurich','Tsinghua',
 'Peking University','NYU','UCLA','UW','U Tokyo','KAIST','HKU','USTC','SJTU','NTU'].forEach(n => { INST_WEIGHT[n] = 70; });
['CAIS','METR','Patronus AI','BigCode','FutureHouse','Mercor','TIGER-Lab','AE Studio',
 'ZeroEntropy','Grammarly','Upwork','The Fin AI','Laude Institute','Li Auto','Metastone'].forEach(n => { INST_WEIGHT[n] = 40; });
// canonical institutions that are companies / industry labs (the rest are academic)
const INDUSTRY = new Set(['OpenAI','Google','Meta','Microsoft','Anthropic','Amazon','Apple','IBM',
  'Bloomberg','ByteDance','Tencent','Alibaba','Salesforce','J.P. Morgan','Scale AI','DeepSeek',
  'Ant Group','Zhipu AI','Shanghai AI Lab','Metastone','Li Auto','METR','Patronus AI','FutureHouse',
  'Mercor','AE Studio','ZeroEntropy','Grammarly','Upwork','The Fin AI','Laude Institute']);
const MIN_NAMED = 3;   // an institution needs this many papers to earn its own legend row

const canonTok = t => { t = t.trim(); return INST_ALIAS[t] || t; };
function rawInstitution(p){   // the single canonical institution we attribute a paper to
  const parts = (p.author_group || '').split('/').map(canonTok).filter(Boolean);
  if (!parts.length) return null;
  // an institution with no explicit weight defaults to 50 — between the 40 and
  // 70 tiers above — so an unlisted collaborator currently outranks tier-40
  // names (METR, Patronus AI, …) in attribution; add it to a tier instead of
  // relying on this default if that's ever the wrong call for a real paper.
  return parts.reduce((a, b) => (INST_WEIGHT[b] || 50) > (INST_WEIGHT[a] || 50) ? b : a);
}
const INST_COUNT = new Map();
PAPERS.forEach(p => { const i = rawInstitution(p); if (i) INST_COUNT.set(i, (INST_COUNT.get(i) || 0) + 1); });
function institutionOf(p){    // the legend bucket: the institution itself, or an "Other" catch-all
  const i = rawInstitution(p);
  if (!i) return null;
  if ((INST_COUNT.get(i) || 0) >= MIN_NAMED) return i;
  return INDUSTRY.has(i) ? 'Other (industry)' : 'Other (academia)';
}

/* venue — keep only the conference, dropping the year and track, so e.g.
   "ICML 2024", "NeurIPS 2025 Workshop" and "NeurIPS Datasets & Benchmarks" all
   collapse onto their conference; anything not a known venue → "arXiv". */
const VENUE_CONF = [
  ['NeurIPS',/neurips|nips/],['ICLR',/iclr/],['ICML',/icml/],['NAACL',/naacl/],['EMNLP',/emnlp/],
  ['ACL',/acl/],['COLM',/colm/],['TACL',/tacl/],['TMLR',/tmlr/],['JMLR',/jmlr/],['CVPR',/cvpr/],
  ['ICCV',/iccv/],['ECCV',/eccv/],['IJCV',/ijcv/],['FAccT',/fa[ac]ct/],['WMT',/\bwmt\b/],
  ['AISec',/aisec/],['NLLP',/nllp/],['Nature',/nature/],['QJE',/qje/],
];
function venueOf(p){
  const v = (p.venue || '').toLowerCase();
  for (const [name, re] of VENUE_CONF) if (re.test(v)) return name;
  return 'arXiv';
}

const DIM_GET = { topic: p => p.topic, group: institutionOf, venue: venueOf };
const valOf = (p, dim) => DIM_GET[dim](p);

// assign palette colors by descending paper count; the catch-all "Other"
// buckets take fixed greys and always sort last.
function buildDim(dim){
  const counts = new Map();
  PAPERS.forEach(p => { const v = valOf(p, dim); if (v) counts.set(v, (counts.get(v) || 0) + 1); });
  const isOther = v => v in OTHER_COLOR;
  const vals = [...counts.keys()].sort((a, b) =>
    (isOther(a) - isOther(b)) || (counts.get(b) - counts.get(a)) || a.localeCompare(b));
  const colors = {}; let pi = 0;
  vals.forEach(v => { colors[v] = OTHER_COLOR[v] || PAL[pi++ % PAL.length]; });
  return { vals, colors, counts };
}
const DIMS = { topic: buildDim('topic'), group: buildDim('group'), venue: buildDim('venue') };
function colorFor(dim, val){ const d = DIMS[dim]; return (d && d.colors[val]) || SLATE; }

// log-scaled node size: sqrt() flattened everything above ~1k citations onto
// the same blob, so 500 / 5k / 50k were indistinguishable. log10 keeps the
// whole range separated; the 14×/decade slope gives ~12px under 10 cites,
// ~50px at 500, ~64px at 5k, up to ~80px at the 70k foundational hubs.
function size(c){ return Math.round(12 + 14 * Math.log10(Math.max(0, c || 0) + 1)); }

// touch devices have no hover-to-preview — the hint's "hover a node · tap to
// open" is two desktop-only steps; touch only has the one (tap opens directly).
if (window.matchMedia && window.matchMedia('(hover: none)').matches) {
  const hintEl = document.getElementById('hint');
  hintEl.textContent = '// older ← time → newer · tap a node to open · drag to pan';
}

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
      // survey: a tagged node just gets a bright ring in the survey colour —
      // no dimming, no edge colouring (kept before node.sel so a selection
      // ring still overrides it). Ring width is zoom-compensated (data(surveyBW),
      // kept live by the 'zoom' handler below) so it stays legible at the map's
      // default fit-out zoom instead of shrinking to a sub-pixel line.
      { selector: 'node.survey', style: { 'border-width': 'data(surveyBW)', 'border-color': 'data(surveyC)', 'z-index': 6 }},
      { selector: 'node.sel', style: { 'border-width': 3, 'border-color': ACCENT, 'border-style': 'dashed' }},
      { selector: 'edge.hl', style: { 'line-color': ACCENT, 'target-arrow-color': ACCENT, 'opacity': 1, 'width': 2.4, 'z-index': 9 }},
    ],
    layout: { name: 'preset' },
  });
  if (import.meta.env?.DEV) window.cy = cy; // dev-only handle for debugging/tests

  /* ---- color-by switch + legend ---- */
  let curDim = 'topic';
  // a *tapped* legend row pins that category's isolation. Tap works on touch
  // (mobile has no hover), so this is what makes the legend usable on phones;
  // desktop hover still previews on top of any pin. null = nothing pinned.
  let pinnedCat = null;
  let curSurvey = null;             // active survey spine (null = none); see applySurvey
  function applyColor(dim){
    curDim = dim;
    clearPin();                       // a pin from another dimension is meaningless
    cy.nodes().forEach(n => n.data('bg', n.data(dim === 'topic' ? 'topicC' : dim === 'group' ? 'groupC' : 'venueC')));
    document.querySelectorAll('#seg button').forEach(b => b.classList.toggle('on', b.dataset.dim === dim));
    renderLegend();
    resetHighlight();                 // keep the resting state (selection / pin / survey)
  }
  document.getElementById('seg').addEventListener('click', e => {
    const b = e.target.closest('button'); if (b) applyColor(b.dataset.dim);
  });

  function renderLegend(){
    const present = [...new Set(PAPERS.map(p => valOf(p, curDim)).filter(Boolean))];
    const ordered = DIMS[curDim].vals.filter(v => present.includes(v));
    const el = document.getElementById('legend');
    let cap = '';
    if (curSurvey && surveyById.has(curSurvey)){
      const s = surveyById.get(curSurvey);
      const n = surveyMembers.get(curSurvey).size;
      // optional survey write-up page (surveys.json `page`) → "read →" link
      const rd = s.page ? `<a class="rd mono" href="${s.page}" style="color:${s.color};border-color:${s.color}">read&nbsp;→</a>` : '';
      cap = `<div class="surveycap"><span class="dot" style="color:${s.color};background:${s.color}"></span>${s.label}<span class="n">· ${n} papers</span>${rd}</div>`;
    }
    el.innerHTML = cap + '<h4>// ' + (curDim === 'group' ? 'institution' : curDim) + '</h4>' +
      ordered.map(v => `<div class="row${v === pinnedCat ? ' active' : ''}" data-val="${v}"><span class="sw" style="background:${colorFor(curDim, v)}"></span>${v}</div>`).join('');
    el.querySelectorAll('.row').forEach(r => {
      r.onmouseenter = () => showCategory(r.dataset.val);   // desktop hover preview
      r.onmouseleave = resetHighlight;
      r.onclick = () => {                                    // tap = pin/unpin (touch + desktop)
        pinnedCat = pinnedCat === r.dataset.val ? null : r.dataset.val;
        el.querySelectorAll('.row').forEach(x => x.classList.toggle('active', x.dataset.val === pinnedCat));
        resetHighlight();
      };
    });
  }
  function showCategory(val){
    cy.batch(() => {
      cy.elements().addClass('faded');
      cy.nodes().filter(n => { const p = byId.get(n.id()); return p && valOf(p, curDim) === val; }).removeClass('faded');
    });
  }
  // resting state, by priority: a node selection (panel) owns the fade if
  // present; else a pinned legend category; else show everything. (A survey
  // doesn't dim anything — it only rings + centres its members.)
  function resetHighlight(){
    if (cy.$('node.sel').length) return;
    if (pinnedCat) { showCategory(pinnedCat); return; }
    cy.elements().removeClass('faded');
  }
  function clearPin(){
    pinnedCat = null;
    document.querySelectorAll('#legend .row.active').forEach(r => r.classList.remove('active'));
  }

  /* ---- survey spine -------------------------------------------------------
     Selecting a survey pulls its tagged papers to the vertical centre of each
     time column (the spine) and rings them in the survey colour. The rest of
     the map is left exactly as-is — no dimming, no edge colouring — so the only
     change a reader sees is the centred, ringed subset. The persistent
     `.survey` class carries the ring; hover/selection/search layer on top
     unchanged.                                                                */
  const surveyLayout = new Map();    // id -> Map(slug -> {x,y}), computed once
  function layoutFor(id){
    if (!surveyLayout.has(id)){
      const { positions: sp } = computeTimeline(PAPERS, EDGES, {
        sizeOf: p => size(p.citation_count), band: 'quarter', colGap: 185, vGap: 30,
        centerSet: surveyMembers.get(id),
      });
      surveyLayout.set(id, sp);
    }
    return surveyLayout.get(id);
  }
  // Ring width in model units so it renders at a legible fixed screen size
  // regardless of zoom (a flat px width shrinks to sub-pixel at the map's
  // default fit-out zoom, which made the whole feature look inert).
  const ringWidth = () => Math.min(22, Math.max(4, 3 / cy.zoom()));
  cy.on('zoom', () => {
    const survey = cy.$('node.survey');
    if (survey.nonempty()) survey.data('surveyBW', ringWidth());
  });
  function applySurvey(id){
    curSurvey = (id && surveyById.has(id)) ? id : null;
    const target = curSurvey ? layoutFor(curSurvey) : positions;
    cy.batch(() => {
      cy.nodes().removeClass('survey');
      if (curSurvey){
        const col = surveyById.get(curSurvey).color || ACCENT;
        const mem = surveyMembers.get(curSurvey);
        cy.nodes().filter(n => mem.has(n.id())).addClass('survey').data('surveyC', col).data('surveyBW', ringWidth());
      }
    });
    // glide every node to its layout (x unchanged → the time axis stays put)
    cy.nodes().forEach(n => { const pp = target.get(n.id()); if (pp) n.animate({ position: pp }, { duration: 430, easing: 'ease-out' }); });
    // Fit to the ringed subset when a survey is active (padded generously) so
    // the spine actually lands at a zoom where its ring and labels read —
    // fitting the whole graph, as before, left the ring at a near-invisible
    // sub-pixel width and the spine looked like nothing had happened.
    setTimeout(() => {
      const fitTarget = curSurvey ? { eles: cy.$('node.survey'), padding: 90 } : { padding: 60 };
      cy.animate({ fit: fitTarget, duration: 360, easing: 'ease-out' });
    }, 460);
    const sel = document.getElementById('survey');
    sel.classList.toggle('on', !!curSurvey);
    sel.style.background = curSurvey ? surveyById.get(curSurvey).color : '';
    renderLegend();
    resetHighlight();
  }
  // populate + wire the survey dropdown (hidden when no surveys are defined)
  if (SURVEYS.length){
    const sel = document.getElementById('survey');
    document.getElementById('surveyby').hidden = false;
    SURVEYS.forEach(s => {
      const o = document.createElement('option');
      o.value = s.id; o.textContent = `${s.label} (${surveyMembers.get(s.id).size})`;
      sel.appendChild(o);
    });
    sel.addEventListener('change', e => applySurvey(e.target.value));
    // deep link: /?survey=<id> opens with that spine active (survey pages link here)
    const want = new URLSearchParams(location.search).get('survey');
    if (want && surveyById.has(want)){ sel.value = want; applySurvey(want); }
  }

  /* ---- side panel ---- */
  const panel = document.getElementById('panel'), pbody = document.getElementById('pbody');
  function openPaper(p){
    clearPin();                       // selecting a node and pinning a legend category are exclusive modes
    cy.batch(() => {
      cy.elements().removeClass('sel hl').addClass('faded');
      const n = cy.$id(p.slug);
      n.closedNeighborhood().removeClass('faded');
      n.addClass('sel');
      n.connectedEdges().addClass('hl').removeClass('faded');
    });

    // the institution chip shows the specific institution we attribute to (not
    // the "Other" bucket), but is coloured by its legend bucket for consistency.
    const tags = [
      [valOf(p, 'topic'), colorFor('topic', valOf(p, 'topic'))],
      [rawInstitution(p), colorFor('group', valOf(p, 'group'))],
      [valOf(p, 'venue'), colorFor('venue', valOf(p, 'venue'))],
    ].filter(t => t[0]);
    // survey membership chips (a paper can belong to several surveys)
    const surveyChips = (p.tags || []).map(id => surveyById.get(id)).filter(Boolean)
      .map(s => `<span class="chip survey"><span class="d" style="background:${s.color}"></span>${s.label}</span>`).join('');

    const cited = (citesOf.get(p.slug) || []).map(id => byId.get(id));
    const venue = p.venue || 'arXiv';
    const cc = (p.citation_count ?? null);
    const href = p.explainer ? `/${p.explainer}` : null;

    pbody.innerHTML = `
      <div class="kick">${p.year ?? ''} · ${venue.toLowerCase()}</div>
      <h2>${p.title}</h2>
      <div class="meta">${p.authors || ''}</div>
      <div class="cites"><b>${cc === null ? '—' : cc.toLocaleString()}</b><span>citations</span></div>
      <div class="chips">${tags.map(t => `<span class="chip"><span class="d" style="background:${t[1]}"></span>${t[0]}</span>`).join('')}${surveyChips}</div>
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
  cy.on('tap', e => { if (e.target === cy){ panel.classList.remove('open'); clearPin(); cy.elements().removeClass('sel hl faded'); resetHighlight(); }});
  document.getElementById('close').onclick = () => { panel.classList.remove('open'); clearPin(); cy.elements().removeClass('sel hl faded'); resetHighlight(); };

  /* ---- search ---- */
  document.getElementById('q').addEventListener('input', e => {
    const v = e.target.value.trim().toLowerCase();
    if (!v){ resetHighlight(); return; }   // empty search → back to pin (if any) or full graph
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
    cy.edges().removeClass('hl');
    resetHighlight();                 // back to full graph, a pinned category, or the survey spine
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
  // model-unit gap between adjacent ticks (columns are evenly spaced — see
  // timeline.js), used below to know when zoomed-out labels would overlap.
  const tickGap = ticks.length > 1 ? ticks[1].x - ticks[0].x : 0;
  function placeAxis(){
    const z = cy.zoom(), px = cy.pan().x;
    ticks.forEach(t => { t.el.style.transform = `translateX(${(t.x * z + px).toFixed(1)}px)`; });
    // sub-labels ("Q2", "Q3", …) start to overlap below ~70px of screen space
    // per tick; past that, keep only the year-boundary labels (same rule the
    // ≤640px media query already applies for narrow screens).
    axisEl.classList.toggle('dense', tickGap * z < 70);
  }
  cy.on('pan zoom resize', placeAxis);

  // Fit — to the active survey's ringed subset if one is selected (matches
  // applySurvey's own fit target, so a deferred fit here, e.g. from the
  // resize retry below, can't clobber a deep-linked `/?survey=` view with a
  // full-graph fit), otherwise to the whole graph. Then check whether the
  // configured zoom floor clamped it: the timeline's bounding box needs a
  // lower zoom to fit than `minZoom` allows on a narrow viewport (e.g. a
  // phone), which would otherwise crop most of the map. Lower the floor once
  // and re-fit so the whole timeline is always reachable.
  function fitNow(){
    const eles = curSurvey ? cy.$('node.survey') : cy.elements();
    const pad = curSurvey ? 90 : 70;
    cy.fit(eles, pad);
    if (cy.zoom() === cy.minZoom()){
      const bb = eles.boundingBox();
      const need = Math.min((cy.width() - pad * 2) / bb.w, (cy.height() - pad * 2) / bb.h);
      if (need > 0 && need < cy.minZoom()){
        cy.minZoom(need * 0.9);
        cy.fit(eles, pad);
      }
    }
    placeAxis();
  }

  applyColor('topic');
  cy.ready(() => {
    if (cy.width() && cy.height()){ fitNow(); return; }
    // The container can measure 0×0 at ready time (a backgrounded tab, an
    // embedded preview) — cy.fit() silently no-ops there and the map is stuck
    // at zoom 1. Retry once, the first time the container reports a real size.
    const onFirstResize = () => {
      if (cy.width() && cy.height()){ cy.off('resize', onFirstResize); fitNow(); }
    };
    cy.on('resize', onFirstResize);
  });
}
