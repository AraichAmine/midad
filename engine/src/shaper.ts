/**
 * Midad — Client-Side Runtime Arabic Shaper & Baseline Welder
 *
 * Implements real-time cursive PAW partitioning and smooth cubic baseline welding
 * directly in TypeScript, enabling arbitrary user-typed Arabic text to be animated
 * on the fly without server-side pre-rendering.
 *
 * Mathematical Invariants:
 * - Single-M command: exactly one M per PAW baseline trunk.
 * - C⁰ positional continuity: joint gap distance Δ < 0.05 font units.
 * - G¹ tangent continuity: outgoing vs incoming tangent angle Δθ < 12°.
 * - Temporal causality: delayed strokes positioned in absolute canvas coordinates.
 */

import type { DelayedStrokeData, PawData, Point, Stroke, WordData } from './types';

export interface DirectedGlyphStroke {
  points: Point[];
  length: number;
}

export interface DirectedGlyphDelayed {
  role: 'dot' | 'hamza' | 'madda' | 'inner_mark';
  points: Point[];
  length: number;
  attachment_s: number;
}

export interface DirectedGlyph {
  char: string;
  form: string;
  trunk_strokes: DirectedGlyphStroke[];
  delayed_strokes: DirectedGlyphDelayed[];
  anchors: {
    entry_anchor?: Point;
    exit_anchor?: Point;
  };
}

export type GlyphCatalog = Record<string, DirectedGlyph>;

/** Characters that break cursive connection to the left */
export const NON_CONNECTING = new Set<string>([
  'ا', 'أ', 'إ', 'آ', 'د', 'ذ', 'ر', 'ز', 'و', 'ء',
]);

/** Right-joining only letters (have only isolated and final forms) */
export const RIGHT_JOINING = new Set<string>([
  'ا', 'أ', 'إ', 'آ', 'د', 'ذ', 'ر', 'ز', 'و',
]);

/**
 * Partition Arabic text into Pieces of Arabic Words (PAWs).
 */
export function partitionPaws(text: string): string[][] {
  const paws: string[][] = [];
  let currentPaw: string[] = [];

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];

    // Whitespace and punctuation start a new PAW
    if (/\s|[.,!?;:()،؛؟]/.test(ch)) {
      if (currentPaw.length > 0) {
        paws.push(currentPaw);
        currentPaw = [];
      }
      continue;
    }

    // Alef variants (ا أ إ آ) are always isolated: they break cursive
    // connection on both sides, so they form their own single-letter PAW.
    if (/[اأإآ]/.test(ch)) {
      if (currentPaw.length > 0) {
        paws.push(currentPaw);
        currentPaw = [];
      }
      paws.push([ch]);
      continue;
    }

    currentPaw.push(ch);

    // Non-connecting letter breaks connection to the following letter
    if (NON_CONNECTING.has(ch)) {
      paws.push(currentPaw);
      currentPaw = [];
    }
  }

  if (currentPaw.length > 0) {
    paws.push(currentPaw);
  }

  return paws;
}

/**
 * Determine contextual glyph form (isolated, initial, medial, final).
 */
export function determineForm(
  char: string,
  index: number,
  pawLetters: string[],
): 'isolated' | 'initial' | 'medial' | 'final' {
  if (char === 'ء') return 'isolated';

  const n = pawLetters.length;
  if (n === 1) return 'isolated';

  if (RIGHT_JOINING.has(char)) {
    return index === 0 ? 'isolated' : 'final';
  }

  if (index === 0) return 'initial';
  if (index === n - 1) return 'final';
  return 'medial';
}

/**
 * Prune hook spurs at stroke terminals and align tangents to horizontal (-1, 0).
 */
export function cleanAndAlignStroke(
  points: Point[],
  isInitial: boolean,
  isMedial: boolean,
  isFinal: boolean,
): Point[] {
  if (points.length < 6) return points.slice();

  let pts = points.map((p) => [p[0], p[1]] as Point);

  // Clean trailing spurs on initial/medial connecting exits
  if (isInitial || isMedial) {
    const n = pts.length;
    let cut = n;
    for (let k = n - 1; k >= Math.max(n - 6, 2); k--) {
      const stepDx = pts[k][0] - pts[k - 1][0];
      const stepDy = Math.abs(pts[k][1] - pts[k - 1][1]);
      if (stepDx > 0.5 || stepDy > 10.0) {
        cut = k;
        break;
      }
    }
    if (cut < n && cut >= 4) {
      pts = pts.slice(0, cut);
    }

    // Force terminal exit tangent strictly horizontal (-1, 0)
    const last = pts[pts.length - 1];
    const prev = pts[pts.length - 2];
    pts[pts.length - 1] = [last[0], prev[1]];
  }

  // Clean entry on medial/final connecting entries
  if (isMedial || isFinal) {
    if (pts.length >= 6) {
      const first = pts[0];
      const second = pts[1];
      pts[0] = [first[0], second[1]];
    }
  }

  return pts;
}

/**
 * Shape and weld a single PAW into continuous baseline trunk and delayed strokes.
 */
function buildPawTrunk(
  pawLetters: string[],
  catalog: GlyphCatalog,
  bridge: number = 25.0,
): {
  d: string;
  trunkLength: number;
  letterTranslations: Point[];
  secondaryStrokes: { points: Point[]; length: number }[];
} {
  const commands: string[] = [];
  const letterTranslations: Point[] = [];
  const secondaryStrokes: { points: Point[]; length: number }[] = [];
  let currentLength = 0;
  let prevExitX = 0;
  let prevExitY = 0;

  for (let idx = 0; idx < pawLetters.length; idx++) {
    const char = pawLetters[idx];
    const form = determineForm(char, idx, pawLetters);
    const key = `${char}_${form}`;
    const glyph = catalog[key] || catalog[`${char}_isolated`];

    if (!glyph || !glyph.trunk_strokes || glyph.trunk_strokes.length === 0) {
      letterTranslations.push([0, 0]);
      continue;
    }

    const s0Raw = glyph.trunk_strokes[0].points;
    const isInit = idx === 0 && pawLetters.length > 1;
    const isMed = idx > 0 && idx < pawLetters.length - 1;
    const isFin = idx === pawLetters.length - 1 && pawLetters.length > 1;

    const s0Pts = cleanAndAlignStroke(s0Raw, isInit, isMed, isFin);
    const entryPt = s0Pts[0];
    const exitPt = s0Pts[s0Pts.length - 1];

    let dx = 0;
    if (idx === 0) {
      dx = 0;
    } else {
      let currBridge = bridge;
      const prevChar = pawLetters[idx - 1];
      if (['ه', 'ح', 'خ', 'ج'].includes(prevChar) && ['ر', 'ز'].includes(char)) {
        currBridge = 150.0;
      }
      dx = prevExitX - currBridge - entryPt[0];
    }
    const dy = 0;
    letterTranslations.push([dx, dy]);

    const shiftedPts = s0Pts.map((p) => [p[0] + dx, p[1] + dy] as Point);
    const strokeStart = shiftedPts[0];

    // Collect secondary strokes (e.g. Tah upright mast)
    for (let sIdx = 1; sIdx < glyph.trunk_strokes.length; sIdx++) {
      const sec = glyph.trunk_strokes[sIdx];
      secondaryStrokes.push({
        points: sec.points.map((p) => [p[0] + dx, p[1] + dy] as Point),
        length: sec.length || 100,
      });
    }

    if (idx === 0) {
      commands.push(`M ${strokeStart[0].toFixed(1)} ${strokeStart[1].toFixed(1)}`);
    } else {
      // Weld letter i to letter i+1 via tangent-aligned horizontal cubic fillet
      const span = prevExitX - strokeStart[0];
      const cp1X = prevExitX - 0.4 * span;
      const cp1Y = prevExitY;
      const cp2X = strokeStart[0] + 0.4 * span;
      const cp2Y = strokeStart[1];

      commands.push(
        `C ${cp1X.toFixed(1)} ${cp1Y.toFixed(1)} ${cp2X.toFixed(1)} ${cp2Y.toFixed(1)} ${strokeStart[0].toFixed(1)} ${strokeStart[1].toFixed(1)}`,
      );
      currentLength += Math.hypot(span, prevExitY - strokeStart[1]);
    }

    // Append interior points
    for (let pIdx = 1; pIdx < shiftedPts.length; pIdx++) {
      const pt = shiftedPts[pIdx];
      commands.push(`L ${pt[0].toFixed(1)} ${pt[1].toFixed(1)}`);
      const prevP = shiftedPts[pIdx - 1];
      currentLength += Math.hypot(pt[0] - prevP[0], pt[1] - prevP[1]);
    }

    prevExitX = shiftedPts[shiftedPts.length - 1][0];
    prevExitY = shiftedPts[shiftedPts.length - 1][1];
  }

  return {
    d: commands.join(' '),
    trunkLength: currentLength,
    letterTranslations,
    secondaryStrokes,
  };
}

/**
 * Shift an SVG path string by dx, dy, properly preserving command arity (M, L, C, Q, Z).
 */
export function shiftPathD(d: string, dx: number, dy: number = 0): string {
  const tokens = d.match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g) || [];
  const parts: string[] = [];
  let i = 0;
  while (i < tokens.length) {
    const token = tokens[i];
    if (/^[a-zA-Z]$/.test(token)) {
      const cmd = token;
      parts.push(cmd);
      i++;
      if (cmd === 'M' || cmd === 'L') {
        const x = parseFloat(tokens[i++]);
        const y = parseFloat(tokens[i++]);
        parts.push((x + dx).toFixed(1), (y + dy).toFixed(1));
      } else if (cmd === 'C') {
        const cp1X = parseFloat(tokens[i++]);
        const cp1Y = parseFloat(tokens[i++]);
        const cp2X = parseFloat(tokens[i++]);
        const cp2Y = parseFloat(tokens[i++]);
        const endX = parseFloat(tokens[i++]);
        const endY = parseFloat(tokens[i++]);
        parts.push(
          (cp1X + dx).toFixed(1),
          (cp1Y + dy).toFixed(1),
          (cp2X + dx).toFixed(1),
          (cp2Y + dy).toFixed(1),
          (endX + dx).toFixed(1),
          (endY + dy).toFixed(1),
        );
      } else if (cmd === 'Q') {
        const cx = parseFloat(tokens[i++]);
        const cy = parseFloat(tokens[i++]);
        const x = parseFloat(tokens[i++]);
        const y = parseFloat(tokens[i++]);
        parts.push(
          (cx + dx).toFixed(1),
          (cy + dy).toFixed(1),
          (x + dx).toFixed(1),
          (y + dy).toFixed(1),
        );
      }
    } else {
      i++;
    }
  }
  return parts.join(' ');
}

/**
 * Shape arbitrary Arabic text into a complete WordData structure.
 */
export function shapeArabicText(
  text: string,
  catalog: GlyphCatalog,
  options: { bridge?: number; pawGap?: number } = {},
): WordData {
  const bridge = options.bridge ?? 25.0;
  const pawGap = options.pawGap ?? 80.0;

  const paws = partitionPaws(text);
  const pawDataList: {
    pawId: string;
    letters: string;
    trunkD: string;
    trunkLength: number;
    shiftX: number;
    globalMinX: number;
    delayedRecords: DelayedStrokeData[];
  }[] = [];

  let runningXOffset = 0.0;

  for (let pawIdx = 0; pawIdx < paws.length; pawIdx++) {
    const pawLetters = paws[pawIdx];
    const pawId = `paw_${pawIdx}`;
    const trunkRes = buildPawTrunk(pawLetters, catalog, bridge);

    const delayedRecords: DelayedStrokeData[] = [];

    for (let lIdx = 0; lIdx < pawLetters.length; lIdx++) {
      const char = pawLetters[lIdx];
      const form = determineForm(char, lIdx, pawLetters);
      const glyph = catalog[`${char}_${form}`] || catalog[`${char}_isolated`];
      if (!glyph) continue;

      const [dx, dy] = trunkRes.letterTranslations[lIdx];
      for (const ds of glyph.delayed_strokes || []) {
        const shiftedPoints = ds.points.map((p) => [p[0] + dx, p[1] + dy] as Point);
        delayedRecords.push({
          role: ds.role,
          attachment_s: ds.attachment_s,
          points: shiftedPoints,
          length: ds.length,
        });
      }
    }

    // Add secondary strokes
    for (const sec of trunkRes.secondaryStrokes) {
      delayedRecords.push({
        role: 'inner_mark',
        attachment_s: 0.5,
        points: sec.points,
        length: sec.length,
      });
    }

    // Compute paw bounds
    let pawMinX = Infinity;
    let pawMaxX = -Infinity;
    const tokens = trunkRes.d.match(/[-+]?\d*\.?\d+/g) || [];
    for (let k = 0; k < tokens.length - 1; k += 2) {
      const x = parseFloat(tokens[k]);
      if (x < pawMinX) pawMinX = x;
      if (x > pawMaxX) pawMaxX = x;
    }
    for (const ds of delayedRecords) {
      for (const pt of ds.points || []) {
        if (pt[0] < pawMinX) pawMinX = pt[0];
        if (pt[0] > pawMaxX) pawMaxX = pt[0];
      }
    }
    if (!Number.isFinite(pawMinX)) {
      pawMinX = 0;
      pawMaxX = 100;
    }

    let shiftX = 0;
    if (pawIdx === 0) {
      shiftX = 0.0;
    } else {
      shiftX = runningXOffset - pawGap - pawMaxX;
    }

    const globalMinX = pawMinX + shiftX;
    runningXOffset = globalMinX;

    pawDataList.push({
      pawId,
      letters: pawLetters.join(''),
      trunkD: trunkRes.d,
      trunkLength: trunkRes.trunkLength,
      shiftX,
      globalMinX,
      delayedRecords,
    });
  }

  // Normalize so leftmost x is at 50.0
  const minX = Math.min(...pawDataList.map((p) => p.globalMinX), 0);
  const normShift = 50.0 - minX;

  const finalPaws: PawData[] = pawDataList.map((pdata) => {
    const totalShift = pdata.shiftX + normShift;

    // Shift trunk path
    const shiftedTrunkD = shiftPathD(pdata.trunkD, totalShift, 0);

    // Shift delayed strokes
    const shiftedDelayed: DelayedStrokeData[] = pdata.delayedRecords.map((ds, idx) => {
      const pts = (ds.points || []).map((p) => [p[0] + totalShift, p[1]] as Point);
      const dParts = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`);
      return {
        id: `${pdata.pawId}_delayed_${idx}`,
        role: ds.role,
        attachment_s: ds.attachment_s,
        d: dParts.join(' '),
        length: ds.length,
      };
    });

    const trunkStroke: Stroke = {
      id: `${pdata.pawId}_trunk`,
      d: shiftedTrunkD,
      length: Math.round(pdata.trunkLength),
      type: 'trunk',
    };

    return {
      id: pdata.pawId,
      letters: pdata.letters,
      trunkStroke,
      delayedStrokes: shiftedDelayed,
    };
  });

  return {
    text,
    paws: finalPaws,
  };
}
