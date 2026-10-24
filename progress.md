# MIDAD ENGINE — PROJECT PROGRESS & RESUMPTION LOG

## Project Overview
**Midad** is an open-source Arabic handwriting animation engine modeled after Vara.js, designed specifically for cursive right-to-left (RTL) script with continuous baseline welding across Pieces of Arabic Words (PAWs) and delayed rendering of dots and vocalizations (*i'jam* and *tashkeel*).

- **Project Root**: `/home/ubuntu/workspace/midad`
- **Git Safety Guard**: `git config remote.origin.pushurl "no_push_allowed"` (Local repository only; remote push is strictly forbidden).
- **Sub-Agent Execution**: `openCode` running in tmux session `midad` (`tmux attach -t midad`).

---

## Completed Milestones

### 1. Environment Bootstrap & Monorepo Initialization (`278ec84`)
- Monorepo scaffolded: `pipeline/` (Python 3.12), `engine/` (TypeScript / Vite / Vitest / Playwright), `fixtures/`, `debugger/`.
- Native dependencies installed: `libcairo2-dev`, `libpango1.0-dev`, `libharfbuzz-dev`, `libfreetype6-dev`, `fontconfig`.
- Python virtualenv at `pipeline/.venv` with `fonttools`, `uharfbuzz`, `shapely`, `scikit-image`, `scipy`, `numpy`, `bezier`, `pillow`, `pytest`.
- Node dependencies in `engine/` with Playwright Chromium installed.
- Reference fonts placed in `fixtures/fonts/`: `Amiri-Regular.ttf`, `ArefRuqaa-Regular.ttf`, `NotoNaskhArabic-Regular.ttf`.

### 2. Day-1 Task A: Ground-Truth Arabic Rules Registry (`023fc65`)
- `pipeline/src/rules.py` and `fixtures/rules/arabic_character_rules.json` created.
- Covers all 28 basic letters, plus ة, ى, ء, and 4 Lam-Alif ligatures (35 character forms total).
- Verification: 287 passed, 7 skipped in `pipeline/tests/test_day1_rules.py`.

### 3. Day-1 Task B: HarfBuzz Shaping & 5-Letter Skeleton Prototype (`605dd84`)
- `pipeline/src/extractor.py` and `pipeline/src/skeletonizer.py` implemented.
- Automatic contour separation between rasm trunks and i'jam dots.
- Distance-transform weighted dilation IoU algorithm yielding **0.956 to 0.993** IoU across all 14 prototype forms (`ا`, `ب`, `ج`, `د`, `ر`).
- Deterministic Voronoi/medial-axis extraction with `rng=0` tie-breaking.
- Fixture exported to `fixtures/skeletons/prototype_5.json`.
- Verification: 50 passed in `pipeline/tests/test_day1_prototype.py`.

### 4. Day-1 Task C: Playwright & Vitest Regression Harness (`2d15d6e`)
- `engine/src/types.ts` and `engine/src/validator.ts` implemented.
- Structural invariants enforced: single `M` command per PAW baseline, $C^0$ positional continuity, $\ge 85\%$ RTL monotonicity, and strict temporal causality for delayed strokes.
- Verification: 14 passed in `engine/tests/validator.test.ts` (Vitest), 1 passed in `engine/tests/day1_harness.spec.ts` (Playwright headless Chromium). Verification screenshot saved to `engine/tests/artifacts/day1_harness.png`.

---

## Active Milestone: MILESTONE 1 — Full Glyph Skeleton Extraction (~130 Forms)

### Objectives
1. Scale skeleton extraction from the 5 prototype letters to all **~130 core Arabic glyph forms**:
   - 28 letters across valid positional forms (Isolated, Initial, Medial, Final).
   - Right-joining letters (`ا`, `د`, `ذ`, `ر`, `ز`, `و`, `ة`, `ى`): Isolated + Final.
   - Dual-joining letters (20 letters): Isolated + Initial + Medial + Final.
   - Mandatory Lam-Alif ligatures (`لا`, `لأ`, `لإ`, `لآ`): Isolated + Final.
   - Hamza forms.
   - Total: ~120–135 glyph forms.
2. Topological Invariance: loop / cycle count check matches `rules.expected_loop_count` via Euler characteristic ($\chi = V - E$) or graph cycle detection.
3. Dilation IoU: $\ge 0.80$ for non-loop glyphs, $\ge 0.75$ for loop glyphs.
4. Output: `fixtures/skeletons/all_glyphs.json` and verification via `pipeline/tests/test_milestone1_topology.py`.

---

## Resumption Instructions (If Interrupted)
1. Verify git status and current branch:
   ```bash
   cd /home/ubuntu/workspace/midad
   git status
   git log -n 5 --oneline
   ```
2. Verify Python virtualenv:
   ```bash
   /home/ubuntu/workspace/midad/pipeline/.venv/bin/pytest pipeline/tests/
   ```
3. Verify Node engine:
   ```bash
   npm --prefix /home/ubuntu/workspace/midad/engine run test:unit
   npx --prefix /home/ubuntu/workspace/midad/engine playwright test
   ```
4. Attach to sub-agent tmux session:
   ```bash
   tmux attach -t midad
   ```
5. Check `/tmp/opencode_task.md` for current task specification.
