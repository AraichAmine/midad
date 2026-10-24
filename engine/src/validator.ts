/**
 * Invariant checks for welded Arabic baselines and delayed-stroke timing.
 *
 * The validator is intentionally dependency-free so it can run in Vitest, in
 * the browser harness and in a future CI pipeline without a DOM.
 */

import type {
  AnimationTimeline,
  Point,
  StrokeSegment,
  TimelineItem,
} from './types';

export const CONTINUITY_TOLERANCE = 1e-3;
export const RTL_MIN_RATIO = 0.85;
export const RTL_SAMPLE_COUNT = 100;

const EPS = 1e-9;
const COMMAND_ARITY: Record<string, number> = {
  M: 2,
  L: 2,
  C: 6,
  Q: 4,
  Z: 0,
};

const TOKEN_PATTERN = /[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g;
const ALLOWED_COMMANDS = new Set(['M', 'L', 'C', 'Q', 'Z']);

export interface PawContinuityResult {
  valid: boolean;
  rtlRatio: number;
  singleMove: boolean;
  c0Continuous: boolean;
  errors: string[];
}

export interface CausalityResult {
  valid: boolean;
  errors: string[];
}

/** Convert an SVG path string into typed command segments. */
export function parseSvgPath(svgPathD: string): StrokeSegment[] {
  if (typeof svgPathD !== 'string') {
    throw new TypeError('SVG path data must be a string');
  }
  const tokens = svgPathD.match(TOKEN_PATTERN) ?? [];
  const segments: StrokeSegment[] = [];
  let index = 0;
  let activeCommand: string | null = null;
  let activeRelative = false;
  let currentPoint: Point = [0, 0];
  let subpathStart: Point = [0, 0];

  const readNumber = (): number => {
    const token = tokens[index];
    if (token === undefined || /^[a-zA-Z]$/.test(token)) {
      throw new Error(`Expected a number at token ${index} in path`);
    }
    index += 1;
    const value = Number(token);
    if (!Number.isFinite(value)) {
      throw new Error(`Invalid number ${token} in path`);
    }
    return value;
  };

  while (index < tokens.length) {
    const token = tokens[index];
    if (/^[a-zA-Z]$/.test(token)) {
      activeCommand = token.toUpperCase();
      activeRelative = token === token.toLowerCase();
      index += 1;
      if (!ALLOWED_COMMANDS.has(activeCommand)) {
        throw new Error(`Unsupported SVG command '${token}'`);
      }
    } else if (activeCommand === null) {
      throw new Error('SVG path must start with a command');
    }

    const command = activeCommand;
    if (command === null) {
      throw new Error('SVG path must start with a command');
    }
    const relative = activeRelative;
    const arity = COMMAND_ARITY[command];
    if (arity === 0) {
      // close path: represented as a line back to the subpath start.
      if (
        command === 'Z' &&
        (currentPoint[0] !== subpathStart[0] ||
          currentPoint[1] !== subpathStart[1])
      ) {
        segments.push({ command: 'L', points: [subpathStart] });
        currentPoint = subpathStart;
      }
      activeCommand = null;
      continue;
    }

    const values: number[] = [];
    for (let offset = 0; offset < arity; offset += 1) {
      const value = readNumber();
      if (relative) {
        const isX = offset % 2 === 0;
        values.push(value + (isX ? currentPoint[0] : currentPoint[1]));
      } else {
        values.push(value);
      }
    }

    if (command === 'M') {
      const point: Point = [values[0], values[1]];
      segments.push({ command: 'M', points: [point] });
      currentPoint = point;
      subpathStart = point;
      // A second coordinate pair after M is an implicit lineto.
      activeCommand = 'L';
    } else if (command === 'L') {
      const point: Point = [values[0], values[1]];
      segments.push({ command: 'L', points: [point] });
      currentPoint = point;
    } else if (command === 'Q') {
      const control: Point = [values[0], values[1]];
      const point: Point = [values[2], values[3]];
      segments.push({ command: 'Q', points: [control, point] });
      currentPoint = point;
    } else if (command === 'C') {
      const control1: Point = [values[0], values[1]];
      const control2: Point = [values[2], values[3]];
      const point: Point = [values[4], values[5]];
      segments.push({ command: 'C', points: [control1, control2, point] });
      currentPoint = point;
    }
  }

  return segments;
}

function segmentEnd(segment: StrokeSegment): Point {
  return segment.points[segment.points.length - 1];
}

function segmentStart(segment: StrokeSegment, previous: Point): Point {
  return segment.command === 'M' ? segment.points[0] : previous;
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function evaluateSegment(
  segment: StrokeSegment,
  start: Point,
  t: number,
): Point {
  if (segment.command === 'M' || segment.command === 'L') {
    const end = segment.points[0];
    return [start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t];
  }
  if (segment.command === 'Q') {
    const [control, end] = segment.points;
    const mt = 1 - t;
    return [
      mt * mt * start[0] + 2 * mt * t * control[0] + t * t * end[0],
      mt * mt * start[1] + 2 * mt * t * control[1] + t * t * end[1],
    ];
  }
  const [control1, control2, end] = segment.points;
  const mt = 1 - t;
  return [
    mt ** 3 * start[0] +
      3 * mt * mt * t * control1[0] +
      3 * mt * t * t * control2[0] +
      t ** 3 * end[0],
    mt ** 3 * start[1] +
      3 * mt * mt * t * control1[1] +
      3 * mt * t * t * control2[1] +
      t ** 3 * end[1],
  ];
}

/**
 * Sample a parsed path at equal arc-length intervals.  At least 50 samples are
 * always produced (the default is 100), matching the RTL invariant.
 */
export function samplePathPoints(
  segments: StrokeSegment[],
  sampleCount: number = RTL_SAMPLE_COUNT,
): Point[] {
  const drawing = segments.filter((segment) => segment.command !== 'M');
  if (drawing.length === 0) {
    return [];
  }

  const dense: Point[] = [];
  let current: Point = segments[0].points[0];
  for (const segment of segments) {
    if (segment.command === 'M') {
      current = segment.points[0];
      dense.push(current);
      continue;
    }
    const start = current;
    const steps = 32;
    for (let step = 1; step <= steps; step += 1) {
      dense.push(evaluateSegment(segment, start, step / steps));
    }
    current = segmentEnd(segment);
  }

  if (dense.length < 2) {
    return dense;
  }

  const cumulative: number[] = [0];
  for (let index = 1; index < dense.length; index += 1) {
    cumulative.push(
      cumulative[index - 1] + distance(dense[index - 1], dense[index]),
    );
  }
  const total = cumulative[cumulative.length - 1];
  if (total <= EPS) {
    return [dense[0]];
  }

  const count = Math.max(50, Math.floor(sampleCount));
  const result: Point[] = [];
  let cursor = 0;
  for (let sample = 0; sample < count; sample += 1) {
    const target = (total * sample) / (count - 1);
    while (cursor + 1 < cumulative.length && cumulative[cursor + 1] < target) {
      cursor += 1;
    }
    if (cursor + 1 >= cumulative.length) {
      result.push(dense[dense.length - 1]);
      continue;
    }
    const span = cumulative[cursor + 1] - cumulative[cursor];
    const fraction = span <= EPS ? 0 : (target - cumulative[cursor]) / span;
    const a = dense[cursor];
    const b = dense[cursor + 1];
    result.push([
      a[0] + (b[0] - a[0]) * fraction,
      a[1] + (b[1] - a[1]) * fraction,
    ]);
  }
  return result;
}

function computeRtlRatio(samples: Point[]): number {
  if (samples.length < 2) {
    return 0;
  }
  let totalLength = 0;
  let compliantLength = 0;
  for (let index = 1; index < samples.length; index += 1) {
    const previous = samples[index - 1];
    const current = samples[index];
    const dx = current[0] - previous[0];
    const dy = current[1] - previous[1];
    const length = Math.hypot(dx, dy);
    totalLength += length;
    // Right-to-left means moving left, or descending vertically for letters
    // such as alef.  A flat LTR horizontal move satisfies neither condition.
    if (dx <= EPS || dy < -EPS) {
      compliantLength += length;
    }
  }
  return totalLength <= EPS ? 0 : compliantLength / totalLength;
}

/**
 * Verify a welded baseline path: one move command, C0 continuity, and at least
 * 85% right-to-left motion measured along the arc length.
 */
export function assertPawContinuity(svgPathD: string): PawContinuityResult {
  const errors: string[] = [];
  let segments: StrokeSegment[] = [];
  try {
    segments = parseSvgPath(svgPathD);
  } catch (error) {
    return {
      valid: false,
      rtlRatio: 0,
      singleMove: false,
      c0Continuous: false,
      errors: [
        `Failed to parse SVG path: ${
          error instanceof Error ? error.message : String(error)
        }`,
      ],
    };
  }

  const moveIndices = segments
    .map((segment, index) => (segment.command === 'M' ? index : -1))
    .filter((index) => index >= 0);
  const singleMove =
    moveIndices.length === 1 && moveIndices[0] === 0 && segments.length > 1;
  if (!singleMove) {
    errors.push(
      `Expected exactly one 'M' command at index 0; found ${moveIndices.length} ` +
        `move command(s) at ${JSON.stringify(moveIndices)}`,
    );
  }

  let c0Continuous = segments.length > 1;
  let previousEnd: Point | null = null;
  for (let index = 0; index < segments.length; index += 1) {
    const segment = segments[index];
    const start = previousEnd
      ? segmentStart(segment, previousEnd)
      : segment.points[0];
    if (previousEnd && distance(previousEnd, start) > CONTINUITY_TOLERANCE) {
      c0Continuous = false;
      errors.push(
        `C0 discontinuity before segment ${index} (${segment.command}): ` +
          `expected (${previousEnd[0]}, ${previousEnd[1]}), ` +
          `got (${start[0]}, ${start[1]})`,
      );
    }
    previousEnd = segmentEnd(segment);
  }

  const samples = samplePathPoints(segments, RTL_SAMPLE_COUNT);
  const rtlRatio = computeRtlRatio(samples);
  if (samples.length < 50) {
    errors.push(
      `RTL check requires at least 50 samples; got ${samples.length}`,
    );
  }
  if (rtlRatio < RTL_MIN_RATIO) {
    errors.push(
      `RTL monotonicity failed: ${(rtlRatio * 100).toFixed(2)}% of arc length ` +
        `moves right-to-left (minimum ${(RTL_MIN_RATIO * 100).toFixed(0)}%)`,
    );
  }

  return {
    valid: errors.length === 0,
    rtlRatio,
    singleMove,
    c0Continuous,
    errors,
  };
}

function overlaps(first: TimelineItem, second: TimelineItem): boolean {
  return (
    first.startTime < second.endTime - EPS &&
    second.startTime < first.endTime - EPS
  );
}

/**
 * Verify delayed-stroke causality:
 *   1. each paw's trunk finishes before any of its delayed strokes start;
 *   2. all strokes of paw k finish before paw k+1's trunk starts;
 *   3. no negative durations and no overlapping delayed strokes.
 */
export function assertDelayedStrokeCausality(
  timeline: AnimationTimeline,
): CausalityResult {
  const errors: string[] = [];

  if (!timeline || !Array.isArray(timeline.paws) || !Array.isArray(timeline.items)) {
    return { valid: false, errors: ['Timeline must contain paws and items arrays'] };
  }

  const pawById = new Map(timeline.paws.map((paw) => [paw.id, paw]));
  const itemsByPaw = new Map<string, TimelineItem[]>();
  for (const item of timeline.items) {
    if (!Number.isFinite(item.startTime) || !Number.isFinite(item.endTime)) {
      errors.push(`Item '${item.strokeId}' has non-finite timestamps`);
      continue;
    }
    if (item.endTime < item.startTime - EPS) {
      errors.push(
        `Item '${item.strokeId}' has negative duration ` +
          `(${item.startTime} -> ${item.endTime})`,
      );
    }
    if (!pawById.has(item.pawId)) {
      errors.push(`Item '${item.strokeId}' references unknown paw '${item.pawId}'`);
      continue;
    }
    const existing = itemsByPaw.get(item.pawId) ?? [];
    existing.push(item);
    itemsByPaw.set(item.pawId, existing);
  }

  const trunks = new Map<string, TimelineItem>();
  for (const paw of timeline.paws) {
    const items = itemsByPaw.get(paw.id) ?? [];
    const pawTrunks = items.filter((item) => item.type === 'trunk');
    if (pawTrunks.length !== 1) {
      errors.push(
        `Paw '${paw.id}' must have exactly one trunk timeline item; ` +
          `found ${pawTrunks.length}`,
      );
    } else {
      trunks.set(paw.id, pawTrunks[0]);
    }

    const delayed = items.filter((item) => item.type === 'delayed');
    const trunk = pawTrunks[0];

    if (trunk) {
      for (const item of delayed) {
        if (trunk.endTime > item.startTime + CONTINUITY_TOLERANCE) {
          errors.push(
            `Delayed stroke '${item.strokeId}' starts at ${item.startTime} ` +
              `before paw '${paw.id}' trunk finishes at ${trunk.endTime}`,
          );
        }
      }
    }

    const sortedDelayed = [...delayed].sort(
      (a, b) => a.startTime - b.startTime || a.endTime - b.endTime,
    );
    for (let index = 1; index < sortedDelayed.length; index += 1) {
      if (overlaps(sortedDelayed[index - 1], sortedDelayed[index])) {
        errors.push(
          `Delayed strokes '${sortedDelayed[index - 1].strokeId}' and ` +
            `'${sortedDelayed[index].strokeId}' overlap within paw '${paw.id}'`,
        );
      }
    }
  }

  for (let index = 0; index < timeline.paws.length - 1; index += 1) {
    const paw = timeline.paws[index];
    const nextPaw = timeline.paws[index + 1];
    const nextTrunk = trunks.get(nextPaw.id);
    if (!nextTrunk) {
      continue;
    }
    const items = itemsByPaw.get(paw.id) ?? [];
    for (const item of items) {
      if (item.endTime > nextTrunk.startTime + CONTINUITY_TOLERANCE) {
        errors.push(
          `Item '${item.strokeId}' from paw '${paw.id}' ends at ` +
            `${item.endTime}, after paw '${nextPaw.id}' trunk starts at ` +
            `${nextTrunk.startTime}`,
        );
      }
    }
  }

  return { valid: errors.length === 0, errors };
}
