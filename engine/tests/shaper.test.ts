/**
 * Unit Tests for Client-Side Runtime Arabic Shaper & Welder
 */

import { describe, expect, it } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

import {
  determineForm,
  partitionPaws,
  cleanAndAlignStroke,
  shapeArabicText,
  type GlyphCatalog,
} from '../src/shaper';
import { assertPawContinuity } from '../src/validator';
import { Midad } from '../src/midad';

const GLYPHS_PATH = path.resolve(__dirname, '../dist/fonts/noto_naskh_glyphs.json');

describe('Runtime Arabic Shaper & Baseline Welder', () => {
  describe('PAW Partitioning', () => {
    it('splits text at non-connecting letters (ا, د, ر, و, etc.)', () => {
      // كتب -> single PAW (all connecting)
      expect(partitionPaws('كتب')).toEqual([['ك', 'ت', 'ب']]);

      // دار -> 'د' (non-connecting), 'ا' (non-connecting), 'ر' -> 3 PAWs
      expect(partitionPaws('دار')).toEqual([['د'], ['ا'], ['ر']]);

      // كتاب -> 'كت' + 'ا' + 'ب' -> 3 PAWs
      expect(partitionPaws('كتاب')).toEqual([['ك', 'ت'], ['ا'], ['ب']]);

      // مدينة -> 'مد' + 'ي' + 'ن' + 'ة' -> 'مد' + 'ينة' -> 2 PAWs
      expect(partitionPaws('مدينة')).toEqual([['م', 'د'], ['ي', 'ن', 'ة']]);
    });

    it('splits text at spaces and punctuation', () => {
      const paws = partitionPaws('كتب قلم!');
      expect(paws).toEqual([['ك', 'ت', 'ب'], ['ق', 'ل', 'م']]);
    });
  });

  describe('Form Determination', () => {
    it('correctly assigns isolated, initial, medial, and final forms', () => {
      const paw = ['ك', 'ت', 'ب'];
      expect(determineForm('ك', 0, paw)).toBe('initial');
      expect(determineForm('ت', 1, paw)).toBe('medial');
      expect(determineForm('ب', 2, paw)).toBe('final');

      // Single letter is isolated
      expect(determineForm('د', 0, ['د'])).toBe('isolated');

      // Right-joining letters have only isolated or final forms
      expect(determineForm('د', 0, ['د', 'ا'])).toBe('isolated');
      expect(determineForm('ا', 1, ['د', 'ا'])).toBe('final');
    });
  });

  describe('Stroke Cleaning & Alignment', () => {
    it('forces horizontal terminal exit tangent for connecting strokes', () => {
      const rawPoints: [number, number][] = [
        [500, 100],
        [400, 95],
        [300, 90],
        [200, 85],
        [150, 80],
        [100, 60], // downward hook spur
      ];

      const cleaned = cleanAndAlignStroke(rawPoints, true, false, false);
      expect(cleaned.length).toBeGreaterThan(3);

      const last = cleaned[cleaned.length - 1];
      const prev = cleaned[cleaned.length - 2];
      // Exit tangent must be strictly horizontal (same y coordinate)
      expect(last[1]).toBe(prev[1]);
    });
  });

  describe('Arbitrary Arabic Text Synthesis', () => {
    const rawCatalog = JSON.parse(fs.readFileSync(GLYPHS_PATH, 'utf-8'));
    const catalog: GlyphCatalog = rawCatalog.glyphs || rawCatalog;

    it('synthesizes arbitrary Arabic words with Single-M invariant', () => {
      const wordsToTest = ['مرحبا', 'سلام', 'نور', 'قلم', 'جمال'];

      for (const word of wordsToTest) {
        const shaped = shapeArabicText(word, catalog);
        expect(shaped.text).toBe(word);
        expect(shaped.paws.length).toBeGreaterThan(0);

        for (const paw of shaped.paws) {
          // Assert Single-M invariant
          const report = assertPawContinuity(paw.trunkStroke.d);
          expect(
            report.valid,
            `Word "${word}" paw "${paw.id}" failed: ${report.errors.join('; ')} | SVG: ${paw.trunkStroke.d.slice(0, 100)}...`,
          ).toBe(true);
          expect(report.errors).toHaveLength(0);

          // Assert trunk stroke length is positive
          expect(paw.trunkStroke.length).toBeGreaterThan(0);
        }
      }
    });

    it('integrates seamlessly with Midad instance for arbitrary user-typed text', async () => {
      const container = document.createElement('div');
      document.body.appendChild(container);

      // Create Midad instance passing the glyphs catalog directly
      const midad = new Midad(container, { glyphs: catalog }, 'سلام', {
        autoAnimation: false,
      });

      await new Promise<void>((resolve) => midad.ready(resolve));

      expect(midad.isReady).toBe(true);
      expect(midad.get()).toBeDefined();

      // Play & seek
      midad.play();
      expect(midad.state).toBe('playing');
      midad.seek(0.5);

      midad.destroy();
    });
  });
});
