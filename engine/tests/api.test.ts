/**
 * MILESTONE 6: Public API & Font Packaging Verification Suite
 *
 * Verifies Midad API semantics:
 * 1. Constructor container resolution, default options merging.
 * 2. In-memory FontData, single WordData, and JSON loading.
 * 3. Text specification parsing & queue normalization.
 * 4. Playback controls (play, pause, resume, restart, reset, seek, state, get).
 * 5. Callback helpers (ready, animationEnd) and Event Emitter (on, once, off).
 * 6. BiDi fallback & graceful error recovery for missing words or non-Arabic characters.
 * 7. Distribution size gates (< 25 KB gzipped engine bundle, < 95 KB gzipped font JSON).
 */

import { describe, expect, it, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as zlib from 'zlib';

import { Midad } from '../src/midad';
import type { FontData, MidadTextSpec, WordData } from '../src/types';

// Mock sample font data with 2 canonical words for isolated fast testing
const mockSampleFont: FontData = {
  font: 'NotoNaskhArabic-Test',
  num_words: 2,
  words: [
    {
      text: 'كتب',
      paws: [
        {
          id: 'paw_0',
          letters: 'كتب',
          trunkStroke: {
            id: 'paw_0_trunk',
            d: 'M 500 100 L 400 100 L 300 100 L 200 100',
            length: 300,
            type: 'trunk',
          },
          delayedStrokes: [
            {
              id: 'paw_0_delayed_0',
              role: 'dot',
              attachment_s: 0.3,
              d: 'M 420 180 L 415 180',
              length: 10,
            },
            {
              id: 'paw_0_delayed_1',
              role: 'dot',
              attachment_s: 0.35,
              d: 'M 430 180 L 425 180',
              length: 10,
            },
          ],
        },
      ],
    },
    {
      text: 'قلم',
      paws: [
        {
          id: 'paw_0',
          letters: 'قلم',
          trunkStroke: {
            id: 'paw_0_trunk',
            d: 'M 400 120 L 300 120 L 200 50 L 150 -50',
            length: 320,
            type: 'trunk',
          },
          delayedStrokes: [
            {
              id: 'paw_0_delayed_0',
              role: 'dot',
              attachment_s: 0.2,
              d: 'M 380 200 L 375 200',
              length: 10,
            },
          ],
        },
      ],
    },
  ],
};

function createMockContainer(): HTMLElement {
  const div = document.createElement('div');
  div.id = 'midad-test-container';
  document.body.appendChild(div);
  return div;
}

describe('Milestone 6: Midad Public API', () => {
  describe('Constructor & Configuration', () => {
    it('initializes with default options and HTMLElement container', () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', {
        autoAnimation: false,
      });

      expect(midad.container).toBe(container);
      expect(midad.options.autoAnimation).toBe(false);
      expect(midad.options.speed).toBe(1500);
      expect(midad.options.strokeWidth).toBe(28.0);
      expect(midad.options.color).toBe('#06b6d4');
      expect(midad.options.queued).toBe(true);

      midad.destroy();
    });

    it('resolves container from string DOM selector', () => {
      const container = createMockContainer();
      container.id = 'custom-selector-box';

      const midad = new Midad('#custom-selector-box', mockSampleFont, 'كتب', {
        autoAnimation: false,
      });

      expect(midad.container).toBe(container);
      midad.destroy();
    });

    it('throws descriptive error if DOM selector not found', () => {
      expect(() => {
        new Midad('#non-existent-box', mockSampleFont, 'كتب');
      }).toThrow(/Container element '#non-existent-box' not found in DOM/);
    });

    it('normalizes single string text into MidadTextSpec queue', () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', {
        autoAnimation: false,
        color: '#ff0055',
        strokeWidth: 32,
      });

      expect(midad.texts).toHaveLength(1);
      expect(midad.texts[0].text).toBe('كتب');
      expect(midad.texts[0].color).toBe('#ff0055');
      expect(midad.texts[0].strokeWidth).toBe(32);

      midad.destroy();
    });

    it('normalizes array of mixed string and MidadTextSpec objects', () => {
      const container = createMockContainer();
      const texts: (string | MidadTextSpec)[] = [
        'كتب',
        { text: 'قلم', color: '#10b981', strokeWidth: 20, speed: 2000 },
      ];

      const midad = new Midad(container, mockSampleFont, texts, {
        autoAnimation: false,
      });

      expect(midad.texts).toHaveLength(2);
      expect(midad.texts[0].text).toBe('كتب');
      expect(midad.texts[0].color).toBe('#06b6d4');
      expect(midad.texts[1].text).toBe('قلم');
      expect(midad.texts[1].color).toBe('#10b981');
      expect(midad.texts[1].strokeWidth).toBe(20);
      expect(midad.texts[1].speed).toBe(2000);

      midad.destroy();
    });
  });

  describe('Font Loading & Sources', () => {
    it('accepts direct FontData object and triggers ready event', async () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', { autoAnimation: false });

      await new Promise<void>((resolve) => {
        midad.ready(() => {
          expect(midad.isReady).toBe(true);
          expect(midad.fontData).toBe(mockSampleFont);
          resolve();
        });
      });

      midad.destroy();
    });

    it('accepts single WordData object wrapped into FontData', async () => {
      const container = createMockContainer();
      const singleWord: WordData = mockSampleFont.words![0];
      const midad = new Midad(container, singleWord, 'كتب', { autoAnimation: false });

      await new Promise<void>((resolve) => {
        midad.ready(() => {
          expect(midad.isReady).toBe(true);
          expect(midad.fontData?.words).toHaveLength(1);
          expect(midad.fontData?.words?.[0]?.text).toBe('كتب');
          resolve();
        });
      });

      midad.destroy();
    });

    it('parses inline font JSON string', async () => {
      const container = createMockContainer();
      const jsonStr = JSON.stringify(mockSampleFont);
      const midad = new Midad(container, jsonStr, 'قلم', { autoAnimation: false });

      await new Promise<void>((resolve) => {
        midad.ready(() => {
          expect(midad.isReady).toBe(true);
          expect(midad.fontData?.num_words).toBe(2);
          resolve();
        });
      });

      midad.destroy();
    });
  });

  describe('Playback Controls & Methods', () => {
    it('implements play, pause, resume, reset, restart, seek, and state', async () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', { autoAnimation: false });

      await new Promise<void>((resolve) => midad.ready(resolve));

      // Initial state
      expect(midad.state).toBe('idle');
      expect(midad.get()).toBeDefined();

      // Play
      midad.play();
      expect(midad.state).toBe('playing');

      // Pause
      midad.pause();
      expect(midad.state).toBe('paused');

      // Resume
      midad.resume();
      expect(midad.state).toBe('playing');

      // Seek
      midad.seek(0.5);
      expect(midad.renderer?.svgElement).toBeDefined();

      // Reset
      midad.reset();
      expect(midad.state).toBe('idle');

      // Restart
      midad.restart();
      expect(midad.state).toBe('playing');

      midad.destroy();
    });

    it('supports chainable method invocations', async () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', { autoAnimation: false });

      await new Promise<void>((resolve) => midad.ready(resolve));

      const ret = midad.pause().resume().seek(0.2).reset().restart();
      expect(ret).toBe(midad);

      midad.destroy();
    });
  });

  describe('Event Emitter & Callbacks', () => {
    it('fires ready and allows .ready(callback) registration', async () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', { autoAnimation: false });
      const readySpy = vi.fn();

      midad.ready(readySpy);
      await new Promise((r) => setTimeout(r, 50));

      expect(readySpy).toHaveBeenCalled();
      midad.destroy();
    });

    it('supports .on(), .once(), and .off() event listeners', () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', { autoAnimation: false });

      const handler = vi.fn();
      midad.on('start', handler);

      // Trigger start manually via renderer or mock
      midad['emit']('start', { text: 'test' });
      expect(handler).toHaveBeenCalledTimes(1);

      midad.off('start', handler);
      midad['emit']('start', { text: 'test' });
      expect(handler).toHaveBeenCalledTimes(1);

      // Once test
      const onceHandler = vi.fn();
      midad.once('pawStart', onceHandler);
      midad['emit']('pawStart', { pawId: 'paw_0' });
      midad['emit']('pawStart', { pawId: 'paw_0' });
      expect(onceHandler).toHaveBeenCalledTimes(1);

      midad.destroy();
    });

    it('dispatches animationEnd alias on word completion', () => {
      const container = createMockContainer();
      const midad = new Midad(container, mockSampleFont, 'كتب', { autoAnimation: false });
      const animEndSpy = vi.fn();

      midad.animationEnd(animEndSpy);

      // Emit complete event
      midad['emit']('animationEnd', { wordIndex: 0, wordText: 'كتب' });
      expect(animEndSpy).toHaveBeenCalledWith(0, expect.objectContaining({ text: 'كتب' }));

      midad.destroy();
    });
  });

  describe('BiDi & Missing Word Fallback', () => {
    it('gracefully handles words missing from the font dictionary without throwing', async () => {
      const container = createMockContainer();
      const warningSpy = vi.fn();

      // "unknown_word_123" is not in mockSampleFont
      const midad = new Midad(container, mockSampleFont, 'كلمة_غير_موجودة', {
        autoAnimation: false,
      });

      midad.on('warning', warningSpy);

      await new Promise<void>((resolve) => midad.ready(resolve));

      expect(warningSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          code: 'WORD_NOT_FOUND',
          text: 'كلمة_غير_موجودة',
        }),
      );

      // Midad should still be operational and use graceful fallback
      expect(midad.isReady).toBe(true);
      expect(midad.state).toBe('idle');

      midad.destroy();
    });
  });

  describe('Distribution Package Size Gates', () => {
    const rootDir = path.resolve(__dirname, '../../');
    const distDir = path.join(rootDir, 'engine/dist');
    const packagedFontPath = path.join(rootDir, 'engine/dist/fonts/noto_naskh_50.json');

    it('engine ES module bundle is strictly < 25 KB gzipped', () => {
      const esPath = path.join(distDir, 'midad.es.js');
      expect(fs.existsSync(esPath)).toBe(true);

      const content = fs.readFileSync(esPath);
      const gzipped = zlib.gzipSync(content);
      const gzipKb = gzipped.length / 1024;

      // Assert < 25 KB gzipped
      expect(gzipKb).toBeLessThan(25.0);
    });

    it('engine UMD bundle is strictly < 25 KB gzipped', () => {
      const umdPath = path.join(distDir, 'midad.umd.js');
      expect(fs.existsSync(umdPath)).toBe(true);

      const content = fs.readFileSync(umdPath);
      const gzipped = zlib.gzipSync(content);
      const gzipKb = gzipped.length / 1024;

      // Assert < 25 KB gzipped
      expect(gzipKb).toBeLessThan(25.0);
    });

    it('packaged 50-word font JSON is strictly < 95 KB gzipped', () => {
      expect(fs.existsSync(packagedFontPath)).toBe(true);

      const content = fs.readFileSync(packagedFontPath);
      const gzipped = zlib.gzipSync(content);
      const gzipKb = gzipped.length / 1024;

      // Assert < 95 KB gzipped
      expect(gzipKb).toBeLessThan(95.0);
    });
  });
});
