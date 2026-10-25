"""Generate standalone debugger/midad_player.html for interactive handwriting playback.

Embeds fixtures/golden/welded_50_words.json and engine/dist/midad.umd.js
so the player is completely self-contained and operates without a web server.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_JSON = REPO_ROOT / "fixtures" / "golden" / "welded_50_words.json"
UMD_BUNDLE = REPO_ROOT / "engine" / "dist" / "midad.umd.js"
OUT_HTML = REPO_ROOT / "debugger" / "midad_player.html"


def generate_player_html():
    with GOLDEN_JSON.open(encoding="utf-8") as f:
        font_data = json.load(f)

    with UMD_BUNDLE.open(encoding="utf-8") as f:
        umd_code = f.read()

    words = font_data["words"]
    word_texts = [w["text"] for w in words]
    words_json = json.dumps(font_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MIDAD — Interactive Arabic Handwriting Engine</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Inter:wght@300;400;500;600;700&family=Noto+Naskh+Arabic:wght@400;600;700&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      /* Design System: Midad Player — Dark Mode (OLED) */
      --color-background: #0f172a;
      --color-foreground: #f8fafc;
      --color-card: #1b2336;
      --color-card-foreground: #f8fafc;
      --color-muted: #272f42;
      --color-muted-foreground: #94a3b8;
      --color-border: #475569;
      --color-primary: #1e293b;
      --color-on-primary: #ffffff;
      --color-secondary: #334155;
      --color-on-secondary: #ffffff;
      --color-accent: #22c55e;
      --color-on-accent: #0f172a;
      --color-destructive: #ef4444;
      --color-on-destructive: #000000;
      --color-ring: #ffffff;

      /* Ink accents (handwriting strokes) */
      --ink-cyan: #06b6d4;
      --ink-emerald: #10b981;
      --ink-amber: #f59e0b;
      --ink-purple: #a855f7;
      --ink-rose: #f43f5e;
      --ink-white: #f8fafc;

      --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
      --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
      --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.15);
      --shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.2);

      --space-xs: 0.25rem;
      --space-sm: 0.5rem;
      --space-md: 1rem;
      --space-lg: 1.5rem;
      --space-xl: 2rem;
      --space-2xl: 3rem;

      --radius-sm: 0.5rem;
      --radius-md: 0.75rem;
      --radius-lg: 1rem;
      --radius-full: 9999px;

      --font-ui: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-arabic: 'Noto Naskh Arabic', 'Amiri', 'Segoe UI', serif;
      --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;

      --transition: 180ms ease;
    }}

    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }}
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    html {{
      scrollbar-gutter: stable;
    }}

    body {{
      background: var(--color-background);
      color: var(--color-foreground);
      font-family: var(--font-ui);
      font-size: 16px;
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }}

    :focus-visible {{
      outline: 2px solid var(--color-ring);
      outline-offset: 2px;
      border-radius: 2px;
    }}

    /* Header Bar */
    header {{
      background: rgba(15, 23, 42, 0.8);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--color-border);
      padding: 1rem var(--space-lg);
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 50;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: var(--space-md);
    }}

    .logo-mark {{
      width: 40px;
      height: 40px;
      border-radius: var(--radius-md);
      background: linear-gradient(135deg, var(--ink-cyan) 0%, var(--ink-emerald) 100%);
      display: grid;
      place-items: center;
      box-shadow: 0 0 20px rgba(6, 182, 212, 0.35);
    }}

    .logo-mark svg {{
      width: 20px;
      height: 20px;
      fill: #0f172a;
    }}

    .brand-copy {{
      display: flex;
      flex-direction: column;
      line-height: 1.15;
    }}

    .brand-title {{
      font-family: var(--font-arabic);
      font-size: 1.5rem;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: -0.02em;
    }}

    .brand-subtitle {{
      font-size: 0.75rem;
      color: var(--color-muted-foreground);
      letter-spacing: 0.03em;
      font-family: var(--font-ui);
      font-weight: 500;
      text-transform: uppercase;
    }}

    .header-badges {{
      display: flex;
      gap: var(--space-sm);
      align-items: center;
    }}

    .badge {{
      background: rgba(34, 197, 94, 0.1);
      border: 1px solid rgba(34, 197, 94, 0.2);
      color: var(--color-accent);
      padding: 0.2rem 0.7rem;
      border-radius: var(--radius-full);
      font-size: 0.7rem;
      font-weight: 600;
      font-family: var(--font-mono);
      display: flex;
      align-items: center;
      gap: 0.35rem;
      cursor: default;
    }}

    /* Main Container */
    main {{
      max-width: 1400px;
      margin: var(--space-lg) auto;
      padding: 0 var(--space-md) var(--space-2xl);
      width: 100%;
      display: grid;
      grid-template-columns: 1fr 360px;
      gap: var(--space-lg);
      flex: 1;
    }}

    @media (max-width: 1024px) {{
      main {{
        grid-template-columns: 1fr;
        gap: var(--space-md);
      }}
    }}

    @media (max-width: 640px) {{
      main {{
        padding: 0 var(--space-sm) var(--space-xl);
      }}
    }}

    /* Stage Panel */
    .stage-card {{
      background: var(--color-card);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      backdrop-filter: blur(20px);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: var(--shadow-xl);
    }}

    .stage-topbar {{
      padding: 1rem var(--space-lg);
      border-bottom: 1px solid var(--color-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(0, 0, 0, 0.2);
    }}

    .current-word-title {{
      font-family: var(--font-arabic);
      font-size: 2.75rem;
      font-weight: 700;
      color: #ffffff;
      display: flex;
      align-items: baseline;
      gap: var(--space-md);
      line-height: 1;
    }}

    .word-index-tag {{
      font-size: 0.7rem;
      font-family: var(--font-mono);
      color: var(--color-muted-foreground);
      font-weight: 500;
      padding-top: 0.35rem;
      letter-spacing: 0.05em;
    }}

    .live-status-pill {{
      display: flex;
      align-items: center;
      gap: var(--space-sm);
      background: rgba(0, 0, 0, 0.35);
      padding: 0.3rem 0.85rem;
      border-radius: var(--radius-full);
      border: 1px solid var(--color-border);
      font-size: 0.72rem;
      font-family: var(--font-ui);
      font-weight: 500;
    }}

    .status-dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--color-muted-foreground);
      transition: background var(--transition), box-shadow var(--transition);
    }}
    .status-dot.playing {{
      background: var(--color-accent);
      box-shadow: 0 0 12px var(--color-accent);
    }}
    .status-dot.paused {{
      background: var(--ink-amber);
      box-shadow: 0 0 12px var(--ink-amber);
    }}
    .status-dot.idle {{
      background: var(--color-muted-foreground);
    }}

    /* Canvas Area */
    .canvas-viewport {{
      flex: 1;
      min-height: 520px;
      position: relative;
      background: radial-gradient(circle at center, rgba(17, 24, 39, 0.8) 0%, rgba(8, 12, 20, 0.95) 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      overflow: hidden;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
    }}

    /* Grid lines in canvas */
    .canvas-viewport::before {{
      content: '';
      position: absolute;
      inset: 0;
      background-image: 
        linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      border-radius: var(--radius-lg);
      mask-image: linear-gradient(to bottom, black 80%, transparent 100%);
      -webkit-mask-image: linear-gradient(to bottom, black 80%, transparent 100%);
    }}

    #midadContainer {{
      width: 100%;
      height: 100%;
      min-height: 460px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      z-index: 2;
    }}

    /* SVG Stroke Glow */
    .glow-effect .midad-stroke {{
      filter: drop-shadow(0 0 10px currentColor);
    }}

    /* Empty stage state */
    .empty-stage {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: var(--space-md);
      color: var(--color-muted-foreground);
      text-align: center;
      padding: var(--space-xl);
    }}

    .empty-stage svg {{
      width: 64px;
      height: 64px;
      opacity: 0.5;
    }}

    /* Timeline & Playback Bar */
    .playback-toolbar {{
      padding: var(--space-lg);
      background: rgba(0, 0, 0, 0.25);
      border-top: 1px solid var(--color-border);
      display: flex;
      flex-direction: column;
      gap: var(--space-lg);
    }}

    .scrubber-row {{
      display: flex;
      align-items: center;
      gap: var(--space-md);
    }}

    .time-label {{
      font-size: 0.75rem;
      font-family: var(--font-mono);
      color: var(--color-muted-foreground);
      min-width: 56px;
      text-align: center;
      direction: ltr;
    }}

    .scrubber-slider {{
      flex: 1;
      -webkit-appearance: none;
      height: 5px;
      border-radius: var(--radius-full);
      background: rgba(255, 255, 255, 0.1);
      outline: none;
      cursor: pointer;
    }}
    .scrubber-slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      width: 15px;
      height: 15px;
      border-radius: 50%;
      background: var(--color-accent);
      box-shadow: 0 0 10px rgba(34, 197, 94, 0.45);
      cursor: pointer;
      transition: transform var(--transition);
    }}
    .scrubber-slider::-webkit-slider-thumb:hover {{
      transform: scale(1.2);
    }}
    .scrubber-slider:focus-visible::-webkit-slider-thumb {{
      box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.25);
    }}

    .controls-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-sm);
    }}

    .btn-group {{
      display: flex;
      gap: var(--space-sm);
    }}

    .btn {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--color-border);
      color: var(--color-foreground);
      padding: 0.55rem 1.1rem;
      border-radius: var(--radius-md);
      font-size: 0.8rem;
      font-weight: 600;
      font-family: var(--font-ui);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: var(--space-sm);
      transition: all var(--transition);
      line-height: 1;
    }}
    .btn:hover {{
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }}
    .btn:focus-visible {{
      border-color: var(--color-ring);
    }}
    .btn svg {{
      width: 16px;
      height: 16px;
      flex-shrink: 0;
    }}
    .btn.primary {{
      background: var(--color-accent);
      border-color: transparent;
      color: var(--color-on-accent);
      box-shadow: 0 0 0 rgba(34, 197, 94, 0);
    }}
    .btn.primary:hover {{
      background: #29d470;
      box-shadow: 0 4px 14px rgba(34, 197, 94, 0.35);
    }}
    .btn.primary:active {{
      transform: translateY(0);
    }}
    .btn.active {{
      background: var(--color-accent);
      border-color: transparent;
      color: var(--color-on-accent);
      box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.2);
    }}
    .btn.secondary {{
      background: rgba(255, 255, 255, 0.03);
      color: var(--color-muted-foreground);
    }}
    .btn.secondary:hover {{
      color: var(--color-foreground);
      border-color: var(--color-border);
    }}

    /* Sidebar Panel */
    .sidebar {{
      display: flex;
      flex-direction: column;
      gap: var(--space-lg);
    }}

    .panel-card {{
      background: var(--color-card);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: var(--space-lg);
      backdrop-filter: blur(20px);
      box-shadow: var(--shadow-lg);
    }}

    .panel-title {{
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--color-foreground);
      margin-bottom: var(--space-md);
      display: flex;
      align-items: center;
      justify-content: space-between;
      letter-spacing: 0.05em;
      font-family: var(--font-mono);
      text-transform: uppercase;
    }}

    .panel-title .count {{
      font-size: 0.68rem;
      font-weight: 500;
      color: var(--color-muted-foreground);
      background: var(--color-muted);
      padding: 0.1rem 0.55rem;
      border-radius: var(--radius-full);
    }}

    .word-picker-select {{
      width: 100%;
      background: rgba(2, 6, 12, 0.6);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      color: var(--color-foreground);
      padding: 0.6rem 0.8rem;
      font-family: var(--font-arabic);
      font-size: 1.2rem;
      cursor: pointer;
      outline: none;
      transition: border-color var(--transition), box-shadow var(--transition);
    }}
    .word-picker-select:focus-visible {{
      border-color: var(--color-ring);
      box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.1);
    }}
    .word-picker-select option {{
      background: #0b1120;
      color: #f8fafc;
    }}

    /* Quick Chips */
    .quick-chips {{
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-sm);
      margin-top: var(--space-sm);
    }}

    .chip {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 0.3rem 0.75rem;
      font-family: var(--font-arabic);
      font-size: 0.95rem;
      color: var(--color-muted-foreground);
      cursor: pointer;
      transition: all var(--transition);
      line-height: 1.2;
    }}
    .chip:hover {{
      background: rgba(6, 182, 212, 0.1);
      border-color: var(--ink-cyan);
      color: var(--ink-cyan);
      transform: translateY(-1px);
    }}
    .chip.active {{
      background: rgba(6, 182, 212, 0.15);
      border-color: var(--ink-cyan);
      color: var(--ink-cyan);
      box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.15);
    }}
    .chip:focus-visible {{
      outline: 2px solid var(--color-ring);
      outline-offset: 1px;
    }}

    /* Control Sliders in Sidebar */
    .setting-group {{
      display: flex;
      flex-direction: column;
      gap: var(--space-sm);
      margin-bottom: var(--space-md);
    }}

    .setting-label {{
      display: flex;
      justify-content: space-between;
      font-size: 0.72rem;
      color: var(--color-muted-foreground);
      font-family: var(--font-mono);
    }}

    .setting-value {{
      font-weight: 600;
      color: var(--ink-cyan);
      font-family: var(--font-mono);
    }}

    .slider {{
      -webkit-appearance: none;
      height: 4px;
      border-radius: var(--radius-full);
      background: rgba(255, 255, 255, 0.08);
      outline: none;
      cursor: pointer;
    }}
    .slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--ink-cyan);
      cursor: pointer;
      transition: transform var(--transition), box-shadow var(--transition);
    }}
    .slider::-webkit-slider-thumb:hover {{
      transform: scale(1.2);
    }}
    .slider:focus-visible::-webkit-slider-thumb {{
      box-shadow: 0 0 0 4px rgba(6, 182, 212, 0.25);
    }}

    /* Palette colors */
    .color-palette {{
      display: flex;
      gap: var(--space-sm);
      margin-top: var(--space-xs);
    }}

    .color-swatch {{
      width: 26px;
      height: 26px;
      border-radius: 50%;
      cursor: pointer;
      border: 2px solid transparent;
      transition: transform var(--transition), border-color var(--transition);
    }}
    .color-swatch:hover {{
      transform: scale(1.15);
    }}
    .color-swatch.active {{
      transform: scale(1.2);
      border-color: #ffffff;
      box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.15);
    }}
    .color-swatch:focus-visible {{
      outline: 2px solid var(--color-ring);
      outline-offset: 1px;
    }}

    /* Event Log List */
    .event-log {{
      max-height: 150px;
      overflow-y: auto;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: var(--space-sm);
      font-family: var(--font-mono);
      font-size: 0.68rem;
      color: var(--color-muted-foreground);
      display: flex;
      flex-direction: column-reverse;
      gap: var(--space-xs);
    }}
    .log-item {{
      padding: 0.15rem 0.3rem;
      border-radius: 2px;
      border-right: 2px solid var(--ink-cyan);
      background: rgba(255, 255, 255, 0.02);
      color: #cbd5e1;
    }}
    .log-item.complete {{
      border-right-color: var(--color-accent);
      color: var(--color-accent);
    }}
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="logo-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div class="brand-copy">
        <div class="brand-title">مِداد</div>
        <div class="brand-subtitle">Arabic Handwriting Engine</div>
      </div>
    </div>
    <div class="header-badges">
      <span class="badge">C0 / G1 Welds</span>
      <span class="badge">Midad API</span>
      <span class="badge">50 Words</span>
    </div>
  </header>

  <main>
    <!-- Left: Stage Canvas & Controls -->
    <div class="stage-card">
      <div class="stage-topbar">
        <div class="current-word-title" id="wordHeading">
          كتب
          <span class="word-index-tag" id="wordIndexTag">#1 من 50</span>
        </div>
        <div class="live-status-pill">
          <span class="status-dot playing" id="statusDot"></span>
          <span id="statusText">Playing</span>
        </div>
      </div>

      <div class="canvas-viewport" id="canvasViewport">
        <div id="midadContainer"></div>
        <div class="empty-stage" id="emptyStage" style="display:none;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <line x1="3" y1="3" x2="21" y2="21"/>
          </svg>
          <p>Select a word to begin playback</p>
        </div>
      </div>

      <div class="playback-toolbar">
        <div class="scrubber-row">
          <span class="time-label" id="currentTimeLabel">0.00s</span>
          <input type="range" class="scrubber-slider" id="scrubber" min="0" max="100" value="0">
          <span class="time-label" id="totalTimeLabel">0.00s</span>
        </div>

        <div class="controls-row">
          <div class="btn-group">
            <button class="btn primary" id="playPauseBtn" aria-label="إيقاف مؤقت">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
              <span>إيقاف مؤقت</span>
            </button>
            <button class="btn secondary" id="restartBtn" aria-label="إعادة التشغيل">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 4v16a3 3 0 0 0 3 3h16"/><polyline points="1 4 1 20 5 16"/><polyline points="23 4 23 20 19 16"/></svg>
              <span>إعادة التشغيل</span>
            </button>
            <button class="btn secondary" id="prevWordBtn" aria-label="السابقة">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
              <span>السابقة</span>
            </button>
            <button class="btn secondary" id="nextWordBtn" aria-label="التالي">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
              <span>التالي</span>
            </button>
          </div>
          <div class="btn-group">
            <button class="btn secondary" id="toggleGlowBtn" aria-label="إضاءة (Glow)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              <span>إضاءة</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Sidebar Settings & Diagnostics -->
    <div class="sidebar">
      <!-- Word Selector -->
      <div class="panel-card">
        <div class="panel-title">
          <span>اختيار الكلمة</span>
          <span class="count" id="wordCount">50</span>
        </div>
        <select class="word-picker-select" id="wordSelect" aria-label="اختر كلمة">
          <!-- Populated dynamically -->
        </select>
        <div class="quick-chips" id="quickChips">
          <!-- Populated dynamically -->
        </div>
      </div>

      <!-- Animation Settings -->
      <div class="panel-card">
        <div class="panel-title">
          <span>إعدادات الحركة</span>
        </div>

        <div class="setting-group">
          <div class="setting-label">
            <span>سرعة الرسم</span>
            <span class="setting-value" id="speedVal">1.0x</span>
          </div>
          <input type="range" class="slider" id="speedSlider" min="25" max="300" value="100">
        </div>

        <div class="setting-group">
          <div class="setting-label">
            <span>سمك الخط</span>
            <span class="setting-value" id="strokeVal">28 px</span>
          </div>
          <input type="range" class="slider" id="strokeSlider" min="12" max="55" value="28">
        </div>

        <div class="setting-group">
          <div class="setting-label">
            <span>لون الحبر</span>
          </div>
          <div class="color-palette" id="colorPalette">
            <button class="color-swatch active" data-color="#06b6d4" style="background:#06b6d4;" type="button" title="Cyan" aria-pressed="true"></button>
            <button class="color-swatch" data-color="#10b981" style="background:#10b981;" type="button" title="Emerald" aria-pressed="false"></button>
            <button class="color-swatch" data-color="#f59e0b" style="background:#f59e0b;" type="button" title="Amber" aria-pressed="false"></button>
            <button class="color-swatch" data-color="#a855f7" style="background:#a855f7;" type="button" title="Purple" aria-pressed="false"></button>
            <button class="color-swatch" data-color="#f43f5e" style="background:#f43f5e;" type="button" title="Rose" aria-pressed="false"></button>
            <button class="color-swatch" data-color="#f8fafc" style="background:#f8fafc;" type="button" title="White" aria-pressed="false"></button>
          </div>
        </div>
      </div>

      <!-- Diagnostics & Events -->
      <div class="panel-card">
        <div class="panel-title">
          <span>سجل الأحداث</span>
          <span class="count" id="eventCountBadge">0 أحداث</span>
        </div>
        <div class="event-log" id="eventLog">
          <div class="log-item">Engine initialized and ready</div>
        </div>
      </div>
    </div>
  </main>

  <!-- Embedded UMD Engine -->
  <script>
    {umd_code}
  </script>

  <!-- Player Controller -->
  <script>
    const FONT_DATA = {words_json};
    const WORDS = FONT_DATA.words;

    let currentIndex = 0;
    let midadInstance = null;
    let currentSpeedMultiplier = 1.0;
    let currentStrokeWidth = 28;
    let currentColor = '#06b6d4';
    let isGlow = false;
    let isSeeking = false;

    // DOM Elements
    const container = document.getElementById('midadContainer');
    const wordSelect = document.getElementById('wordSelect');
    const quickChips = document.getElementById('quickChips');
    const wordHeading = document.getElementById('wordHeading');
    const wordIndexTag = document.getElementById('wordIndexTag');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const playPauseBtn = document.getElementById('playPauseBtn');
    const restartBtn = document.getElementById('restartBtn');
    const prevWordBtn = document.getElementById('prevWordBtn');
    const nextWordBtn = document.getElementById('nextWordBtn');
    const scrubber = document.getElementById('scrubber');
    const currentTimeLabel = document.getElementById('currentTimeLabel');
    const totalTimeLabel = document.getElementById('totalTimeLabel');
    const speedSlider = document.getElementById('speedSlider');
    const speedVal = document.getElementById('speedVal');
    const strokeSlider = document.getElementById('strokeSlider');
    const strokeVal = document.getElementById('strokeVal');
    const colorPalette = document.getElementById('colorPalette');
    const toggleGlowBtn = document.getElementById('toggleGlowBtn');
    const eventLog = document.getElementById('eventLog');
    const eventCountBadge = document.getElementById('eventCountBadge');
    let eventCount = 1;

    function addLog(msg, isComplete = false) {{
      eventCount++;
      eventCountBadge.textContent = `${{eventCount}} أحداث`;
      const item = document.createElement('div');
      item.className = 'log-item' + (isComplete ? ' complete' : '');
      const ts = (new Date()).toLocaleTimeString();
      item.textContent = `[${{ts}}] ${{msg}}`;
      eventLog.prepend(item);
    }}

    // Populate dropdown and chips
    WORDS.forEach((w, idx) => {{
      const opt = document.createElement('option');
      opt.value = idx;
      opt.textContent = `${{idx + 1}}. ${{w.text}} (${{w.paws.length}} PAWs)`;
      wordSelect.appendChild(opt);
    }});

    const FEATURED_WORDS = ['كتب', 'محمد', 'العربية', 'صابر', 'طالب', 'ربيع', 'مربع', 'فجر', 'نهر', 'قرآن'];
    FEATURED_WORDS.forEach(tw => {{
      const foundIdx = WORDS.findIndex(w => w.text === tw);
      if (foundIdx !== -1) {{
        const chip = document.createElement('div');
        chip.className = 'chip' + (foundIdx === 0 ? ' active' : '');
        chip.textContent = tw;
        chip.onclick = () => selectWord(foundIdx);
        quickChips.appendChild(chip);
      }}
    }});

    function updateWordUI(idx) {{
      const w = WORDS[idx];
      wordHeading.textContent = w.text;
      wordIndexTag.textContent = `#${{idx + 1}} من ${{WORDS.length}} (${{w.paws.length}} PAWs)`;
      wordSelect.value = idx;
      document.getElementById('wordCount').textContent = WORDS.length;

      const emptyStage = document.getElementById('emptyStage');
      if (emptyStage) emptyStage.style.display = 'none';

      document.querySelectorAll('.chip').forEach(c => {{
        c.classList.toggle('active', c.textContent.trim() === w.text);
      }});
    }}

    function initMidadForWord(idx) {{
      const targetWord = WORDS[idx];
      updateWordUI(idx);

      if (midadInstance) {{
        midadInstance.destroy();
        midadInstance = null;
      }}
      container.innerHTML = '';

      const MidadClass = window.Midad?.Midad || window.Midad;
      midadInstance = new MidadClass(container, FONT_DATA, targetWord.text, {{
        autoAnimation: true,
        speed: 1500 * currentSpeedMultiplier,
        strokeWidth: currentStrokeWidth,
        color: currentColor,
        pauseBetweenStrokes: 40,
        pauseBetweenPaws: 100,
      }});

      midadInstance.on('start', (d) => {{
        statusDot.className = 'status-dot playing';
        statusText.textContent = 'Playing';
        playPauseBtn.textContent = 'إيقاف مؤقت';
        if (d?.duration) {{
          totalTimeLabel.textContent = `${{d.duration.toFixed(2)}}s`;
        }}
        addLog(`Started '${{targetWord.text}}'`);
      }});

      midadInstance.on('pawStart', (d) => {{
        addLog(`PAW start: ${{d?.pawId}}`);
      }});

      midadInstance.on('progress', (d) => {{
        if (!isSeeking && d) {{
          currentTimeLabel.textContent = `${{d.currentTime.toFixed(2)}}s`;
          totalTimeLabel.textContent = `${{d.totalDuration.toFixed(2)}}s`;
          scrubber.value = (d.progress * 100).toFixed(1);
        }}
      }});

      midadInstance.on('complete', () => {{
        statusDot.className = 'status-dot paused';
        statusText.textContent = 'Completed';
        playPauseBtn.textContent = 'إعادة البدء';
        addLog(`Completed '${{targetWord.text}}'`, true);
      }});
    }}

    function selectWord(idx) {{
      currentIndex = idx;
      initMidadForWord(currentIndex);
    }}

    // Event Handlers
    wordSelect.onchange = (e) => selectWord(parseInt(e.target.value, 10));

    prevWordBtn.onclick = () => {{
      const prev = (currentIndex - 1 + WORDS.length) % WORDS.length;
      selectWord(prev);
    }};

    nextWordBtn.onclick = () => {{
      const next = (currentIndex + 1) % WORDS.length;
      selectWord(next);
    }};

    playPauseBtn.onclick = () => {{
      if (!midadInstance) return;
      if (midadInstance.state === 'playing') {{
        midadInstance.pause();
        statusDot.className = 'status-dot paused';
        statusText.textContent = 'Paused';
        playPauseBtn.textContent = 'استئناف';
      }} else if (midadInstance.state === 'paused') {{
        midadInstance.resume();
        statusDot.className = 'status-dot playing';
        statusText.textContent = 'Playing';
        playPauseBtn.textContent = 'إيقاف مؤقت';
      }} else {{
        midadInstance.restart();
      }}
    }};

    restartBtn.onclick = () => {{
      if (midadInstance) {{
        midadInstance.restart();
      }}
    }};

    // Scrubber interaction
    scrubber.oninput = (e) => {{
      isSeeking = true;
      const progress = parseFloat(e.target.value) / 100.0;
      if (midadInstance) {{
        midadInstance.seek(progress);
      }}
    }};
    scrubber.onchange = () => {{
      isSeeking = false;
    }};

    // Sliders
    speedSlider.oninput = (e) => {{
      currentSpeedMultiplier = parseFloat(e.target.value) / 100.0;
      speedVal.textContent = `${{currentSpeedMultiplier.toFixed(2)}}x`;
      if (midadInstance?.renderer) {{
        midadInstance.renderer.setSpeed(currentSpeedMultiplier);
      }}
    }};

    strokeSlider.oninput = (e) => {{
      currentStrokeWidth = parseInt(e.target.value, 10);
      strokeVal.textContent = `${{currentStrokeWidth}} px`;
      initMidadForWord(currentIndex);
    }};

    // Color swatches
    colorPalette.querySelectorAll('.color-swatch').forEach(sw => {{
      sw.onclick = () => {{
        colorPalette.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
        sw.classList.add('active');
        currentColor = sw.dataset.color;
        initMidadForWord(currentIndex);
      }};
    }});

    // Glow toggle
    toggleGlowBtn.onclick = () => {{
      isGlow = !isGlow;
      container.classList.toggle('glow-effect', isGlow);
      toggleGlowBtn.classList.toggle('active', isGlow);
    }};

    // Initial Load
    initMidadForWord(0);
  </script>
</body>
</html>
"""

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Generated standalone Midad Web Player: {OUT_HTML} ({len(html)/1024:.1f} KB)")


if __name__ == "__main__":
    generate_player_html()
