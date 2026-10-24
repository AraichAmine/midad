"""DAY-1 TASK A verification suite for the Arabic character rules registry.

Run with::

    pipeline/.venv/bin/pytest pipeline/tests/test_day1_rules.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make ``pipeline/src`` importable without requiring the package to be installed.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import rules  # noqa: E402  (import after sys.path setup)

RULES = rules.ARABIC_CHARACTER_RULES

REQUIRED_FIELDS = {
    "char",
    "name",
    "base_unicode",
    "joining_type",
    "forms",
    "dot_count",
    "dot_placement",
    "has_hamza",
    "has_madda",
    "has_crossbar",
    "has_inner_mark",
    "expected_loop_count",
}

FORM_KEYS = {"isolated", "initial", "medial", "final"}

BASIC_LETTERS = (
    "ا",
    "ب",
    "ت",
    "ث",
    "ج",
    "ح",
    "خ",
    "د",
    "ذ",
    "ر",
    "ز",
    "س",
    "ش",
    "ص",
    "ض",
    "ط",
    "ظ",
    "ع",
    "غ",
    "ف",
    "ق",
    "ك",
    "ل",
    "م",
    "ن",
    "ه",
    "و",
    "ي",
)

ADDITIONAL_GLYPHS = ("ة", "ى", "ء", "أ", "إ", "آ")
LIGATURES = ("لا", "لأ", "لإ", "لآ")

# Independent ground truth: (base unicode, joining type, dot count, dot placement)
EXPECTED_ORTHOGRAPHY = {
    "ا": ("0x0627", "R", 0, "none"),
    "ب": ("0x0628", "D", 1, "below"),
    "ت": ("0x062A", "D", 2, "above"),
    "ث": ("0x062B", "D", 3, "above"),
    "ج": ("0x062C", "D", 1, "below"),
    "ح": ("0x062D", "D", 0, "none"),
    "خ": ("0x062E", "D", 1, "above"),
    "د": ("0x062F", "R", 0, "none"),
    "ذ": ("0x0630", "R", 1, "above"),
    "ر": ("0x0631", "R", 0, "none"),
    "ز": ("0x0632", "R", 1, "above"),
    "س": ("0x0633", "D", 0, "none"),
    "ش": ("0x0634", "D", 3, "above"),
    "ص": ("0x0635", "D", 0, "none"),
    "ض": ("0x0636", "D", 1, "above"),
    "ط": ("0x0637", "D", 0, "none"),
    "ظ": ("0x0638", "D", 1, "above"),
    "ع": ("0x0639", "D", 0, "none"),
    "غ": ("0x063A", "D", 1, "above"),
    "ف": ("0x0641", "D", 1, "above"),
    "ق": ("0x0642", "D", 2, "above"),
    "ك": ("0x0643", "D", 0, "none"),
    "ل": ("0x0644", "D", 0, "none"),
    "م": ("0x0645", "D", 0, "none"),
    "ن": ("0x0646", "D", 1, "above"),
    "ه": ("0x0647", "D", 0, "none"),
    "و": ("0x0648", "R", 0, "none"),
    "ي": ("0x064A", "D", 2, "below"),
    "ة": ("0x0629", "R", 2, "above"),
    "ى": ("0x0649", "R", 0, "none"),
    "ء": ("0x0621", "U", 0, "none"),
    "أ": ("0x0623", "R", 0, "none"),
    "إ": ("0x0625", "R", 0, "none"),
    "آ": ("0x0622", "R", 0, "none"),
    "لا": ("0xFEFB", "R", 0, "none"),
    "لأ": ("0xFEF7", "R", 0, "none"),
    "لإ": ("0xFEF9", "R", 0, "none"),
    "لآ": ("0xFEF5", "R", 0, "none"),
}

EXPECTED_LOOP_COUNTS = {
    "ص": 1,
    "ض": 1,
    "ط": 1,
    "ظ": 1,
    "ف": 1,
    "ق": 1,
    "م": 1,
    "ه": 1,
    "و": 1,
    "ة": 1,
}

EXPECTED_CROSSBARS = {"ط", "ظ", "ك"}
EXPECTED_HAMZA = {"ء", "أ", "إ", "لأ", "لإ"}
EXPECTED_MADDA = {"آ", "لآ"}


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_all_28_basic_letters_present():
    assert len(BASIC_LETTERS) == 28
    missing = [char for char in BASIC_LETTERS if char not in RULES]
    assert missing == [], f"missing basic letters: {missing}"


def test_additional_glyphs_and_ligatures_present():
    for char in ADDITIONAL_GLYPHS + LIGATURES:
        assert char in RULES, f"missing glyph {char!r}"


def test_registry_contains_no_unexpected_entries():
    expected = set(BASIC_LETTERS) | set(ADDITIONAL_GLYPHS) | set(LIGATURES)
    assert set(RULES) == expected


def test_expected_orthography_table_covers_every_rule():
    assert set(EXPECTED_ORTHOGRAPHY) == set(RULES)


# ---------------------------------------------------------------------------
# Schema and Unicode integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("char", list(RULES))
def test_record_has_required_schema(char):
    record = RULES[char]
    assert set(record) == REQUIRED_FIELDS
    assert record["char"] == char
    assert isinstance(record["name"], str) and record["name"].startswith("ARABIC ")
    assert record["joining_type"] in {"D", "R", "U"}
    assert record["dot_count"] in {0, 1, 2, 3}
    assert record["dot_placement"] in {"above", "below", "inside", "none"}
    for flag in ("has_hamza", "has_madda", "has_crossbar"):
        assert isinstance(record[flag], bool)
    assert record["expected_loop_count"] in {0, 1}
    assert set(record["forms"]) == FORM_KEYS


@pytest.mark.parametrize("char", list(RULES))
def test_unicode_fields_are_valid_hex(char):
    record = RULES[char]
    base = int(record["base_unicode"], 16)
    assert record["base_unicode"] == f"0x{base:04X}"
    # Presentation forms live in Arabic Presentation Forms-B.
    for form in record["forms"].values():
        if form is None:
            continue
        value = int(form, 16)
        assert form == f"0x{value:04X}"
        assert 0xFE70 <= value <= 0xFEFF

    if len(char) == 1:
        assert ord(char) == base
    else:
        # Lam-Alif ligatures are keyed by their decomposition (two letters);
        # their declared base code point is the isolated presentation form.
        assert int(record["forms"]["isolated"], 16) == base


@pytest.mark.parametrize("char", list(RULES))
def test_orthography_matches_standard_arabic(char):
    expected_base, expected_joining, expected_dots, expected_placement = (
        EXPECTED_ORTHOGRAPHY[char]
    )
    record = RULES[char]
    assert record["base_unicode"] == expected_base
    assert record["joining_type"] == expected_joining
    assert record["dot_count"] == expected_dots
    assert record["dot_placement"] == expected_placement
    if expected_dots == 0:
        assert record["dot_placement"] == "none"
    else:
        assert record["dot_placement"] in {"above", "below"}


# ---------------------------------------------------------------------------
# Joining behaviour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "char", [c for c, rec in RULES.items() if rec["joining_type"] == "R"]
)
def test_right_joining_letters_only_have_isolated_and_final(char):
    forms = RULES[char]["forms"]
    assert forms["initial"] is None
    assert forms["medial"] is None
    assert forms["isolated"] is not None
    assert forms["final"] is not None


@pytest.mark.parametrize(
    "char", [c for c, rec in RULES.items() if rec["joining_type"] == "D"]
)
def test_dual_joining_letters_have_all_four_forms(char):
    forms = RULES[char]["forms"]
    for key in ("isolated", "initial", "medial", "final"):
        assert forms[key] is not None, f"{char!r} missing {key} form"


def test_non_joining_letters_have_no_joined_forms():
    non_joining = [c for c, rec in RULES.items() if rec["joining_type"] == "U"]
    assert non_joining == ["ء"]
    for char in non_joining:
        forms = RULES[char]["forms"]
        assert forms["isolated"] is not None
        assert forms["initial"] is None
        assert forms["medial"] is None
        assert forms["final"] is None


def test_lam_alif_ligatures_only_have_isolated_and_final():
    for char in LIGATURES:
        forms = RULES[char]["forms"]
        assert forms["initial"] is None
        assert forms["medial"] is None
        assert forms["isolated"] is not None
        assert forms["final"] is not None


def test_presentation_forms_are_unique_across_registry():
    seen: dict[str, str] = {}
    for char, record in RULES.items():
        for position, form in record["forms"].items():
            if form is None:
                continue
            assert form not in seen, (
                f"presentation form {form} reused by {char!r}/{position} "
                f"and {seen[form]}"
            )
            seen[form] = f"{char!r}/{position}"


# ---------------------------------------------------------------------------
# Dots, loops and other visual features
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("char", list(RULES))
def test_dot_count_matches_unicode_character_name_where_applicable(char):
    """The declared dots must agree with the numeric suffix of the letter name.

    Only the basic letters use the BEH/TEH/... family names; for those Unicode
    encodes the dot count in the name itself, which is a useful cross-check.
    """
    if char not in BASIC_LETTERS:
        pytest.skip("dot naming convention only applies to the basic letters")
    name = RULES[char]["name"].rsplit(" ", 1)[-1]
    numeric_names = {
        "BEH": 1,
        "TEH": 2,
        "THEH": 3,
        "JEEM": 1,
        "KHAH": 1,
        "THAL": 1,
        "ZAIN": 1,
        "SHEEN": 3,
        "DAD": 1,
        "ZAH": 1,
        "GHAIN": 1,
        "FEH": 1,
        "QAF": 2,
        "NOON": 1,
        "YEH": 2,
    }
    if name in numeric_names:
        assert RULES[char]["dot_count"] == numeric_names[name]
        assert RULES[char]["dot_placement"] in {"above", "below"}


@pytest.mark.parametrize("char", list(RULES))
def test_loop_count_matches_ground_truth(char):
    assert RULES[char]["expected_loop_count"] == EXPECTED_LOOP_COUNTS.get(char, 0)


@pytest.mark.parametrize("char", list(RULES))
def test_crossbar_matches_ground_truth(char):
    assert RULES[char]["has_crossbar"] is (char in EXPECTED_CROSSBARS)


@pytest.mark.parametrize("char", list(RULES))
def test_hamza_and_madda_flags_match_ground_truth(char):
    assert RULES[char]["has_hamza"] is (char in EXPECTED_HAMZA)
    assert RULES[char]["has_madda"] is (char in EXPECTED_MADDA)


def test_specific_orthography_examples():
    # A handful of high-risk confusables called out explicitly.
    assert RULES["ب"]["dot_count"] == 1
    assert RULES["ب"]["dot_placement"] == "below"
    assert RULES["ت"]["dot_count"] == 2
    assert RULES["ث"]["dot_count"] == 3
    assert RULES["ج"]["dot_placement"] == "below"
    assert RULES["ي"]["dot_count"] == 2
    assert RULES["ي"]["dot_placement"] == "below"
    assert RULES["ة"]["dot_count"] == 2
    assert RULES["ة"]["expected_loop_count"] == 1
    assert RULES["ك"]["has_crossbar"] is True
    assert RULES["ط"]["has_crossbar"] is True
    assert RULES["ظ"]["has_crossbar"] is True
    assert RULES["ء"]["has_hamza"] is True
    assert RULES["لآ"]["has_madda"] is True


# ---------------------------------------------------------------------------
# JSON fixture export / round-trip
# ---------------------------------------------------------------------------


def test_fixture_path_points_into_repository():
    assert rules.RULES_FIXTURE_PATH == (
        Path(rules.__file__).resolve().parents[2]
        / "fixtures"
        / "rules"
        / "arabic_character_rules.json"
    )


def test_checked_in_fixture_exists_and_is_valid_json():
    fixture = rules.RULES_FIXTURE_PATH
    assert fixture.is_file(), f"missing fixture: {fixture}"
    with fixture.open(encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    assert len(data) == len(RULES)


def test_checked_in_fixture_matches_in_memory_rules_exactly():
    with rules.RULES_FIXTURE_PATH.open(encoding="utf-8") as handle:
        on_disk = json.load(handle)
    assert on_disk == RULES


def test_fixture_preserves_arabic_characters_as_utf8():
    raw = rules.RULES_FIXTURE_PATH.read_text(encoding="utf-8")
    for char in RULES:
        assert char in raw, f"{char!r} was escaped instead of written as UTF-8"


def test_export_round_trip_to_temporary_path(tmp_path):
    target = tmp_path / "exported_rules.json"
    written = rules.export_rules_json(target)
    assert written == target
    assert json.loads(target.read_text(encoding="utf-8")) == RULES
    assert rules.load_rules_json(target) == RULES


def test_exporting_to_default_path_is_idempotent():
    before = rules.RULES_FIXTURE_PATH.read_text(encoding="utf-8")
    written = rules.export_rules_json()
    after = written.read_text(encoding="utf-8")
    assert written == rules.RULES_FIXTURE_PATH
    assert after == before
    assert json.loads(after) == RULES


def test_get_rule_returns_records_and_rejects_unknown_characters():
    assert rules.get_rule("ب") is RULES["ب"]
    with pytest.raises(KeyError):
        rules.get_rule("A")
