# MIDAD ENGINE — PROJECT PROGRESS & RESUMPTION LOG

## Project Overview
**Midad** is an open-source Arabic handwriting animation engine modeled after Vara.js, designed specifically for cursive right-to-left (RTL) script with continuous baseline welding across Pieces of Arabic Words (PAWs) and delayed rendering of dots and vocalizations (*i'jam* and *tashkeel*).

- **Project Root**: `/home/ubuntu/workspace/midad`
- **Git Safety Guard**: `git config remote.origin.pushurl "no_push_allowed"` (Local repository only; remote push is strictly forbidden).
- **Sub-Agent Execution**: `openCode` running in tmux session `midad` (`tmux attach -t midad`) using model `nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b`.

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

### 5. Milestone 1: Full Glyph Skeleton Extraction (~113 Forms) (COMPLETE ✅)
- Scaled skeleton extraction across the full Arabic alphabet + ligatures:
  - 113 total glyph presentation forms cataloged in `fixtures/skeletons/all_glyphs.json`.
  - Topological genus / loop counts match `rules.expected_loop_count` across all bowl/loop letters (ص, ض, ط, ظ, ف, ق, م, ه, و, ة).
  - Graph-based cycle rank `compute_loop_count(coords, adj)` implemented.
  - Calibrated dilation IoU performance:
    - Min IoU: **0.9366** (exceeds $\ge 0.75$ / $\ge 0.80$ gates by a wide margin)
    - Max IoU: **0.9932**
    - Mean IoU: **0.9737**
  - Anchor points (`entry_anchor`, `exit_anchor`) computed for joining compatibility.
- Verification: 12 passed in `pipeline/tests/test_milestone1_topology.py`.
- Monorepo full python suite: **349 passed, 7 skipped in 43.21s**.

---

## Active Milestone: MILESTONE 2 — Stroke Graph & PAW Trajectory Ordering

### Objectives
1. **Kinematic Stroke Parameterization**:
   - Parameterize centerline paths $s \in [0, 1]$ adhering strictly to Arabic calligraphic writing direction:
     - Right-to-Left (RTL) horizontal progression: $\frac{dx}{ds} \le 0$ for $\ge 85\%$ of arc length.
     - Top-to-Bottom descending vertical progression (e.g. Alef, Lam masts, Kaf ascenders).
     - Proper loop traversal order (e.g. Waw head clockwise/counterclockwise as per Naskh ductus).
2. **Anchor Coordinate Precision**:
   - Exact entry (`entry_anchor`) and exit (`exit_anchor`) points matched to font baseline $y \approx 0$ for inter-glyph welding.
3. **Audit Debugger Harness**:
   - Create `/debugger/milestone2_audit.html`:
     - Displays all 113 glyphs in an interactive grid.
     - Layers: original font contour (translucent), skeleton path (bold orange), entry point (green dot), exit point (red dot), animated flow direction indicators.
4. **Human-in-the-Loop (HITL) Checkpoint #1**:
   - Once Milestone 2 passes automated tests (`pipeline/tests/test_milestone2_kinematics.py`), pause and emit the status report for human visual approval before proceeding to Milestone 3.

---

## Operational Notes
- **Vitest**: Skipped per user instruction to avoid worker thread hangs in this environment. Engine validation uses Playwright headless tests and isolated verification scripts.
- **Terminal Execution Guard**: Strict timeout (`timeout 30s ...`) applied to all commands to prevent indefinite execution.

---

## Resumption Instructions (If Interrupted)
1. Verify git status and current branch:
   ```bash
   cd /home/ubuntu/workspace/midad
   timeout 10s git status
   timeout 10s git log -n 5 --oneline
   ```
2. Verify Python pipeline tests:
   ```bash
   timeout 60s /home/ubuntu/workspace/midad/pipeline/.venv/bin/pytest pipeline/tests/test_milestone1_topology.py
   ```
3. Check Milestone 2 progress:
   ```bash
   ls -la debugger/milestone2_audit.html pipeline/src/trajectory.py
   ```
