/**
 * SVG handwriting animation renderer for Midad.
 *
 * Implements smooth SVG stroke-dashoffset drawing with requestAnimationFrame,
 * calligraphic styling, precise playback control, and lifecycle event dispatch.
 */

import type {
  AnimationTimeline,
  MidadEventType,
  MidadOptions,
  PlaybackState,
  TimelineItem,
} from './types';
import type { BoundingBox, ScheduledAnimation } from './scheduler';

export interface StrokeElementMap {
  pathElement: SVGPathElement;
  item: TimelineItem;
  length: number;
}

export type RendererEventCallback = (eventName: MidadEventType, data?: any) => void;

export class MidadRenderer {
  public container: HTMLElement;
  public svgElement: SVGSVGElement | null = null;
  public viewportGroup: SVGGElement | null = null;
  public state: PlaybackState = 'idle';

  private scheduled: ScheduledAnimation;
  private options: MidadOptions;
  private strokeMap: Map<string, StrokeElementMap> = new Map();
  private rafId: number | null = null;
  private lastTimestamp: number | null = null;
  private currentTime: number = 0; // seconds
  private speedMultiplier: number = 1.0;
  private onEvent?: RendererEventCallback;

  // Active tracking for lifecycle events
  private activeStrokes: Set<string> = new Set();
  private completedStrokes: Set<string> = new Set();
  private activePaws: Set<string> = new Set();
  private completedPaws: Set<string> = new Set();

  constructor(
    container: HTMLElement,
    scheduled: ScheduledAnimation,
    options: MidadOptions = {},
    onEvent?: RendererEventCallback,
  ) {
    this.container = container;
    this.scheduled = scheduled;
    this.options = {
      strokeWidth: 28.0,
      color: '#06b6d4',
      autoAnimation: true,
      nibAngle: -45,
      ...options,
    };
    this.onEvent = onEvent;

    this.initDOM();
  }

  /**
   * Initialize SVG DOM structure inside the container.
   */
  private initDOM(): void {
    const { boundingBox, timeline } = this.scheduled;

    // Create SVG element
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', boundingBox.viewBox);
    svg.setAttribute('class', 'midad-svg');
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.overflow = 'visible';
    svg.style.display = 'block';

    // Defs for optional calligraphic filters/shadows
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    svg.appendChild(defs);

    // Viewport group inverted on Y axis to match font coordinates
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', 'midad-viewport');
    g.setAttribute('transform', 'scale(1, -1)');
    svg.appendChild(g);

    const baseColor = this.options.color || '#06b6d4';
    const strokeWidth = this.options.strokeWidth || 28.0;

    // Build stroke paths for all paws
    for (const paw of timeline.paws) {
      // 1. Trunk Path
      if (paw.trunkStroke?.d) {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('id', paw.trunkStroke.id);
        path.setAttribute('class', 'midad-stroke midad-trunk');
        path.setAttribute('d', paw.trunkStroke.d);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke', baseColor);
        path.setAttribute('stroke-width', strokeWidth.toString());
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        g.appendChild(path);
      }

      // 2. Secondary Paths (e.g. Tah/Zah upright masts)
      for (const ss of paw.secondaryStrokes || []) {
        if (ss.d) {
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('id', ss.id);
          path.setAttribute('class', 'midad-stroke midad-secondary');
          path.setAttribute('d', ss.d);
          path.setAttribute('fill', 'none');
          path.setAttribute('stroke', baseColor);
          path.setAttribute('stroke-width', (strokeWidth * 0.9).toString());
          path.setAttribute('stroke-linecap', 'round');
          path.setAttribute('stroke-linejoin', 'round');
          g.appendChild(path);
        }
      }

      // 3. Delayed Strokes (dots, hamza, madda)
      for (const ds of paw.delayedStrokes) {
        if (ds.d) {
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('id', ds.id);
          path.setAttribute('class', 'midad-stroke midad-delayed');
          path.setAttribute('d', ds.d);
          path.setAttribute('fill', 'none');
          // Dot color can match trunk or role
          path.setAttribute('stroke', baseColor);
          path.setAttribute('stroke-width', (strokeWidth * 1.05).toString());
          path.setAttribute('stroke-linecap', 'round');
          path.setAttribute('stroke-linejoin', 'round');
          g.appendChild(path);
        }
      }
    }

    this.container.appendChild(svg);
    this.svgElement = svg;
    this.viewportGroup = g;

    // Cache lengths and initialize dash offsets
    for (const item of timeline.items) {
      const el = g.querySelector<SVGPathElement>(`#${CSS.escape(item.strokeId)}`);
      if (el) {
        let length = item.strokeId.includes('delayed') ? 60 : 300;
        try {
          if (typeof el.getTotalLength === 'function') {
            const measured = el.getTotalLength();
            if (measured > 0) length = measured;
          }
        } catch {
          // Fallback in headless environment without layout engine
        }

        // Initially hidden
        el.style.strokeDasharray = `${length} ${length}`;
        el.style.strokeDashoffset = `${length}`;

        this.strokeMap.set(item.strokeId, {
          pathElement: el,
          item,
          length,
        });
      }
    }
  }

  /**
   * Start or resume animation playback.
   */
  public play(): void {
    if (this.state === 'playing') return;

    if (this.currentTime >= this.scheduled.timeline.totalDuration) {
      this.reset();
    }

    this.state = 'playing';
    this.lastTimestamp = null;
    this.emit('start', { duration: this.scheduled.timeline.totalDuration });
    this.rafId = requestAnimationFrame(this.onAnimationFrame.bind(this));
  }

  /**
   * Pause animation playback.
   */
  public pause(): void {
    if (this.state !== 'playing') return;
    this.state = 'paused';
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  /**
   * Resume animation from paused state.
   */
  public resume(): void {
    if (this.state === 'paused') {
      this.play();
    }
  }

  /**
   * Reset animation back to initial state.
   */
  public reset(): void {
    this.pause();
    this.currentTime = 0;
    this.activeStrokes.clear();
    this.completedStrokes.clear();
    this.activePaws.clear();
    this.completedPaws.clear();

    for (const { pathElement, length } of this.strokeMap.values()) {
      pathElement.style.strokeDashoffset = `${length}`;
    }

    this.state = 'idle';
  }

  /**
   * Restart animation from beginning.
   */
  public restart(): void {
    this.reset();
    this.play();
  }

  /**
   * Seek to a specific progress fraction in [0, 1].
   */
  public seek(progress: number): void {
    const clamped = Math.max(0, Math.min(1, progress));
    this.currentTime = clamped * this.scheduled.timeline.totalDuration;
    this.updateStrokes(this.currentTime);

    this.emit('progress', {
      currentTime: this.currentTime,
      totalDuration: this.scheduled.timeline.totalDuration,
      progress: clamped,
    });
  }

  /**
   * Set playback speed multiplier (e.g. 0.5x, 1.0x, 2.0x).
   */
  public setSpeed(multiplier: number): void {
    if (multiplier > 0) {
      this.speedMultiplier = multiplier;
    }
  }

  /**
   * Main requestAnimationFrame tick callback.
   */
  private onAnimationFrame(now: number): void {
    if (this.state !== 'playing') return;

    if (this.lastTimestamp === null) {
      this.lastTimestamp = now;
    }

    const deltaSec = ((now - this.lastTimestamp) / 1000.0) * this.speedMultiplier;
    this.lastTimestamp = now;
    this.currentTime += deltaSec;

    const totalDuration = this.scheduled.timeline.totalDuration;
    const progress = Math.min(1.0, totalDuration > 0 ? this.currentTime / totalDuration : 1.0);

    this.updateStrokes(this.currentTime);

    this.emit('progress', {
      currentTime: Math.min(this.currentTime, totalDuration),
      totalDuration,
      progress,
    });

    if (this.currentTime >= totalDuration) {
      this.state = 'completed';
      this.rafId = null;
      this.emit('complete');
      return;
    }

    this.rafId = requestAnimationFrame(this.onAnimationFrame.bind(this));
  }

  /**
   * Update all path dash offsets and trigger lifecycle events based on time t.
   */
  private updateStrokes(t: number): void {
    const { timeline } = this.scheduled;

    for (const item of timeline.items) {
      const entry = this.strokeMap.get(item.strokeId);
      if (!entry) continue;

      const { pathElement, length } = entry;
      const { startTime, endTime, pawId, strokeId } = item;

      // PAW start event check
      if (t >= startTime && !this.activePaws.has(pawId)) {
        this.activePaws.add(pawId);
        this.emit('pawStart', { pawId });
      }

      if (t <= startTime) {
        // Not started yet
        pathElement.style.strokeDashoffset = `${length}`;
      } else if (t >= endTime) {
        // Fully drawn
        pathElement.style.strokeDashoffset = '0';

        // Stroke end event
        if (this.activeStrokes.has(strokeId) && !this.completedStrokes.has(strokeId)) {
          this.activeStrokes.delete(strokeId);
          this.completedStrokes.add(strokeId);
          this.emit('strokeEnd', { strokeId, pawId });
        }
      } else {
        // Actively animating
        if (!this.activeStrokes.has(strokeId)) {
          this.activeStrokes.add(strokeId);
          this.emit('strokeStart', { strokeId, pawId });
        }

        const span = Math.max(0.001, endTime - startTime);
        const fraction = (t - startTime) / span;
        const offset = Math.max(0, length * (1.0 - fraction));
        pathElement.style.strokeDashoffset = `${offset.toFixed(2)}`;
      }
    }

    // Check PAW completions
    for (const paw of timeline.paws) {
      if (this.activePaws.has(paw.id) && !this.completedPaws.has(paw.id)) {
        const pawItems = timeline.items.filter((it) => it.pawId === paw.id);
        const allDone = pawItems.every((it) => t >= it.endTime);
        if (allDone) {
          this.completedPaws.add(paw.id);
          this.emit('pawEnd', { pawId: paw.id });
        }
      }
    }
  }

  /**
   * Dispatch lifecycle event to listener.
   */
  private emit(event: MidadEventType, data?: any): void {
    if (this.onEvent) {
      this.onEvent(event, data);
    }
  }

  /**
   * Destroy renderer and remove created SVG elements.
   */
  public destroy(): void {
    this.pause();
    if (this.svgElement && this.svgElement.parentNode) {
      this.svgElement.parentNode.removeChild(this.svgElement);
    }
    this.strokeMap.clear();
    this.svgElement = null;
    this.viewportGroup = null;
  }
}
