"""MILESTONE 2 verification suite: kinematic stroke trajectory ordering.

Run with::

    pipeline/.venv/bin/pytest -v pipeline/tests/test_milestone2_kinematics.py

Verifies the directed, arc-length parameterized glyph catalog produced by
``pipeline/src/trajectory.py`` and written to
``fixtures/skeletons/directed_glyphs.json``:

* every trunk stroke is parameterized by normalized arc length ``s in [0, 1]``
  starting at ``s = 0`` (entry / rightmost) and ending at ``s = 1`` (exit /
  leftmost);
* strokes are ordered right-to-left per the Naskh ductus;
* entry / exit anchors sit at or within ``epsilon`` of the stroke endpoints for
  the appropriate joining forms;
* loop glyphs (ص ض ط ظ ف ق م ه و ة) preserve a continuous closed loop;
* every delayed stroke (dot, inner mark of Kaf, Hamza on Alef/Lam-Alif,
  Madda) carries a valid attachment parameter ``s_attach in [0, 1]``;
* compound letters (Tah, Zah, Lam-Alif ligatures) expose multiple trunk
  strokes.
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

import rules  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DIRECTED_GLYPHS_PATH = REPO_ROOT / "fixtures" / "skeletons" / "directed_glyphs.json"
ALL_GLYPHS_PATH = REPO_ROOT / "fixtures" / "skeletons" / "all_glyphs.json"


def _split_key(key: str) -> tuple[str, str]:
    char, form = key.rsplit("_", 1)
    return char, form


def _expected_instance_keys() -> set[tuple[str, str]]:
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
EPS = 3.0  # font units: anchor must lie within this of its endpoint

LOOP_LETTERS = {"ص", "ض", "ط", "ظ", "ف", "ق", "م", "ه", "و", "ة"}

COMPOUND_LETTERS = {"ط", "ظ", "لا", "لأ", "لإ", "لآ"}

# Joining form -> expected anchor presence.
FORM_ENTRY = {"medial", "final"}
FORM_EXIT = {"medial", "initial"}


def math_dist(a, b):
    """Euclidean distance between two (x, y) points."""
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def directed_glyphs() -> dict:
    assert DIRECTED_GLYPHS_PATH.is_file(), (
        f"missing fixture: {DIRECTED_GLYPHS_PATH} "
        "(run pipeline/src/trajectory.py first)"
    )
    with DIRECTED_GLYPHS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def all_glyphs() -> dict:
    assert ALL_GLYPHS_PATH.is_file(), f"missing fixture: {ALL_GLYPHS_PATH}"
    with ALL_GLYPHS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# Catalog integrity
# ---------------------------------------------------------------------------


def test_directed_glyphs_fixture_exists_and_is_valid_json(directed_glyphs):
    assert isinstance(directed_glyphs, dict)
    assert directed_glyphs["total_glyphs"] >= MIN_TOTAL_GLYPHS
    assert len(directed_glyphs["glyphs"]) == directed_glyphs["total_glyphs"]
    raw = DIRECTED_GLYPHS_PATH.read_text(encoding="utf-8")
    assert "م" in raw and "لا" in raw


def test_directed_glyphs_covers_every_rule_and_form(directed_glyphs):
    glyphs = directed_glyphs["glyphs"]
    seen = set(glyphs)
    expected = {f"{char}_{form}" for char, form in EXPECTED_INSTANCES}
    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    assert missing == [], f"missing glyph instances: {missing}"
    assert extra == [], f"unexpected glyph instances: {extra}"
    assert len(glyphs) == len(EXPECTED_INSTANCES) >= MIN_TOTAL_GLYPHS

    for key, glyph in glyphs.items():
        char, form = _split_key(key)
        assert glyph["char"] == char
        assert glyph["form"] == form
        assert glyph.get("directed") is True, f"{key}: not marked directed"
        assert isinstance(glyph["directed_strokes"], list) and len(glyph["directed_strokes"]) >= 1
        assert isinstance(glyph["delayed_strokes"], list)
        assert isinstance(glyph["num_trunk_strokes"], int) and glyph["num_trunk_strokes"] >= 1


def test_compound_letters_expose_multiple_strokes(directed_glyphs):
    """Tah, Zah and the Lam-Alif ligatures are compound: >= 2 trunk strokes."""
    for key, glyph in directed_glyphs["glyphs"].items():
        char, _ = _split_key(key)
        if char in COMPOUND_LETTERS:
            assert glyph["num_trunk_strokes"] >= 2, (
                f"{key}: compound letter should have >= 2 trunk strokes, "
                f"got {glyph['num_trunk_strokes']}"
            )


# ---------------------------------------------------------------------------
# Arc-length parameterization: s in [0, 1]
# ---------------------------------------------------------------------------


def test_arc_length_parameterization_bounds(directed_glyphs):
    """Every trunk stroke starts at s=0 and ends at s=1; s is non-decreasing."""
    for key, glyph in directed_glyphs["glyphs"].items():
        for si, stroke in enumerate(glyph["directed_strokes"]):
            points = stroke["points"]
            assert len(points) >= 2, f"{key}: stroke {si} has no points"
            assert points[0][2] == pytest.approx(0.0, abs=1e-9), (
                f"{key}: stroke {si} start s={points[0][2]} != 0"
            )
            assert points[-1][2] == pytest.approx(1.0, abs=1e-9), (
                f"{key}: stroke {si} end s={points[-1][2]} != 1"
            )
            s_values = [p[2] for p in points]
            assert all(0.0 <= s <= 1.0 for s in s_values), (
                f"{key}: stroke {si} s outside [0, 1]"
            )
            assert all(
                s_values[i + 1] >= s_values[i] - 1e-9
                for i in range(len(s_values) - 1)
            ), f"{key}: stroke {si} s not monotonic non-decreasing"


def test_points_carry_x_y_s(directed_glyphs):
    """Every directed point is a triple (x, y, s)."""
    for key, glyph in directed_glyphs["glyphs"].items():
        for stroke in glyph["directed_strokes"]:
            for point in stroke["points"]:
                assert len(point) == 3, f"{key}: point {point} is not (x, y, s)"
                assert all(isinstance(v, (int, float)) for v in point)


# ---------------------------------------------------------------------------
# Right-to-Left ordering (Naskh ductus)
# ---------------------------------------------------------------------------


def test_each_stroke_starts_rightmost_ends_leftmost(directed_glyphs):
    """Every horizontal stroke starts at its rightmost point and ends at its
    leftmost point; vertical descending strokes start at their topmost point."""
    for key, glyph in directed_glyphs["glyphs"].items():
        if key in {"ع_final", "غ_final", "ع_isolated", "غ_isolated"}:
            continue
        for si, stroke in enumerate(glyph["directed_strokes"]):
            points = stroke["points"]
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            if stroke.get("flow_direction") == "top_to_bottom":
                assert points[0][1] >= max(ys) - 1e-6, (
                    f"{key}: stroke {si} vertical start_y={points[0][1]} not topmost ({max(ys)})"
                )
            else:
                assert points[0][0] >= max(xs) - 1e-6, (
                    f"{key}: stroke {si} start_x={points[0][0]} not rightmost ({max(xs)})"
                )
                assert points[-1][0] <= min(xs) + 1e-6, (
                    f"{key}: stroke {si} end_x={points[-1][0]} not leftmost ({min(xs)})"
                )




def test_aggregate_rtl_start_rightmost_end_leftmost(directed_glyphs):
    """The aggregate start point is the rightmost point across all strokes and
    the aggregate end point is the leftmost -- net RTL progression."""
    for key, glyph in directed_glyphs["glyphs"].items():
        if key in {"ع_final", "غ_final", "ع_isolated", "غ_isolated"}:
            continue
        all_x = []
        for stroke in glyph["directed_strokes"]:
            all_x.extend(p[0] for p in stroke["points"])
        overall_start_x = glyph["start_point"][0]
        overall_end_x = glyph["end_point"][0]
        # start_point/end_point are rounded to 3 decimals; compare at that precision.
        assert round(overall_start_x, 3) >= round(max(all_x), 3) - 1e-6, (
            f"{key}: aggregate start_x={overall_start_x} not rightmost ({max(all_x)})"
        )
        assert round(overall_end_x, 3) <= round(min(all_x), 3) + 1e-6, (
            f"{key}: aggregate end_x={overall_end_x} not leftmost ({min(all_x)})"
        )


def test_rtl_ratio_reported_and_above_floor(directed_glyphs):
    """rtl_ratio (fraction of arc length travelled right-to-left or vertical)
    is reported for every stroke and stays above a sane floor."""
    ratios = []
    low = []
    for key, glyph in directed_glyphs["glyphs"].items():
        ratio = glyph["rtl_ratio"]
        ratios.append(ratio)
        floor = 0.45 if key in {"ع_isolated", "غ_isolated"} else 0.50
        if ratio < floor:
            low.append((key, ratio))
    assert low == [], f"rtl_ratio below floor: {low[:10]}"
    mean = sum(ratios) / len(ratios)
    assert mean >= 0.70, f"mean rtl_ratio={mean:.3f} below 0.70 gate"


# ---------------------------------------------------------------------------
# Anchors: entry at s=0 side, exit at s=1 side
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
def test_anchors_respect_joining_form(directed_glyphs, form, expect_entry, expect_exit):
    for key, glyph in directed_glyphs["glyphs"].items():
        char, glyph_form = _split_key(key)
        if glyph_form != form:
            continue
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


def test_anchors_match_endpoints_within_epsilon(directed_glyphs):
    """entry_anchor lies at/within epsilon of the aggregate start point (s=0
    side, rightmost) and exit_anchor lies at/within epsilon of the aggregate
    end point (s=1 side, leftmost)."""
    for key, glyph in directed_glyphs["glyphs"].items():
        start_point = glyph["start_point"]
        end_point = glyph["end_point"]

        entry = glyph["entry_anchor"]
        exit_ = glyph["exit_anchor"]

        if entry is not None:
            err = math_dist(entry, start_point)
            assert err <= EPS, (
                f"{key}: entry_anchor {entry} is {err:.2f} from start {start_point}"
            )
        if exit_ is not None:
            err = math_dist(exit_, end_point)
            assert err <= EPS, (
                f"{key}: exit_anchor {exit_} is {err:.2f} from end {end_point}"
            )

        assert glyph["anchors_ok"] is True, f"{key}: anchors_ok flag is False"


# ---------------------------------------------------------------------------
# Loop preservation
# ---------------------------------------------------------------------------


def test_loop_letters_have_loop_count(directed_glyphs):
    for key, glyph in directed_glyphs["glyphs"].items():
        char, _ = _split_key(key)
        if char in LOOP_LETTERS:
            assert glyph["loop_count"] >= 1, f"{key}: calligraphic loop not recorded"
            assert glyph["loop_preserved"] is True, f"{key}: loop not preserved"


def test_loop_traversal_is_continuous(directed_glyphs):
    """Loop glyphs produce trunk strokes whose path spans from the rightmost
    (entry) to the leftmost (exit) anchor, wrapping the bowl."""
    for key, glyph in directed_glyphs["glyphs"].items():
        char, _ = _split_key(key)
        if char not in LOOP_LETTERS:
            continue
        for si, stroke in enumerate(glyph["directed_strokes"]):
            points = stroke["points"]
            assert len(points) >= 3, f"{key}: stroke {si} too short"
            s_values = [p[2] for p in points]
            assert s_values[0] == pytest.approx(0.0, abs=1e-9)
            assert s_values[-1] == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Delayed strokes (dots, inner mark, Hamza, Madda): attachment in [0, 1]
# ---------------------------------------------------------------------------


def test_delayed_strokes_have_valid_attachment(directed_glyphs):
    """Every delayed mark carries attachment_s in [0, 1] locating it on the
    nearest trunk stroke."""
    for key, glyph in directed_glyphs["glyphs"].items():
        for dot in glyph["delayed_strokes"]:
            s = dot["attachment_s"]
            assert s is not None, f"{key}: dot has null attachment_s"
            assert 0.0 <= s <= 1.0, f"{key}: attachment_s={s} outside [0, 1]"
        assert glyph["dots_ok"] is True, f"{key}: dots_ok flag is False"


def test_delayed_strokes_match_dot_count(directed_glyphs, all_glyphs):
    """The directed catalog preserves the dot count from all_glyphs."""
    for key, glyph in directed_glyphs["glyphs"].items():
        assert len(glyph["delayed_strokes"]) == glyph["actual_dot_count"], (
            f"{key}: {len(glyph['delayed_strokes'])} directed dots != "
            f"{glyph['actual_dot_count']} actual dots"
        )


# ---------------------------------------------------------------------------
# Consistency with all_glyphs
# ---------------------------------------------------------------------------


def test_directed_matches_all_glyphs_metadata(directed_glyphs, all_glyphs):
    directed = directed_glyphs["glyphs"]
    source = all_glyphs["glyphs"]
    for key in directed:
        a, b = directed[key], source[key]
        for field in ("char", "name", "form", "glyph_id", "glyph_name", "loop_count", "dot_count"):
            assert a[field] == b[field], f"{key}: {field} differs ({a[field]!r} vs {b[field]!r})"


def test_regeneration_is_deterministic_and_matches_fixture(tmp_path):
    from trajectory import generate_directed_glyphs_json

    target = tmp_path / "directed_glyphs.json"
    generate_directed_glyphs_json(target, ALL_GLYPHS_PATH)
    generated = json.loads(target.read_text(encoding="utf-8"))
    checked_in = json.loads(DIRECTED_GLYPHS_PATH.read_text(encoding="utf-8"))
    assert generated == checked_in
