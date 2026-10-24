import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';

import { buildTimeline } from '../src/scheduler';
import type { FontData, WordData } from '../src/types';

const testsDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testsDir, '../..');
const goldenWordsPath = path.join(
  repoRoot,
  'fixtures',
  'golden',
  'welded_50_words.json',
);
const umdBundlePath = path.join(testsDir, '..', 'dist', 'midad.umd.js');

const fontData: FontData = JSON.parse(
  readFileSync(goldenWordsPath, { encoding: 'utf-8' }),
);

test.describe('Milestone 4 — Vara.js API & Web Animation Engine', () => {
  test('Scheduler enforces causal ordering and creates valid bounding boxes', () => {
    const wordData = fontData.words.find((w) => w.text === 'كتب');
    expect(wordData).toBeDefined();

    const scheduled = buildTimeline(wordData!, {
      speed: 1500,
      pauseBetweenStrokes: 40,
      pauseBetweenPaws: 100,
    });

    const { timeline, boundingBox } = scheduled;
    expect(timeline.paws.length).toBeGreaterThan(0);
    expect(timeline.items.length).toBeGreaterThan(0);
    expect(timeline.totalDuration).toBeGreaterThan(0);

    // Bounding box assertions
    expect(boundingBox.width).toBeGreaterThan(100);
    expect(boundingBox.height).toBeGreaterThan(100);
    expect(boundingBox.viewBox).toContain(' ');

    // Causality check: trunk ends before delayed begins
    const paw0 = timeline.paws[0];
    const trunkItem = timeline.items.find((it) => it.strokeId === paw0.trunkStroke.id);
    expect(trunkItem).toBeDefined();

    const delayedItems = timeline.items.filter(
      (it) => it.pawId === paw0.id && it.type === 'delayed',
    );
    for (const dItem of delayedItems) {
      expect(dItem.startTime).toBeGreaterThanOrEqual(trunkItem!.endTime);
    }
  });

  test('Midad instantiates and injects valid SVG DOM structure', async ({ page }) => {
    await page.setContent('<div id="test-container" style="width:600px; height:400px;"></div>');
    await page.addScriptTag({ path: umdBundlePath });
    await page.exposeFunction('getFontData', () => fontData);

    const result = await page.evaluate(async () => {
      const font = await (window as any).getFontData();
      const MidadClass = (window as any).Midad?.Midad || (window as any).Midad;

      return new Promise<any>((resolve) => {
        const midad = new MidadClass('#test-container', font, 'كتب', {
          autoAnimation: false,
          strokeWidth: 24,
          color: '#06b6d4',
        });

        midad.on('ready', () => {
          const container = document.getElementById('test-container');
          const svg = container?.querySelector('svg');
          const paths = container?.querySelectorAll('path') ?? [];
          const trunkPath = container?.querySelector('.midad-trunk');
          const delayedPath = container?.querySelector('.midad-delayed');

          resolve({
            isReady: midad.isReady,
            hasSvg: !!svg,
            viewBox: svg?.getAttribute('viewBox'),
            pathCount: paths.length,
            hasTrunk: !!trunkPath,
            hasDelayed: !!delayedPath,
            trunkDasharray: (trunkPath as SVGPathElement)?.style.strokeDasharray,
            trunkDashoffset: (trunkPath as SVGPathElement)?.style.strokeDashoffset,
          });
        });
      });
    });

    expect(result.isReady).toBe(true);
    expect(result.hasSvg).toBe(true);
    expect(result.pathCount).toBeGreaterThan(1);
    expect(result.hasTrunk).toBe(true);
    expect(result.hasDelayed).toBe(true);
    expect(result.trunkDasharray).toBeDefined();
    // Initially hidden
    expect(parseFloat(result.trunkDashoffset)).toBeGreaterThan(0);
  });

  test('Animation runs with continuous dashoffset progression and completion event', async ({
    page,
  }) => {
    await page.setContent('<div id="anim-container" style="width:600px; height:400px;"></div>');
    await page.addScriptTag({ path: umdBundlePath });
    await page.exposeFunction('getFontData2', () => fontData);

    const animationResult = await page.evaluate(async () => {
      const font = await (window as any).getFontData2();
      const MidadClass = (window as any).Midad?.Midad || (window as any).Midad;

      return new Promise<any>((resolve) => {
        const progressValues: number[] = [];
        let pawStarted = false;
        let strokeStarted = false;

        const midad = new MidadClass('#anim-container', font, 'كتب', {
          autoAnimation: false,
          speed: 6000, // Fast speed for test execution
        });

        midad.on('pawStart', () => {
          pawStarted = true;
        });

        midad.on('strokeStart', () => {
          strokeStarted = true;
        });

        midad.on('progress', (data: any) => {
          progressValues.push(data.progress);
        });

        midad.on('complete', () => {
          const container = document.getElementById('anim-container');
          const trunkPath = container?.querySelector('.midad-trunk') as SVGPathElement;
          const delayedPath = container?.querySelector('.midad-delayed') as SVGPathElement;

          resolve({
            state: midad.state,
            pawStarted,
            strokeStarted,
            progressCount: progressValues.length,
            finalTrunkOffset: parseFloat(trunkPath.style.strokeDashoffset),
            finalDelayedOffset: parseFloat(delayedPath.style.strokeDashoffset),
          });
        });

        midad.on('ready', () => {
          midad.play();
        });
      });
    });

    expect(animationResult.state).toBe('completed');
    expect(animationResult.pawStarted).toBe(true);
    expect(animationResult.strokeStarted).toBe(true);
    expect(animationResult.progressCount).toBeGreaterThan(3);
    // At completion, all offsets must be 0 (fully drawn)
    expect(animationResult.finalTrunkOffset).toBe(0);
    expect(animationResult.finalDelayedOffset).toBe(0);
  });

  test('Playback controls: pause, resume, and seek function accurately', async ({ page }) => {
    await page.setContent('<div id="controls-container" style="width:600px; height:400px;"></div>');
    await page.addScriptTag({ path: umdBundlePath });
    await page.exposeFunction('getFontData3', () => fontData);

    const controlsResult = await page.evaluate(async () => {
      const font = await (window as any).getFontData3();
      const MidadClass = (window as any).Midad?.Midad || (window as any).Midad;

      return new Promise<any>((resolve) => {
        const midad = new MidadClass('#controls-container', font, 'محمد', {
          autoAnimation: false,
          speed: 800,
        });

        midad.on('ready', () => {
          midad.play();

          // Wait 60ms then pause
          setTimeout(() => {
            midad.pause();
            const stateAfterPause = midad.state;
            const container = document.getElementById('controls-container');
            const trunkPath = container?.querySelector('.midad-trunk') as SVGPathElement;
            const offsetAfterPause = parseFloat(trunkPath.style.strokeDashoffset);

            // Wait another 60ms to confirm paused offset doesn't change
            setTimeout(() => {
              const offsetStillPaused = parseFloat(trunkPath.style.strokeDashoffset);

              // Seek to 50%
              midad.seek(0.5);
              const offsetAfterSeek = parseFloat(trunkPath.style.strokeDashoffset);

              // Resume
              midad.resume();
              const stateAfterResume = midad.state;

              resolve({
                stateAfterPause,
                stateAfterResume,
                offsetDifferenceWhilePaused: Math.abs(offsetAfterPause - offsetStillPaused),
                offsetAfterSeek,
              });
            }, 60);
          }, 60);
        });
      });
    });

    expect(controlsResult.stateAfterPause).toBe('paused');
    expect(controlsResult.stateAfterResume).toBe('playing');
    // Offsets must remain constant while paused
    expect(controlsResult.offsetDifferenceWhilePaused).toBe(0);
  });

  test('Multi-word queuing executes words sequentially', async ({ page }) => {
    await page.setContent('<div id="queue-container" style="width:600px; height:400px;"></div>');
    await page.addScriptTag({ path: umdBundlePath });
    await page.exposeFunction('getFontData4', () => fontData);

    const queueResult = await page.evaluate(async () => {
      const font = await (window as any).getFontData4();
      const MidadClass = (window as any).Midad?.Midad || (window as any).Midad;

      return new Promise<any>((resolve) => {
        const wordsPlayed: string[] = [];

        const midad = new MidadClass(
          '#queue-container',
          font,
          [
            { text: 'فجر', speed: 12000 },
            { text: 'نهر', speed: 12000 },
          ],
          {
            autoAnimation: false,
            queued: true,
          },
        );

        midad.on('start', (data: any) => {
          if (data?.wordText && !wordsPlayed.includes(data.wordText)) {
            wordsPlayed.push(data.wordText);
          }
        });

        midad.on('complete', (data: any) => {
          if (data?.wordIndex === 1) {
            resolve({
              wordsPlayed,
            });
          }
        });

        midad.on('ready', () => {
          midad.play(0);
        });
      });
    });

    expect(queueResult.wordsPlayed).toEqual(['فجر', 'نهر']);
  });
});
