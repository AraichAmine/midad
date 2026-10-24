"""HarfBuzz shaping and glyph-outline extraction utilities.

The extractor is deliberately small: it wraps ``uharfbuzz`` for text shaping
and ``fontTools`` for outline extraction, returning plain Python data that the
skeletonizer and JSON exporter can consume without depending on font objects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import uharfbuzz as hb
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon

Point = tuple[float, float]


# ---------------------------------------------------------------------------
# Shaping
# ---------------------------------------------------------------------------


def shape_text(
    text: str,
    font_path: str | Path,
    direction: str = "rtl",
    script: str = "Arab",
    language: str = "ara",
) -> list[dict[str, Any]]:
    """Shape ``text`` into a list of positioned glyph records.

    Parameters mirror the HarfBuzz concepts of direction, script and language.
    The returned glyphs are in HarfBuzz's output order (visual order for RTL
    text).  Each record contains the required fields ``glyph_id``, ``cluster``,
    ``x_advance``, ``y_advance``, ``x_offset`` and ``y_offset`` plus the glyph
    name for convenience.
    """

    if not text:
        return []

    font_path = Path(font_path)
    if not font_path.is_file():
        raise FileNotFoundError(f"font not found: {font_path}")

    blob = hb.Blob.from_file_path(str(font_path))
    face = hb.Face(blob)
    font = hb.Font(face)

    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.direction = direction
    buffer.script = script
    buffer.language = language
    hb.shape(font, buffer)

    # Read the glyph names once from the font's post/cmap tables.
    tt_font = TTFont(str(font_path), lazy=True)
    glyph_order = tt_font.getGlyphOrder()

    records: list[dict[str, Any]] = []
    for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
        glyph_id = int(info.codepoint)
        glyph_name = (
            glyph_order[glyph_id]
            if 0 <= glyph_id < len(glyph_order)
            else f"gid{glyph_id}"
        )
        records.append(
            {
                "glyph_id": glyph_id,
                "glyph_name": glyph_name,
                "cluster": int(info.cluster),
                "x_advance": float(position.x_advance),
                "y_advance": float(position.y_advance),
                "x_offset": float(position.x_offset),
                "y_offset": float(position.y_offset),
            }
        )
    tt_font.close()
    return records


# ---------------------------------------------------------------------------
# Outlines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Contour:
    """A single flattened outline contour in font units.

    The points are ordered as the font stores them.  ``polygon`` exposes a
    Shapely view for area/containment checks, while ``path_d`` provides a
    simple SVG path for debugging.
    """

    points: tuple[Point, ...]
    closed: bool = True

    @property
    def area(self) -> float:
        """Signed shoelace area in square font units."""
        if len(self.points) < 3:
            return 0.0
        total = 0.0
        for (x1, y1), (x2, y2) in zip(self.points, self.points[1:] + self.points[:1]):
            total += x1 * y2 - x2 * y1
        return total / 2.0

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def polygon(self) -> Polygon:
        polygon = Polygon(self.points)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        return polygon

    @property
    def path_d(self) -> str:
        if not self.points:
            return ""
        head = f"M {self.points[0][0]:.3f} {self.points[0][1]:.3f}"
        tail = " ".join(f"L {x:.3f} {y:.3f}" for x, y in self.points[1:])
        return f"{head} {tail} Z"

    def translated(self, dx: float, dy: float) -> "Contour":
        return Contour(
            tuple((x + dx, y + dy) for x, y in self.points),
            closed=self.closed,
        )

    def to_list(self) -> list[list[float]]:
        return [[round(x, 3), round(y, 3)] for x, y in self.points]


def _sample_quadratic(
    out: list[Point], start: Point, control: Point, end: Point, steps: int = 10
) -> None:
    for index in range(1, steps + 1):
        t = index / steps
        one_minus_t = 1.0 - t
        out.append(
            (
                one_minus_t * one_minus_t * start[0]
                + 2.0 * one_minus_t * t * control[0]
                + t * t * end[0],
                one_minus_t * one_minus_t * start[1]
                + 2.0 * one_minus_t * t * control[1]
                + t * t * end[1],
            )
        )


def _sample_cubic(
    out: list[Point],
    start: Point,
    control1: Point,
    control2: Point,
    end: Point,
    steps: int = 14,
) -> None:
    for index in range(1, steps + 1):
        t = index / steps
        one_minus_t = 1.0 - t
        out.append(
            (
                one_minus_t**3 * start[0]
                + 3.0 * one_minus_t**2 * t * control1[0]
                + 3.0 * one_minus_t * t**2 * control2[0]
                + t**3 * end[0],
                one_minus_t**3 * start[1]
                + 3.0 * one_minus_t**2 * t * control1[1]
                + 3.0 * one_minus_t * t**2 * control2[1]
                + t**3 * end[1],
            )
        )


def _recordings_to_contours(recording: Iterable[tuple[str, tuple[Any, ...]]]) -> list[Contour]:
    """Flatten a fontTools recording into closed polylines."""

    contours: list[Contour] = []
    current: list[Point] | None = None

    def finish(closed: bool) -> None:
        nonlocal current
        if current and len(current) >= 3:
            # Remove duplicated closing point.
            if len(current) > 1 and current[0] == current[-1]:
                current.pop()
            contours.append(Contour(tuple(current), closed=closed))
        current = None

    for operation, arguments in recording:
        if operation == "moveTo":
            finish(closed=False)
            current = [tuple(arguments[0])]
        elif operation == "lineTo":
            if current is None:
                current = [tuple(arguments[0])]
            else:
                current.append(tuple(arguments[0]))
        elif operation == "qCurveTo":
            if current is None:
                current = []
            points = list(arguments)
            # fontTools passes None for an all-off-curve TrueType contour.
            if points and points[-1] is None:
                points = points[:-1]
                if points:
                    implied = (
                        (points[-1][0] + points[0][0]) / 2.0,
                        (points[-1][1] + points[0][1]) / 2.0,
                    )
                    current = [implied]
                    points.append(implied)
            if not current:
                continue
            end = tuple(points[-1])
            controls = [tuple(point) for point in points[:-1]]
            previous = current[-1]
            for index, control in enumerate(controls):
                if index < len(controls) - 1:
                    following = controls[index + 1]
                    implied_end = (
                        (control[0] + following[0]) / 2.0,
                        (control[1] + following[1]) / 2.0,
                    )
                else:
                    implied_end = end
                _sample_quadratic(current, previous, control, implied_end)
                previous = implied_end
        elif operation == "curveTo":
            if not current:
                current = []
            end = tuple(arguments[-1])
            _sample_cubic(current, current[-1], tuple(arguments[0]), tuple(arguments[1]), end)
        elif operation == "closePath":
            finish(closed=True)
        elif operation == "endPath":
            finish(closed=False)
        elif operation == "addComponent":
            # DecomposingRecordingPen should have already expanded components.
            continue

    finish(closed=False)
    return contours


def extract_glyph_contours(
    font_path: str | Path, glyph_id_or_name: str | int
) -> list[Contour]:
    """Extract flattened contours for a glyph.

    ``glyph_id_or_name`` accepts a glyph id, a glyph name, a single character
    (looked up through the font's cmap), or a string like ``"0x0628"``.
    Curves are flattened into polygons; each returned :class:`Contour` is a
    closed polygon in font units.
    """

    font_path = Path(font_path)
    if not font_path.is_file():
        raise FileNotFoundError(f"font not found: {font_path}")

    tt_font = TTFont(str(font_path))
    try:
        glyph_set = tt_font.getGlyphSet()
        glyph_name = _resolve_glyph_name(tt_font, glyph_id_or_name)
        if glyph_name not in glyph_set:
            raise KeyError(f"glyph {glyph_name!r} not found in {font_path}")

        recording_pen = DecomposingRecordingPen(glyph_set)
        glyph_set[glyph_name].draw(recording_pen)
        return _recordings_to_contours(recording_pen.value)
    finally:
        tt_font.close()


def _resolve_glyph_name(tt_font: TTFont, glyph_id_or_name: str | int) -> str:
    if isinstance(glyph_id_or_name, int):
        return tt_font.getGlyphName(glyph_id_or_name)

    value = str(glyph_id_or_name)
    if value.lower().startswith("0x"):
        code_point = int(value, 16)
        cmap = tt_font.getBestCmap() or {}
        name = cmap.get(code_point)
        if name is not None:
            return name
        return tt_font.getGlyphName(code_point)
    if value.isdigit():
        # A bare number is treated as a glyph id for convenience.
        return tt_font.getGlyphName(int(value))
    if len(value) == 1:
        cmap = tt_font.getBestCmap() or {}
        name = cmap.get(ord(value))
        if name is not None:
            return name
    return value


# ---------------------------------------------------------------------------
# Shaped text -> positioned contours
# ---------------------------------------------------------------------------


def extract_text_contours(
    font_path: str | Path,
    text: str,
    cluster: int | None = None,
    *,
    direction: str = "rtl",
    script: str = "Arab",
    language: str = "ara",
) -> list[Contour]:
    """Extract positioned outlines for shaped text.

    Glyph advances and offsets are applied, so merged contours from a whole
    word share one coordinate space.  When ``cluster`` is given only glyphs
    belonging to that input cluster are kept (useful for isolated/initial/
    medial/final forms built with tatweel context).
    """

    glyphs = shape_text(text, font_path, direction, script, language)
    contours: list[Contour] = []
    pen_x = 0.0
    for glyph in glyphs:
        if cluster is None or glyph["cluster"] == cluster:
            dx = pen_x + glyph["x_offset"]
            dy = glyph["y_offset"]
            for contour in extract_glyph_contours(font_path, glyph["glyph_id"]):
                contours.append(contour.translated(dx, dy))
        pen_x += glyph["x_advance"]
    return contours


_FORM_CONTEXT = {
    "isolated": "{char}",
    "initial": "{char}\u0640",
    "medial": "\u0640{char}\u0640",
    "final": "\u0640{char}",
}


def shape_letter_form(
    font_path: str | Path, char: str, form: str
) -> dict[str, Any]:
    """Return the shaped glyphs for one positional form of a single letter.

    Tatweel is used as a joining context so HarfBuzz selects the real
    initial/medial/final glyph instead of a synthetic presentation form.
    """

    if form not in _FORM_CONTEXT:
        raise ValueError(f"unknown form {form!r}")
    if len(char) != 1:
        raise ValueError("shape_letter_form expects a single character")

    text = _FORM_CONTEXT[form].format(char=char)
    cluster = text.index(char)
    glyphs = shape_text(text, font_path)
    target = [glyph for glyph in glyphs if glyph["cluster"] == cluster]
    if not target:
        raise ValueError(f"no glyphs shaped for {char!r} / {form}")
    return {
        "char": char,
        "form": form,
        "text": text,
        "cluster": cluster,
        "glyphs": target,
        "all_glyphs": glyphs,
    }


def contours_for_letter_form(
    font_path: str | Path, char: str, form: str
) -> list[Contour]:
    """Shaped, positioned contours for a letter form (tatweel context filtered)."""

    shaped = shape_letter_form(font_path, char, form)
    return extract_text_contours(
        font_path, shaped["text"], cluster=shaped["cluster"]
    )


def contour_polygons(contours: Sequence[Contour]) -> list[Polygon]:
    """Convert contours to valid Shapely polygons."""

    polygons: list[Polygon] = []
    for contour in contours:
        polygon = contour.polygon
        if not polygon.is_empty and polygon.area > 0:
            polygons.append(polygon)
    return polygons


def font_units_per_em(font_path: str | Path) -> int:
    tt_font = TTFont(str(font_path), lazy=True)
    try:
        return int(tt_font["head"].unitsPerEm)
    finally:
        tt_font.close()


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
