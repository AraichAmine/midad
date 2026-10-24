import { describe, expect, it } from 'vitest';

import type { AnimationTimeline, Paw, Stroke } from '../src/types';
import {
  assertDelayedStrokeCausality,
  assertPawContinuity,
  parseSvgPath,
  samplePathPoints,
} from '../src/validator';

function stroke(id: string, type: Stroke['type'] = 'trunk'): Stroke {
  return { id, d: 'M 0 0 L 1 0', length: 1, type };
}

function paw(id: string, delayedIds: string[]): Paw {
  return {
    id,
    trunkStroke: stroke(`trunk-${id}`, 'trunk'),
    delayedStrokes: delayedIds.map((delayed) => stroke(delayed, 'dot')),
  };
}

function timeline(items: AnimationTimeline['items']): AnimationTimeline {
  const paws = [paw('p1', ['dot-1']), paw('p2', ['dot-2'])];
  return { paws, items, totalDuration: 4 };
}

describe('assertPawContinuity', () => {
  it('accepts a welded RTL cubic baseline', () => {
    const result = assertPawContinuity(
      'M 200 100 C 180 100 160 100 140 100 ' +
        'C 120 100 100 100 80 100 C 60 100 40 100 20 100',
    );

    expect(result.valid).toBe(true);
    expect(result.singleMove).toBe(true);
    expect(result.c0Continuous).toBe(true);
    expect(result.rtlRatio).toBeGreaterThanOrEqual(0.85);
    expect(result.errors).toEqual([]);
  });

  it('accepts a descending vertical stroke (alef-like motion)', () => {
    const result = assertPawContinuity(
      'M 100 220 C 100 200 100 180 100 160 ' +
        'C 100 140 100 120 100 100 C 100 80 100 60 100 40',
    );
    expect(result.valid).toBe(true);
    expect(result.rtlRatio).toBeGreaterThanOrEqual(0.85);
  });

  it('rejects an internal M command and reports a singleMove error', () => {
    const result = assertPawContinuity(
      'M 200 100 C 180 100 160 100 140 100 ' +
        'M 120 100 C 100 100 80 100 60 100',
    );

    expect(result.valid).toBe(false);
    expect(result.singleMove).toBe(false);
    expect(result.c0Continuous).toBe(false);
    expect(result.errors.join('\n')).toMatch(/single|exactly one 'M'/i);
  });

  it('rejects an LTR path on the RTL monotonicity invariant', () => {
    const result = assertPawContinuity(
      'M 0 100 C 20 100 40 100 60 100 ' +
        'C 80 100 100 100 120 100 C 140 100 160 100 180 100',
    );

    expect(result.valid).toBe(false);
    expect(result.singleMove).toBe(true);
    expect(result.c0Continuous).toBe(true);
    expect(result.rtlRatio).toBeLessThan(0.85);
    expect(result.errors.join('\n')).toMatch(/RTL monotonicity/i);
  });

  it('rejects a path with a continuity gap at a move command', () => {
    const result = assertPawContinuity(
      'M 200 100 C 180 100 160 100 140 100 ' +
        'M 139.9 100 C 120 100 100 100 80 100',
    );
    expect(result.valid).toBe(false);
    expect(result.c0Continuous).toBe(false);
    expect(result.errors.join('\n')).toMatch(/C0 discontinuity/i);
  });

  it('reports malformed and unsupported paths instead of throwing', () => {
    const empty = assertPawContinuity('');
    expect(empty.valid).toBe(false);
    expect(empty.singleMove).toBe(false);
    expect(empty.c0Continuous).toBe(false);
    expect(empty.errors.length).toBeGreaterThan(0);

    const unsupported = assertPawContinuity('M 10 10 A 5 5 0 0 1 0 0');
    expect(unsupported.valid).toBe(false);
    expect(unsupported.errors.join('\n')).toMatch(/Unsupported SVG command/i);
  });

  it('samples at least 50 points and computes a stable ratio', () => {
    const segments = parseSvgPath(
      'M 100 100 C 80 100 60 100 40 100 C 20 100 10 100 0 100',
    );
    const samples = samplePathPoints(segments);
    expect(samples.length).toBeGreaterThanOrEqual(50);
    expect(samples[0][0]).toBeGreaterThan(samples[samples.length - 1][0]);
  });

  it('parses implicit coordinate repeats and relative commands', () => {
    const implicit = parseSvgPath('M 200 100 180 100 160 100');
    expect(implicit.map((segment) => segment.command)).toEqual(['M', 'L', 'L']);
    expect(implicit[2].points[0]).toEqual([160, 100]);

    const relative = parseSvgPath('M 200 100 l -20 0 l -20 5');
    expect(relative[1].points[0]).toEqual([180, 100]);
    expect(relative[2].points[0]).toEqual([160, 105]);
  });
});

describe('assertDelayedStrokeCausality', () => {
  it('accepts a valid causally ordered timeline', () => {
    const result = assertDelayedStrokeCausality(
      timeline([
        { strokeId: 'trunk-p1', pawId: 'p1', type: 'trunk', startTime: 0, endTime: 1 },
        { strokeId: 'dot-1', pawId: 'p1', type: 'delayed', startTime: 1, endTime: 1.5 },
        { strokeId: 'trunk-p2', pawId: 'p2', type: 'trunk', startTime: 2, endTime: 3 },
        { strokeId: 'dot-2', pawId: 'p2', type: 'delayed', startTime: 3, endTime: 3.5 },
      ]),
    );

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('rejects a dot that starts before its trunk finishes', () => {
    const result = assertDelayedStrokeCausality(
      timeline([
        { strokeId: 'trunk-p1', pawId: 'p1', type: 'trunk', startTime: 0, endTime: 1 },
        { strokeId: 'dot-1', pawId: 'p1', type: 'delayed', startTime: 0.5, endTime: 1.5 },
        { strokeId: 'trunk-p2', pawId: 'p2', type: 'trunk', startTime: 2, endTime: 3 },
        { strokeId: 'dot-2', pawId: 'p2', type: 'delayed', startTime: 3, endTime: 3.5 },
      ]),
    );

    expect(result.valid).toBe(false);
    expect(result.errors.join('\n')).toMatch(/before paw 'p1' trunk finishes/i);
  });

  it('rejects a delayed stroke that finishes after the next paw begins', () => {
    const result = assertDelayedStrokeCausality(
      timeline([
        { strokeId: 'trunk-p1', pawId: 'p1', type: 'trunk', startTime: 0, endTime: 1 },
        { strokeId: 'dot-1', pawId: 'p1', type: 'delayed', startTime: 1, endTime: 2.5 },
        { strokeId: 'trunk-p2', pawId: 'p2', type: 'trunk', startTime: 2, endTime: 3 },
        { strokeId: 'dot-2', pawId: 'p2', type: 'delayed', startTime: 3, endTime: 3.5 },
      ]),
    );

    expect(result.valid).toBe(false);
    expect(result.errors.join('\n')).toMatch(/after paw 'p2' trunk starts|ends at/i);
  });

  it('rejects negative durations', () => {
    const result = assertDelayedStrokeCausality(
      timeline([
        { strokeId: 'trunk-p1', pawId: 'p1', type: 'trunk', startTime: 0, endTime: -1 },
        { strokeId: 'dot-1', pawId: 'p1', type: 'delayed', startTime: 1, endTime: 1.5 },
      ]),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.join('\n')).toMatch(/negative duration/i);
  });

  it('rejects overlapping delayed strokes within a paw', () => {
    const paws = [
      {
        ...paw('p1', ['dot-1', 'dot-1b']),
      },
    ];
    const result = assertDelayedStrokeCausality({
      paws,
      items: [
        { strokeId: 'trunk-p1', pawId: 'p1', type: 'trunk', startTime: 0, endTime: 1 },
        { strokeId: 'dot-1', pawId: 'p1', type: 'delayed', startTime: 1, endTime: 2 },
        { strokeId: 'dot-1b', pawId: 'p1', type: 'delayed', startTime: 1.5, endTime: 2.5 },
      ],
      totalDuration: 2.5,
    });

    expect(result.valid).toBe(false);
    expect(result.errors.join('\n')).toMatch(/overlap/i);
  });

  it('reports missing trunks and unknown paws', () => {
    const result = assertDelayedStrokeCausality({
      paws: [paw('p1', ['dot-1'])],
      items: [
        { strokeId: 'dot-1', pawId: 'missing', type: 'delayed', startTime: 1, endTime: 2 },
      ],
      totalDuration: 2,
    });
    expect(result.valid).toBe(false);
    expect(result.errors.join('\n')).toMatch(/unknown paw/i);
    expect(result.errors.join('\n')).toMatch(/exactly one trunk/i);
  });
});
