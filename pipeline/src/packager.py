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


def simplify_and_format_path(
    points: list[list[float]],
    tolerance: float = 0.8,
    precision: int = 1,
) -> tuple[str, float]:
    """Simplify points via Ramer-Douglas-Peucker and format as SVG path data."""
    if not points:
        return "", 0.0

    if len(points) >= 3 and tolerance > 0.0:
        try:
            ls = LineString(points).simplify(tolerance, preserve_topology=False)
            simp_pts = list(ls.coords)
        except Exception:
            simp_pts = points
    else:
        simp_pts = points

    # Compute length
    length = 0.0
    for i in range(1, len(simp_pts)):
        dx = simp_pts[i][0] - simp_pts[i - 1][0]
        dy = simp_pts[i][1] - simp_pts[i - 1][1]
        length += (dx * dx + dy * dy) ** 0.5

    # Format path string
    parts: list[str] = []
    first = simp_pts[0]
    parts.append(f"M {compact_number(first[0], precision)} {compact_number(first[1], precision)}")
    for pt in simp_pts[1:]:
        parts.append(f"L {compact_number(pt[0], precision)} {compact_number(pt[1], precision)}")

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


if __name__ == "__main__":
    out_path, raw_sz, gz_sz = export_packaged_font(tolerance=0.8, precision=1)
    print(f"Packaged font written to: {out_path}")
    print(f"Raw size:  {raw_sz / 1024:.2f} KB ({raw_sz} bytes)")
    print(f"Gzip size: {gz_sz / 1024:.2f} KB ({gz_sz} bytes)")
    assert gz_sz < 95 * 1024, f"Font package exceeds 95 KB gzipped: {gz_sz} bytes"
    print("Verification PASSED: Font package is strictly < 95 KB gzipped!")
