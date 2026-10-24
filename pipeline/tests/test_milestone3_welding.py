"""MILESTONE 3 verification suite: RTL shaping & baseline welding.

Run with::

    pipeline/.venv/bin/pytest -v pipeline/tests/test_milestone3_welding.py

Verifies the welded PAW baseline engine in ``pipeline/src/shaper.py`` and the
golden fixture ``fixtures/golden/welded_50_words.json``:

* Test 1: Every PAW trunk has exactly one ``M`` command (Single-M invariant).
* Test 2: C0 positional continuity on all welded joints, distance Delta < 0.05.
* Test 3: G1 tangent continuity on all welded joints, Delta theta < 12 deg.
* Test 4: Delayed-stroke temporal causality (trunk finishes before any
  delayed mark starts; PAWs ordered in time).
* Test 5: Golden fixture matches a clean regeneration.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

# Make ``pipeline/src`` importable without installing the project.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import shaper  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
WELDED_50_WORDS_PATH = REPO_ROOT / "fixtures" / "golden" / "welded_50_words.json"

# Tolerances (mirror engine/src/validator.ts).
CONTINUITY_TOLERANCE = 1e-3
C0_MAX_DELTA = 0.05  # font units
G1_MAX_DELTA_DEG = 12.0  # degrees

_TOKEN_PATTERN = re.compile(r"[MLCQZmlcqz]|-?\d+(?:\.\d+)?")


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _unit(dx, dy):
    n = math.hypot(dx, dy)
    if n == 0:
        return 0.0, 0.0
    return dx / n, dy / n


def _angle_deg(v):
    return math.degrees(math.atan2(v[1], v[0]))


def _angle_delta(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


# ---------------------------------------------------------------------------
# SVG path parsing (mirrors engine/src/validator.ts parseSvgPath)
# ---------------------------------------------------------------------------


def parse_svg_path(d):
    """Parse an SVG path string into a list of segments.

    Each segment is a tuple:
      ('M', None, start, end)
      ('L', None, start, end)
      ('C', (control1, control2), start, end)
    where start/end are (x, y) points.  The first segment must be 'M'.
    """

    tokens = _TOKEN_PATTERN.findall(d)
    segs = []
    active = None
    cur = [0.0, 0.0]
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            active = tok.upper()
            i += 1
            continue
        if active == "M":
            end = (float(tokens[i]), float(tokens[i + 1]))
            segs.append(("M", None, tuple(cur), end))
            cur = [end[0], end[1]]
            i += 2
        elif active == "L":
            end = (float(tokens[i]), float(tokens[i + 1]))
            segs.append(("L", None, tuple(cur), end))
            cur = [end[0], end[1]]
            i += 2
        elif active == "C":
            c1 = (float(tokens[i]), float(tokens[i + 1]))
            c2 = (float(tokens[i + 2]), float(tokens[i + 3]))
            end = (float(tokens[i + 4]), float(tokens[i + 5]))
            segs.append(("C", (c1, c2), tuple(cur), end))
            cur = [end[0], end[1]]
            i += 6
        else:
            # Q / Z not emitted by the shaper; skip defensively.
            i += 1
    return segs


def seg_end_tangent(seg):
    """Outgoing unit tangent at the end of a segment (direction of travel)."""
    if seg[0] == "L":
        return _unit(seg[3][0] - seg[2][0], seg[3][1] - seg[2][1])
    if seg[0] == "C":
        _c1, c2 = seg[1]
        end = seg[3]
        return _unit(end[0] - c2[0], end[1] - c2[1])
    return (1.0, 0.0)


def seg_start_tangent(seg):
    """Incoming unit tangent at the start of a segment (direction leaving start)."""
    if seg[0] == "L":
        return _unit(seg[3][0] - seg[2][0], seg[3][1] - seg[2][1])
    if seg[0] == "C":
        c1, _c2 = seg[1]
        start = seg[2]
        return _unit(c1[0] - start[0], c1[1] - start[1])
    return (1.0, 0.0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def golden():
    assert WELDED_50_WORDS_PATH.is_file(), (
        f"missing fixture: {WELDED_50_WORDS_PATH} "
        "(run pipeline/src/shaper.py first)"
    )
    with WELDED_50_WORDS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def catalog():
    return shaper.load_directed_glyphs()


# ---------------------------------------------------------------------------
# Test 1: Single-M invariant
# ---------------------------------------------------------------------------


def count_m_commands(d):
    return d.count(" M") + (1 if d.startswith("M ") else 0)


def test_every_paw_trunk_has_single_m_command(golden):
    """Each PAW baseline trunk MUST be a single path starting with exactly one
    ``M`` command and no subsequent ``M`` commands."""
    failures = []
    for word in golden["words"]:
        for paw in word["paws"]:
            d = paw["trunkStroke"]["d"]
            n = count_m_commands(d)
            if n != 1:
                failures.append(
                    f"{word['text']} / {paw['letters']}: {n} 'M' commands"
                )
    assert failures == [], f"Single-M invariant violated: {failures[:8]}"


# ---------------------------------------------------------------------------
# Test 2: C0 continuity
# ---------------------------------------------------------------------------


def test_c0_continuity_on_welded_joints(golden):
    """C0 positional continuity on all welded joints: distance Delta < 0.05."""
    failures = []
    for word in golden["words"]:
        for paw in word["paws"]:
            segs = parse_svg_path(paw["trunkStroke"]["d"])
            for i in range(1, len(segs)):
                prev_end = segs[i - 1][3]
                cur_start = segs[i][2]
                delta = _dist(prev_end, cur_start)
                if delta > C0_MAX_DELTA:
                    failures.append(
                        f"{word['text']} / {paw['letters']}: joint {i} C0 "
                        f"delta={delta:.4f} > 0.05"
                    )
    assert failures == [], f"C0 continuity violated: {failures[:8]}"


# ---------------------------------------------------------------------------
# Test 3: G1 tangent continuity
# ---------------------------------------------------------------------------


def test_g1_tangent_continuity_on_welded_joints(golden):
    """G1 tangent continuity on all welded joints: Delta theta < 12 deg.

    Only letter-to-letter boundaries (marked by a weld ``C`` segment) are
    checked, per the spec: the outgoing tangent of letter ``i`` at exit vs the
    incoming tangent of letter ``i+1`` at entry.
    """
    failures = []
    for word in golden["words"]:
        for paw in word["paws"]:
            segs = parse_svg_path(paw["trunkStroke"]["d"])
            for i in range(1, len(segs) - 1):
                if segs[i][0] != "C":
                    continue
                weld = segs[i]
                # At the weld start: outgoing tangent of previous segment vs
                # incoming tangent of the weld.
                tout = seg_end_tangent(segs[i - 1])
                wtin = seg_start_tangent(weld)
                d1 = _angle_delta(_angle_deg(tout), _angle_deg(wtin))
                # At the weld end: outgoing tangent of the weld vs incoming of
                # the next segment.
                if i + 1 < len(segs):
                    wtout = seg_end_tangent(weld)
                    ntin = seg_start_tangent(segs[i + 1])
                    d2 = _angle_delta(_angle_deg(wtout), _angle_deg(ntin))
                else:
                    d2 = 0.0
                for d in (d1, d2):
                    if d > G1_MAX_DELTA_DEG:
                        failures.append(
                            f"{word['text']} / {paw['letters']}: joint G1 "
                            f"delta={d:.2f} deg > 12"
                        )
                        break
    assert failures == [], f"G1 continuity violated: {failures[:8]}"


# ---------------------------------------------------------------------------
# Test 4: Delayed-stroke temporal causality
# ---------------------------------------------------------------------------


def test_delayed_stroke_temporal_causality(golden):
    """Delayed strokes must start strictly after their PAW trunk finishes, and
    PAWs must be ordered in time (all of paw k before paw k+1's trunk)."""

    EPS = CONTINUITY_TOLERANCE
    failures = []

    for word in golden["words"]:
        timeline = word["timeline"]
        items = timeline["items"]
        paws = timeline["paws"]

        # Build per-paw item lists.
        items_by_paw = {}
        for item in items:
            items_by_paw.setdefault(item["pawId"], []).append(item)

        # Each paw has exactly one trunk item.
        for paw in paws:
            paw_trunks = [it for it in items_by_paw.get(paw["id"], []) if it["type"] == "trunk"]
            if len(paw_trunks) != 1:
                failures.append(
                    f"{word['text']} / {paw['id']}: {len(paw_trunks)} trunk items"
                )
                continue
            trunk = paw_trunks[0]
            delayed = [it for it in items_by_paw.get(paw["id"], []) if it["type"] == "delayed"]
            # Causality rule 1: trunk finishes before any delayed mark starts.
            for item in delayed:
                if trunk["endTime"] > item["startTime"] + EPS:
                    failures.append(
                        f"{word['text']} / {paw['id']}: delayed '{item['strokeId']}' "
                        f"starts {item['startTime']} before trunk ends {trunk['endTime']}"
                    )
            # No overlapping delayed strokes within a paw.
            sorted_delayed = sorted(delayed, key=lambda it: (it["startTime"], it["endTime"]))
            for a, b in zip(sorted_delayed, sorted_delayed[1:]):
                if a["startTime"] < b["endTime"] - EPS and b["startTime"] < a["endTime"] - EPS:
                    failures.append(
                        f"{word['text']} / {paw['id']}: delayed strokes overlap "
                        f"'{a['strokeId']}' / '{b['strokeId']}'"
                    )

        # Causality rule 2: all strokes of paw k finish before paw k+1's trunk.
        trunks = {}
        for paw in paws:
            paw_trunks = [it for it in items_by_paw.get(paw["id"], []) if it["type"] == "trunk"]
            if paw_trunks:
                trunks[paw["id"]] = paw_trunks[0]
        paw_ids = [p["id"] for p in paws]
        for i in range(len(paw_ids) - 1):
            next_trunk = trunks.get(paw_ids[i + 1])
            if not next_trunk:
                continue
            for item in items_by_paw.get(paw_ids[i], []):
                if item["endTime"] > next_trunk["startTime"] + EPS:
                    failures.append(
                        f"{word['text']} / {paw_ids[i]}: '{item['strokeId']}' ends "
                        f"{item['endTime']} after next paw trunk starts {next_trunk['startTime']}"
                    )

        # Non-negative durations.
        for item in items:
            if item["endTime"] < item["startTime"] - EPS:
                failures.append(
                    f"{word['text']} / {item['strokeId']}: negative duration"
                )

    assert failures == [], f"Causality violated: {failures[:8]}"


# ---------------------------------------------------------------------------
# Test 5: Golden fixture matches regeneration
# ---------------------------------------------------------------------------


def test_golden_matches_regeneration(tmp_path, golden, catalog):
    """The checked-in golden fixture matches a clean regeneration."""
    target = tmp_path / "welded_50_words.json"
    shaper.generate_welded_50_words(target)
    generated = json.loads(target.read_text(encoding="utf-8"))
    checked_in = json.loads(WELDED_50_WORDS_PATH.read_text(encoding="utf-8"))
    assert generated == checked_in, "regenerated golden fixture does not match checked-in fixture"
