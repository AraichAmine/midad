/**
 * Midad Engine — Public Entry Point
 */

export { Midad, default } from './midad';
export { MidadRenderer } from './renderer';
export {
  buildTimeline,
  computePointsLength,
  computeWordBoundingBox,
  normalizePaws,
  pointsToSvgPath,
  type BoundingBox,
  type ScheduledAnimation,
  type SchedulerOptions,
} from './scheduler';
export * from './types';
export * from './validator';
