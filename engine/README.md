# Midad (مداد) — Arabic Handwriting Animation Engine

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue)
![Python](https://img.shields.io/badge/Python-3.12-green)
![Bundle Size](https://img.shields.io/badge/engine_bundle-%3C%208.1%20KB%20gzipped-brightgreen)
![Font Size](https://img.shields.io/badge/packaged_font-%3C%2048.9%20KB%20gzipped-brightgreen)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

**An open-source handwriting animation engine modeled after Vara.js, designed specifically for Arabic cursive script.**

[Features](#key-features) •
[Quick Start](#quick-start) •
[API Reference](#api-reference) •
[Architecture](#architecture--mathematical-invariants) •
[Interactive Debuggers](#interactive-debuggers) •
[Contributing](#development--testing)

</div>

---

## Overview

Arabic script presents unique mathematical challenges for animated handwriting engines:
- **Right-to-Left (RTL) Cursive Flow**: Glyphs connect continuously along the baseline within each Piece of Arabic Word (PAW).
- **Baseline Welding**: Letters must weld together seamlessly without self-intersecting loops, diamond notches, or baseline spikes.
- **Strict Temporal Causality**: Dots (*i'jam*) and diacritics (*tashkeel*, *hamza*, *madda*) must be drawn **after** the parent letter/PAW baseline has finished drawing—never before.

**Midad** solves these challenges with a dual-pipeline architecture:
1. **Python Pipeline**: HarfBuzz glyph extraction, medial-axis skeletonization, calligraphic ductus ordering, cubic baseline welding, and RDP packaging.
2. **TypeScript Web Engine**: High-performance SVG `stroke-dasharray` / `stroke-dashoffset` rendering, Vara.js-compatible API, causal timeline scheduling, and zero external runtime dependencies.

---

## Key Features

- **Continuous RTL Baseline Welding**:
  - **Single-`M` Invariant**: Exactly one SVG `M` (moveto) command per PAW baseline trunk.
  - **$C^0$ Positional Continuity**: Joint distance $\Delta < 0.05$ font units.
  - **$G^1$ Tangent Continuity**: Incoming and outgoing joint tangent angle $\Delta \theta < 12^\circ$.
- **Calligraphic Temporal Causality**:
  - Baseline trunk draws first.
  - Delayed strokes (dots, hamza, madda, kaf mark) animate in sequence based on their baseline attachment parameter $s_{\text{attach}}$.
  - Calibrated pen-lift pauses between strokes ($40\text{ ms}$) and PAWs ($100\text{ ms}$).
- **Vara.js-Compatible API**:
  - Direct drop-in compatibility with familiar Vara.js semantics: `new Midad(selector, font, texts, options)`.
  - Methods: `play()`, `pause()`, `resume()`, `restart()`, `reset()`, `seek(progress)`, `get(index)`.
  - Callbacks & Events: `ready(cb)`, `animationEnd(cb)`, `.on()`, `.once()`, `.off()`.
- **Ultra-Lightweight Production Distribution**:
  - Standalone Engine: **8.04 KB gzipped** (27.59 KB raw ES / 19.47 KB raw UMD).
  - 50-Word Packaged Font: **48.8 KB gzipped** (159 KB raw JSON).
  - **Zero runtime dependencies**.

---

## Quick Start

### 1. Browser (UMD via Script Tag)

```html
<div id="midad-container" style="width: 600px; height: 300px;"></div>

<!-- Include Midad UMD bundle -->
<script src="dist/midad.umd.js"></script>

<script>
  // Initialize Midad with container selector and font JSON URL
  const midad = new Midad('#midad-container', 'dist/fonts/noto_naskh_50.json', [
    {
      text: 'كتب',
      strokeWidth: 26,
      color: '#06b6d4',
      speed: 1500
    }
  ], {
    autoAnimation: true,
    pauseBetweenStrokes: 40,
    pauseBetweenPaws: 100
  });

  midad.ready(() => {
    console.log('Midad font loaded and ready to animate!');
  });

  midad.animationEnd((wordIndex, textSpec) => {
    console.log('Finished animating word:', textSpec.text);
  });
</script>
```

### 2. Modern ES Modules / NPM

```typescript
import { Midad } from 'midad';
import fontData from './fonts/noto_naskh_50.json';

const container = document.getElementById('arabic-canvas')!;

const midad = new Midad(container, fontData, [
  { text: 'محمد', color: '#10b981', strokeWidth: 28 },
  { text: 'جميل', color: '#f59e0b', strokeWidth: 24 }
], {
  autoAnimation: true,
  queued: true
});

midad.on('pawStart', ({ pawId }) => console.log('Started PAW:', pawId));
midad.on('strokeEnd', ({ strokeId }) => console.log('Finished stroke:', strokeId));
```

---

## API Reference

### `new Midad(container, fontSource, texts, options)`

#### Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `container` | `string \| HTMLElement` | CSS selector (e.g. `'#canvas'`) or DOM element. |
| `fontSource` | `string \| FontData \| WordData` | URL string to font JSON, raw JSON string, or preloaded font object. |
| `texts` | `string \| MidadTextSpec \| (string \| MidadTextSpec)[]` | Words to animate. |
| `options` | `MidadOptions` | Optional global configuration object. |

#### Global Options (`MidadOptions`)

```typescript
interface MidadOptions {
  autoAnimation?: boolean;       // Start playing immediately when ready (default: true)
  queued?: boolean;              // Play multiple words in sequence (default: true)
  speed?: number;               // Drawing speed in font units/second (default: 1500)
  duration?: number;            // Fixed total duration in ms (overrides speed if set)
  strokeWidth?: number;         // Stroke width in user units (default: 28.0)
  color?: string;               // Ink color hex/CSS string (default: '#06b6d4')
  pauseBetweenStrokes?: number; // Millisecond pause before delayed marks (default: 40)
  pauseBetweenPaws?: number;    // Millisecond pause between PAWs/words (default: 100)
}
```

#### Per-Text Specification (`MidadTextSpec`)

```typescript
interface MidadTextSpec {
  text: string;                 // Arabic word string (e.g. 'خطاط')
  color?: string;               // Word-specific ink color
  strokeWidth?: number;         // Word-specific stroke width
  speed?: number;               // Word-specific drawing speed
  duration?: number;            // Word-specific duration in ms
  pauseBetweenStrokes?: number; // Word-specific mark pause
  pauseBetweenPaws?: number;    // Word-specific PAW pause
}
```

#### Methods

- **`midad.play(wordIndex?)`**: Start or resume playback.
- **`midad.pause()`**: Pause the active animation.
- **`midad.resume()`**: Resume from paused state.
- **`midad.restart(wordIndex?)`**: Rewind to beginning and play immediately.
- **`midad.reset(wordIndex?)`**: Rewind to beginning and reset state to `idle`.
- **`midad.seek(progress)`**: Seek current word to progress fraction ($0.0 \le p \le 1.0$).
- **`midad.get(index?)`**: Returns the rendered `<svg>` element.
- **`midad.state`**: Get current playback status (`'idle' | 'playing' | 'paused' | 'completed'`).
- **`midad.destroy()`**: Clean up DOM elements, cancel animation frames, and remove listeners.

#### Events & Callbacks

```typescript
// Vara.js compatible convenience helpers:
midad.ready((data) => { /* Font loaded & parsed */ });
midad.animationEnd((wordIndex, textSpec) => { /* Word animation finished */ });

// Full Event Emitter (.on, .once, .off):
midad.on('ready', ({ wordsCount }) => {});
midad.on('start', () => {});
midad.on('pawStart', ({ pawId }) => {});
midad.on('pawEnd', ({ pawId }) => {});
midad.on('strokeStart', ({ strokeId, pawId }) => {});
midad.on('strokeEnd', ({ strokeId, pawId }) => {});
midad.on('progress', ({ currentTime, totalDuration, progress }) => {});
midad.on('complete', () => {});
midad.on('warning', ({ code, message }) => {});
```

---

## Architecture & Mathematical Invariants

```
                ┌───────────────────────────────────────────────┐
                │          HarfBuzz & FontTools Pipeline        │
                │  - Glyph outline extraction & separation      │
                │  - Medial-axis Voronoi skeletonization        │
                │  - Dilation IoU verification (≥ 0.93 - 0.99)  │
                └──────────────────────┬────────────────────────┘
                                       ▼
                ┌───────────────────────────────────────────────┐
                │        Calligraphic Ductus Ordering           │
                │  - Multi-stroke decomposition (Tah, Lam-Alif) │
                │  - Topological loop repair (Sad, Ain, Meem)   │
                │  - RTL monotonic arc-length s ∈ [0, 1]        │
                └──────────────────────┬────────────────────────┘
                                       ▼
                ┌───────────────────────────────────────────────┐
                │           RTL Baseline Welding Engine         │
                │  - PAW partitioning at non-connecting letters │
                │  - Tangent-aligned cubic baseline fillets     │
                │  - Invariants: Single-M, C⁰ < 0.05, G¹ < 12°  │
                └──────────────────────┬────────────────────────┘
                                       ▼
                ┌───────────────────────────────────────────────┐
                │        Midad TypeScript Animation Engine      │
                │  - Causal timeline scheduler                  │
                │  - 60 FPS requestAnimationFrame renderer      │
                │  - Vara.js-compatible public API             │
                └───────────────────────────────────────────────┘
```

### Invariants Enforced by Automated Verification:
1. **Topological Genus**: Euler characteristic matches calligraphy rules (closed loops on ص, ض, ط, ظ, ف, ق, م, ه, و, ة).
2. **Single-`M` Command**: 100% of PAW baseline trunks contain exactly one SVG `M` command.
3. **$C^0$ Continuity**: Joint gap distance $\Delta = 0.0000$ font units (threshold $< 0.05$).
4. **$G^1$ Continuity**: Joint tangent deviation $\Delta \theta = 0.00^\circ$ (threshold $< 12^\circ$).
5. **Temporal Causality**: Delayed strokes are guaranteed to begin **strictly after** the parent PAW baseline completes.
6. **Package Size Budgets**:
   - Engine bundle: strictly $< 25\text{ KB}$ gzipped (actual: **8.04 KB**).
   - Font package: strictly $< 95\text{ KB}$ gzipped (actual: **48.8 KB**).

---

## Interactive Debuggers

The repository includes standalone HTML visual debuggers with zero external dependencies:

| Tool | Path | Description |
| :--- | :--- | :--- |
| **Midad Web Player** | `debugger/midad_player.html` | Interactive showcase across 50 canonical Arabic words with scrubber timeline, play/pause, speed controls ($0.25\times$–$3.0\times$), ink palettes, and live event HUD. |
| **Joints Inspector** | `debugger/milestone3_joints.html` | Visual audit of welded baseline joints, displaying green $C^0/G^1$ markers and delayed stroke attachments. |
| **Calligraphy Auditor** | `debugger/milestone2_audit.html` | Ductus inspection across 119 Arabic glyph presentation forms with directional chevrons and loop classifiers. |

To view any debugger locally:
```bash
npx vite --port 4173
# Then open http://localhost:4173/debugger/midad_player.html
```

---

## Development & Testing

### Monorepo Structure

```
midad/
├── engine/              # TypeScript / Vite / Vitest / Playwright engine
│   ├── src/             # Core engine: midad.ts, renderer.ts, scheduler.ts, types.ts
│   ├── tests/           # Vitest and Playwright regression suites
│   └── dist/            # Production ES/UMD bundles and packaged fonts
├── pipeline/            # Python 3.12 HarfBuzz & skeletonization pipeline
│   ├── src/             # rules.py, extractor.py, skeletonizer.py, shaper.py, packager.py
│   └── tests/           # Pytest mathematical invariant test suites
├── fixtures/            # Golden fixtures, reference fonts, and character rules
└── debugger/            # Standalone visual inspection and player web apps
```

### Running Test Suites

```bash
# 1. Engine Vitest API Suite
cd engine && npx vitest run tests/api.test.ts

# 2. Engine Playwright Visual Regression Suite
npx playwright test engine/tests/milestone5_visual.spec.ts

# 3. Python Pipeline Mathematical Invariants
pipeline/.venv/bin/pytest pipeline/tests/test_milestone3_welding.py
```

---

## License

MIT License. Open source and free for commercial and non-commercial use.
