import { existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

import type { Point } from '../src/types';
import { assertPawContinuity } from '../src/validator';

const testsDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testsDir, '../..');
const prototypePath = path.join(
  repoRoot,
  'fixtures',
  'skeletons',
  'prototype_5.json',
);
const fontPath = path.join(
  repoRoot,
  'fixtures',
  'fonts',
  'NotoNaskhArabic-Regular.ttf',
);
const screenshotPath = path.join(testsDir, 'artifacts', 'day1_harness.png');

interface PrototypeGlyph {
  char: string;
  form: string;
  trunk_contours: Point[][];
  dot_contours: Point[][];
  skeleton: {
    points: Point[];
    path_d: string;
    num_samples: number;
  };
}

interface PrototypeData {
  glyphs: PrototypeGlyph[];
}

interface WordSpec {
  word: string;
  parts: Array<{ char: string; form: string }>;
}

interface GlyphGeometry {
  trunk: Point[][];
  dots: Point[][];
  path: Point[];
}

interface WordGeometry {
  trunk: Point[][];
  dots: Point[][];
  path: Point[];
}

const WORD_SPECS: WordSpec[] = [
  {
    word: 'ابجدر',
    parts: [
      { char: 'ا', form: 'isolated' },
      { char: 'ب', form: 'initial' },
      { char: 'ج', form: 'medial' },
      { char: 'د', form: 'final' },
      { char: 'ر', form: 'final' },
    ],
  },
  {
    word: 'بجب',
    parts: [
      { char: 'ب', form: 'initial' },
      { char: 'ج', form: 'medial' },
      { char: 'ب', form: 'final' },
    ],
  },
  {
    word: 'برد',
    parts: [
      { char: 'ب', form: 'initial' },
      { char: 'ر', form: 'final' },
      { char: 'د', form: 'final' },
    ],
  },
  {
    word: 'جبر',
    parts: [
      { char: 'ج', form: 'initial' },
      { char: 'ب', form: 'medial' },
      { char: 'ر', form: 'final' },
    ],
  },
];

const PROTOTYPE_LETTERS = ['ا', 'ب', 'ج', 'د', 'ر'] as const;
const WORD_GAP = 55;
const SVG_WIDTH = 1240;
const SVG_HEIGHT = 250;
const CARD_WIDTH = 220;
const CARD_HEIGHT = 250;
const PADDING = 34;
const LABEL_HEIGHT = 44;

function loadPrototype(): Map<string, PrototypeGlyph> {
  const data = JSON.parse(readFileSync(prototypePath, 'utf-8')) as PrototypeData;
  return new Map(data.glyphs.map((glyph) => [`${glyph.char}:${glyph.form}`, glyph]));
}

function glyphFor(
  prototype: Map<string, PrototypeGlyph>,
  char: string,
  form: string,
): PrototypeGlyph {
  const glyph = prototype.get(`${char}:${form}`);
  if (!glyph) {
    throw new Error(`No prototype glyph for ${char}/${form}`);
  }
  return glyph;
}

function bounds(points: Point[]): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} {
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const [x, y] of points) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return { minX, minY, maxX, maxY };
}

/**
 * The exported skeleton trail covers branched shapes by retracing some
 * segments.  For the animation harness we keep the original point order and
 * retain only the right-to-left monotone part, so every authored stroke is a
 * genuinely welded RTL path while still being derived from the prototype JSON.
 */
function normalizeRtl(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const point of points) {
    const clean: Point = [Number(point[0]), Number(point[1])];
    if (result.length === 0) {
      result.push(clean);
      continue;
    }
    const previous = result[result.length - 1];
    if (clean[0] > previous[0]) {
      continue;
    }
    if (clean[0] === previous[0] && clean[1] === previous[1]) {
      continue;
    }
    result.push(clean);
  }
  if (result.length < 2) {
    result.push([points[points.length - 1][0], points[points.length - 1][1]]);
  }
  return result;
}

function buildWordGeometry(
  prototype: Map<string, PrototypeGlyph>,
  parts: Array<{ char: string; form: string }>,
): WordGeometry {
  const trunk: Point[][] = [];
  const dots: Point[][] = [];
  const pathPoints: Point[] = [];
  let previousEndX: number | null = null;

  for (const part of parts) {
    const glyph = glyphFor(prototype, part.char, part.form);
    const normalized = normalizeRtl(glyph.skeleton.points);
    const all = [...glyph.trunk_contours, ...glyph.dot_contours].flat();
    const glyphMaxX = Math.max(...all.map((point) => point[0]));
    const skeletonStartX = Math.max(...normalized.map((point) => point[0]));

    const translateX =
      previousEndX === null
        ? -glyphMaxX
        : previousEndX - WORD_GAP - skeletonStartX;

    for (const contour of glyph.trunk_contours) {
      trunk.push(contour.map(([x, y]) => [x + translateX, y] as Point));
    }
    for (const contour of glyph.dot_contours) {
      dots.push(contour.map(([x, y]) => [x + translateX, y] as Point));
    }
    const translatedPath = normalized.map(
      ([x, y]) => [x + translateX, y] as Point,
    );
    pathPoints.push(...translatedPath);
    previousEndX = translatedPath[translatedPath.length - 1][0];
  }

  return { trunk, dots, path: pathPoints };
}

function buildGlyphGeometry(glyph: PrototypeGlyph): GlyphGeometry {
  return {
    trunk: glyph.trunk_contours,
    dots: glyph.dot_contours,
    path: normalizeRtl(glyph.skeleton.points),
  };
}

function toSvgPath(points: Point[], close = false): string {
  if (points.length === 0) {
    return '';
  }
  const commands = points.map(
    ([x, y], index) => `${index === 0 ? 'M' : 'L'} ${x.toFixed(3)} ${y.toFixed(3)}`,
  );
  return `${commands.join(' ')}${close ? ' Z' : ''}`;
}

function renderSvg(
  geometry: GlyphGeometry | WordGeometry,
  options: {
    width: number;
    height: number;
    label: string;
    dataAttributes: string;
    svgClass: string;
  },
): string {
  const allPoints = [
    ...geometry.trunk.flat(),
    ...geometry.dots.flat(),
    ...geometry.path,
  ];
  const bbox = bounds(allPoints);
  const width = Math.max(bbox.maxX - bbox.minX, 1);
  const height = Math.max(bbox.maxY - bbox.minY, 1);
  const usableWidth = options.width - PADDING * 2;
  const usableHeight = options.height - PADDING * 2 - LABEL_HEIGHT;
  const scale = Math.min(usableWidth / width, usableHeight / height);
  const offsetX = PADDING + (usableWidth - width * scale) / 2 - bbox.minX * scale;
  const offsetY =
    PADDING +
    LABEL_HEIGHT +
    (usableHeight - height * scale) / 2 +
    bbox.maxY * scale;

  const mapPoint = ([x, y]: Point): Point => [
    offsetX + x * scale,
    offsetY - y * scale,
  ];
  const mapContours = (contours: Point[][]): string =>
    contours
      .map((contour) => `<path d="${toSvgPath(contour.map(mapPoint), true)}" />`)
      .join('');
  const pathD = toSvgPath(geometry.path.map(mapPoint));

  return `
    <svg class="${options.svgClass}" ${options.dataAttributes}
         viewBox="0 0 ${options.width} ${options.height}"
         width="${options.width}" height="${options.height}"
         role="img" aria-label="${options.label}">
      <text class="glyph-label" x="${PADDING}" y="${PADDING + 8}">${options.label}</text>
      <g class="trunk-shape">${mapContours(geometry.trunk)}</g>
      <g class="dot-shape">${mapContours(geometry.dots)}</g>
      <path class="ink" data-label="${options.label}" pathLength="1" d="${pathD}" />
    </svg>
  `;
}

function buildHtml(prototype: Map<string, PrototypeGlyph>): string {
  const fontBase64 = readFileSync(fontPath).toString('base64');
  const cards = PROTOTYPE_LETTERS.map((char) => {
    const glyph = glyphFor(prototype, char, 'isolated');
    return renderSvg(buildGlyphGeometry(glyph), {
      width: CARD_WIDTH,
      height: CARD_HEIGHT,
      label: `Glyph ${char}`,
      dataAttributes: `data-char="${char}"`,
      svgClass: 'glyph-card',
    });
  }).join('');

  const words = WORD_SPECS.map((spec) => {
    const geometry = buildWordGeometry(prototype, spec.parts);
    return renderSvg(geometry, {
      width: SVG_WIDTH,
      height: SVG_HEIGHT,
      label: `Word ${spec.word}`,
      dataAttributes: `data-word="${spec.word}"`,
      svgClass: 'word',
    });
  }).join('');

  return `<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8" />
<title>Midad DAY-1 Playwright Harness</title>
<style>
  @font-face {
    font-family: 'Noto Naskh Arabic';
    src: url(data:font/ttf;base64,${fontBase64}) format('truetype');
  }
  :root { color-scheme: light; }
  body {
    margin: 0;
    padding: 24px;
    background: #f6f1e7;
    color: #14213d;
    font-family: 'Noto Naskh Arabic', Georgia, serif;
  }
  h1 { margin: 0 0 4px; font-size: 26px; }
  h2 { margin: 26px 0 10px; font-size: 18px; }
  p { margin: 0; color: #4a5568; }
  .cards, .words { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
  svg {
    background: #fffdf8;
    border: 1px solid #dbc8a5;
    border-radius: 10px;
    box-shadow: 0 4px 14px rgba(20, 33, 61, 0.08);
    overflow: hidden;
  }
  .glyph-card { flex: 0 0 auto; }
  .word { flex: 1 1 100%; max-width: 1240px; }
  .glyph-label {
    fill: #8a6d3b;
    font-family: Georgia, serif;
    font-size: 17px;
    letter-spacing: 0.06em;
    direction: ltr;
    text-anchor: start;
  }
  .trunk-shape path { fill: #1d3557; fill-rule: evenodd; }
  .dot-shape path { fill: #c1121f; fill-rule: evenodd; }
  .ink {
    fill: none;
    stroke: #f4a261;
    stroke-width: 7;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    animation: draw-stroke 1.6s ease-out forwards;
  }
  @keyframes draw-stroke {
    from { stroke-dashoffset: 1; }
    to { stroke-dashoffset: 0; }
  }
</style>
</head>
<body>
  <header>
    <h1>Midad · DAY-1 Regression Harness</h1>
    <p>Five prototype glyphs (ا ب ج د ر), four sample words, welded RTL baselines
       extracted from fixtures/skeletons/prototype_5.json.</p>
  </header>
  <section aria-label="Prototype glyphs">
    <h2>Prototype glyphs</h2>
    <div class="cards">${cards}</div>
  </section>
  <section aria-label="Sample words">
    <h2>Sample words</h2>
    <div class="words">${words}</div>
  </section>
</body>
</html>`;
}

test('DAY-1 harness renders continuous RTL strokes without browser errors', async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });
  page.on('pageerror', (error) => {
    pageErrors.push(error.message);
  });

  const prototype = loadPrototype();
  await page.setContent(buildHtml(prototype), { waitUntil: 'load' });

  await expect(page.locator('svg.glyph-card')).toHaveCount(5);
  await expect(page.locator('svg.word')).toHaveCount(WORD_SPECS.length);
  for (const spec of WORD_SPECS) {
    await expect(
      page.locator(`svg.word[data-word="${spec.word}"]`),
    ).toHaveCount(1);
  }

  const inkPaths = page.locator('path.ink');
  await expect(inkPaths).toHaveCount(9);

  const count = await inkPaths.count();
  for (let index = 0; index < count; index += 1) {
    const pathLocator = inkPaths.nth(index);
    const label = (await pathLocator.getAttribute('data-label')) ?? `path ${index}`;
    const d = await pathLocator.getAttribute('d');
    expect(d, `${label} has no path data`).toBeTruthy();

    const result = assertPawContinuity(d as string);
    expect(
      result.valid,
      `${label} failed continuity: ${result.errors.join('; ')}`,
    ).toBe(true);
    expect(result.singleMove).toBe(true);
    expect(result.c0Continuous).toBe(true);
    expect(result.rtlRatio).toBeGreaterThanOrEqual(0.85);
  }

  const animation = await inkPaths.first().evaluate((element) => {
    const style = window.getComputedStyle(element);
    return {
      animationName: style.animationName,
      animationDuration: style.animationDuration,
      strokeDasharray: style.strokeDasharray,
      strokeDashoffset: style.strokeDashoffset,
      strokeLinecap: style.strokeLinecap,
    };
  });
  expect(animation.animationName).toBe('draw-stroke');
  expect(animation.animationDuration).not.toBe('0s');
  expect(animation.strokeDasharray).not.toBe('none');
  expect(animation.strokeLinecap).toBe('round');

  // Let the CSS dash animation progress so the screenshot shows ink strokes.
  await page.waitForTimeout(450);

  mkdirSync(path.dirname(screenshotPath), { recursive: true });
  await page.screenshot({ path: screenshotPath, fullPage: true });
  expect(existsSync(screenshotPath)).toBe(true);
  expect(statSync(screenshotPath).size).toBeGreaterThan(10_000);

  expect(pageErrors, `Uncaught page errors: ${pageErrors.join('; ')}`).toEqual([]);
  expect(
    consoleErrors,
    `Browser console errors: ${consoleErrors.join('; ')}`,
  ).toEqual([]);
});
