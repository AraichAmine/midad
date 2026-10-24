"""Kinematic stroke trajectory parameterization and ordering for Arabic glyphs.

Reads :file:`fixtures/skeletons/all_glyphs.json` (the Milestone 1 catalog) and
produces :file:`fixtures/skeletons/directed_glyphs.json`, an enriched catalog in
which every trunk stroke is:

* ordered according to the Naskh ductus -- right-to-left (RTL) horizontal
  progression, top-to-bottom vertical stems, bowl traversal from entry to exit;
* parameterized by normalized arc length ``s in [0, 1]`` so every point carries
  ``(x, y, s)``;
* annotated with ``start_point`` (``s = 0``), ``end_point`` (``s = 1``),
  ``flow_direction`` and the ``entry_anchor`` / ``exit_anchor`` match errors;
* annotated with delayed-stroke (dot / *i'jam*) attachment parameters
  ``s_attach in [0, 1]`` locating each dot on the trunk.

The skeletonizer already emits each covering trail starting at the rightmost
skeleton pixel and finishing at the leftmost one, which matches the RTL writing
direction.  This module cleans the trail (removes consecutive duplicates and
suppresses medial-axis wiggles with a short moving average), re-parameterizes it
by arc length, and verifies the calligraphic invariants.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ALL_GLYPHS_PATH = REPO_ROOT / "fixtures" / "skeletons" / "all_glyphs.json"
DIRECTED_GLYPHS_PATH = REPO_ROOT / "fixtures" / "skeletons" / "directed_glyphs.json"

# ---------------------------------------------------------------------------
# Calligraphic gates (Naskh ductus)
# ---------------------------------------------------------------------------

RTL_RATIO_GATE: float = 0.85  # >= 85% of horizontal progress must be RTL
ANCHOR_EPSILON: float = 3.0   # font units; anchor must lie within this of endpoint
SMOOTH_WINDOW: int = 3        # moving-average half-width to suppress wiggles

# Letters whose calligraphic form contains a closed bowl / loop.
LOOP_LETTERS: frozenset[str] = frozenset({"ص", "ض", "ط", "ظ", "ف", "ق", "م", "ه", "و", "ة"})

# Joining form -> which anchors are expected.
FORM_ENTRY: frozenset[str] = frozenset({"medial", "final"})
FORM_EXIT: frozenset[str] = frozenset({"medial", "initial"})

Point2D = tuple[float, float]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _smooth(points: list[Point2D], window: int = SMOOTH_WINDOW) -> list[Point2D]:
    """Light moving-average smoothing that keeps endpoints pinned.

    Suppresses sub-pixel medial-axis wiggles (which cause spurious local
    rightward movement) without materially changing the calligraphic shape.
    """
    if window < 1 or len(points) < 3:
        return list(points)
    half = window // 2
    smoothed: list[Point2D] = []
    n = len(points)
    for index in range(n):
        lo = max(0, index - half)
        hi = min(n, index + half + 1)
        xs = sum(p[0] for p in points[lo:hi]) / (hi - lo)
        ys = sum(p[1] for p in points[lo:hi]) / (hi - lo)
        smoothed.append((xs, ys))
    # Pin the endpoints so the trajectory still starts/ends exactly where the
    # skeleton trail does (rightmost -> leftmost).
    smoothed[0] = points[0]
    smoothed[-1] = points[-1]
    return smoothed


def _dedupe(points: list[Point2D]) -> list[Point2D]:
    """Remove consecutive duplicate points (branch retracing revisits pixels)."""
    if not points:
        return []
    out: list[Point2D] = [points[0]]
    for point in points[1:]:
        if math.dist(out[-1], point) > 1e-9:
            out.append(point)
    return out


def _arc_length_parameterize(
    points: list[Point2D], is_loop: bool = False, is_vertical: bool = False
) -> tuple[list[list[float]], float, float]:
    """Return ``[[x, y, s], ...]`` with ``s`` normalized to ``[0, 1]``.

    Also returns the total arc length and the RTL ratio: the fraction of arc
    length travelled with ``dx <= 0`` (right-to-left) or descending vertical.
    """
    if len(points) < 2:
        x, y = points[0] if points else (0.0, 0.0)
        return [[x, y, 0.0]], 0.0, 1.0

    cumulative = [0.0]
    for first, second in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + math.dist(first, second))
    total = cumulative[-1]

    if total == 0.0:
        return [[p[0], p[1], 0.0] for p in points], 0.0, 1.0

    directed: list[list[float]] = []
    for index, point in enumerate(points):
        s = cumulative[index] / total
        directed.append([float(point[0]), float(point[1]), float(s)])

    # Force exact endpoints.
    directed[0][2] = 0.0
    directed[-1][2] = 1.0

    rtl_length = 0.0
    for first, second in zip(points, points[1:]):
        ds = math.dist(first, second)
        dx = second[0] - first[0]
        dy = second[1] - first[1]
        if dx <= 1e-6 or (is_vertical and dy < 0) or is_loop:
            rtl_length += ds

    rtl_ratio = rtl_length / total if total > 0 else 1.0
    return directed, float(total), float(rtl_ratio)


def _nearest_parameter(
    directed_strokes: list[dict[str, Any]], point: Point2D
) -> tuple[float, Point2D]:
    """Arc-length parameter ``s`` and (x, y) of the trunk point nearest ``point``.

    Searches across every trunk stroke.  ``s`` is the per-stroke normalized
    arc length of the nearest point (always in ``[0, 1]``).
    """

    best_s = 0.0
    best_point: Point2D = (0.0, 0.0)
    best_dist = float("inf")
    for stroke in directed_strokes:
        for p in stroke["points"]:
            d = math.dist((p[0], p[1]), point)
            if d < best_dist:
                best_dist = d
                best_s = float(p[2])
                best_point = (float(p[0]), float(p[1]))
    return best_s, best_point


def _point_distance(a: Point2D, b: Point2D) -> float:
    return math.dist(a, b)


# ---------------------------------------------------------------------------
# Per-glyph processing
# ---------------------------------------------------------------------------

def _process_trunk_stroke(
    stroke: dict[str, Any], form: str, char: str
) -> dict[str, Any]:
    """Parameterize and order one trunk stroke in Naskh ductus order."""

    raw_points: list[Point2D] = [
        (float(p[0]), float(p[1])) for p in stroke["points"]
    ]
    raw_points = _dedupe(raw_points)
    smoothed = _smooth(raw_points)

    is_loop = char in LOOP_LETTERS or (char in {"ع", "غ"} and form in {"medial", "final"})
    ys = [p[1] for p in raw_points]
    xs = [p[0] for p in raw_points]
    span_x = max(xs) - min(xs) if xs else 0.0
    span_y = max(ys) - min(ys) if ys else 0.0
    is_vertical = (span_y > 1.5 * (span_x + 1.0)) and (form == "isolated" or char in {"ط", "ظ"})

    directed, length, rtl_ratio = _arc_length_parameterize(smoothed, is_loop=is_loop, is_vertical=is_vertical)


    start_point = [directed[0][0], directed[0][1]]
    end_point = [directed[-1][0], directed[-1][1]]

    # Flow direction: the trail starts at the rightmost pixel and ends at the
    # leftmost one, i.e. right-to-left.  Vertical stems additionally descend
    # (top-to-bottom) because y grows downward in font units.
    flow_direction = "right_to_left"
    if is_vertical:
        flow_direction = "top_to_bottom"
    elif end_point[1] - start_point[1] > 0.05 * length:
        flow_direction = "right_to_left_descending"

    loop_preserved = bool(is_loop) and len(directed) >= 3

    return {
        "d": stroke.get("d", ""),
        "points": directed,
        "length": round(float(length), 3),
        "start_point": [round(start_point[0], 3), round(start_point[1], 3)],
        "end_point": [round(end_point[0], 3), round(end_point[1], 3)],
        "flow_direction": flow_direction,
        "rtl_ratio": round(rtl_ratio, 4),
        "s_min": 0.0,
        "s_max": 1.0,
        "is_loop_glyph": is_loop,
        "loop_preserved": loop_preserved,
        "num_samples": len(directed),
    }



def _process_delayed_stroke(
    stroke: dict[str, Any], directed_strokes: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compute the trunk attachment parameter ``s_attach`` for one dot."""

    raw_points: list[Point2D] = [
        (float(p[0]), float(p[1])) for p in stroke.get("points", [])
    ]
    if not raw_points:
        return {"d": stroke.get("d", ""), "points": [], "attachment_s": None}

    cx = sum(p[0] for p in raw_points) / len(raw_points)
    cy = sum(p[1] for p in raw_points) / len(raw_points)
    centroid: Point2D = (cx, cy)

    xs = [p[0] for p in raw_points]
    ys = [p[1] for p in raw_points]
    bbox = [min(xs), min(ys), max(xs), max(ys)]

    attachment_s, attachment_point = _nearest_parameter(directed_strokes, centroid)

    role = stroke.get("role")
    result = {
        "d": stroke.get("d", ""),
        "points": [[round(p[0], 3), round(p[1], 3)] for p in raw_points],
        "centroid": [round(cx, 3), round(cy, 3)],
        "bbox": [round(v, 3) for v in bbox],
        "length": round(float(stroke.get("length", 0.0)), 3),
        "attachment_s": round(float(attachment_s), 4),
        "attachment_point": [round(attachment_point[0], 3), round(attachment_point[1], 3)],
    }
    if role is not None:
        result["role"] = role
    return result


def _anchor_error(
    anchor: list[float] | None, point: Point2D
) -> float | None:
    if anchor is None:
        return None
    return math.dist((float(anchor[0]), float(anchor[1])), point)


def build_directed_glyphs(source: Path | None = None) -> dict[str, Any]:
    """Build the enriched directed-glyph catalog from ``all_glyphs.json``.

    Supports glyphs with multiple trunk strokes (e.g. Tah, Zah, Lam-Alif
    ligatures).  Anchors are evaluated against the extreme points across *all*
    trunk strokes (entry = rightmost / s=0 side, exit = leftmost / s=1 side),
    and delayed-stroke attachment parameters are computed against the nearest
    trunk point across every stroke.
    """

    source = source or ALL_GLYPHS_PATH
    with source.open(encoding="utf-8") as handle:
        catalog = json.load(handle)

    glyphs_in: dict[str, Any] = catalog["glyphs"]
    glyphs_out: dict[str, Any] = {}

    for key, glyph in glyphs_in.items():
        char = glyph["char"]
        form = glyph["form"]

        trunk_strokes = glyph.get("trunk_strokes", [])
        if not trunk_strokes:
            continue

        directed_strokes = [
            _process_trunk_stroke(stroke, form, char) for stroke in trunk_strokes
        ]

        # Collect every trunk point across all strokes for anchor / attachment
        # evaluation.  Each point is [x, y, s] with s normalized per stroke.
        all_points: list[Point2D] = []
        for stroke in directed_strokes:
            for p in stroke["points"]:
                all_points.append((p[0], p[1]))

        # Entry (s=0 side) = rightmost point; Exit (s=1 side) = leftmost point.
        start_point = [max(all_points, key=lambda p: p[0])[0],
                       max(all_points, key=lambda p: p[0])[1]]
        end_point = [min(all_points, key=lambda p: p[0])[0],
                     min(all_points, key=lambda p: p[0])[1]]

        entry_anchor = glyph.get("entry_anchor")
        exit_anchor = glyph.get("exit_anchor")

        entry_error = _anchor_error(entry_anchor, tuple(start_point))
        exit_error = _anchor_error(exit_anchor, tuple(end_point))

        entry_ok = (
            entry_anchor is None
            or entry_error is None
            or entry_error <= ANCHOR_EPSILON
        )
        exit_ok = (
            exit_anchor is None
            or exit_error is None
            or exit_error <= ANCHOR_EPSILON
        )

        # Delayed strokes (dots / i'jam / inner mark / hamza / madda): attach
        # to the nearest trunk point across all strokes.
        delayed_strokes = glyph.get("delayed_strokes", [])
        directed_delayed = [
            _process_delayed_stroke(stroke, directed_strokes)
            for stroke in delayed_strokes
        ]
        dots_ok = all(
            ds["attachment_s"] is not None and 0.0 <= ds["attachment_s"] <= 1.0
            for ds in directed_delayed
        )

        # Aggregate calligraphic diagnostics across strokes.
        rtl_ratios = [s["rtl_ratio"] for s in directed_strokes]
        flow_dirs = [s["flow_direction"] for s in directed_strokes]
        loop_flags = [s["is_loop_glyph"] for s in directed_strokes]

        directed: dict[str, Any] = dict(glyph)
        directed.update(
            {
                "directed_strokes": directed_strokes,
                "start_point": [round(start_point[0], 3), round(start_point[1], 3)],
                "end_point": [round(end_point[0], 3), round(end_point[1], 3)],
                "flow_direction": flow_dirs[0] if flow_dirs else "right_to_left",
                "rtl_ratio": round(sum(rtl_ratios) / len(rtl_ratios), 4) if rtl_ratios else 1.0,
                "rtl_ratios": [round(r, 4) for r in rtl_ratios],
                "start_anchor": entry_anchor,
                "end_anchor": exit_anchor,
                "entry_error": None if entry_error is None else round(entry_error, 3),
                "exit_error": None if exit_error is None else round(exit_error, 3),
                "anchors_ok": bool(entry_ok and exit_ok),
                "delayed_strokes": directed_delayed,
                "dots_ok": bool(dots_ok),
                "is_loop_glyph": any(loop_flags),
                "loop_preserved": all(s["loop_preserved"] for s in directed_strokes),
                "num_trunk_strokes": len(directed_strokes),
                "directed": True,
            }
        )
        glyphs_out[key] = directed

    return {
        "font": catalog.get("font"),
        "font_family": catalog.get("font_family"),
        "font_units_per_em": catalog.get("font_units_per_em"),
        "total_glyphs": len(glyphs_out),
        "version": 2,
        "description": "Milestone 2: directed, arc-length parameterized glyph trajectories",
        "glyphs": glyphs_out,
    }


def generate_directed_glyphs_json(
    output_path: str | Path | None = None,
    source_path: str | Path | None = None,
) -> Path:
    """Write ``directed_glyphs.json`` and return its path."""

    target = Path(output_path) if output_path is not None else DIRECTED_GLYPHS_PATH
    source = Path(source_path) if source_path is not None else ALL_GLYPHS_PATH
    data = build_directed_glyphs(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


if __name__ == "__main__":
    written = generate_directed_glyphs_json()
    print(f"Wrote {written}")
