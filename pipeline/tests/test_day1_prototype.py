"""DAY-1 TASK B verification suite: shaping, skeletons and prototype export.

Run with::

    pipeline/.venv/bin/pytest -v pipeline/tests/test_day1_prototype.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon, shape

# Make ``pipeline/src`` importable without installing the project.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import extractor  # noqa: E402
import rules  # noqa: E402
import skeletonizer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "fixtures" / "fonts"
NOTO_FONT = FONT_DIR / "NotoNaskhArabic-Regular.ttf"
PROTOTYPE_PATH = REPO_ROOT / "fixtures" / "skeletons" / "prototype_5.json"

SAMPLES = ("ابجدر", "بجب", "برد", "جبر")

EXPECTED_FORMS = {
    "ا": ("isolated", "final"),
    "ب": ("isolated", "initial", "medial", "final"),
    "ج": ("isolated", "initial", "medial", "final"),
    "د": ("isolated", "final"),
    "ر": ("isolated", "final"),
}

REQUIRED_SHAPE_FIELDS = {
    "glyph_id",
    "cluster",
    "x_advance",
    "y_advance",
    "x_offset",
    "y_offset",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prototype() -> dict:
    assert PROTOTYPE_PATH.is_file(), f"missing prototype fixture: {PROTOTYPE_PATH}"
    with PROTOTYPE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def font_path() -> Path:
    assert NOTO_FONT.is_file(), f"missing font: {NOTO_FONT}"
    return NOTO_FONT


# ---------------------------------------------------------------------------
# HarfBuzz shaping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sample", SAMPLES)
def test_shape_text_returns_valid_glyph_sequence(sample, font_path):
    glyphs = extractor.shape_text(sample, font_path)
    assert isinstance(glyphs, list)
    assert len(glyphs) >= len(sample)

    for glyph in glyphs:
        assert REQUIRED_SHAPE_FIELDS <= set(glyph)
        assert isinstance(glyph["glyph_id"], int)
        assert glyph["glyph_id"] >= 0
        assert isinstance(glyph["cluster"], int)
        assert 0 <= glyph["cluster"] < len(sample)
        assert isinstance(glyph["x_advance"], float)
        assert isinstance(glyph["y_advance"], float)
        assert isinstance(glyph["x_offset"], float)
        assert isinstance(glyph["y_offset"], float)
        assert glyph["x_advance"] >= 0.0
        assert glyph["y_advance"] == 0.0

    # Arabic shaping must produce at least one advance-bearing glyph.
    assert sum(glyph["x_advance"] for glyph in glyphs) > 0.0


@pytest.mark.parametrize("sample", SAMPLES)
def test_shape_text_clusters_cover_input_right_to_left(sample, font_path):
    glyphs = extractor.shape_text(sample, font_path)
    clusters = [glyph["cluster"] for glyph in glyphs]
    assert set(clusters) == set(range(len(sample)))
    # HarfBuzz emits RTL output in visual right-to-left order, so clusters
    # are non-increasing.
    assert clusters == sorted(clusters, reverse=True)
    # At least minimal ligature/context behaviour: no empty output.
    assert all(isinstance(glyph["glyph_name"], str) for glyph in glyphs)


def test_shape_text_is_context_sensitive(font_path):
    isolated = extractor.shape_text("ب", font_path)
    word = extractor.shape_text("بب", font_path)
    assert isolated
    assert word
    assert [glyph["glyph_id"] for glyph in isolated] != [
        glyph["glyph_id"] for glyph in word
    ]

    # Joining forms are selected through tatweel context.
    initial = extractor.shape_letter_form(font_path, "ب", "initial")
    medial = extractor.shape_letter_form(font_path, "ب", "medial")
    final = extractor.shape_letter_form(font_path, "ب", "final")

    def trunk_name(shaped):
        # Dot glyphs have zero advance; pick the advance-bearing trunk glyph.
        return max(shaped["glyphs"], key=lambda glyph: glyph["x_advance"])["glyph_name"]

    isolated_trunk = max(isolated, key=lambda glyph: glyph["x_advance"])["glyph_name"]
    isolated_name = isolated_trunk
    initial_name = trunk_name(initial)
    medial_name = trunk_name(medial)
    final_name = trunk_name(final)
    assert len({isolated_name, initial_name, medial_name, final_name}) >= 3


def test_shape_text_direction_override_and_empty_input(font_path):
    glyphs = extractor.shape_text("بجب", font_path, direction="rtl", script="Arab", language="ara")
    assert glyphs
    assert extractor.shape_text("", font_path) == []


def test_shape_text_rejects_missing_font(tmp_path):
    with pytest.raises(FileNotFoundError):
        extractor.shape_text("ب", tmp_path / "missing.ttf")


# ---------------------------------------------------------------------------
# Contour extraction
# ---------------------------------------------------------------------------


def test_extract_glyph_contours_returns_closed_polygons(font_path):
    glyphs = extractor.shape_text("ب", font_path)
    trunk_glyph = next(
        glyph for glyph in glyphs if glyph["glyph_name"] == "uni066E"
    )
    contours = extractor.extract_glyph_contours(font_path, trunk_glyph["glyph_id"])
    assert contours
    assert all(isinstance(contour, extractor.Contour) for contour in contours)
    assert all(len(contour.points) >= 3 for contour in contours)
    for contour in contours:
        assert contour.area != 0
        assert contour.polygon.is_valid
        assert contour.polygon.area > 0
        assert contour.path_d.startswith("M ")
        assert contour.path_d.endswith("Z")


def test_extract_glyph_contours_accepts_name_id_char_and_hex(font_path):
    by_name = extractor.extract_glyph_contours(font_path, "uni066E")
    by_id = extractor.extract_glyph_contours(font_path, 14)
    by_char = extractor.extract_glyph_contours(font_path, "ب")
    by_hex = extractor.extract_glyph_contours(font_path, "0x0628")
    assert by_name and by_id and by_char and by_hex
    assert len(by_name) == len(by_id)
    assert len(by_char) == len(by_hex)


def test_contours_for_letter_form_are_positioned(font_path):
    for char in "ابجدر":
        for form in EXPECTED_FORMS[char]:
            contours = extractor.contours_for_letter_form(font_path, char, form)
            assert contours, f"no contours for {char!r}/{form}"
            polygons = extractor.contour_polygons(contours)
            assert polygons
            assert max(polygon.area for polygon in polygons) > 0


# ---------------------------------------------------------------------------
# Trunk / dot separation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("char", ["ب", "ج"])
@pytest.mark.parametrize("form", ["isolated", "initial", "medial", "final"])
def test_separate_trunk_and_dots_on_beh_and_jeem(char, form, font_path):
    rule = rules.ARABIC_CHARACTER_RULES[char]
    contours = extractor.contours_for_letter_form(font_path, char, form)
    partition = skeletonizer.separate_trunk_and_dots(
        contours, rule["dot_count"], rule["dot_placement"]
    )

    assert len(partition["trunk_contours"]) >= 1
    assert len(partition["trunk_polygons"]) >= 1
    assert len(partition["dot_contours"]) == rule["dot_count"]
    assert len(partition["dot_polygons"]) == rule["dot_count"]
    assert partition["actual_dot_count"] == rule["dot_count"]
    assert partition["expected_dot_count"] == rule["dot_count"]

    trunk_area = partition["trunk_polygon"].area
    assert trunk_area > 0
    for dot in partition["dot_polygons"]:
        assert dot.area < trunk_area
        # ب and ج dots are below the baseline / trunk centroid.
        assert dot.centroid.y < 0 or dot.centroid.y < partition["trunk_polygon"].centroid.y


def test_separate_trunk_and_dots_validates_placement(font_path):
    contours = extractor.contours_for_letter_form(font_path, "ب", "isolated")
    with pytest.raises(ValueError):
        skeletonizer.separate_trunk_and_dots(contours, 1, "above")


def test_zero_expected_dots_keeps_every_contour_as_trunk(font_path):
    contours = extractor.contours_for_letter_form(font_path, "ب", "isolated")
    partition = skeletonizer.separate_trunk_and_dots(contours, 0, "none")
    assert len(partition["dot_contours"]) == 0
    assert len(partition["trunk_contours"]) == len(contours)
    assert partition["actual_dot_count"] == 0


# ---------------------------------------------------------------------------
# Skeleton, anchors and IoU
# ---------------------------------------------------------------------------


def test_extract_centerline_is_a_single_continuous_path(font_path):
    contour = extractor.contours_for_letter_form(font_path, "ب", "isolated")
    trunk = skeletonizer.separate_trunk_and_dots(contour, 1, "below")["trunk_polygon"]
    skeleton = skeletonizer.extract_centerline(trunk, num_samples=100)

    assert skeleton["num_samples"] == 100
    assert len(skeleton["points"]) == 100
    assert len(skeleton["widths"]) == 100
    assert all(width > 0 for width in skeleton["widths"])
    assert skeleton["path_d"].startswith("M ")
    assert skeleton["path_d"].count("M") == 1
    assert skeleton["path_d"].count("C") == 99
    assert len(skeleton["segments"]) == 99
    assert skeleton["length"] > 0
    assert skeleton["ordered"] == "right_to_left"

    # The trail starts at the right extremity and ends at the left extremity.
    assert skeleton["points"][0][0] == max(point[0] for point in skeleton["points"])
    assert skeleton["points"][-1][0] == min(point[0] for point in skeleton["points"])


@pytest.mark.parametrize(
    "form,has_entry,has_exit",
    [
        ("isolated", False, False),
        ("initial", False, True),
        ("medial", True, True),
        ("final", True, False),
    ],
)
def test_compute_anchors_respects_joining_form(form, has_entry, has_exit, font_path):
    contour = extractor.contours_for_letter_form(font_path, "ب", form)
    partition = skeletonizer.separate_trunk_and_dots(contour, 1, "below")
    skeleton = skeletonizer.extract_centerline(partition["trunk_polygon"])
    anchors = skeletonizer.compute_anchors(skeleton, form)

    assert anchors["entry"] is not None if has_entry else anchors["entry"] is None
    assert anchors["exit"] is not None if has_exit else anchors["exit"] is None
    if anchors["entry"] is not None:
        assert len(anchors["entry"]) == 2
        assert anchors["entry"][0] == pytest.approx(
            max(point[0] for point in skeleton["points"]), abs=1e-3
        )
    if anchors["exit"] is not None:
        assert len(anchors["exit"]) == 2
        assert anchors["exit"][0] == pytest.approx(
            min(point[0] for point in skeleton["points"]), abs=1e-3
        )


def test_compute_dilation_iou_exceeds_threshold(font_path):
    contour = extractor.contours_for_letter_form(font_path, "ب", "isolated")
    trunk = skeletonizer.separate_trunk_and_dots(contour, 1, "below")["trunk_polygon"]
    skeleton = skeletonizer.extract_centerline(trunk)
    iou = skeletonizer.compute_dilation_iou(trunk, skeleton)
    assert 0.80 <= iou <= 1.0

    # A pure polyline without widths also gets calibrated by the function.
    polyline_iou = skeletonizer.compute_dilation_iou(trunk, skeleton["points"])
    assert 0.0 < polyline_iou <= 1.0

    # An explicit constant stroke width is supported too.
    constant_iou = skeletonizer.compute_dilation_iou(
        trunk, skeleton, stroke_width=skeleton["stroke_width"]
    )
    assert 0.0 < constant_iou <= 1.0


# ---------------------------------------------------------------------------
# Prototype fixture
# ---------------------------------------------------------------------------


def test_prototype_fixture_exists_and_is_valid_json():
    assert PROTOTYPE_PATH.is_file()
    raw = PROTOTYPE_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, dict)
    assert data["num_instances"] == 14
    assert len(data["glyphs"]) == 14
    # Arabic text must remain human-readable UTF-8, not \u escapes.
    assert "ا" in raw and "ب" in raw


def test_prototype_contains_every_letter_and_form(prototype):
    assert set(prototype["letters"]) == set(EXPECTED_FORMS)
    counts: dict[str, int] = {}
    seen = set()
    for glyph in prototype["glyphs"]:
        counts[glyph["char"]] = counts.get(glyph["char"], 0) + 1
        key = (glyph["char"], glyph["form"])
        assert key not in seen
        seen.add(key)
        assert glyph["form"] in EXPECTED_FORMS[glyph["char"]]

    assert counts == {char: len(forms) for char, forms in EXPECTED_FORMS.items()}
    assert sum(counts.values()) == 14
    assert seen == {
        (char, form) for char, forms in EXPECTED_FORMS.items() for form in forms
    }


def test_prototype_instances_have_expected_metadata(prototype):
    assert prototype["font"] == "fixtures/fonts/NotoNaskhArabic-Regular.ttf"
    assert prototype["font_units_per_em"] == 1000

    for glyph in prototype["glyphs"]:
        char = glyph["char"]
        form = glyph["form"]
        expected_dots = {"ب": 1, "ج": 1}.get(char, 0)
        expected_placement = {"ب": "below", "ج": "below"}.get(char, "none")
        assert glyph["expected_dot_count"] == expected_dots
        assert glyph["dot_count"] == expected_dots
        assert glyph["dot_placement"] == expected_placement
        assert glyph["glyph_ids"]
        assert glyph["glyph_names"]
        assert glyph["trunk_contours"]
        assert len(glyph["dot_contours"]) == expected_dots

        trunk = shape(glyph["trunk_polygon"])
        assert isinstance(trunk, Polygon)
        assert trunk.is_valid
        assert trunk.area > 0
        for dot_points in glyph["dot_contours"]:
            dot = Polygon(dot_points)
            assert dot.is_valid
            assert dot.area < trunk.area

        # Anchors are present exactly when the joining form requires them.
        anchors = glyph["anchors"]
        if form == "isolated":
            assert anchors == {"entry": None, "exit": None}
        elif form == "initial":
            assert anchors["entry"] is None
            assert anchors["exit"] is not None
        elif form == "medial":
            assert anchors["entry"] is not None
            assert anchors["exit"] is not None
        else:
            assert anchors["entry"] is not None
            assert anchors["exit"] is None


@pytest.mark.parametrize(
    "index", range(14)
)
def test_every_prototype_skeleton_is_single_path_with_iou_and_anchors(index, prototype):
    glyph = prototype["glyphs"][index]
    skeleton = glyph["skeleton"]
    points = skeleton["points"]
    widths = skeleton["widths"]
    path_d = skeleton["path_d"]

    # One continuous cubic path: exactly one move command, no subpaths.
    assert path_d.startswith("M ")
    assert path_d.count("M") == 1
    assert "C " in path_d
    assert path_d.count("C") == len(points) - 1
    assert len(skeleton["segments"]) == len(points) - 1
    assert skeleton["num_samples"] == len(points) == 100
    assert len(widths) == len(points)
    assert all(width > 0 for width in widths)
    assert skeleton["length"] > 0

    # Ordered right-to-left from right extremity to left extremity.
    assert points[0][0] == max(point[0] for point in points)
    assert points[-1][0] == min(point[0] for point in points)
    assert skeleton["ordered"] == "right_to_left"

    # IoU is stored and independently reproducible from the exported data.
    assert 0.80 <= glyph["iou"] <= 1.0
    trunk = shape(glyph["trunk_polygon"])
    recomputed = skeletonizer.compute_dilation_iou(
        trunk, {"points": points, "widths": widths}
    )
    assert recomputed >= 0.80
    assert recomputed == pytest.approx(glyph["iou"], abs=5e-3)

    # Anchors exist according to the form.
    form = glyph["form"]
    anchors = glyph["anchors"]
    if form == "medial":
        assert anchors["entry"] is not None
    if form in {"initial", "medial"}:
        assert anchors["exit"] is not None
    if form == "final":
        assert anchors["entry"] is not None


def test_generate_prototype_json_is_deterministic_and_matches_fixture(tmp_path):
    target = tmp_path / "prototype_5.json"
    written = skeletonizer.generate_prototype_5_json(target)
    assert written == target
    generated = json.loads(target.read_text(encoding="utf-8"))
    checked_in = json.loads(PROTOTYPE_PATH.read_text(encoding="utf-8"))
    assert generated == checked_in


def test_all_prototype_iou_values_pass_threshold(prototype):
    assert all(glyph["iou"] >= 0.80 for glyph in prototype["glyphs"])
    assert min(glyph["iou"] for glyph in prototype["glyphs"]) > 0.90


def test_prototype_letter_order_and_font_metrics(prototype):
    order = [glyph["char"] for glyph in prototype["glyphs"]]
    assert order == [
        "ا",
        "ا",
        "ب",
        "ب",
        "ب",
        "ب",
        "ج",
        "ج",
        "ج",
        "ج",
        "د",
        "د",
        "ر",
        "ر",
    ]
    assert prototype["font_family"] == "Noto Naskh Arabic"
    assert (REPO_ROOT / prototype["font"]).is_file()
