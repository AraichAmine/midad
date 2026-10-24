/**
 * Spatial-temporal animation timeline scheduler for Midad.
 *
 * Enforces strict calligraphic causality:
 * 1. Each PAW baseline trunk completes before its delayed strokes begin.
 * 2. All delayed strokes within a PAW finish before the next PAW begins.
 * 3. Speeds and durations are proportionally calibrated by arc-length.
 */

import type {
  AnimationTimeline,
  DelayedStrokeData,
  Paw,
  PawData,
  Point,
  Stroke,
  TimelineItem,
  WordData,
} from './types';
import { assertDelayedStrokeCausality } from './validator';

export interface BoundingBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  width: number;
  height: number;
  viewBox: string;
}

export interface ScheduledAnimation {
  timeline: AnimationTimeline;
  boundingBox: BoundingBox;
}

export interface SchedulerOptions {
  speed?: number; // font units per second (default: 1500)
  duration?: number; // total duration in milliseconds (if provided, overrides speed)
  pauseBetweenStrokes?: number; // ms pause between consecutive strokes within a PAW (default: 40)
  pauseBetweenPaws?: number; // ms pause between consecutive PAWs (default: 100)
  padding?: number; // viewBox padding in font units (default: 50)
}

const DEFAULT_SPEED = 1500; // font units per second
const DEFAULT_PAUSE_STROKES = 40; // ms
const DEFAULT_PAUSE_PAWS = 100; // ms
const DEFAULT_PADDING = 60; // font units
const NUMBER_PATTERN = /[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g;

/**
 * Approximate the Euclidean arc-length of a list of 2D points.
 */
export function computePointsLength(points: Point[]): number {
  if (!points || points.length < 2) return 0;
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i][0] - points[i - 1][0];
    const dy = points[i][1] - points[i - 1][1];
    total += Math.hypot(dx, dy);
  }
  return total;
}

/**
 * Convert a point sequence to an SVG path data string (`M ... L ...`).
 */
export function pointsToSvgPath(points: Point[]): string {
  if (!points || points.length === 0) return '';
  const first = points[0];
  const parts = [`M ${first[0].toFixed(2)} ${first[1].toFixed(2)}`];
  for (let i = 1; i < points.length; i++) {
    parts.push(`L ${points[i][0].toFixed(2)} ${points[i][1].toFixed(2)}`);
  }
  return parts.join(' ');
}

/**
 * Calculate the bounding box of a word including all trunk and delayed strokes.
 */
export function computeWordBoundingBox(word: WordData, padding: number = DEFAULT_PADDING): BoundingBox {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const paw of word.paws) {
    // 1. Trunk stroke coordinates
    if (paw.trunkStroke?.d) {
      const numbers = paw.trunkStroke.d.match(NUMBER_PATTERN);
      if (numbers) {
        for (let i = 0; i < numbers.length - 1; i += 2) {
          const x = parseFloat(numbers[i]);
          const y = parseFloat(numbers[i + 1]);
          if (Number.isFinite(x) && Number.isFinite(y)) {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }
    }

    // 2. Delayed strokes coordinates
    if (paw.delayedStrokes) {
      for (const ds of paw.delayedStrokes) {
        if (ds.points) {
          for (const [x, y] of ds.points) {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        } else if (ds.d) {
          const numbers = ds.d.match(NUMBER_PATTERN);
          if (numbers) {
            for (let i = 0; i < numbers.length - 1; i += 2) {
              const x = parseFloat(numbers[i]);
              const y = parseFloat(numbers[i + 1]);
              if (Number.isFinite(x) && Number.isFinite(y)) {
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
              }
            }
          }
        }
      }
    }
  }

  // Fallback defaults if empty
  if (!Number.isFinite(minX) || !Number.isFinite(maxX)) {
    minX = 0;
    minY = -200;
    maxX = 1000;
    maxY = 800;
  }

  const paddedMinX = minX - padding;
  const paddedMinY = minY - padding;
  const paddedMaxX = maxX + padding;
  const paddedMaxY = maxY + padding;
  const width = Math.max(100, paddedMaxX - paddedMinX);
  const height = Math.max(100, paddedMaxY - paddedMinY);

  // Note: For font coordinate systems where y is positive upwards,
  // the SVG viewBox with transform="scale(1, -1)" is: minX -maxY width height
  const viewBox = `${paddedMinX.toFixed(1)} ${(-paddedMaxY).toFixed(1)} ${width.toFixed(1)} ${height.toFixed(1)}`;

  return {
    minX: paddedMinX,
    minY: paddedMinY,
    maxX: paddedMaxX,
    maxY: paddedMaxY,
    width,
    height,
    viewBox,
  };
}

/**
 * Normalizes PAW data into standard Paw objects with typed strokes.
 */
export function normalizePaws(pawsData: PawData[]): Paw[] {
  return pawsData.map((pd, pawIndex) => {
    const pawId = pd.id || `paw_${pawIndex}`;

    const trunkStroke: Stroke = {
      id: pd.trunkStroke?.id || `${pawId}_trunk`,
      d: pd.trunkStroke.d,
      length: pd.trunkStroke.length || 100,
      type: 'trunk',
      startPoint: pd.trunkStroke.startPoint,
      endPoint: pd.trunkStroke.endPoint,
    };

    const delayedStrokes: Stroke[] = (pd.delayedStrokes || []).map((ds, dsIndex) => {
      const strokeId = ds.id || `${pawId}_delayed_${dsIndex}`;
      const d = ds.d || (ds.points ? pointsToSvgPath(ds.points) : '');
      const length = ds.length || (ds.points ? computePointsLength(ds.points) : 50);

      return {
        id: strokeId,
        d,
        length,
        type: 'dot',
      };
    });

    const secondaryStrokes: Stroke[] = (pd.secondaryStrokes || []).map((ss, ssIndex) => {
      const strokeId = ss.id || `${pawId}_secondary_${ssIndex}`;
      return {
        id: strokeId,
        d: ss.d,
        length: ss.length || 100,
        type: 'secondary',
      };
    });

    return {
      id: pawId,
      trunkStroke,
      delayedStrokes,
      secondaryStrokes,
    };
  });
}

/**
 * Builds an AnimationTimeline with causal guarantees and calibrated timestamps.
 */
export function buildTimeline(
  word: WordData,
  options: SchedulerOptions = {},
): ScheduledAnimation {
  const paws = normalizePaws(word.paws);
  const pauseBetweenStrokes = (options.pauseBetweenStrokes ?? DEFAULT_PAUSE_STROKES) / 1000.0;
  const pauseBetweenPaws = (options.pauseBetweenPaws ?? DEFAULT_PAUSE_PAWS) / 1000.0;
  const speed = options.speed ?? DEFAULT_SPEED; // font units per second

  // 1. Calculate total length across all strokes
  let totalLength = 0;
  for (const paw of paws) {
    totalLength += paw.trunkStroke.length;
    for (const ss of paw.secondaryStrokes || []) {
      totalLength += ss.length;
    }
    for (const ds of paw.delayedStrokes) {
      totalLength += ds.length;
    }
  }

  // 2. Determine duration scaling
  const hasFixedDuration = typeof options.duration === 'number' && options.duration > 0;
  const totalTargetDrawingSec = hasFixedDuration ? options.duration! / 1000.0 : totalLength / speed;

  const getDuration = (length: number): number => {
    if (totalLength <= 0) return 0.1;
    if (hasFixedDuration) {
      return (length / totalLength) * totalTargetDrawingSec;
    }
    return Math.max(0.02, length / speed);
  };

  // 3. Assemble timeline items sequentially
  const items: TimelineItem[] = [];
  let currentTime = 0.0;

  for (let pawIdx = 0; pawIdx < paws.length; pawIdx++) {
    const paw = paws[pawIdx];

    // Step A: Trunk Stroke
    const trunkDuration = getDuration(paw.trunkStroke.length);
    const trunkStart = currentTime;
    const trunkEnd = trunkStart + trunkDuration;
    items.push({
      strokeId: paw.trunkStroke.id,
      pawId: paw.id,
      type: 'trunk',
      startTime: trunkStart,
      endTime: trunkEnd,
    });
    currentTime = trunkEnd;

    // Step B: Secondary Strokes (e.g. Tah/Zah upright masts)
    if (paw.secondaryStrokes && paw.secondaryStrokes.length > 0) {
      for (const ss of paw.secondaryStrokes) {
        currentTime += pauseBetweenStrokes;
        const secDuration = getDuration(ss.length);
        const secStart = currentTime;
        const secEnd = secStart + secDuration;
        items.push({
          strokeId: ss.id,
          pawId: paw.id,
          type: 'secondary',
          startTime: secStart,
          endTime: secEnd,
        });
        currentTime = secEnd;
      }
    }

    // Step C: Delayed Strokes (Dots, Hamza, Madda, Kaf mark)
    if (paw.delayedStrokes.length > 0) {
      for (const ds of paw.delayedStrokes) {
        currentTime += pauseBetweenStrokes;
        const dotDuration = getDuration(ds.length);
        const dotStart = currentTime;
        const dotEnd = dotStart + dotDuration;
        items.push({
          strokeId: ds.id,
          pawId: paw.id,
          type: 'delayed',
          startTime: dotStart,
          endTime: dotEnd,
        });
        currentTime = dotEnd;
      }
    }

    // Inter-PAW pause before next letter group
    if (pawIdx < paws.length - 1) {
      currentTime += pauseBetweenPaws;
    }
  }

  const timeline: AnimationTimeline = {
    paws,
    items,
    totalDuration: currentTime,
  };

  // 4. Validate causality invariant
  const causality = assertDelayedStrokeCausality(timeline);
  if (!causality.valid) {
    throw new Error(`Timeline causality failure: ${causality.errors.join('; ')}`);
  }

  const boundingBox = computeWordBoundingBox(word, options.padding);

  return {
    timeline,
    boundingBox,
  };
}
