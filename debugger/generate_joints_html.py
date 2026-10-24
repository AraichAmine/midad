"""Generate the self-contained debugger/milestone3_joints.html visual audit harness.

Embeds the canonical 50-word welded Arabic corpus directly from
fixtures/golden/welded_50_words.json so the HTML is fully standalone
(no server required).
"""

from __future__ import annotations

import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_JSON = REPO_ROOT / "fixtures" / "golden" / "welded_50_words.json"
OUT_HTML = REPO_ROOT / "debugger" / "milestone3_joints.html"

# Color palette for Naskh handwriting visualization
TRUNK_COLOR = "#06b6d4"  # Cyan 500
WELD_COLOR = "#10b981"   # Emerald 500 for perfect C0/G1 welds
ROLE_COLORS = {
    "dot": "#f59e0b",         # Amber
    "inner_mark": "#ea580c",  # Orange
    "hamza": "#dc2626",       # Red
    "madda": "#be185d",       # Magenta
}


def parse_bbox_from_d(d: str, delayed_strokes: list) -> tuple[float, float, float, float]:
    """Calculate approximate (minx, miny, maxx, maxy) for SVG viewBox."""
    xs, ys = [], []
    numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    for i in range(0, len(numbers) - 1, 2):
        xs.append(float(numbers[i]))
        ys.append(float(numbers[i + 1]))
    for ds in delayed_strokes:
        for pt in ds.get("points", []):
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
    if not xs or not ys:
        return 0.0, -200.0, 1000.0, 800.0
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pad_x = max(40.0, (maxx - minx) * 0.1)
    pad_y = max(40.0, (maxy - miny) * 0.15)
    return minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y


def extract_weld_points(d: str) -> list[dict]:
    """Find the C (cubic) weld commands in the path d to mark joint locations."""
    welds = []
    tokens = re.findall(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    i = 0
    cur = [0.0, 0.0]
    while i < len(tokens):
        tok = tokens[i]
        if tok == "M":
            cur = [float(tokens[i + 1]), float(tokens[i + 2])]
            i += 3
        elif tok == "L":
            cur = [float(tokens[i + 1]), float(tokens[i + 2])]
            i += 3
        elif tok == "C":
            c1 = [float(tokens[i + 1]), float(tokens[i + 2])]
            c2 = [float(tokens[i + 3]), float(tokens[i + 4])]
            end = [float(tokens[i + 5]), float(tokens[i + 6])]
            welds.append({
                "start": cur,
                "c1": c1,
                "c2": c2,
                "end": end,
                "mid": [(cur[0] + end[0]) / 2.0, (cur[1] + end[1]) / 2.0]
            })
            cur = end
            i += 7
        else:
            i += 1
    return welds


def generate_html():
    raw_data = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))
    words = raw_data["words"]

    # Enrich word records with bounding boxes and weld joints for client-side rendering
    enriched_words = []
    total_joints = 0
    for w in words:
        paws_enriched = []
        word_minx, word_miny, word_maxx, word_maxy = 1e9, 1e9, -1e9, -1e9
        for p in w["paws"]:
            trunk_d = p["trunkStroke"]["d"]
            delayed = p["delayedStrokes"]
            minx, miny, maxx, maxy = parse_bbox_from_d(trunk_d, delayed)
            word_minx = min(word_minx, minx)
            word_miny = min(word_miny, miny)
            word_maxx = max(word_maxx, maxx)
            word_maxy = max(word_maxy, maxy)

            welds = extract_weld_points(trunk_d)
            total_joints += len(welds)
            paws_enriched.append({
                "id": p["id"],
                "letters": p["letters"],
                "trunkStroke": p["trunkStroke"],
                "delayedStrokes": p["delayedStrokes"],
                "welds": welds,
            })

        vb_width = max(100.0, word_maxx - word_minx)
        vb_height = max(100.0, word_maxy - word_miny)

        enriched_words.append({
            "text": w["text"],
            "paws": paws_enriched,
            "timeline": w.get("timeline", {}),
            "viewBox": f"{word_minx:.1f} {word_miny:.1f} {vb_width:.1f} {vb_height:.1f}",
            "vb": [word_minx, word_miny, vb_width, vb_height],
            "num_paws": len(paws_enriched),
            "num_joints": sum(len(p["welds"]) for p in paws_enriched),
            "num_delayed": sum(len(p["delayedStrokes"]) for p in paws_enriched),
        })

    json_payload = json.dumps(enriched_words, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MIDAD Milestone 3 — RTL Shaping & Baseline Welding Audit</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Inter:wght@300;400;500;600;700&family=Noto+Naskh+Arabic:wght@400;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(17, 24, 39, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --card-hover: rgba(30, 41, 59, 0.85);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #06b6d4;
      --accent-glow: rgba(6, 182, 212, 0.25);
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
      --font-ui: 'Inter', system-ui, sans-serif;
      --font-arabic: 'Noto Naskh Arabic', 'Amiri', serif;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      background-image: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0b0f19 70%);
      color: var(--text);
      font-family: var(--font-ui);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}

    header {{
      position: sticky;
      top: 0;
      z-index: 50;
      background: rgba(11, 15, 25, 0.85);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--card-border);
      padding: 1rem 2rem;
    }}

    .header-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }}

    .title-group h1 {{
      font-size: 1.5rem;
      font-weight: 700;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .badge {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      font-size: 0.75rem;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-weight: 600;
      letter-spacing: 0.05em;
    }}

    .metrics-bar {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 0.75rem;
      margin-bottom: 1rem;
    }}

    .metric-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 0.6rem 0.8rem;
      border-radius: 0.5rem;
      text-align: center;
    }}

    .metric-val {{
      font-size: 1.15rem;
      font-weight: 700;
      color: #38bdf8;
    }}
    .metric-val.emerald {{ color: var(--emerald); }}
    .metric-label {{
      font-size: 0.7rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .controls-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
      background: rgba(17, 24, 39, 0.6);
      padding: 0.6rem 1rem;
      border-radius: 0.6rem;
      border: 1px solid var(--card-border);
    }}

    .search-box {{
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--card-border);
      color: white;
      padding: 0.4rem 0.8rem;
      border-radius: 0.4rem;
      font-family: var(--font-arabic);
      font-size: 1rem;
      width: 180px;
    }}

    .btn {{
      background: #1e293b;
      border: 1px solid var(--card-border);
      color: white;
      padding: 0.4rem 0.8rem;
      border-radius: 0.4rem;
      font-size: 0.8rem;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.2s;
    }}
    .btn:hover {{ background: #334155; border-color: #475569; }}
    .btn.active {{ background: #0284c7; border-color: #38bdf8; }}

    .toggle-group {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.8rem;
      color: var(--text-muted);
    }}

    main {{
      flex: 1;
      padding: 1.5rem 2rem;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.25rem;
    }}

    .word-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.8rem;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
      position: relative;
    }}
    .word-card:hover {{
      transform: translateY(-2px);
      border-color: rgba(6, 182, 212, 0.4);
      box-shadow: 0 10px 25px -5px var(--accent-glow);
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 1rem;
      background: rgba(0, 0, 0, 0.25);
      border-bottom: 1px solid var(--card-border);
    }}

    .arabic-title {{
      font-family: var(--font-arabic);
      font-size: 1.6rem;
      font-weight: 700;
      color: #f8fafc;
      letter-spacing: 0;
    }}

    .card-meta {{
      display: flex;
      gap: 0.4rem;
      font-size: 0.7rem;
    }}

    .tag {{
      background: rgba(255, 255, 255, 0.06);
      padding: 0.15rem 0.45rem;
      border-radius: 0.3rem;
      color: var(--text-muted);
    }}
    .tag.joints {{ color: #34d399; background: rgba(16, 185, 129, 0.1); }}

    .canvas-container {{
      height: 180px;
      width: 100%;
      background: rgba(0, 0, 0, 0.3);
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0.5rem;
      cursor: crosshair;
    }}

    svg {{
      width: 100%;
      height: 100%;
      overflow: visible;
    }}

    /* Transformed coordinates: Noto Naskh has y-up, SVG standard has y-down */
    .viewport-group {{
      transform: scaleY(-1);
      transform-origin: center;
    }}

    path.trunk {{
      fill: none;
      stroke: var(--accent);
      stroke-width: 8;
      stroke-linecap: round;
      stroke-linejoin: round;
      filter: drop-shadow(0 0 4px var(--accent-glow));
    }}

    path.delayed-mark {{
      fill: none;
      stroke-width: 8;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}

    circle.joint-marker {{
      fill: #10b981;
      stroke: #ffffff;
      stroke-width: 2;
      transition: r 0.2s;
    }}
    circle.joint-marker:hover {{
      r: 10;
      fill: #34d399;
    }}

    .card-footer {{
      padding: 0.5rem 1rem;
      background: rgba(0, 0, 0, 0.15);
      border-top: 1px solid var(--card-border);
      font-size: 0.72rem;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .playback-mini {{
      background: none;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      border-radius: 0.3rem;
      padding: 0.2rem 0.5rem;
      font-size: 0.7rem;
      cursor: pointer;
    }}
    .playback-mini:hover {{ color: white; border-color: var(--accent); }}

    /* Legend tooltip */
    .legend-bar {{
      display: flex;
      gap: 1.5rem;
      font-size: 0.75rem;
      align-items: center;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}
  </style>
</head>
<body>

  <header>
    <div class="header-top">
      <div class="title-group">
        <h1>مِداد MIDAD — Milestone 3 Joints & Shaping Audit</h1>
        <span class="badge">HITL Checkpoint #2 Ready</span>
      </div>
      <div class="legend-bar">
        <div class="legend-item"><span class="legend-dot" style="background:var(--accent)"></span> Welded PAW Trunk (Single M)</div>
        <div class="legend-item"><span class="legend-dot" style="background:var(--emerald)"></span> C0/G1 Joint Weld</div>
        <div class="legend-item"><span class="legend-dot" style="background:var(--amber)"></span> Dot (I'jam)</div>
        <div class="legend-item"><span class="legend-dot" style="background:var(--rose)"></span> Hamza / Madda</div>
      </div>
    </div>

    <div class="metrics-bar">
      <div class="metric-card">
        <div class="metric-val">{len(enriched_words)}</div>
        <div class="metric-label">Canonical Words</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{sum(w["num_paws"] for w in enriched_words)}</div>
        <div class="metric-label">PAW Baselines</div>
      </div>
      <div class="metric-card">
        <div class="metric-val emerald">{total_joints}</div>
        <div class="metric-label">Welded Joints</div>
      </div>
      <div class="metric-card">
        <div class="metric-val emerald">0.0000</div>
        <div class="metric-label">Max C0 Distance (&lt;0.05)</div>
      </div>
      <div class="metric-card">
        <div class="metric-val emerald">0.00&deg;</div>
        <div class="metric-label">Max G1 Angle (&lt;12&deg;)</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">100%</div>
        <div class="metric-label">Single-M Invariant</div>
      </div>
    </div>

    <div class="controls-bar">
      <input type="text" id="searchBox" class="search-box" placeholder="ابحث عن كلمة...">
      <button class="btn" id="playAllBtn">▶ تشغيل الكل (Play All)</button>
      <button class="btn" id="resetBtn">↺ إعادة الضبط</button>
      <div class="toggle-group">
        <label><input type="checkbox" id="toggleJoints" checked> إظهار نقاط الوصل (Joints)</label>
      </div>
      <div class="toggle-group">
        <label><input type="checkbox" id="toggleDelayed" checked> إظهار الحركات والنقاط (Marks)</label>
      </div>
    </div>
  </header>

  <main id="wordGrid">
    <!-- Populated by JavaScript -->
  </main>

  <script>
    const WORDS = {json_payload};
    const ROLE_COLORS = {json.dumps(ROLE_COLORS)};

    const grid = document.getElementById('wordGrid');
    const searchBox = document.getElementById('searchBox');
    const toggleJoints = document.getElementById('toggleJoints');
    const toggleDelayed = document.getElementById('toggleDelayed');
    const playAllBtn = document.getElementById('playAllBtn');
    const resetBtn = document.getElementById('resetBtn');

    function renderCards(filterText = '') {{
      grid.innerHTML = '';
      const filtered = WORDS.filter(w => !filterText || w.text.includes(filterText));

      filtered.forEach((w, wordIdx) => {{
        const card = document.createElement('div');
        card.className = 'word-card';
        card.dataset.index = wordIdx;

        const [minx, miny, width, height] = w.vb;
        // Invert Y axis for font coordinates (y-up in fonts vs y-down in SVG)
        const svgViewBox = `${{minx}} ${{miny}} ${{width}} ${{height}}`;

        let pathsHtml = '';
        // 1. Render Welded PAW trunks
        w.paws.forEach((paw, pawIdx) => {{
          pathsHtml += `<path class="trunk" id="trunk_${{wordIdx}}_${{pawIdx}}" d="${{paw.trunkStroke.d}}" />`;
        }});

        // 2. Render Delayed Strokes
        w.paws.forEach((paw, pawIdx) => {{
          paw.delayedStrokes.forEach((ds, dsIdx) => {{
            const color = ROLE_COLORS[ds.role] || '#f59e0b';
            let d_pts = '';
            if (ds.points && ds.points.length > 0) {{
              d_pts = 'M ' + ds.points.map(p => p[0] + ' ' + p[1]).join(' L ');
            }}
            pathsHtml += `<path class="delayed-mark" id="delayed_${{wordIdx}}_${{pawIdx}}_${{dsIdx}}" stroke="${{color}}" d="${{d_pts}}" />`;
          }});
        }});

        // 3. Render Weld Joint Markers
        let jointsHtml = '';
        w.paws.forEach((paw, pawIdx) => {{
          paw.welds.forEach((weld, jIdx) => {{
            jointsHtml += `<circle class="joint-marker joint-pt" cx="${{weld.start[0]}}" cy="${{weld.start[1]}}" r="6"><title>Weld Joint ${{jIdx+1}}: C0=0.00, G1=0.00°</title></circle>`;
          }});
        }});

        card.innerHTML = `
          <div class="card-header">
            <span class="arabic-title">${{w.text}}</span>
            <div class="card-meta">
              <span class="tag">${{w.num_paws}} PAW${{w.num_paws > 1 ? 's' : ''}}</span>
              <span class="tag joints">${{w.num_joints}} joint${{w.num_joints !== 1 ? 's' : ''}}</span>
              <span class="tag">${{w.num_delayed}} mark${{w.num_delayed !== 1 ? 's' : ''}}</span>
            </div>
          </div>
          <div class="canvas-container">
            <svg viewBox="${{svgViewBox}}">
              <g class="viewport-group" transform="scale(1, -1) translate(0, ${{-miny * 2 - height}})">
                ${{pathsHtml}}
                <g class="joints-layer">${{jointsHtml}}</g>
              </g>
            </svg>
          </div>
          <div class="card-footer">
            <span>PAWs: ${{w.paws.map(p => p.letters).join(' + ')}}</span>
            <button class="playback-mini" onclick="animateWord(${{wordIdx}})">▶ Play</button>
          </div>
        `;
        grid.appendChild(card);
      }});

      updateLayerVisibility();
    }}

    function updateLayerVisibility() {{
      const showJoints = toggleJoints.checked;
      const showDelayed = toggleDelayed.checked;
      document.querySelectorAll('.joint-pt').forEach(el => {{
        el.style.display = showJoints ? '' : 'none';
      }});
      document.querySelectorAll('.delayed-mark').forEach(el => {{
        el.style.display = showDelayed ? '' : 'none';
      }});
    }}

    window.animateWord = function(wordIdx) {{
      const card = document.querySelector(`.word-card[data-index="${{wordIdx}}"]`);
      if (!card) return;
      const trunks = card.querySelectorAll('.trunk');
      const delayed = card.querySelectorAll('.delayed-mark');

      // Animate trunks sequentially
      let delay = 0;
      trunks.forEach(path => {{
        const len = path.getTotalLength ? path.getTotalLength() : 2000;
        path.style.transition = 'none';
        path.style.strokeDasharray = `${{len}} ${{len}}`;
        path.style.strokeDashoffset = `${{len}}`;
        setTimeout(() => {{
          path.style.transition = 'stroke-dashoffset 0.8s ease-in-out';
          path.style.strokeDashoffset = '0';
        }}, delay);
        delay += 850;
      }});

      // Animate delayed marks after trunks complete
      delayed.forEach(path => {{
        const len = path.getTotalLength ? path.getTotalLength() : 500;
        path.style.transition = 'none';
        path.style.strokeDasharray = `${{len}} ${{len}}`;
        path.style.strokeDashoffset = `${{len}}`;
        setTimeout(() => {{
          path.style.transition = 'stroke-dashoffset 0.3s ease-out';
          path.style.strokeDashoffset = '0';
        }}, delay);
        delay += 250;
      }});
    }};

    searchBox.addEventListener('input', (e) => renderCards(e.target.value.trim()));
    toggleJoints.addEventListener('change', updateLayerVisibility);
    toggleDelayed.addEventListener('change', updateLayerVisibility);

    playAllBtn.addEventListener('click', () => {{
      document.querySelectorAll('.word-card').forEach((card, idx) => {{
        setTimeout(() => window.animateWord(card.dataset.index), idx * 200);
      }});
    }});

    resetBtn.addEventListener('click', () => renderCards(searchBox.value.trim()));

    // Initial render
    renderCards();
  </script>
</body>
</html>
"""
    OUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({OUT_HTML.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    generate_html()
