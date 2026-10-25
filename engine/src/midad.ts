/**
 * Midad — Open-Source Arabic Handwriting Animation Engine
 * Modeled after Vara.js, designed specifically for right-to-left (RTL) cursive
 * script with continuous baseline welding and causal delayed-stroke scheduling.
 *
 * Public API:
 *   const midad = new Midad('#container', fontJsonUrl, [
 *     { text: 'كتب', strokeWidth: 24, color: '#06b6d4' }
 *   ], options);
 */

import { buildTimeline, type ScheduledAnimation } from './scheduler';
import { MidadRenderer } from './renderer';
import { shapeArabicText } from './shaper';
import type {
  FontData,
  MidadEventHandler,
  MidadEventType,
  MidadOptions,
  MidadTextSpec,
  PlaybackState,
  WordData,
} from './types';

export class Midad {
  public container: HTMLElement;
  public fontData: FontData | null = null;
  public options: MidadOptions;
  public texts: MidadTextSpec[] = [];
  public currentWordIndex: number = 0;
  public renderer: MidadRenderer | null = null;
  public isReady: boolean = false;

  private listeners: Map<MidadEventType, Set<MidadEventHandler>> = new Map();
  private scheduledWords: ScheduledAnimation[] = [];

  constructor(
    container: string | HTMLElement,
    fontDataOrUrl: string | FontData | WordData,
    texts: string | MidadTextSpec | (string | MidadTextSpec)[],
    options: MidadOptions = {},
  ) {
    // 1. Resolve container element
    if (typeof container === 'string') {
      const el = document.querySelector<HTMLElement>(container);
      if (!el) {
        throw new Error(`Midad: Container element '${container}' not found in DOM`);
      }
      this.container = el;
    } else {
      this.container = container;
    }

    // 2. Normalize options
    this.options = {
      autoAnimation: true,
      queued: true,
      speed: 1500,
      strokeWidth: 28.0,
      color: '#06b6d4',
      pauseBetweenStrokes: 40,
      pauseBetweenPaws: 100,
      ...options,
    };

    // 3. Normalize texts array
    const rawTexts = Array.isArray(texts) ? texts : [texts];
    this.texts = rawTexts.map((item, idx) => {
      if (typeof item === 'string') {
        return {
          text: item,
          id: `text_${idx}`,
          color: this.options.color,
          strokeWidth: this.options.strokeWidth,
        };
      }
      return {
        id: item.id || `text_${idx}`,
        color: item.color || this.options.color,
        strokeWidth: item.strokeWidth || this.options.strokeWidth,
        ...item,
      };
    });

    // 4. Load font data asynchronously
    this.loadFontData(fontDataOrUrl).catch((err) => {
      console.error('Midad: Failed to load font data:', err);
    });
  }

  /**
   * Load font data from an in-memory object, JSON fetch, or Node environment.
   */
  private async loadFontData(fontSource: string | FontData | WordData): Promise<void> {
    if (typeof fontSource === 'string') {
      // Check if URL or JSON string or file path
      if (fontSource.trim().startsWith('{')) {
        this.fontData = JSON.parse(fontSource) as FontData;
      } else {
        // Try fetch (browser) or dynamic import / fallback
        if (typeof fetch === 'function') {
          const resp = await fetch(fontSource);
          if (!resp.ok) {
            throw new Error(`Failed to fetch font JSON: ${resp.status} ${resp.statusText}`);
          }
          this.fontData = (await resp.json()) as FontData;
        } else {
          throw new Error('Midad: fetch is not available to load font URL');
        }
      }
    } else if ('glyphs' in fontSource) {
      this.fontData = fontSource as FontData;
    } else if ('words' in fontSource) {
      this.fontData = fontSource as FontData;
    } else if ('paws' in fontSource) {
      // Single word object passed directly
      this.fontData = {
        words: [fontSource as WordData],
      };
    } else if (typeof fontSource === 'object' && fontSource !== null && !Array.isArray(fontSource)) {
      // Direct glyph catalog object
      this.fontData = {
        glyphs: fontSource as Record<string, any>,
      };
    } else {
      throw new TypeError('Midad: Invalid font data format');
    }

    this.onFontReady();
  }

  /**
   * Prepare animations once font data is loaded.
   */
  private onFontReady(): void {
    if (!this.fontData) {
      throw new Error('Midad: Loaded font data is null');
    }

    // Map requested texts to word data
    const wordsMap = new Map<string, WordData>();
    for (const w of this.fontData.words || []) {
      wordsMap.set(w.text, w);
    }

    this.scheduledWords = [];

    for (const textSpec of this.texts) {
      let wordData = wordsMap.get(textSpec.text);

      // Attempt runtime shaping if not in pre-rendered words dictionary
      if (!wordData && this.fontData.glyphs) {
        try {
          wordData = shapeArabicText(textSpec.text, this.fontData.glyphs);
        } catch (err) {
          console.warn(`Midad: Runtime shaping failed for '${textSpec.text}':`, err);
        }
      }

      if (!wordData) {
        console.warn(`Midad: Word '${textSpec.text}' not found in font dictionary; using closest fallback`);
        // Defer the warning event so listeners registered immediately after
        // construction (e.g. in a test) can still receive it.
        queueMicrotask(() => {
          this.emit('warning', {
            code: 'WORD_NOT_FOUND',
            text: textSpec.text,
            message: `Word '${textSpec.text}' not found in font dictionary; using closest fallback`,
          });
        });
        // Use first word as graceful fallback if exact word not found
        const fallback = (this.fontData.words && this.fontData.words[0]) || null;
        if (fallback) {
          const scheduled = buildTimeline(fallback, {
            speed: textSpec.speed ?? this.options.speed,
            duration: textSpec.duration ?? this.options.duration,
            pauseBetweenStrokes: textSpec.pauseBetweenStrokes ?? this.options.pauseBetweenStrokes,
            pauseBetweenPaws: textSpec.pauseBetweenPaws ?? this.options.pauseBetweenPaws,
          });
          this.scheduledWords.push(scheduled);
        }
        continue;
      }

      const scheduled = buildTimeline(wordData, {
        speed: textSpec.speed ?? this.options.speed,
        duration: textSpec.duration ?? this.options.duration,
        pauseBetweenStrokes: textSpec.pauseBetweenStrokes ?? this.options.pauseBetweenStrokes,
        pauseBetweenPaws: textSpec.pauseBetweenPaws ?? this.options.pauseBetweenPaws,
      });

      this.scheduledWords.push(scheduled);
    }

    this.isReady = true;
    if (this.options.autoAnimation) {
      this.play(0);
    } else {
      this.mountWordRenderer(0);
    }
    this.emit('ready', { wordsCount: this.scheduledWords.length });
  }

  /**
   * Start or continue animation playback.
   */
  public play(wordIndex?: number): this {
    if (!this.isReady) {
      // Defer play until ready
      this.once('ready', () => this.play(wordIndex));
      return this;
    }

    if (typeof wordIndex === 'number' && wordIndex >= 0 && wordIndex < this.scheduledWords.length) {
      this.currentWordIndex = wordIndex;
      this.mountWordRenderer(this.currentWordIndex);
    } else if (!this.renderer) {
      this.mountWordRenderer(this.currentWordIndex);
    }

    if (this.renderer) {
      this.renderer.play();
    }

    return this;
  }

  /**
   * Mount and attach the renderer for a specific word index.
   */
  private mountWordRenderer(index: number): void {
    if (this.renderer) {
      this.renderer.destroy();
      this.renderer = null;
    }

    const scheduled = this.scheduledWords[index];
    if (!scheduled) return;

    const textSpec = this.texts[index];
    const wordOptions: MidadOptions = {
      ...this.options,
      color: textSpec?.color || this.options.color,
      strokeWidth: textSpec?.strokeWidth || this.options.strokeWidth,
    };

    this.renderer = new MidadRenderer(
      this.container,
      scheduled,
      wordOptions,
      (eventName, data) => {
        // Forward renderer events to Midad listeners
        this.emit(eventName, {
          wordIndex: index,
          wordText: textSpec?.text,
          ...data,
        });

        // Handle queued word progression
        if (eventName === 'complete') {
          // Also dispatch Vara.js compatible animationEnd event
          this.emit('animationEnd', {
            wordIndex: index,
            wordText: textSpec?.text,
            ...data,
          });

          if (this.options.queued && index + 1 < this.scheduledWords.length) {
            this.currentWordIndex = index + 1;
            // Short delay before next word
            setTimeout(() => {
              this.mountWordRenderer(this.currentWordIndex);
              this.renderer?.play();
            }, this.options.pauseBetweenPaws ?? 100);
          }
        }
      },
    );
  }

  /**
   * Pause animation playback.
   */
  public pause(): this {
    this.renderer?.pause();
    return this;
  }

  /**
   * Resume animation playback.
   */
  public resume(): this {
    this.renderer?.resume();
    return this;
  }

  /**
   * Reset animation back to initial state.
   */
  public reset(wordIndex?: number): this {
    if (typeof wordIndex === 'number' && wordIndex >= 0 && wordIndex < this.scheduledWords.length) {
      this.currentWordIndex = wordIndex;
      this.mountWordRenderer(this.currentWordIndex);
    }
    this.renderer?.reset();
    return this;
  }

  /**
   * Restart current or specified word animation from beginning.
   */
  public restart(wordIndex?: number): this {
    const targetIndex = typeof wordIndex === 'number' ? wordIndex : this.currentWordIndex;
    this.play(targetIndex);
    this.renderer?.restart();
    return this;
  }

  /**
   * Vara.js-compatible helper: register ready callback.
   */
  public ready(handler: (data?: any) => void): this {
    return this.on('ready', handler);
  }

  /**
   * Vara.js-compatible helper: register animation complete/end callback.
   */
  public animationEnd(handler: (wordIndex: number, textSpec?: MidadTextSpec) => void): this {
    return this.on('animationEnd', (data) => {
      const idx = data?.wordIndex ?? this.currentWordIndex;
      handler(idx, this.texts[idx]);
    });
  }

  /**
   * Seek current word to a progress fraction in [0, 1].
   */
  public seek(progress: number): this {
    this.renderer?.seek(progress);
    return this;
  }

  /**
   * Get current playback state.
   */
  public get state(): PlaybackState {
    return this.renderer ? this.renderer.state : 'idle';
  }

  /**
   * Get the SVG element or current renderer.
   */
  public get(index?: number): SVGSVGElement | null {
    return this.renderer?.svgElement ?? null;
  }

  /**
   * Register an event listener.
   */
  public on(event: MidadEventType, handler: MidadEventHandler): this {
    let handlers = this.listeners.get(event);
    if (!handlers) {
      handlers = new Set();
      this.listeners.set(event, handlers);
    }
    handlers.add(handler);

    // If 'ready' is registered when already ready, trigger on next microtask
    if (event === 'ready' && this.isReady) {
      queueMicrotask(() => {
        handler({ wordsCount: this.scheduledWords.length });
      });
    }

    return this;
  }

  /**
   * Register a one-time event listener.
   */
  public once(event: MidadEventType, handler: MidadEventHandler): this {
    const onceWrapper: MidadEventHandler = (data) => {
      this.off(event, onceWrapper);
      handler(data);
    };
    return this.on(event, onceWrapper);
  }

  /**
   * Remove an event listener.
   */
  public off(event: MidadEventType, handler: MidadEventHandler): this {
    const handlers = this.listeners.get(event);
    if (handlers) {
      handlers.delete(handler);
    }
    return this;
  }

  /**
   * Emit an event to all registered listeners.
   */
  private emit(event: MidadEventType, data?: any): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler(data);
        } catch (err) {
          console.error(`Midad: Error in '${event}' event listener:`, err);
        }
      }
    }
  }

  /**
   * Clean up DOM elements, timers, and listeners.
   */
  public destroy(): void {
    if (this.renderer) {
      this.renderer.destroy();
      this.renderer = null;
    }
    this.listeners.clear();
    this.scheduledWords = [];
  }
}

export default Midad;
