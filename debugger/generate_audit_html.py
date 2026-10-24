"""Generate the self-contained debugger/milestone2_audit.html audit harness.

Embeds directed glyph data (multi-stroke trunk trajectories + delayed marks)
extracted live from Noto Naskh Arabic so the HTML is fully standalone
(no server required).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "src"))

import extractor
import skeletonizer
import rules

REPO_ROOT = Path(__file__).resolve().parents[1]
FONT = REPO_ROOT / "fixtures" / "fonts" / "NotoNaskhArabic-Regular.ttf"
OUT_HTML = REPO_ROOT / "debugger" / "milestone2_audit.html"
DIRECTED_JSON = REPO_ROOT / "fixtures" / "skeletons" / "directed_glyphs.json"

# Stroke colors for compound letters (Naskh ductus order: stroke 1 -> stroke 2).
STROKE_COLORS = ["#22c3ee", "#e11d48", "#7c3aed", "#f59e0b"]
# Role colors for delayed marks / dots.
ROLE_COLORS = {
    "dot": "#f59e0b",
    "inner_mark": "#ea580c",
    "hamza": "#dc2626",
    "madda": "#be185d",
}


def contours_for(char: str, form: str):
    if len(char) == 1:
        return extractor.contours_for_letter_form(FONT, char, form)
    text = char if form == "isolated" else "\u0640" + char
    return extractor.extract_text_contours(FONT, text)


def build_embedded_data() -> dict:
    directed = json.loads(DIRECTED_JSON.read_text(encoding="utf-8"))
    glyphs_out = {}
    for key, glyph in directed["glyphs"].items():
        char = glyph["char"]
        form = glyph["form"]
        rule = rules.ARABIC_CHARACTER_RULES[char]

        contours = contours_for(char, form)
        partition = skeletonizer.separate_trunk_and_dots(
            contours, rule["dot_count"], rule["dot_placement"], rule
        )
        trunk_polygon = partition["trunk_polygon"]

        # Original trunk contour rings (translucent layer).
        trunk_rings = []
        rings = [trunk_polygon.exterior.coords] + [
            i.coords for i in trunk_polygon.interiors
        ]
        for ring in rings:
            trunk_rings.append(
                [[round(x, 2), round(y, 2)] for x, y in ring]
            )

        # Dot/contour rings for delayed marks (translucent fill).
        dot_rings = []
        for dot in partition["dot_polygons"]:
            dot_rings.append(
                [[round(x, 2), round(y, 2)] for x, y in dot.exterior.coords]
            )

        # Multi-stroke trunk trajectories, each with its own color.
        directed_strokes = []
        for index, stroke in enumerate(glyph["directed_strokes"]):
            directed_strokes.append(
                {
                    "index": index,
                    "color": STROKE_COLORS[index % len(STROKE_COLORS)],
                    "points": stroke["points"],  # [[x, y, s], ...]
                    "length": stroke["length"],
                }
            )

        # Delayed marks with roles (dot, inner_mark, hamza, madda).
        delayed = []
        for ds in glyph["delayed_strokes"]:
            role = ds.get("role", "dot")
            delayed.append(
                {
                    "role": role,
                    "color": ROLE_COLORS.get(role, "#f59e0b"),
                    "points": ds["points"],
                    "centroid": ds["centroid"],
                    "attachment_s": ds["attachment_s"],
                    "attachment_point": ds["attachment_point"],
                }
            )

        glyphs_out[key] = {
            "char": char,
            "name": glyph["name"],
            "form": form,
            "joining_type": glyph["joining_type"],
            "loop_count": glyph["loop_count"],
            "dot_count": glyph["dot_count"],
            "has_inner_mark": glyph.get("has_inner_mark", False),
            "has_hamza": glyph.get("has_hamza", False),
            "has_madda": glyph.get("has_madda", False),
            "rtl_ratio": glyph["rtl_ratio"],
            "flow_direction": glyph["flow_direction"],
            "start_point": glyph["start_point"],
            "end_point": glyph["end_point"],
            "entry_anchor": glyph["entry_anchor"],
            "exit_anchor": glyph["exit_anchor"],
            "anchors_ok": glyph["anchors_ok"],
            "dots_ok": glyph["dots_ok"],
            "num_trunk_strokes": glyph["num_trunk_strokes"],
            "trunk_contours": trunk_rings,
            "dot_contours": dot_rings,
            "directed_strokes": directed_strokes,
            "delayed_strokes": delayed,
        }

    return {
        "font": directed.get("font"),
        "font_family": directed.get("font_family"),
        "font_units_per_em": directed.get("font_units_per_em"),
        "total_glyphs": len(glyphs_out),
        "glyphs": glyphs_out,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Midad &mdash; Milestone 2 Kinematic Audit</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Noto Sans Arabic", sans-serif;
         margin: 0; background: #f5f5f7; color: #1a1a1a; direction: rtl; }
  header { background: #0f172a; color: #fff; padding: 1rem 1.5rem; position: sticky; top: 0; z-index: 100; }
  header h1 { margin: 0; font-size: 1.15rem; letter-spacing: 0.05em; }
  header .sub { font-size: 0.85rem; opacity: .85; margin-top: .2rem; }
  .toolbar { display: flex; flex-wrap: wrap; gap: .6rem; align-items: center;
             padding: .75rem 1.5rem; background: #e2e8f0; border-bottom: 1px solid #cbd5e1; }
  .toolbar label { font-size: .8rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: #475569; }
  .toolbar select, .toolbar input, .toolbar button { font-size: .9rem; padding: .35rem .6rem; border: 1px solid #94a3b8; border-radius: .4rem; background: #fff; }
  .toolbar button { cursor: pointer; background: #2563eb; color: #fff; border-color: #1d4ed8; }
  .toolbar button.active { background: #dc2626; border-color: #b91c1c; }
  .toolbar button.playing { background: #059669; border-color: #047857; }
  .toolbar span.status { margin-left: auto; font-size: .85rem; color: #334155; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
          gap: 1rem; padding: 1rem 1.5rem; max-width: 1400px; margin: 0 auto; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: .8rem;
          overflow: hidden; display: flex; flex-direction: column; height: 300px; position: relative; }
  .card header { padding: .55rem .75rem; border-bottom: 1px solid #f1f5f9; background: #f8fafc; }
  .card .char { font-size: 1.6rem; font-weight: 700; line-height: 1; font-variant-numeric: normal; }
  .card .meta { font-size: .70rem; color: #64748b; margin-top: .12rem; line-height: 1.35; }
  .svg-wrap { flex: 1; position: relative; overflow: hidden; background: #fafafa; }
  svg { width: 100%; height: 100%; display: block; overflow: visible; }
  .glyph-contour { fill: #94a3b8; opacity: .30; stroke: none; }
  .glyph-contour.inactive { display: none; }
  .glyph-dot { opacity: .50; stroke: none; }
  .glyph-dot.inactive { display: none; }
  .dot-marker { stroke: #fff; stroke-width: 1.2; r: 3.5; }
  .dot-marker.inactive { display: none; }
  .anchor { fill: none; stroke: #0ea5e9; stroke-width: 2; r: 7; stroke-dasharray: 4 4; }
  .anchor.inactive { display: none; }
  .dot-start { fill: #16a34a; stroke: #fff; stroke-width: 1.5; r: 5; }
  .dot-end { fill: #dc2626; stroke: #fff; stroke-width: 1.5; r: 5; }
  .chevron { stroke: none; }
  .label { position: absolute; bottom: .45rem; left: .5rem; right: .5rem;
           font-size: .60rem; color: #475569; background: rgba(255,255,255,.88);
           padding: .1rem .4rem; border-radius: .25rem; pointer-events: none; line-height: 1.3; }
  .card.empty { visibility: hidden; pointer-events: none; background: transparent; border: none; box-shadow: none; height: 0; margin: 0; }
  .controls-note { grid-column: 1 / -1; font-size: .8rem; color: #64748b; padding: 0 1.5rem .5rem; text-align: center; }
  .hidden { display: none !important; }
  .rtl { direction: rtl; }
  .stroke-legend { font-size: .68rem; color: #64748b; margin-top: .05rem; }
</style>
</head>
<body>
<header>
  <h1>Midad &mdash; Milestone 2 Kinematic Audit</h1>
  <div class="sub">Arabic handwriting animation engine &mdash; calligraphic ductus &amp; topological repair &mdash; Human-in-the-Loop Checkpoint #1</div>
</header>

<div class="toolbar">
  <label>Letter</label>
  <select id="fLetter"><option value="">All letters</option></select>

  <label>Form</label>
  <select id="fForm"><option value="">All forms</option><option>isolated</option><option>initial</option><option>medial</option><option>final</option></select>

  <label>Loop</label>
  <select id="fLoop"><option value="">All</option><option>loop</option><option>non-loop</option></select>

  <label>Layers</label>
  <button id="btnContour" class="active" onclick="toggleLayer(this,'contour')">Contour</button>
  <button id="btnTraj" class="active" onclick="toggleLayer(this,'traj')">Trajectory</button>
  <button id="btnDots" class="active" onclick="toggleLayer(this,'dots')">Marks</button>
  <button id="btnAnchors" class="active" onclick="toggleLayer(this,'anchors')">Anchors</button>

  <button id="btnPlay" class="active playing" onclick="togglePlay()">Pause</button>
  <span class="status" id="status">Loading glyphs&hellip;</span>
</div>

<div id="grid" class="grid"></div>
<div class="controls-note">
  Green dot = start (s=0)&nbsp;&nbsp;Red dot = end (s=1)&nbsp;&nbsp;Blue rings = entry/exit anchors&nbsp;&nbsp;
  Colored dots = delayed marks (amber=dot, red=hamza, magenta=madda, orange=inner mark)&nbsp;&nbsp;
  Strokes are drawn in ductus order: 1=cyan, 2=rose, 3=violet, 4=amber
</div>

<script id="data" type="application/json">
%%DATA%%
</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const GLYPHS = DATA.glyphs;
const KEYS = Object.keys(GLYPHS);

const FORM_LABELS = { isolated: 'معزول', initial: 'أولية', medial: 'وسطى', final: 'نهاية' };

// ---------- UI state ----------
let filters = { letter: '', form: '', loop: '' };
let layers = { contour: true, traj: true, dots: true, anchors: true };
let playing = true;
let animId = null;

// ---------- SVG helpers ----------
function svgPath(points) {
  if (!points || points.length < 2) return '';
  let d = `M ${points[0][0].toFixed(2)} ${(-points[0][1]).toFixed(2)}`;
  for (let i = 1; i < points.length; i++) {
    d += ` L ${points[i][0].toFixed(2)} ${(-points[i][1]).toFixed(2)}`;
  }
  return d;
}

function ringPath(ring) {
  if (!ring || ring.length < 3) return '';
  let d = `M ${ring[0][0].toFixed(2)} ${(-ring[0][1]).toFixed(2)}`;
  for (let i = 1; i < ring.length; i++) {
    d += ` L ${ring[i][0].toFixed(2)} ${(-ring[i][1]).toFixed(2)}`;
  }
  return d + ' Z';
}

function bboxOfRings(rings) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const ring of rings) {
    for (const [x, y] of ring) {
      minX = Math.min(minX, x); minY = Math.min(minY, y);
      maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
    }
  }
  return { minX, minY, maxX, maxY };
}

function fitView(svg, rings) {
  const bb = bboxOfRings(rings);
  if (!rings.length || bb.minX === Infinity) return;
  const pad = 12;
  const width = svg.clientWidth || 220;
  const height = svg.clientHeight || 200;
  const w = bb.maxX - bb.minX || 1;
  const h = bb.maxY - bb.minY || 1;
  const scale = Math.min((width - 2 * pad) / w, (height - 2 * pad) / h);
  const cx = (bb.minX + bb.maxX) / 2;
  const cy = (bb.minY + bb.maxY) / 2;
  svg.setAttribute('viewBox', `${cx - w/2 - pad/scale} ${-(cy + h/2 + pad/scale)} ${w + 2*pad/scale} ${h + 2*pad/scale}`);
}

// ---------- Rendering ----------
function renderCard(key) {
  const g = GLYPHS[key];
  const card = document.createElement('article');
  card.className = 'card';
  card.dataset.key = key;

  const roleLabels = { dot: 'dot', inner_mark: 'inner mark', hamza: 'hamza', madda: 'madda' };
  const marksInfo = g.delayed_strokes.map(m => roleLabels[m.role] || m.role).join(', ') || 'none';

  const header = document.createElement('div');
  header.className = 'header';
  header.innerHTML = `<div class="char rtl">${g.char}</div>
    <div class="meta">${g.name} &middot; ${FORM_LABELS[g.form]} &middot; strokes=${g.num_trunk_strokes} &middot; marks=${marksInfo} &middot; loop=${g.loop_count} &middot; RTL=${(g.rtl_ratio*100).toFixed(0)}% &middot; ${g.anchors_ok ? 'anchors OK' : 'anchors FAIL'}</div>`;
  card.appendChild(header);

  const wrap = document.createElement('div');
  wrap.className = 'svg-wrap';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  wrap.appendChild(svg);

  // translucent original contour
  const contourGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  contourGroup.classList.add('glyph-contour');
  for (const ring of g.trunk_contours) {
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', ringPath(ring));
    p.classList.add('glyph-contour');
    contourGroup.appendChild(p);
  }
  svg.appendChild(contourGroup);

  // multi-stroke trajectories, each in its own color (ductus order)
  const strokePaths = [];
  for (const stroke of g.directed_strokes) {
    const pts = stroke.points.map(p => [p[0], p[1]]);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', svgPath(pts));
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', stroke.color);
    path.setAttribute('stroke-width', '2.6');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    path.setAttribute('opacity', '0.95');
    path.classList.add('traj-stroke');
    path.dataset.strokeIndex = stroke.index;
    svg.appendChild(path);
    strokePaths.push({ path, pts: stroke.points, index: stroke.index });
  }

  // animated chevrons (one per stroke, sequenced)
  const animGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  animGroup.classList.add('chevron-anim');
  svg.appendChild(animGroup);

  // start / end dots
  const [sx, sy] = g.start_point;
  const [ex, ey] = g.end_point;
  const startDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  startDot.setAttribute('cx', sx); startDot.setAttribute('cy', -sy);
  startDot.setAttribute('r', '5'); startDot.classList.add('dot-start');
  svg.appendChild(startDot);
  const endDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  endDot.setAttribute('cx', ex); endDot.setAttribute('cy', -ey);
  endDot.setAttribute('r', '5'); endDot.classList.add('dot-end');
  svg.appendChild(endDot);

  // anchors (blue rings)
  const anchorEls = [];
  if (g.entry_anchor) {
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', g.entry_anchor[0]); c.setAttribute('cy', -g.entry_anchor[1]);
    c.setAttribute('r', '7'); c.classList.add('anchor'); svg.appendChild(c);
    anchorEls.push(c);
  }
  if (g.exit_anchor) {
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', g.exit_anchor[0]); c.setAttribute('cy', -g.exit_anchor[1]);
    c.setAttribute('r', '7'); c.classList.add('anchor'); svg.appendChild(c);
    anchorEls.push(c);
  }

  // delayed marks (role-colored dots)
  const markEls = [];
  for (const m of g.delayed_strokes) {
    const [mx, my] = m.attachment_point;
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', mx); c.setAttribute('cy', -my);
    c.setAttribute('r', '4'); c.setAttribute('fill', m.color);
    c.classList.add('dot-marker');
    c.dataset.role = m.role;
    svg.appendChild(c);
    markEls.push(c);
  }

  // translucent mark contours
  const dotGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  dotGroup.classList.add('glyph-dot');
  for (const ring of g.dot_contours) {
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', ringPath(ring));
    p.setAttribute('fill', '#f59e0b'); p.setAttribute('opacity', '.40');
    dotGroup.appendChild(p);
  }
  svg.appendChild(dotGroup);

  const label = document.createElement('div');
  label.className = 'label';
  label.textContent = `${g.char} &mdash; ${FORM_LABELS[g.form]} &middot; s \\in [0,1] &middot; start=(${g.start_point[0].toFixed(0)},${g.start_point[1].toFixed(0)}) end=(${g.end_point[0].toFixed(0)},${g.end_point[1].toFixed(0)})`;
  card.appendChild(label);

  card.appendChild(wrap);
  return { card, svg, strokePaths, animGroup, anchorEls, markEls };
}

const rendered = {};
const grid = document.getElementById('grid');

function applyFilters() {
  grid.innerHTML = '';
  rendered = {};
  let shown = 0;
  for (const key of KEYS) {
    const g = GLYPHS[key];
    if (filters.letter && g.char !== filters.letter) continue;
    if (filters.form && g.form !== filters.form) continue;
    if (filters.loop === 'loop' && g.loop_count < 1) continue;
    if (filters.loop === 'non-loop' && g.loop_count >= 1) continue;
    const rc = renderCard(key);
    grid.appendChild(rc.card);
    rendered[key] = rc;
    fitView(rc.svg, g.trunk_contours);
    shown++;
  }
  document.getElementById('status').textContent = `${shown} glyph(s) shown`;
  applyLayers();
  startAnimation();
}

function applyLayers() {
  document.querySelectorAll('.glyph-contour').forEach(el => el.style.display = layers.contour ? '' : 'none');
  document.querySelectorAll('.traj-stroke').forEach(el => el.style.display = layers.traj ? '' : 'none');
  document.querySelectorAll('.dot-marker, .glyph-dot').forEach(el => el.style.display = layers.dots ? '' : 'none');
  document.querySelectorAll('.anchor').forEach(el => el.style.display = layers.anchors ? '' : 'none');
}

function toggleLayer(btn, name) {
  layers[name] = !layers[name];
  btn.classList.toggle('active');
  applyLayers();
}

// ---------- Animation (sequential: stroke 1 -> stroke 2 -> marks) ----------
function startAnimation() {
  if (animId) cancelAnimationFrame(animId);
  if (!playing) return;
  const t0 = performance.now();
  const CYCLE = 5000; // 5 second cycle
  function frame(now) {
    const phase = (now - t0) % CYCLE / CYCLE; // 0 -> 1
    for (const [key, rc] of Object.entries(rendered)) {
      const { strokePaths, animGroup } = rc;
      const nStrokes = strokePaths.length;
      // clear previous chevrons
      while (animGroup.firstChild) animGroup.removeChild(animGroup.firstChild);

      // Each stroke gets an equal slice of the cycle; marks appear at the end.
      const strokeSlot = 1.0 / Math.max(nStrokes, 1);
      for (const sp of strokePaths) {
        const si = sp.index;
        const slotStart = si * strokeSlot;
        const slotEnd = slotStart + strokeSlot * 0.85; // leave gap between strokes
        let t = null;
        if (phase >= slotStart && phase < slotEnd) {
          t = (phase - slotStart) / (slotEnd - slotStart);
        } else if (phase >= slotEnd && si === nStrokes - 1) {
          // hold on last stroke briefly then show marks
          t = null;
        }
        if (t !== null) {
          const pt = pointOnPath(sp.pts, t);
          if (pt) {
            const ang = tangentAngle(sp.pts, t);
            addChevron(animGroup, pt, ang, sp.path.getAttribute('stroke') || '#2563eb');
          }
        }
      }
      // show mark dots in the final slot
      const markSlotStart = 1.0 - strokeSlot * 0.15;
      if (phase >= markSlotStart) {
        rc.markEls.forEach(el => { el.style.opacity = '1'; el.style.filter = 'drop-shadow(0 0 2px #000)'; });
      } else {
        rc.markEls.forEach(el => { el.style.opacity = '0.35'; el.style.filter = 'none'; });
      }
    }
    animId = requestAnimationFrame(frame);
  }
  animId = requestAnimationFrame(frame);
}

function addChevron(group, pt, ang, color) {
  const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  const size = 8;
  const d = `M ${pt.x - size*0.6} ${pt.y - size*0.4} L ${pt.x} ${pt.y} L ${pt.x - size*0.6} ${pt.y + size*0.4}`;
  chevron.setAttribute('d', d);
  chevron.setAttribute('fill', color);
  chevron.setAttribute('transform', `rotate(${ang}, ${pt.x}, ${pt.y})`);
  group.appendChild(chevron);
}

function pointOnPath(pts, t) {
  if (pts.length < 2) return null;
  let len = 0, lens = [0];
  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i][0] - pts[i-1][0];
    const dy = pts[i][1] - pts[i-1][1];
    len += Math.hypot(dx, dy);
    lens.push(len);
  }
  const target = t * len;
  let seg = 0;
  while (seg < pts.length - 1 && lens[seg + 1] < target) seg++;
  const span = lens[seg + 1] - lens[seg] || 1;
  const f = (target - lens[seg]) / span;
  return { x: pts[seg][0] + (pts[seg+1][0] - pts[seg][0]) * f,
           y: pts[seg][1] + (pts[seg+1][1] - pts[seg][1]) * f };
}

function tangentAngle(pts, t) {
  if (pts.length < 2) return 0;
  const p1 = pointOnPath(pts, Math.min(1, t + 0.01));
  const p0 = pointOnPath(pts, Math.max(0, t - 0.01));
  if (!p1 || !p0) return 0;
  return Math.atan2(p1.y - p0.y, p1.x - p0.x) * 180 / Math.PI;
}

function togglePlay() {
  playing = !playing;
  const btn = document.getElementById('btnPlay');
  btn.textContent = playing ? 'Pause' : 'Play';
  btn.classList.toggle('playing');
  if (playing) startAnimation(); else { if (animId) cancelAnimationFrame(animId); }
}

// ---------- Filter wiring ----------
document.getElementById('fLetter').addEventListener('change', e => { filters.letter = e.target.value; applyFilters(); });
document.getElementById('fForm').addEventListener('change', e => { filters.form = e.target.value; applyFilters(); });
document.getElementById('fLoop').addEventListener('change', e => { filters.loop = e.target.value; applyFilters(); });

// populate letter select
const letters = [...new Set(KEYS.map(k => GLYPHS[k].char))];
const sel = document.getElementById('fLetter');
for (const ch of letters) {
  const o = document.createElement('option'); o.value = ch; o.textContent = ch; sel.appendChild(o);
}

// ---------- Init ----------
document.getElementById('status').textContent = `Rendering ${KEYS.length} glyphs&hellip;`;
applyFilters();
</script>
</body>
</html>"""

TEMPLATE_PLACEHOLDER = "%%DATA%%"


def main():
    data = build_embedded_data()
    html = HTML_TEMPLATE.replace(TEMPLATE_PLACEHOLDER, json.dumps(data, ensure_ascii=False, indent=1))
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({len(html)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
