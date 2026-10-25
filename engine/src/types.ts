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

export type StrokeType = 'trunk' | 'dot' | 'tashkeel' | 'secondary';

export interface Stroke {
  id: string;
  d: string;
  length: number;
  type: StrokeType;
  startPoint?: Point;
  endPoint?: Point;
}

/** Delayed mark stroke data representation (dots, hamza, madda, kaf marks). */
export interface DelayedStrokeData {
  id?: string;
  role: 'dot' | 'hamza' | 'madda' | 'inner_mark';
  attachment_s?: number;
  attachment_point?: Point;
  centroid?: Point;
  points?: Point[];
  d?: string;
  length?: number;
}

/** A "paw" is one connected glyph body plus its delayed dot/tashkeel strokes. */
export interface Paw {
  id: string;
  trunkStroke: Stroke;
  delayedStrokes: Stroke[];
  secondaryStrokes?: Stroke[];
}

/** Extended PAW data as stored in golden font fixtures. */
export interface PawData {
  id: string;
  letters?: string;
  trunkStroke: Stroke;
  delayedStrokes: DelayedStrokeData[];
  secondaryStrokes?: Stroke[];
}

export type TimelineItemType = 'trunk' | 'delayed' | 'secondary';

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

/** Word-level data from golden font fixtures or runtime shaper. */
export interface WordData {
  text: string;
  paws: PawData[];
  timeline?: AnimationTimeline;
  items?: TimelineItem[];
  totalDuration?: number;
  viewBox?: string;
  vb?: [number, number, number, number];
}

/** Font JSON data structure containing catalogue of words. */
export interface FontData {
  font?: string;
  total_glyphs?: number;
  num_words?: number;
  words?: WordData[];
  glyphs?: Record<string, any>;
}

/** Configuration options for the Midad engine. */
export interface MidadOptions {
  fontSize?: number;
  strokeWidth?: number;
  color?: string;
  duration?: number; // Total duration in ms (if set, overrides speed)
  speed?: number; // Drawing speed in font units per second (default: 1500)
  autoAnimation?: boolean; // Whether to play immediately upon load (default: true)
  queued?: boolean; // Play multiple texts sequentially (default: true)
  textAlign?: 'right' | 'center' | 'left';
  pauseBetweenStrokes?: number; // Delay between consecutive strokes in ms (default: 50)
  pauseBetweenPaws?: number; // Delay between consecutive PAWs in ms (default: 100)
  calligraphicNib?: boolean; // Simulate calligraphic qalam angle (default: false)
  nibAngle?: number; // Qalam nib angle in degrees (default: -45)
  minStrokeWidth?: number;
  maxStrokeWidth?: number;
}

/** Specification for a single text element in Midad. */
export interface MidadTextSpec {
  text: string;
  fontSize?: number;
  strokeWidth?: number;
  color?: string;
  duration?: number;
  speed?: number;
  delay?: number;
  id?: string;
  y?: number;
  x?: number;
  textAlign?: 'right' | 'center' | 'left';
  pauseBetweenStrokes?: number;
  pauseBetweenPaws?: number;
}

export type PlaybackState = 'idle' | 'playing' | 'paused' | 'completed';

export type MidadEventType =
  | 'ready'
  | 'start'
  | 'pawStart'
  | 'pawEnd'
  | 'strokeStart'
  | 'strokeEnd'
  | 'progress'
  | 'complete'
  | 'animationEnd'
  | 'warning';

export type MidadEventHandler = (data?: any) => void;
