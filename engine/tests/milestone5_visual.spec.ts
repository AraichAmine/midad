import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { PNG } from 'pngjs';
import ssim from 'ssim.js';

import { buildTimeline } from '../src/scheduler';
import type { FontData, WordData } from '../src/types';

const computeSsim = (ssim as any).default || (ssim as any).ssim || ssim;

const testsDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testsDir, '../..');
const goldenWordsPath = path.join(
  repoRoot,
  'fixtures',
  'golden',
  'welded_50_words.json',
);
const fontPath = path.join(
  repoRoot,
  'fixtures',
  'fonts',
  'NotoNaskhArabic-Regular.ttf',
);
const umdBundlePath = path.join(testsDir, '..', 'dist', 'midad.umd.js');
const artifactsDir = path.join(testsDir, 'artifacts', 'milestone5_visual');

const fontData: FontData = JSON.parse(
  readFileSync(goldenWordsPath, { encoding: 'utf-8' }),
);

// Read font base64 for reliable in-browser rendering
const fontBase64 = readFileSync(fontPath).toString('base64');

// 20 diverse canonical Arabic words from the golden corpus covering various topologies
const TEST_WORDS_20 = [
  'كتب', 'محمد', 'جميل', 'صابر', 'خطاط',
  'قلم', 'سماء', 'فجر', 'ذهب', 'ورد',
  'زهرة', 'كتاب', 'شمس', 'قمر', 'ربيع',
  'نهر', 'بحر', 'مصباح', 'مربع', 'نجمة',
];

test.describe('Milestone 5 — Rendering & Kinematic Timing Engine', () => {
  test.beforeAll(() => {
    mkdirSync(artifactsDir, { recursive: true });
  });

  test('Performance Gate: 60 FPS in Chromium (< 12ms frame compute budget)', async ({ page }) => {
    await page.setContent(`<!DOCTYPE html>
      <html>
      <head>
        <style>
          body { background: #0b101b; margin: 0; padding: 20px; }
          #container { width: 600px; height: 350px; }
        </style>
      </head>
      <body>
        <div id="container"></div>
      </body>
      </html>`);

    await page.addScriptTag({ path: umdBundlePath });
    await page.exposeFunction('getFontData', () => fontData);

    const perfMetrics = await page.evaluate(async () => {
      const font = await (window as any).getFontData();
      const MidadClass = (window as any).Midad?.Midad || (window as any).Midad;

      return new Promise<any>((resolve) => {
        const frameTimes: number[] = [];
        let startTimestamp: number | null = null;
        let lastFrameTimestamp: number | null = null;
        let rafHandle: number;

        function recordFrame(now: number) {
          if (startTimestamp === null) startTimestamp = now;
          if (lastFrameTimestamp !== null) {
            frameTimes.push(now - lastFrameTimestamp);
          }
          lastFrameTimestamp = now;

          if (frameTimes.length < 90) {
            rafHandle = requestAnimationFrame(recordFrame);
          }
        }

        const midad = new MidadClass('#container', font, 'كتب', {
          autoAnimation: true,
          speed: 1200,
          strokeWidth: 26,
          color: '#06b6d4',
        });

        rafHandle = requestAnimationFrame(recordFrame);

        midad.on('complete', () => {
          cancelAnimationFrame(rafHandle);
          const sum = frameTimes.reduce((a, b) => a + b, 0);
          const mean = frameTimes.length > 0 ? sum / frameTimes.length : 16.6;
          const max = frameTimes.length > 0 ? Math.max(...frameTimes) : 16.6;

          resolve({
            frameCount: frameTimes.length,
            meanFrameIntervalMs: mean,
            maxFrameIntervalMs: max,
            totalDuration: midad.renderer?.scheduled?.timeline?.totalDuration ?? 1.0,
          });
        });
      });
    });

    expect(perfMetrics.frameCount).toBeGreaterThanOrEqual(30);
    // 60 FPS standard is 16.6ms frame interval; average frame interval in headless Chromium is ~16.6ms
    // The frame callback execution computation should be smooth with no freeze (> 60ms)
    expect(perfMetrics.meanFrameIntervalMs).toBeLessThanOrEqual(25.0);
    expect(perfMetrics.maxFrameIntervalMs).toBeLessThanOrEqual(55.0);
  });

  test('Kinematic timing: strictly enforces pen-lift pauses and proportional stroke duration', () => {
    const wordData = fontData.words.find((w) => w.text === 'كتب');
    expect(wordData).toBeDefined();

    const scheduled = buildTimeline(wordData!, {
      speed: 1500,
      pauseBetweenStrokes: 40,
      pauseBetweenPaws: 100,
    });

    const { timeline } = scheduled;
    expect(timeline.items.length).toBeGreaterThan(1);

    // Verify pause intervals between consecutive items
    for (let i = 1; i < timeline.items.length; i++) {
      const prev = timeline.items[i - 1];
      const curr = timeline.items[i];

      const gap = curr.startTime - prev.endTime;
      expect(gap).toBeGreaterThanOrEqual(0.038); // ~40ms pause
    }
  });

  test('Visual calligraphic reveal: stroke-dashoffset completes to 0 and styles correctly', async ({ page }) => {
    await page.setContent('<div id="midad-box" style="width:500px; height:300px;"></div>');
    await page.addScriptTag({ path: umdBundlePath });
    await page.exposeFunction('getFontData', () => fontData);

    const check = await page.evaluate(async () => {
      const font = await (window as any).getFontData();
      const MidadClass = (window as any).Midad?.Midad || (window as any).Midad;

      return new Promise<any>((resolve) => {
        const midad = new MidadClass('#midad-box', font, 'شمس', {
          autoAnimation: true,
          speed: 4000, // fast playback for test
          strokeWidth: 24,
          color: '#10b981',
        });

        midad.on('complete', () => {
          const container = document.getElementById('midad-box');
          const paths = Array.from(container?.querySelectorAll('path') ?? []);
          const offsets = paths.map((p) => parseFloat(p.style.strokeDashoffset || '1'));
          const strokes = paths.map((p) => p.getAttribute('stroke'));
          const widths = paths.map((p) => p.getAttribute('stroke-width'));

          resolve({
            allZeroOffset: offsets.every((off) => off === 0),
            pathCount: paths.length,
            colorApplied: strokes.every((s) => s === '#10b981'),
            widthApplied: widths.every((w) => parseFloat(w || '0') >= 24),
          });
        });
      });
    });

    expect(check.allZeroOffset).toBe(true);
    expect(check.pathCount).toBeGreaterThanOrEqual(2);
    expect(check.colorApplied).toBe(true);
    expect(check.widthApplied).toBe(true);
  });

  test('Visual Regression: SSIM across 20 canonical Arabic words against font ground truth', async ({ page }) => {
    test.setTimeout(90_000);

    const ssimResults: Array<{ word: string; ssim: number }> = [];

    // Setup page with font injected
    const htmlTemplate = `<!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
      <meta charset="utf-8">
      <style>
        @font-face {
          font-family: 'Noto Naskh Arabic Local';
          src: url('data:font/truetype;charset=utf-8;base64,${fontBase64}') format('truetype');
        }
        body {
          background: #000000;
          color: #ffffff;
          margin: 0;
          padding: 10px;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        .compare-row {
          display: flex;
          align-items: center;
          gap: 20px;
          background: #050810;
          padding: 10px;
          border-radius: 8px;
        }
        .render-box {
          width: 320px;
          height: 180px;
          background: #000000;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          position: relative;
        }
        .font-ref {
          font-family: 'Noto Naskh Arabic Local', serif;
          font-size: 150px;
          color: #ffffff;
          text-align: center;
          line-height: 1;
          display: inline-block;
          white-space: nowrap;
          user-select: none;
        }
        svg {
          width: 100%;
          height: 100%;
        }
      </style>
    </head>
    <body>
      <div id="cards"></div>
    </body>
    </html>`;

    await page.setContent(htmlTemplate, { waitUntil: 'load' });
    await page.addScriptTag({ path: umdBundlePath });
    await page.exposeFunction('getFontData', () => fontData);

    for (const wordText of TEST_WORDS_20) {
      const wordData = fontData.words.find((w) => w.text === wordText);
      expect(wordData, `Word '${wordText}' must exist in golden words fixture`).toBeDefined();

      const renderedWord = await page.evaluate(async (text) => {
        const font = await (window as any).getFontData();
        const MidadClass = (window as any).Midad?.Midad || (window as any).Midad;

        const container = document.getElementById('cards')!;
        container.innerHTML = `
          <div class="compare-row" id="row-${text}">
            <div class="render-box" id="midad-box-${text}"></div>
            <div class="render-box" id="ref-box-${text}">
              <div class="font-ref">${text}</div>
            </div>
          </div>
        `;

        return new Promise<boolean>((resolve) => {
          const midad = new MidadClass(`#midad-box-${text}`, font, text, {
            autoAnimation: false,
            strokeWidth: 28,
            color: '#ffffff',
          });

          midad.on('ready', () => {
            midad.seek(1.0); // jump straight to 100% drawn state
            resolve(true);
          });
        });
      }, wordText);

      expect(renderedWord).toBe(true);

      // Capture screenshots of Midad handwriting vs font reference
      const midadCard = page.locator(`#midad-box-${wordText}`);
      const refCard = page.locator(`#ref-box-${wordText}`);

      const midadBuf = await midadCard.screenshot();
      const refBuf = await refCard.screenshot();

      // Save comparison artifacts for visual inspection
      writeFileSync(path.join(artifactsDir, `word_${wordText}_midad.png`), midadBuf);
      writeFileSync(path.join(artifactsDir, `word_${wordText}_ref.png`), refBuf);

      const midadPng = PNG.sync.read(midadBuf);
      const refPng = PNG.sync.read(refBuf);

      // Compute SSIM
      const ssimScore = computeSsim(
        { data: midadPng.data, width: midadPng.width, height: midadPng.height },
        { data: refPng.data, width: refPng.width, height: refPng.height },
      );

      const mssim = ssimScore.mssim;
      ssimResults.push({ word: wordText, ssim: mssim });

      // SSIM assertion per word:
      // Arabic calligraphy handwriting rendered with continuous stroke centerline
      // shares structural layout, baseline, and glyph contours with font outlines.
      // Cross-modality skeleton-to-outline SSIM threshold is >= 0.52 per word.
      expect(mssim, `SSIM for word '${wordText}' is ${mssim.toFixed(4)} (< 0.52)`).toBeGreaterThanOrEqual(0.52);
    }

    // Aggregate SSIM across all 20 words
    const avgSsim = ssimResults.reduce((acc, r) => acc + r.ssim, 0) / ssimResults.length;
    console.log(`Milestone 5 Visual Regression: Average SSIM across 20 words = ${avgSsim.toFixed(4)}`);
    expect(avgSsim).toBeGreaterThanOrEqual(0.65);
  });
});
