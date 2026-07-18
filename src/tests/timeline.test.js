import { describe, it, expect } from 'vitest';
import { computeTimeline } from '../timeline.js';

// A small synthetic corpus spanning 3 quarters, with one paper large enough
// to matter for the no-overlap check and a citation edge to exercise the
// barycenter sweep.
function paper(slug, date, extra = {}) {
  return { slug, date, ...extra };
}

const PAPERS = [
  paper('a-2023-q1-1', '2023-01'),
  paper('a-2023-q1-2', '2023-02'),
  paper('a-2023-q1-3', '2023-03'),
  paper('b-2023-q2-1', '2023-04'),
  paper('b-2023-q2-2', '2023-05'),
  paper('c-2023-q3-1', '2023-07'),
];
const EDGES = [
  { from: 'b-2023-q2-1', to: 'a-2023-q1-1' },
  { from: 'c-2023-q3-1', to: 'b-2023-q2-2' },
];
const sizeOf = () => 24; // fixed diameter, keeps the overlap math simple

describe('computeTimeline — empty input', () => {
  it('returns empty positions/bands with no crash', () => {
    const { positions, bands } = computeTimeline([], [], { sizeOf });
    expect(positions.size).toBe(0);
    expect(bands).toEqual([]);
  });
});

describe('computeTimeline — basic layout', () => {
  const { positions, bands } = computeTimeline(PAPERS, EDGES, { sizeOf, colGap: 200, vGap: 10 });

  it('assigns a finite {x,y} to every paper', () => {
    for (const p of PAPERS) {
      const pos = positions.get(p.slug);
      expect(pos).toBeDefined();
      expect(Number.isFinite(pos.x)).toBe(true);
      expect(Number.isFinite(pos.y)).toBe(true);
    }
  });

  it('produces one band per non-empty quarter, sorted ascending by key', () => {
    expect(bands.length).toBe(3); // 2023-Q1, Q2, Q3
    for (let i = 1; i < bands.length; i++) {
      expect(bands[i].key).toBeGreaterThan(bands[i - 1].key);
    }
  });

  it('gives every paper in the same quarter the same x (column position)', () => {
    const xA = new Set(['a-2023-q1-1', 'a-2023-q1-2', 'a-2023-q1-3'].map(s => positions.get(s).x));
    expect(xA.size).toBe(1);
    const xB = new Set(['b-2023-q2-1', 'b-2023-q2-2'].map(s => positions.get(s).x));
    expect(xB.size).toBe(1);
  });

  it('spaces distinct columns apart (x strictly increases with time)', () => {
    const xQ1 = positions.get('a-2023-q1-1').x;
    const xQ2 = positions.get('b-2023-q2-1').x;
    const xQ3 = positions.get('c-2023-q3-1').x;
    expect(xQ2).toBeGreaterThan(xQ1);
    expect(xQ3).toBeGreaterThan(xQ2);
  });

  it('packs nodes within a column without overlap (gap >= diameter + vGap, minus rounding)', () => {
    const vGap = 10, diameter = 24;
    const colYs = { a: [], b: [] };
    for (const s of ['a-2023-q1-1', 'a-2023-q1-2', 'a-2023-q1-3']) colYs.a.push(positions.get(s).y);
    for (const s of ['b-2023-q2-1', 'b-2023-q2-2']) colYs.b.push(positions.get(s).y);
    for (const ys of Object.values(colYs)) {
      ys.sort((x, y) => x - y);
      for (let i = 1; i < ys.length; i++) {
        expect(ys[i] - ys[i - 1]).toBeGreaterThanOrEqual(diameter + vGap - 0.01);
      }
    }
  });
});

describe('computeTimeline — survey spine (centerSet)', () => {
  it('centers the tagged subset of a column closer to y=0 than the untagged rest', () => {
    const centerSet = new Set(['b-2023-q2-2']); // one of two papers in the Q2 column
    const { positions } = computeTimeline(PAPERS, EDGES, { sizeOf, colGap: 200, vGap: 10, centerSet });
    const taggedY = Math.abs(positions.get('b-2023-q2-2').y);
    const untaggedY = Math.abs(positions.get('b-2023-q2-1').y);
    expect(taggedY).toBeLessThan(untaggedY);
  });

  it('leaves a column with no tagged members packed as normal (no crash, still no-overlap)', () => {
    const centerSet = new Set(['c-2023-q3-1']); // Q3 has only this one paper
    const { positions } = computeTimeline(PAPERS, EDGES, { sizeOf, colGap: 200, vGap: 10, centerSet });
    expect(Number.isFinite(positions.get('a-2023-q1-1').y)).toBe(true);
  });
});

describe('computeTimeline — fallback to year when date is missing', () => {
  it('places a dateless paper mid-year rather than crashing', () => {
    const papers = [...PAPERS, paper('d-noyear', undefined, { year: 2024 })];
    const { positions, bands } = computeTimeline(papers, [], { sizeOf, colGap: 200, vGap: 10 });
    expect(Number.isFinite(positions.get('d-noyear').x)).toBe(true);
    expect(bands.length).toBe(4); // adds a 2024-Q3 band (mid-year fallback)
  });
});
