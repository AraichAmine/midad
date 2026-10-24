/**
 * Core geometry and animation data structures shared by the rendering engine.
 *
 * Coordinates are in SVG user units (the same coordinate system as the source
 * font), with y increasing upwards unless a caller explicitly flips the axis.
 */

export type Point = [number, number];

/**
 * A single parsed SVG path command.
 *
 * For ``M`` and ``L`` the points array contains the destination point.  For
 * ``C`` it contains [control1, control2, destination] and for ``Q`` it contains
 * [control, destination].  The start point is implicit: it is the end point of
 * the preceding segment.
 */
export interface StrokeSegment {
  command: 'M' | 'C' | 'L' | 'Q';
  points: Point[];
}

export type StrokeType = 'trunk' | 'dot' | 'tashkeel';

export interface Stroke {
  id: string;
  d: string;
  length: number;
  type: StrokeType;
}

/** A "paw" is one connected glyph body plus its delayed dot/tashkeel strokes. */
export interface Paw {
  id: string;
  trunkStroke: Stroke;
  delayedStrokes: Stroke[];
}

export type TimelineItemType = 'trunk' | 'delayed';

export interface TimelineItem {
  strokeId: string;
  pawId: string;
  type: TimelineItemType;
  startTime: number;
  endTime: number;
}

export interface AnimationTimeline {
  paws: Paw[];
  items: TimelineItem[];
  totalDuration: number;
}
