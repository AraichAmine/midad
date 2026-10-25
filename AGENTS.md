# AI Agent Operating Guidelines: Midad (مداد)

> **Purpose**: This guide provides operational context, architectural invariants, code standards, and verification rules for AI coding agents (Antigravity, Cursor, Claude Code, Codex, openCode, Aider) contributing to the **Midad** codebase.

---

## 1. Project Mission & Core Architecture

Midad is an open-source Arabic handwriting animation engine designed specifically for cursive right-to-left (RTL) script with continuous baseline welding across Pieces of Arabic Words (PAWs) and causal delayed rendering of dots and vocalizations (*i'jam* and *tashkeel*).

### Monorepo Structure:
- `engine/`: TypeScript / Vite / Vitest / Playwright runtime engine. This is published to npm as `midad`.
- `pipeline/`: Python 3.12 HarfBuzz outline extraction, medial-axis skeletonization, cubic baseline welding, and font packaging.
- `fixtures/`: Reference fonts (`fixtures/fonts/`), character rules registry (`fixtures/rules/`), and golden datasets.
- `debugger/`: Standalone HTML visual inspectors and animation player.

---

## 2. Mathematical Invariants (NON-NEGOTIABLE)

Every modification to the glyph extraction, shaper, or engine **must strictly uphold** these mathematical invariants:

1. **Single-`M` Invariant**:
   - Each PAW baseline trunk MUST be a single continuous SVG path starting with exactly one `M` (moveto) command and **no subsequent `M` commands**.
   - No disconnected segments inside a PAW baseline.

2. **$C^0$ Positional Continuity**:
   - At every welded letter-to-letter joint, the distance gap $\Delta = \|P_{\text{exit}}^{(i)} - P_{\text{entry}}^{(i+1)}\|$ must satisfy $\Delta < 0.05\text{ font units}$.

3. **$G^1$ Tangent Angle Continuity**:
   - The outgoing tangent of letter $i$ and incoming tangent of letter $i+1$ at the weld bridge must satisfy $\Delta \theta < 12^\circ$ (ideally $\approx 0^\circ$ along the horizontal writing ductus).

4. **Strict Temporal Causality**:
   - Delayed marks (dots, hamza, madda, kaf mark) MUST begin animating strictly **after** their parent PAW baseline trunk completes drawing.
   - All delayed marks of a PAW must complete before the subsequent PAW begins.

5. **Distribution Size Budgets**:
   - Standalone engine bundle: strictly $< 25\text{ KB}$ gzipped.
   - Packaged font JSON: strictly $< 95\text{ KB}$ gzipped.

---

## 3. Test & Verification Guidelines

### How to Run Automated Verification:
- **Engine Unit Tests (Vitest)**:
  ```bash
  cd engine && npx vitest run tests/api.test.ts
  ```
- **Engine Typecheck**:
  ```bash
  cd engine && npm run typecheck
  ```
- **Engine Production Build**:
  ```bash
  cd engine && npm run build
  ```
- **Python Mathematical Invariant Suites**:
  ```bash
  pipeline/.venv/bin/pytest pipeline/tests/test_milestone3_welding.py
  pipeline/.venv/bin/pytest pipeline/tests/test_milestone2_kinematics.py
  ```

### Delegation Rule:
- When operating in paired environments with an interactive sub-agent (e.g. openCode running in a tmux session), delegate test runs and inspect pane output rather than spawning unmanaged processes.

---

## 4. Coding Conventions

- **TypeScript (`engine/`)**:
  - Strict mode enabled (`tsconfig.json`).
  - No `any` without explicit justification; use defined types in `types.ts`.
  - Zero external runtime dependencies in production bundle (`vite.config.ts`).
- **Python (`pipeline/`)**:
  - Python 3.12 with type annotations (`from __future__ import annotations`).
  - Standard mathematical libraries: `numpy`, `shapely`, `fonttools`, `uharfbuzz`.
- **Git Hygiene**:
  - Keep commits focused and atomic with descriptive conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`).
  - Never commit build output (`node_modules/`, `.venv/`, temporary test artifacts).
