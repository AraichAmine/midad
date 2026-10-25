"""MILESTONE 6: Font Packaging Pipeline.

Packages welded words and directed glyph fixtures into optimized, production-ready
JSON distribution files with:
- Ramer-Douglas-Peucker spline simplification (tolerance 0.8 on 1000-unit em square)
- Compact coordinate precision (1 decimal place)
- Conversion of delayed stroke point arrays to compact SVG path strings
- Elimination of redundant duplicate timeline structures
- Stripping of debugging metadata

Target:
- Production font JSON < 95 KB gzipped.
- Production glyphs catalog < 45 KB gzipped.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import re
from typing import Any

from shapely.geometry import LineString

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_WORDS_PATH = FIXTURES_DIR / "golden" / "welded_50_words.json"
PACKAGED_FONT_PATH = FIXTURES_DIR / "fonts" / "midad_naskh_50.json"
DIST_FONT_PATH = REPO_ROOT / "engine" / "dist" / "fonts" / "noto_naskh_50.json"

DIRECTED_GLYPHS_PATH = FIXTURES_DIR / "skeletons" / "directed_glyphs.json"
PACKAGED_GLYPHS_PATH = FIXTURES_DIR / "fonts" / "midad_naskh_glyphs.json"
DIST_GLYPHS_PATH = REPO_ROOT / "engine" / "dist" / "fonts" / "noto_naskh_glyphs.json"


def compact_number(val: float, precision: int = 1) -> float | int:
    """Round a float to precision places, returning int if whole."""
    rounded = round(float(val), precision)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def parse_svg_path_points(d: str) -> list[list[float]]:
    """Parse a sequence of points from an SVG path string."""
    tokens = re.findall(r"[-+]?\d*\.?\d+", d)
    pts: list[list[float]] = []
    for i in range(0, len(tokens) - 1, 2):
        pts.append([float(tokens[i]), float(tokens[i + 1])])
    return pts


def simplify_points(
    points: list[list[float]],
    tolerance: float = 0.8,
    precision: int = 1,
) -> list[list[float | int]]:
    """Simplify point sequence via RDP and round coordinates."""
    if not points:
        return []
    if len(points) >= 3 and tolerance > 0.0:
        try:
            ls = LineString(points).simplify(tolerance, preserve_topology=False)
            simp = list(ls.coords)
        except Exception:
            simp = points
    else:
        simp = points
    return [[compact_number(pt[0], precision), compact_number(pt[1], precision)] for pt in simp]


def simplify_and_format_path(
    points: list[list[float]],
    tolerance: float = 0.8,
    precision: int = 1,
) -> tuple[str, float]:
    """Simplify points via Ramer-Douglas-Peucker and format as SVG path data."""
    if not points:
        return "", 0.0

    simp_pts = simplify_points(points, tolerance=tolerance, precision=precision)

    # Compute length
    length = 0.0
    for i in range(1, len(simp_pts)):
        dx = float(simp_pts[i][0]) - float(simp_pts[i - 1][0])
        dy = float(simp_pts[i][1]) - float(simp_pts[i - 1][1])
        length += (dx * dx + dy * dy) ** 0.5

    # Format path string
    parts: list[str] = []
    first = simp_pts[0]
    parts.append(f"M {first[0]} {first[1]}")
    for pt in simp_pts[1:]:
        parts.append(f"L {pt[0]} {pt[1]}")

    return " ".join(parts), round(length, 1)


def package_font_data(
    source_data: dict[str, Any],
    tolerance: float = 0.8,
    precision: int = 1,
) -> dict[str, Any]:
    """Transform raw font fixture data into compact production format."""
    words = source_data.get("words", [])
    packaged_words: list[dict[str, Any]] = []

    for w in words:
        paws_out: list[dict[str, Any]] = []
        for p in w.get("paws", []):
            trunk_stroke = p.get("trunkStroke", {})
            trunk_d = trunk_stroke.get("d", "")
            raw_trunk_pts = parse_svg_path_points(trunk_d)

            simp_d, simp_len = simplify_and_format_path(
                raw_trunk_pts, tolerance=tolerance, precision=precision
            )

            compact_trunk = {
                "id": trunk_stroke.get("id", f"{p.get('id', 'paw')}_trunk"),
                "d": simp_d,
                "length": compact_number(simp_len, 1),
                "type": trunk_stroke.get("type", "trunk"),
            }

            delayed_out: list[dict[str, Any]] = []
            for idx, ds in enumerate(p.get("delayedStrokes", [])):
                pts = ds.get("points")
                if not pts and "d" in ds and ds["d"]:
                    pts = parse_svg_path_points(ds["d"])
                pts = pts or []

                del_d, del_len = simplify_and_format_path(
                    pts, tolerance=tolerance, precision=precision
                )

                delayed_entry: dict[str, Any] = {
                    "id": ds.get("id", f"{p.get('id', 'paw')}_delayed_{idx}"),
                    "role": ds.get("role", "dot"),
                    "attachment_s": compact_number(ds.get("attachment_s", 0.5), 3),
                    "d": del_d,
                    "length": compact_number(del_len, 1),
                }
                delayed_out.append(delayed_entry)

            paws_out.append(
                {
                    "id": p.get("id", "paw"),
                    "letters": p.get("letters", ""),
                    "trunkStroke": compact_trunk,
                    "delayedStrokes": delayed_out,
                }
            )

        packaged_words.append(
            {
                "text": w["text"],
                "paws": paws_out,
            }
        )

    return {
        "font": source_data.get("font", "NotoNaskhArabic-Regular"),
        "total_glyphs": source_data.get("total_glyphs", 119),
        "num_words": len(packaged_words),
        "words": packaged_words,
    }


def package_glyphs_catalog(
    catalog: dict[str, Any],
    tolerance: float = 0.8,
    precision: int = 1,
) -> dict[str, Any]:
    """Package 119 directed glyph skeletons into compact runtime catalog."""
    packaged: dict[str, Any] = {}

    glyphs = catalog.get("glyphs", catalog) if isinstance(catalog, dict) else {}
    for key, glyph in glyphs.items():
        trunk_strokes_out: list[dict[str, Any]] = []
        for s in glyph.get("trunk_strokes", []):
            pts = simplify_points(s.get("points", []), tolerance=tolerance, precision=precision)
            trunk_strokes_out.append(
                {
                    "points": pts,
                    "length": compact_number(s.get("length", 100.0), 1),
                }
            )

        delayed_strokes_out: list[dict[str, Any]] = []
        for ds in glyph.get("delayed_strokes", []):
            pts = simplify_points(ds.get("points", []), tolerance=tolerance, precision=precision)
            delayed_strokes_out.append(
                {
                    "role": ds.get("role", "dot"),
                    "points": pts,
                    "length": compact_number(ds.get("length", 50.0), 1),
                    "attachment_s": compact_number(ds.get("attachment_s", 0.5), 3),
                }
            )

        anchors = glyph.get("anchors", {})
        anchors_out = {}
        for akey, apt in anchors.items():
            if apt is not None:
                anchors_out[akey] = [
                    compact_number(apt[0], precision),
                    compact_number(apt[1], precision),
                ]

        packaged[key] = {
            "char": glyph.get("char", ""),
            "form": glyph.get("form", ""),
            "trunk_strokes": trunk_strokes_out,
            "delayed_strokes": delayed_strokes_out,
            "anchors": anchors_out,
        }

    return packaged


def export_packaged_font(
    source_path: Path = GOLDEN_WORDS_PATH,
    output_path: Path = PACKAGED_FONT_PATH,
    tolerance: float = 0.8,
    precision: int = 1,
) -> tuple[Path, int, int]:
    """Package font JSON and return (output_path, raw_bytes, gzip_bytes)."""
    with source_path.open("r", encoding="utf-8") as f:
        source_data = json.load(f)

    packaged = package_font_data(source_data, tolerance=tolerance, precision=precision)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_json = json.dumps(packaged, separators=(",", ":"), ensure_ascii=False)
    raw_bytes = len(raw_json.encode("utf-8"))

    with output_path.open("w", encoding="utf-8") as f:
        f.write(raw_json)

    gz_bytes = len(gzip.compress(raw_json.encode("utf-8")))

    # Also copy to engine/dist/fonts
    DIST_FONT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DIST_FONT_PATH.open("w", encoding="utf-8") as f:
        f.write(raw_json)

    return output_path, raw_bytes, gz_bytes


def export_packaged_glyphs(
    source_path: Path = DIRECTED_GLYPHS_PATH,
    output_path: Path = PACKAGED_GLYPHS_PATH,
    tolerance: float = 0.8,
    precision: int = 1,
) -> tuple[Path, int, int]:
    """Package directed glyphs JSON and return (output_path, raw_bytes, gzip_bytes)."""
    with source_path.open("r", encoding="utf-8") as f:
        source_data = json.load(f)

    packaged = package_glyphs_catalog(source_data, tolerance=tolerance, precision=precision)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_json = json.dumps(packaged, separators=(",", ":"), ensure_ascii=False)
    raw_bytes = len(raw_json.encode("utf-8"))

    with output_path.open("w", encoding="utf-8") as f:
        f.write(raw_json)

    gz_bytes = len(gzip.compress(raw_json.encode("utf-8")))

    # Also copy to engine/dist/fonts
    DIST_GLYPHS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DIST_GLYPHS_PATH.open("w", encoding="utf-8") as f:
        f.write(raw_json)

    return output_path, raw_bytes, gz_bytes


if __name__ == "__main__":
    out_path, raw_sz, gz_sz = export_packaged_font(tolerance=0.8, precision=1)
    print(f"Packaged words font written to: {out_path}")
    print(f"  Raw: {raw_sz / 1024:.2f} KB, Gzip: {gz_sz / 1024:.2f} KB")

    gout_path, graw_sz, ggz_sz = export_packaged_glyphs(tolerance=0.8, precision=1)
    print(f"Packaged glyphs catalog written to: {gout_path}")
    print(f"  Raw: {graw_sz / 1024:.2f} KB, Gzip: {ggz_sz / 1024:.2f} KB")
