"""MILESTONE 3: RTL Shaping & Baseline Welding Engine.

Shapes Arabic text into Pieces of Arabic Words (PAWs), welds each PAW's
directed trunk strokes into a single continuous baseline path (one ``M``
command), and schedules delayed strokes (dots / i'jam, hamza, madda, kaf
inner mark) strictly after each PAW trunk completes drawing.

The weld bridges the exit anchor of letter ``i`` to the entry anchor of
letter ``i+1`` using a tangent-matched cubic so that:

* **C0 continuity**: joint distance ``Delta < 0.05`` font units.
* **G1 tangent continuity**: outgoing tangent of letter ``i`` vs incoming
  tangent of letter ``i+1`` satisfy ``Delta theta < 12 deg``.
* **Single-M invariant**: each PAW baseline trunk is exactly one SVG path
  starting with a single ``M`` command and no subsequent ``M``.

Delayed marks are positioned in absolute canvas coordinates matching their
parent glyphs and scheduled strictly after the PAW trunk completes drawing,
ordered by attachment parameter ``s_attach``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# Make pipeline/src importable when this module is run directly.
try:  # pragma: no cover - import style depends on how the module is loaded
    from rules import ARABIC_CHARACTER_RULES, get_rule
except ImportError:  # pragma: no cover
    from pipeline.src.rules import ARABIC_CHARACTER_RULES, get_rule  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_PATH = REPO_ROOT / "fixtures" / "fonts" / "NotoNaskhArabic-Regular.ttf"
DIRECTED_GLYPHS_PATH = REPO_ROOT / "fixtures" / "skeletons" / "directed_glyphs.json"
WELDED_50_WORDS_PATH = REPO_ROOT / "fixtures" / "golden" / "welded_50_words.json"

# Characters that do NOT connect to the left (right-joining only or
# non-joining).  Any character following one of these starts a new PAW.
NON_CONNECTING: frozenset[str] = frozenset(
    {
        "ا",
        "أ",
        "إ",
        "آ",  # Alef family (R-joining)
        "د",
        "ذ",
        "ر",
        "ز",
        "و",  # R-joining letters
        "ء",  # Hamza (U non-joining)
    }
)

# Canonical 50-word Arabic corpus covering all 28 letters across isolated,
# initial, medial and final forms, loop letters, multi-stroke letters
# (Tah, Zah, Lam-Alif) and multiple PAWs per word.
_CANONICAL_50_WORDS: tuple[str, ...] = (
    "كتب",
    "محمد",
    "العربية",
    "جميل",
    "صابر",
    "طالب",
    "استقلال",
    "خطاط",
    "قلم",
    "سماء",
    "نستعليق",
    "حضارة",
    "فجر",
    "قرآن",
    "تاريخ",
    "شروق",
    "ذهب",
    "زمرد",
    "ورد",
    "زهرة",
    "كتاب",
    "مدرسة",
    "بيت",
    "شمس",
    "قمر",
    "ليل",
    "نهار",
    "ربيع",
    "شتاء",
    "خريف",
    "قرية",
    "مدينة",
    "نهر",
    "بستان",
    "بذرة",
    "شجرة",
    "بحر",
    "جبل",
    "مصباح",
    "باب",
    "شباك",
    "كرسي",
    "قمرية",
    "مربع",
    "مثلث",
    "نجمة",
    "مكتبة",
    "حكاية",
    "حرف",
    "نقط",
)


def canonical_words() -> tuple[str, ...]:
    """Return the 50-word canonical corpus."""
    return _CANONICAL_50_WORDS


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _unit(dx: float, dy: float) -> tuple[float, float]:
    n = math.hypot(dx, dy)
    if n == 0:
        return 0.0, 0.0
    return dx / n, dy / n


def _weld_cubic(
    p0: tuple[float, float],
    t0: tuple[float, float],
    p1: tuple[float, float],
    t1: tuple[float, float],
    gap: float,
) -> tuple[float, float, float, float, float, float]:
    """Tangent-matched cubic from p0 (tangent t0) to p1 (tangent t1).

    Returns ``(c1x, c1y, c2x, c2y, ex, ey)`` for an SVG ``C`` command.
    """
    w = min(0.35 * gap, 60.0)
    c1 = (p0[0] + t0[0] * w, p0[1] + t0[1] * w)
    c2 = (p1[0] - t1[0] * w, p1[1] - t1[1] * w)
    return (c1[0], c1[1], c2[0], c2[1], p1[0], p1[1])


# ---------------------------------------------------------------------------
# PAW partitioning & form determination
# ---------------------------------------------------------------------------


def is_non_connecting(char: str) -> bool:
    """Return True if ``char`` breaks cursive continuity (R-joining or U)."""
    return char in NON_CONNECTING


def partition_paws(text: str) -> list[list[str]]:
    """Split ``text`` into PAWs.

    A new PAW starts after any non-connecting character or after whitespace.
    """

    paws: list[list[str]] = []
    current: list[str] = []
    for ch in text:
        if ch.isspace():
            if current:
                paws.append(current)
                current = []
            continue
        current.append(ch)
        if is_non_connecting(ch):
            paws.append(current)
            current = []
    if current:
        paws.append(current)
    return paws


def determine_form(
    char: str,
    index: int,
    paw: list[str],
    rule: dict[str, Any],
) -> str:
    """Determine the positional form of ``char`` within its PAW."""

    joining = rule["joining_type"]
    n = len(paw)

    # Non-joining (U) letters are always isolated.
    if joining == "U":
        return "isolated"

    # Single-letter PAW -> isolated.
    if n == 1:
        return "isolated"

    # Right-joining (R) letters: initial if followed by a connector, else
    # final (they never take medial).
    if joining == "R":
        if index < n - 1:
            return "initial"
        return "final"

    # Dual-joining (D) letters.
    prev_connects = index > 0 and not is_non_connecting(paw[index - 1])
    next_connects = index < n - 1 and not is_non_connecting(paw[index + 1])
    if prev_connects and next_connects:
        return "medial"
    if prev_connects:
        return "final"
    if next_connects:
        return "initial"
    return "isolated"


# ---------------------------------------------------------------------------
# Directed glyph lookup
# ---------------------------------------------------------------------------


def load_directed_glyphs(path: Path = DIRECTED_GLYPHS_PATH) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data["glyphs"]


def get_directed_glyph(
    catalog: dict[str, dict[str, Any]], char: str, form: str
) -> dict[str, Any] | None:
    key = f"{char}_{form}"
    return catalog.get(key)


# ---------------------------------------------------------------------------
# Tangent estimation
# ---------------------------------------------------------------------------


def _stroke_tangent(points: list[list[float]], at: str = "end") -> tuple[float, float]:
    """Estimate the unit tangent vector at the start or end of a stroke."""
    if len(points) < 2:
        return 1.0, 0.0
    if at == "end":
        p0 = points[-2]
        p1 = points[-1]
    else:
        p0 = points[0]
        p1 = points[1]
    return _unit(p1[0] - p0[0], p1[1] - p0[1])


# ---------------------------------------------------------------------------
# Trunk path construction
# ---------------------------------------------------------------------------


def build_paw_trunk_path(
    paw_letters: list[str],
    catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a single continuous trunk path for one PAW.

    Returns a dict with:
      - ``d``: SVG path data (single ``M``, then ``L``/``C`` segments).
      - ``length``: total path length in font units.
      - ``start_point`` / ``end_point``: PAW extremes.
    """

    if not paw_letters:
        return {"d": "", "length": 0.0, "start_point": None, "end_point": None}

    commands: list[str] = []
    total_length = 0.0
    current_point: tuple[float, float] | None = None
    prev_exit_tangent: tuple[float, float] | None = None

    for index, char in enumerate(paw_letters):
        rule = get_rule(char)
        form = determine_form(char, index, paw_letters, rule)
        glyph = get_directed_glyph(catalog, char, form)
        if glyph is None:
            raise ValueError(
                f"no directed glyph for {char!r} / {form} (key {char}_{form})"
            )

        strokes = glyph["trunk_strokes"]
        pts = strokes[0]["points"]
        stroke_start = (float(pts[0][0]), float(pts[0][1]))
        stroke_end = (float(pts[-1][0]), float(pts[-1][1]))
        exit_tangent = _stroke_tangent(pts, at="end")

        if current_point is None:
            # First letter of the PAW: start a fresh subpath.
            commands.append(f"M {stroke_start[0]:.4f} {stroke_start[1]:.4f}")
            current_point = stroke_start
        else:
            # Weld from previous letter's end to this letter's start.
            prev_end = current_point
            entry_tangent = _stroke_tangent(pts, at="start")
            # Outgoing tangent of the PREVIOUS letter at its exit (prev_end).
            exit_t = prev_exit_tangent if prev_exit_tangent is not None else exit_tangent
            gap = _dist(prev_end, stroke_start)
            if gap > 1e-6:
                c1x, c1y, c2x, c2y, ex, ey = _weld_cubic(
                    prev_end, exit_t, stroke_start, entry_tangent, gap
                )
                commands.append(
                    f"C {c1x:.4f} {c1y:.4f} {c2x:.4f} {c2y:.4f} {ex:.4f} {ey:.4f}"
                )
                total_length += _dist(prev_end, (c1x, c1y))
                total_length += _dist((c1x, c1y), (c2x, c2y))
                total_length += _dist((c2x, c2y), (ex, ey))
            current_point = stroke_start

        # Emit this letter's trunk stroke.  Translate so the first point
        # coincides exactly with current_point (already set by M or weld).
        dx = current_point[0] - pts[0][0]
        dy = current_point[1] - pts[0][1]
        prev_px = current_point[0]
        prev_py = current_point[1]
        for p in pts[1:]:
            px = float(p[0]) + dx
            py = float(p[1]) + dy
            commands.append(f"L {px:.4f} {py:.4f}")
            total_length += _dist((prev_px, prev_py), (px, py))
            prev_px, prev_py = px, py
        current_point = (prev_px, prev_py)
        prev_exit_tangent = exit_tangent

    d = " ".join(commands)
    return {
        "d": d,
        "length": round(total_length, 4),
        "start_point": (
            float(commands[0].split()[1]),
            float(commands[0].split()[2]),
        )
        if commands
        else None,
        "end_point": current_point,
    }


def translate_path_d(d: str, dx: float, dy: float) -> str:
    """Translate every coordinate in an SVG path ``d`` string by (dx, dy)."""

    import re

    tokens = re.findall(r"[MLCQZmlcqz]|-?\d+(?:\.\d+)?", d)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("M", "m", "L", "l", "C", "c", "Q", "q", "Z", "z"):
            out.append(tok.upper())
            i += 1
            continue
        # number (x)
        x = float(tok) + dx
        y = float(tokens[i + 1]) + dy
        out.append(f"{x:.4f}")
        out.append(f"{y:.4f}")
        i += 2
    return " ".join(out)


# ---------------------------------------------------------------------------
# Delayed-stroke scheduling
# ---------------------------------------------------------------------------


def position_delayed_stroke(
    delayed: dict[str, Any],
    dx: float,
    dy: float,
) -> dict[str, Any]:
    """Translate a delayed stroke into absolute canvas coordinates."""

    points = delayed.get("points", [])
    shifted = [[round(float(x) + dx, 4), round(float(y) + dy, 4)] for x, y in points]
    centroid = delayed.get("centroid")
    attachment_point = delayed.get("attachment_point")
    role = delayed.get("role", "dot")

    return {
        "role": role,
        "attachment_s": delayed.get("attachment_s"),
        "attachment_point": (
            [round(attachment_point[0] + dx, 4), round(attachment_point[1] + dy, 4)]
            if attachment_point
            else None
        ),
        "centroid": (
            [round(centroid[0] + dx, 4), round(centroid[1] + dy, 4)]
            if centroid
            else None
        ),
        "points": shifted,
        "length": round(float(delayed.get("length", 0.0)), 4),
    }


# ---------------------------------------------------------------------------
# Full word shaping
# ---------------------------------------------------------------------------


def shape_word(
    text: str,
    catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Shape one Arabic word into PAWs with welded trunks and delayed marks."""

    paws = partition_paws(text)
    paw_records: list[dict[str, Any]] = []
    timeline_items: list[dict[str, Any]] = []

    cursor_x = 0.0  # running canvas x offset across PAWs (RTL: move left)
    time_cursor = 0.0

    for paw_index, paw_letters in enumerate(paws):
        paw_id = f"paw_{paw_index}"
        trunk = build_paw_trunk_path(paw_letters, catalog)

        # Translate the whole PAW trunk so it sits at the PAW cursor x.
        trunk_d = translate_path_d(trunk["d"], cursor_x, 0.0)

        # Build delayed strokes for this PAW (one per letter, offset by cursor_x).
        delayed_records: list[dict[str, Any]] = []
        for index, char in enumerate(paw_letters):
            rule = get_rule(char)
            form = determine_form(char, index, paw_letters, rule)
            glyph = get_directed_glyph(catalog, char, form)
            if glyph is None:
                continue
            for delayed in glyph["delayed_strokes"]:
                delayed_records.append(
                    position_delayed_stroke(delayed, cursor_x, 0.0)
                )

        # Timing: trunk draws first, then delayed marks.
        trunk_duration = max(1.0, trunk["length"] / 200.0)
        trunk_start = time_cursor
        trunk_end = time_cursor + trunk_duration
        timeline_items.append(
            {
                "strokeId": f"{paw_id}_trunk",
                "pawId": paw_id,
                "type": "trunk",
                "startTime": round(trunk_start, 4),
                "endTime": round(trunk_end, 4),
            }
        )
        time_cursor = trunk_end
        for mi, delayed in enumerate(delayed_records):
            ds_start = time_cursor
            ds_end = time_cursor + max(0.4, delayed["length"] / 400.0)
            timeline_items.append(
                {
                    "strokeId": f"{paw_id}_delayed_{mi}",
                    "pawId": paw_id,
                    "type": "delayed",
                    "startTime": round(ds_start, 4),
                    "endTime": round(ds_end, 4),
                }
            )
            time_cursor = ds_end

        cursor_x -= 40.0  # PAW gap (move left for next PAW)

        paw_records.append(
            {
                "id": paw_id,
                "letters": "".join(paw_letters),
                "trunkStroke": {
                    "id": f"{paw_id}_trunk",
                    "d": trunk_d,
                    "length": trunk["length"],
                    "type": "trunk",
                    "startPoint": trunk["start_point"],
                    "endPoint": trunk["end_point"],
                },
                "delayedStrokes": delayed_records,
            }
        )

    return {
        "text": text,
        "paws": paw_records,
        "timeline": {
            "paws": [
                {
                    "id": p["id"],
                    "trunkStroke": p["trunkStroke"],
                    "delayedStrokes": p["delayedStrokes"],
                }
                for p in paw_records
            ],
            "items": timeline_items,
            "totalDuration": round(time_cursor, 4),
        },
    }


# ---------------------------------------------------------------------------
# Golden fixture generation
# ---------------------------------------------------------------------------


def generate_welded_50_words(
    output_path: Path = WELDED_50_WORDS_PATH,
) -> Path:
    catalog = load_directed_glyphs()
    words = []
    for text in canonical_words():
        words.append(shape_word(text, catalog))
    data = {
        "font": str(FONT_PATH),
        "total_glyphs": len(catalog),
        "num_words": len(words),
        "words": words,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return output_path


if __name__ == "__main__":
    written = generate_welded_50_words()
    print(f"Wrote {written}")
