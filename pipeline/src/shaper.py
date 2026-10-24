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
import re
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
    rule: dict[str, Any] | None = None,
) -> str:
    """Determine the positional form of ``char`` within its PAW.

    In Arabic script, every PAW is a connected cursive sequence:
    - n == 1: isolated
    - index == 0: initial
    - index == n - 1: final
    - middle letters (0 < index < n - 1): medial
    """
    n = len(paw)
    if n == 1:
        return "isolated"
    if index == 0:
        return "initial"
    if index == n - 1:
        return "final"
    return "medial"


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
        return -1.0, 0.0
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


def clean_and_align_stroke(
    points: list[list[float]],
    is_initial: bool = False,
    is_medial: bool = False,
    is_final: bool = False,
) -> list[list[float]]:
    """Clean raster thinning hook spurs and align baseline connecting tangents to (-1, 0)."""
    pts = [list(p) for p in points]
    if len(pts) < 8:
        return pts

    # 1. Prune exit hook if moving right or looping
    if is_initial or is_medial:
        last_n = min(15, len(pts))
        min_x_idx = len(pts) - 1
        for i in range(len(pts) - 1, len(pts) - last_n, -1):
            if pts[i][0] > pts[i - 1][0] + 0.5:
                min_x_idx = i - 1
                break
        if min_x_idx < len(pts) - 1:
            pts = pts[: min_x_idx + 1]

    # 2. Prune entry hook if moving right
    if is_medial or is_final:
        first_n = min(15, len(pts))
        max_x_idx = 0
        for i in range(0, first_n - 1):
            if pts[i + 1][0] > pts[i][0] + 0.5:
                max_x_idx = i + 1
                break
        if max_x_idx > 0:
            pts = pts[max_x_idx:]

    # 3. Align endpoint tangents to strictly horizontal (-1, 0)
    if is_initial or is_medial:
        p_last = pts[-1]
        step = max(5.0, math.hypot(p_last[0] - pts[-2][0], p_last[1] - pts[-2][1]))
        pts[-2] = [p_last[0] + step, p_last[1]]

    if is_medial or is_final:
        p_first = pts[0]
        step = max(5.0, math.hypot(pts[1][0] - p_first[0], pts[1][1] - p_first[1]))
        pts[1] = [p_first[0] - step, p_first[1]]

    return pts


def build_paw_trunk_path(
    paw_letters: list[str],
    catalog: dict[str, dict[str, Any]],
    bridge: float = 20.0,
) -> dict[str, Any]:
    """Build a single continuous trunk path for one PAW with smooth spatial letter placement.

    Letters are placed right-to-left: each letter connects via a smooth tangent-matched
    horizontal cubic bridge with zero loop spikes and exact C0/G1 continuity.
    """

    if not paw_letters:
        return {
            "d": "",
            "length": 0.0,
            "start_point": None,
            "end_point": None,
            "letter_translations": [],
            "secondary_strokes": [],
        }

    commands: list[str] = []
    total_length = 0.0
    letter_translations: list[tuple[float, float]] = []
    secondary_strokes: list[dict[str, Any]] = []

    prev_exit_x: float | None = None
    prev_exit_y: float | None = None
    current_point: tuple[float, float] | None = None

    for index, char in enumerate(paw_letters):
        rule = get_rule(char)
        form = determine_form(char, index, paw_letters, rule)
        glyph = get_directed_glyph(catalog, char, form)
        if glyph is None:
            raise ValueError(
                f"no directed glyph for {char!r} / {form} (key {char}_{form})"
            )

        strokes = glyph["trunk_strokes"]
        s0_raw = strokes[0]["points"]

        is_init = (index == 0 and len(paw_letters) > 1)
        is_med = (0 < index < len(paw_letters) - 1)
        is_fin = (index == len(paw_letters) - 1 and len(paw_letters) > 1)

        s0_pts = clean_and_align_stroke(
            s0_raw, is_initial=is_init, is_medial=is_med, is_final=is_fin
        )
        entry_pt = s0_pts[0]
        exit_pt = s0_pts[-1]

        if index == 0:
            dx = 0.0
        else:
            dx = (prev_exit_x - bridge) - entry_pt[0]
        dy = 0.0
        letter_translations.append((dx, dy))

        shifted_s0 = [[p[0] + dx, p[1] + dy] for p in s0_pts]
        stroke_start = (shifted_s0[0][0], shifted_s0[0][1])

        # Preserve secondary strokes (e.g., Tah upright mast)
        for sec_stroke in strokes[1:]:
            sec_shifted = [[p[0] + dx, p[1] + dy] for p in sec_stroke["points"]]
            secondary_strokes.append(
                {
                    "role": "secondary",
                    "points": sec_shifted,
                    "length": float(sec_stroke.get("length", 100.0)),
                }
            )

        if index == 0:
            commands.append(f"M {stroke_start[0]:.4f} {stroke_start[1]:.4f}")
            current_point = stroke_start
        else:
            prev_end = (prev_exit_x, prev_exit_y)
            # Smooth horizontal cubic bridge along writing ductus
            span = prev_end[0] - stroke_start[0]
            c1 = (prev_end[0] - 0.45 * span, prev_end[1])
            c2 = (stroke_start[0] + 0.45 * span, stroke_start[1])
            commands.append(
                f"C {c1[0]:.4f} {c1[1]:.4f} {c2[0]:.4f} {c2[1]:.4f} {stroke_start[0]:.4f} {stroke_start[1]:.4f}"
            )
            total_length += span
            current_point = stroke_start

        for p in shifted_s0[1:]:
            px, py = p[0], p[1]
            commands.append(f"L {px:.4f} {py:.4f}")
            total_length += math.hypot(px - current_point[0], py - current_point[1])
            current_point = (px, py)

        prev_exit_x = exit_pt[0] + dx
        prev_exit_y = exit_pt[1] + dy

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
        "letter_translations": letter_translations,
        "secondary_strokes": secondary_strokes,
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
    """Shape one Arabic word into spatially placed PAWs with welded trunks and delayed marks."""

    paws = partition_paws(text)
    paw_data_list = []

    # 1. Build local PAWs with intra-PAW spatial placement
    for paw_index, paw_letters in enumerate(paws):
        paw_id = f"paw_{paw_index}"
        trunk_res = build_paw_trunk_path(paw_letters, catalog)

        delayed_records: list[dict[str, Any]] = []
        for index, char in enumerate(paw_letters):
            form = determine_form(char, index, paw_letters)
            glyph = catalog[f"{char}_{form}"]
            dx, dy = trunk_res["letter_translations"][index]
            for ds in glyph["delayed_strokes"]:
                delayed_records.append(
                    position_delayed_stroke(ds, dx, dy)
                )

        # Include secondary strokes (e.g. Tah upright mast)
        for sec in trunk_res["secondary_strokes"]:
            delayed_records.append(
                {
                    "role": "secondary",
                    "attachment_s": 0.5,
                    "attachment_point": sec["points"][0],
                    "centroid": sec["points"][0],
                    "points": sec["points"],
                    "length": sec["length"],
                }
            )

        # Local bounding box
        xs: list[float] = []
        tokens = re.findall(r"[-+]?\d*\.?\d+", trunk_res["d"])
        for k in range(0, len(tokens) - 1, 2):
            xs.append(float(tokens[k]))
        for ds in delayed_records:
            for p in ds["points"]:
                xs.append(float(p[0]))

        paw_data_list.append(
            {
                "paw_id": paw_id,
                "letters": "".join(paw_letters),
                "trunk_d": trunk_res["d"],
                "trunk_length": trunk_res["length"],
                "delayed_records": delayed_records,
                "minx": min(xs) if xs else 0.0,
                "maxx": max(xs) if xs else 0.0,
            }
        )

    # 2. Position PAWs horizontally (RTL progression)
    PAW_GAP = 80.0
    current_left = 0.0
    for idx, pdata in enumerate(paw_data_list):
        if idx == 0:
            shift_x = 0.0
        else:
            # Place rightmost point of this PAW to the left of the previous PAW
            shift_x = (current_left - PAW_GAP) - pdata["maxx"]

        pdata["shift_x"] = shift_x
        pdata["global_minx"] = pdata["minx"] + shift_x
        pdata["global_maxx"] = pdata["maxx"] + shift_x
        current_left = pdata["global_minx"]

    # 3. Global normalization: shift entire word so leftmost point is at x = 50.0
    global_min_x = min(p["global_minx"] for p in paw_data_list)
    norm_shift = 50.0 - global_min_x

    final_paws = []
    timeline_items = []
    time_cursor = 0.0

    for pdata in paw_data_list:
        total_shift = pdata["shift_x"] + norm_shift
        trunk_d_norm = translate_path_d(pdata["trunk_d"], total_shift, 0.0)

        del_norm = []
        for ds in pdata["delayed_records"]:
            del_norm.append(position_delayed_stroke(ds, total_shift, 0.0))

        # Causal Timeline: trunk completes first, then delayed marks
        paw_id = pdata["paw_id"]
        trunk_dur = max(1.0, pdata["trunk_length"] / 200.0)
        t_start = time_cursor
        t_end = time_cursor + trunk_dur
        timeline_items.append(
            {
                "strokeId": f"{paw_id}_trunk",
                "pawId": paw_id,
                "type": "trunk",
                "startTime": round(t_start, 4),
                "endTime": round(t_end, 4),
            }
        )
        time_cursor = t_end

        for mi, ds in enumerate(del_norm):
            ds_start = time_cursor
            ds_end = time_cursor + max(0.4, ds["length"] / 400.0)
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

        tokens = re.findall(r"[-+]?\d*\.?\d+", trunk_d_norm)
        start_pt = [float(tokens[0]), float(tokens[1])]
        end_pt = [float(tokens[-2]), float(tokens[-1])]

        final_paws.append(
            {
                "id": paw_id,
                "letters": pdata["letters"],
                "trunkStroke": {
                    "id": f"{paw_id}_trunk",
                    "d": trunk_d_norm,
                    "length": round(pdata["trunk_length"], 4),
                    "type": "trunk",
                    "startPoint": start_pt,
                    "endPoint": end_pt,
                },
                "delayedStrokes": del_norm,
            }
        )

    return {
        "text": text,
        "paws": final_paws,
        "timeline": {
            "paws": [
                {
                    "id": p["id"],
                    "trunkStroke": p["trunkStroke"],
                    "delayedStrokes": p["delayedStrokes"],
                }
                for p in final_paws
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
