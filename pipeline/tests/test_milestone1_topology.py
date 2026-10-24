"""MILESTONE 1 verification suite: full glyph skeleton extraction, topology and IoU.

Run with::

    pipeline/.venv/bin/pytest -v pipeline/tests/test_milestone1_topology.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

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
ALL_GLYPHS_PATH = REPO_ROOT / "fixtures" / "skeletons" / "all_glyphs.json"

# A glyph key is "{char}_{form}"; the char never contains an underscore, so
# rsplit on the final underscore recovers (char, form) reliably (including the
# multi-character Lam-Alif ligatures such as "لا_isolated").


def _split_key(key: str) -> tuple[str, str]:
    char, form = key.rsplit("_", 1)
    return char, form


def _expected_instance_keys() -> set[tuple[str, str]]:
    """Every (char, form) pair the rules require, i.e. the full catalog."""
    keys: set[tuple[str, str]] = set()
    for char, rule in rules.ARABIC_CHARACTER_RULES.items():
        joining = rule["joining_type"]
        if joining == "D":
            forms = ("isolated", "initial", "medial", "final")
        elif joining == "R":
            forms = ("isolated", "final")
        else:  # "U" non-joining (Hamza)
            forms = ("isolated",)
        for form in forms:
            assert rule["forms"][form] is not None, f"{char!r} missing {form} form"
            keys.add((char, form))
    return keys


EXPECTED_INSTANCES = _expected_instance_keys()
MIN_TOTAL_GLYPHS = 105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def all_glyphs() -> dict:
    assert ALL_GLYPHS_PATH.is_file(), f"missing fixture: {ALL_GLYPHS_PATH}"
    with ALL_GLYPHS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def font_path() -> Path:
    assert NOTO_FONT.is_file(), f"missing font: {NOTO_FONT}"
    return NOTO_FONT


# ---------------------------------------------------------------------------
# Coverage and catalog integrity
# ---------------------------------------------------------------------------


def test_all_glyphs_fixture_exists_and_is_valid_json(all_glyphs):
    assert isinstance(all_glyphs, dict)
    assert all_glyphs["total_glyphs"] >= MIN_TOTAL_GLYPHS
    assert len(all_glyphs["glyphs"]) == all_glyphs["total_glyphs"]
    assert all_glyphs["total_glyphs"] >= MIN_TOTAL_GLYPHS
    # Arabic must remain human-readable UTF-8, not \\u escapes.
    raw = ALL_GLYPHS_PATH.read_text(encoding="utf-8")
    assert "م" in raw and "لا" in raw


def test_all_glyphs_covers_every_rule_and_form(all_glyphs):
    glyphs = all_glyphs["glyphs"]
    seen = set(glyphs)
    expected = {f"{char}_{form}" for char, form in EXPECTED_INSTANCES}
    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    assert missing == [], f"missing glyph instances: {missing}"
    assert extra == [], f"unexpected glyph instances: {extra}"
    assert len(glyphs) == len(EXPECTED_INSTANCES) >= MIN_TOTAL_GLYPHS

    # Every key matches its char/form and stores coherent metadata.
    for key, glyph in glyphs.items():
        char, form = _split_key(key)
        assert glyph["char"] == char
        assert glyph["form"] == form
        assert glyph["glyph_id"] >= 0
        assert isinstance(glyph["glyph_name"], str) and glyph["glyph_name"]
        assert isinstance(glyph["advance_x"], (int, float)) and glyph["advance_x"] >= 0
        assert isinstance(glyph["trunk_strokes"], list) and len(glyph["trunk_strokes"]) >= 1
        assert isinstance(glyph["delayed_strokes"], list)


def test_loop_count_matches_orthography(all_glyphs):
    """The recorded loop count must equal the rules' expected_loop_count."""
    for key, glyph in all_glyphs["glyphs"].items():
        char, _ = _split_key(key)
        expected = rules.ARABIC_CHARACTER_RULES[char]["expected_loop_count"]
        assert glyph["loop_count"] == expected, (
            f"{key}: loop_count={glyph['loop_count']} != expected {expected}"
        )
        assert glyph["expected_loop_count"] == expected


def test_calligraphic_loops_are_preserved(all_glyphs):
    """Loop glyphs (Meem, Waw, Faa, Qaf, Haa, Sad, Dad, Tah, Zah, Teh Marbuta)"""
    loop_letters = {"ص", "ض", "ط", "ظ", "ف", "ق", "م", "ه", "و", "ة"}
    for key, glyph in all_glyphs["glyphs"].items():
        char, _ = _split_key(key)
        if char in loop_letters:
            assert glyph["loop_count"] >= 1, f"{key}: calligraphic loop not recorded"


# ---------------------------------------------------------------------------
# Dilation IoU thresholds
# ---------------------------------------------------------------------------


def test_iou_meets_form_thresholds(all_glyphs):
    for key, glyph in all_glyphs["glyphs"].items():
        iou = glyph["dilation_iou"]
        threshold = 0.75 if glyph["loop_count"] >= 1 else 0.80
        assert iou >= threshold, (
            f"{key}: dilation_iou={iou:.4f} below {threshold:.2f} "
            f"(loop_count={glyph['loop_count']})"
        )
        assert iou <= 1.0, f"{key}: dilation_iou={iou:.4f} > 1.0"


def test_all_iou_values_are_reproducible(all_glyphs, font_path):
    """The stored dilation IoU can be recomputed independently from trunk + strokes."""
    # Sample representative glyphs across single-stroke, loop, and multi-stroke letters
    sample_keys = ["ا_isolated", "ب_initial", "ص_isolated", "ط_isolated", "لا_isolated"]
    for key in sample_keys:
        glyph = all_glyphs["glyphs"][key]
        char, form = _split_key(key)
        # Recompute with local widths, exactly as _build_all_glyphs_entry does.
        entry = skeletonizer._build_all_glyphs_entry(font_path, char, form)
        assert entry["dilation_iou"] == pytest.approx(glyph["dilation_iou"], abs=1e-3)


# ---------------------------------------------------------------------------
# Anchor points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "form,expect_entry,expect_exit",
    [
        ("isolated", False, False),
        ("initial", False, True),
        ("medial", True, True),
        ("final", True, False),
    ],
)
def test_anchors_respect_joining_form(all_glyphs, form, expect_entry, expect_exit):
    for key, glyph in all_glyphs["glyphs"].items():
        char, glyph_form = _split_key(key)
        if glyph_form != form:
            continue
        anchors = (glyph["entry_anchor"], glyph["exit_anchor"])
        if expect_entry:
            assert glyph["entry_anchor"] is not None, f"{key}: missing entry anchor"
            assert len(glyph["entry_anchor"]) == 2
        else:
            assert glyph["entry_anchor"] is None, f"{key}: entry anchor should be null"
        if expect_exit:
            assert glyph["exit_anchor"] is not None, f"{key}: missing exit anchor"
            assert len(glyph["exit_anchor"]) == 2
        else:
            assert glyph["exit_anchor"] is None, f"{key}: exit anchor should be null"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_regeneration_is_deterministic_and_matches_fixture(tmp_path, font_path):
    target = tmp_path / "all_glyphs.json"
    written = skeletonizer.generate_all_glyphs_json(target, font_path)
    assert written == target
    generated = json.loads(target.read_text(encoding="utf-8"))
    checked_in = json.loads(ALL_GLYPHS_PATH.read_text(encoding="utf-8"))
    assert generated == checked_in


def test_compute_loop_count_is_a_valid_graph_invariant(font_path):
    """The graph-based cycle rank helper returns a non-negative integer."""
    from skeletonizer import _rasterize, _skeleton_graph, compute_loop_count
    from skimage.morphology import medial_axis

    contours = extractor.contours_for_letter_form(font_path, "م", "isolated")
    trunk = skeletonizer.separate_trunk_and_dots(contours, 0, "none")["trunk_polygon"]
    mask, _scale, _minx, _maxy = _rasterize(trunk)
    skeleton, _distance = medial_axis(mask, return_distance=True, rng=0)
    coordinates, adjacency = _skeleton_graph(skeleton)
    count = compute_loop_count(coordinates, adjacency)
    assert isinstance(count, int) and count >= 0
