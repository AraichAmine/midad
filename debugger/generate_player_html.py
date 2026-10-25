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
      --bg-gradient: radial-gradient(circle at 50% 0%, #151d30 0%, #080c14 100%);
      --card-bg: rgba(15, 23, 42, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --panel-bg: rgba(30, 41, 59, 0.5);
      --panel-border: rgba(255, 255, 255, 0.1);
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --accent-glow: rgba(6, 182, 212, 0.25);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --font-ui: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-arabic: 'Noto Naskh Arabic', 'Amiri', serif;
      --font-display: 'Outfit', sans-serif;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background: #080c14;
      background-image: var(--bg-gradient);
      color: var(--text-main);
      font-family: var(--font-ui);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }}

    /* Header Bar */
    header {{
      background: rgba(8, 12, 20, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.9rem 2rem;
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
      gap: 1rem;
    }}

    .logo {{
      font-family: var(--font-arabic);
      font-size: 2.2rem;
      font-weight: 700;
      background: linear-gradient(135deg, #38bdf8 0%, #06b6d4 50%, #10b981 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      text-shadow: 0 0 30px rgba(6, 182, 212, 0.3);
      line-height: 1;
    }}

    .brand-title {{
      font-family: var(--font-display);
      font-size: 1.1rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      color: #f1f5f9;
    }}

    .brand-subtitle {{
      font-size: 0.72rem;
      color: var(--text-dim);
      letter-spacing: 0.02em;
    }}

    .header-badges {{
      display: flex;
      gap: 0.6rem;
      align-items: center;
    }}

    .badge {{
      background: rgba(6, 182, 212, 0.12);
      border: 1px solid rgba(6, 182, 212, 0.25);
      color: #38bdf8;
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      font-size: 0.72rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }}
    .badge.emerald {{
      background: rgba(16, 185, 129, 0.12);
      border-color: rgba(16, 185, 129, 0.25);
      color: #34d399;
    }}

    /* Main Container */
    main {{
      max-width: 1300px;
      margin: 1.5rem auto;
      padding: 0 1.5rem 3rem;
      width: 100%;
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 1.5rem;
      flex: 1;
    }}

    @media (max-width: 960px) {{
      main {{
        grid-template-columns: 1fr;
      }}
    }}

    /* Stage Panel */
    .stage-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 1.2rem;
      backdrop-filter: blur(16px);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.7);
    }}

    .stage-topbar {{
      padding: 1rem 1.4rem;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(0, 0, 0, 0.25);
    }}

    .current-word-title {{
      font-family: var(--font-arabic);
      font-size: 2.2rem;
      font-weight: 700;
      color: #ffffff;
      display: flex;
      align-items: baseline;
      gap: 0.8rem;
    }}

    .word-index-tag {{
      font-size: 0.75rem;
      font-family: var(--font-ui);
      color: var(--text-dim);
      font-weight: 500;
    }}

    .live-status-pill {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(0, 0, 0, 0.4);
      padding: 0.35rem 0.8rem;
      border-radius: 0.5rem;
      border: 1px solid var(--panel-border);
      font-size: 0.75rem;
    }}

    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #64748b;
      transition: background 0.3s;
    }}
    .status-dot.playing {{
      background: #10b981;
      box-shadow: 0 0 10px #10b981;
    }}
    .status-dot.paused {{
      background: #f59e0b;
      box-shadow: 0 0 10px #f59e0b;
    }}

    /* Canvas Area */
    .canvas-viewport {{
      flex: 1;
      min-height: 420px;
      position: relative;
      background: radial-gradient(circle at center, rgba(17, 24, 39, 0.9) 0%, rgba(10, 15, 26, 0.95) 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      overflow: hidden;
    }}

    /* Grid lines in canvas */
    .canvas-viewport::before {{
      content: '';
      position: absolute;
      inset: 0;
      background-image: 
        linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 30px 30px;
      pointer-events: none;
    }}

    #midadContainer {{
      width: 100%;
      height: 100%;
      min-height: 380px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      z-index: 2;
    }}

    /* SVG Stroke Glow */
    .glow-effect .midad-stroke {{
      filter: drop-shadow(0 0 8px currentColor);
    }}

    /* Timeline & Playback Bar */
    .playback-toolbar {{
      padding: 1.25rem 1.5rem;
      background: rgba(0, 0, 0, 0.35);
      border-top: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}

    .scrubber-row {{
      display: flex;
      align-items: center;
      gap: 1rem;
    }}

    .time-label {{
      font-size: 0.78rem;
      font-family: var(--font-display);
      color: var(--text-muted);
      min-width: 65px;
      direction: ltr;
      text-align: center;
    }}

    .scrubber-slider {{
      flex: 1;
      -webkit-appearance: none;
      height: 6px;
      border-radius: 9999px;
      background: rgba(255, 255, 255, 0.12);
      outline: none;
      cursor: pointer;
      position: relative;
    }}
    .scrubber-slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--accent-cyan);
      box-shadow: 0 0 12px var(--accent-cyan);
      cursor: pointer;
      transition: transform 0.1s;
    }}
    .scrubber-slider::-webkit-slider-thumb:hover {{
      transform: scale(1.25);
    }}

    .controls-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.8rem;
    }}

    .btn-group {{
      display: flex;
      gap: 0.5rem;
    }}

    .btn {{
      background: rgba(255, 255, 255, 0.07);
      border: 1px solid var(--panel-border);
      color: var(--text-main);
      padding: 0.5rem 1.1rem;
      border-radius: 0.6rem;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.2s;
    }}
    .btn:hover {{
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }}
    .btn.primary {{
      background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%);
      border-color: rgba(6, 182, 212, 0.4);
      color: #ffffff;
      box-shadow: 0 4px 15px var(--accent-glow);
    }}
    .btn.primary:hover {{
      box-shadow: 0 6px 20px rgba(6, 182, 212, 0.45);
    }}

    /* Sidebar Panel */
    .sidebar {{
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}

    .panel-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 1rem;
      padding: 1.25rem;
      backdrop-filter: blur(14px);
    }}

    .panel-title {{
      font-size: 0.88rem;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 0.9rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .word-picker-select {{
      width: 100%;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid var(--panel-border);
      border-radius: 0.6rem;
      color: var(--text-main);
      padding: 0.6rem 0.8rem;
      font-family: var(--font-arabic);
      font-size: 1.15rem;
      cursor: pointer;
      outline: none;
    }}
    .word-picker-select option {{
      background: #0f172a;
      color: #f8fafc;
    }}

    /* Quick Chips */
    .quick-chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin-top: 0.75rem;
    }}

    .chip {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      border-radius: 0.4rem;
      padding: 0.25rem 0.65rem;
      font-family: var(--font-arabic);
      font-size: 0.95rem;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.2s;
    }}
    .chip:hover, .chip.active {{
      background: rgba(6, 182, 212, 0.15);
      border-color: var(--accent-cyan);
      color: #38bdf8;
    }}

    /* Control Sliders in Sidebar */
    .setting-group {{
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      margin-bottom: 0.85rem;
    }}

    .setting-label {{
      display: flex;
      justify-content: space-between;
      font-size: 0.75rem;
      color: var(--text-muted);
    }}

    .setting-value {{
      font-weight: 600;
      color: #38bdf8;
      font-family: var(--font-display);
    }}

    .slider {{
      -webkit-appearance: none;
      height: 5px;
      border-radius: 9999px;
      background: rgba(255, 255, 255, 0.1);
      outline: none;
      cursor: pointer;
    }}
    .slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: #38bdf8;
      cursor: pointer;
    }}

    /* Palette colors */
    .color-palette {{
      display: flex;
      gap: 0.5rem;
      margin-top: 0.3rem;
    }}

    .color-swatch {{
      width: 24px;
      height: 24px;
      border-radius: 50%;
      cursor: pointer;
      border: 2px solid transparent;
      transition: transform 0.15s, border-color 0.15s;
    }}
    .color-swatch:hover, .color-swatch.active {{
      transform: scale(1.2);
      border-color: #ffffff;
    }}

    /* Event Log List */
    .event-log {{
      max-height: 160px;
      overflow-y: auto;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--panel-border);
      border-radius: 0.5rem;
      padding: 0.5rem;
      font-family: monospace;
      font-size: 0.7rem;
      color: var(--text-dim);
      display: flex;
      flex-direction: column-reverse;
      gap: 0.25rem;
    }}
    .log-item {{
      padding: 0.15rem 0.3rem;
      border-radius: 0.2rem;
      border-right: 2px solid var(--accent-cyan);
      background: rgba(255, 255, 255, 0.02);
      color: #cbd5e1;
    }}
    .log-item.complete {{
      border-right-color: #10b981;
      color: #34d399;
    }}
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="logo">مِداد</div>
      <div>
        <div class="brand-title">MIDAD ENGINE</div>
        <div class="brand-subtitle">Arabic Cursive Handwriting Animation Runtime</div>
      </div>
    </div>
    <div class="header-badges">
      <span class="badge emerald">✓ Continuous C0/G1 Welds</span>
      <span class="badge">Midad API Ready</span>
      <span class="badge">50 Words Corpus</span>
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
      </div>

      <div class="playback-toolbar">
        <div class="scrubber-row">
          <span class="time-label" id="currentTimeLabel">0.00s</span>
          <input type="range" class="scrubber-slider" id="scrubber" min="0" max="100" value="0">
          <span class="time-label" id="totalTimeLabel">0.00s</span>
        </div>

        <div class="controls-row">
          <div class="btn-group">
            <button class="btn primary" id="playPauseBtn">❚❚ إيقاف مؤقت</button>
            <button class="btn" id="restartBtn">↺ إعادة التشغيل</button>
            <button class="btn" id="prevWordBtn">السابق ◀</button>
            <button class="btn" id="nextWordBtn">▶ التالي</button>
          </div>
          <div class="btn-group">
            <button class="btn" id="toggleGlowBtn">✨ إضاءة (Glow)</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Sidebar Settings & Diagnostics -->
    <div class="sidebar">
      <!-- Word Selector -->
      <div class="panel-card">
        <div class="panel-title">اختيار الكلمة (Select Word)</div>
        <select class="word-picker-select" id="wordSelect">
          <!-- Populated dynamically -->
        </select>
        <div class="quick-chips" id="quickChips">
          <!-- Populated dynamically -->
        </div>
      </div>

      <!-- Animation Settings -->
      <div class="panel-card">
        <div class="panel-title">إعدادات الحركة (Animation Settings)</div>

        <div class="setting-group">
          <div class="setting-label">
            <span>سرعة الرسم (Speed)</span>
            <span class="setting-value" id="speedVal">1.0x</span>
          </div>
          <input type="range" class="slider" id="speedSlider" min="25" max="300" value="100">
        </div>

        <div class="setting-group">
          <div class="setting-label">
            <span>سمك الخط (Stroke Width)</span>
            <span class="setting-value" id="strokeVal">28 px</span>
          </div>
          <input type="range" class="slider" id="strokeSlider" min="12" max="55" value="28">
        </div>

        <div class="setting-group">
          <div class="setting-label">
            <span>لون الحبر (Ink Color)</span>
          </div>
          <div class="color-palette" id="colorPalette">
            <div class="color-swatch active" data-color="#06b6d4" style="background:#06b6d4;" title="Cyan"></div>
            <div class="color-swatch" data-color="#10b981" style="background:#10b981;" title="Emerald"></div>
            <div class="color-swatch" data-color="#f59e0b" style="background:#f59e0b;" title="Amber"></div>
            <div class="color-swatch" data-color="#a855f7" style="background:#a855f7;" title="Purple"></div>
            <div class="color-swatch" data-color="#f43f5e" style="background:#f43f5e;" title="Rose"></div>
            <div class="color-swatch" data-color="#f8fafc" style="background:#f8fafc;" title="White"></div>
          </div>
        </div>
      </div>

      <!-- Diagnostics & Events -->
      <div class="panel-card">
        <div class="panel-title">
          <span>سجل الأحداث (Event Stream)</span>
          <span style="font-size:0.65rem; color:var(--text-dim);" id="eventCountBadge">0 أحداث</span>
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
        playPauseBtn.textContent = '❚❚ إيقاف مؤقت';
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
        playPauseBtn.textContent = '↺ إعادة البدء';
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
        playPauseBtn.textContent = '▶ استئناف';
      }} else if (midadInstance.state === 'paused') {{
        midadInstance.resume();
        statusDot.className = 'status-dot playing';
        statusText.textContent = 'Playing';
        playPauseBtn.textContent = '❚❚ إيقاف مؤقت';
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
      toggleGlowBtn.style.borderColor = isGlow ? 'var(--accent-cyan)' : '';
      toggleGlowBtn.style.color = isGlow ? '#38bdf8' : '';
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
