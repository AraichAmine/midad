"""Ground-truth Arabic orthography and character-shape rules.

This module is the single source of truth for the basic Arabic letters and the
most common Lam-Alif ligatures.  Each record describes the Unicode code point,
how the glyph joins to its neighbours, the four positional presentation forms
and the visual features a renderer/verifier can count (dots, loops, ...).

Run this file directly to (re)generate the JSON fixture::

    python pipeline/src/rules.py

The exported fixture is ``fixtures/rules/arabic_character_rules.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Record construction helpers
# ---------------------------------------------------------------------------


def _forms(
    isolated: str,
    initial: str | None = None,
    medial: str | None = None,
    final: str | None = None,
) -> dict[str, str | None]:
    """Build a positional-forms record with the four required keys."""
    return {
        "isolated": isolated,
        "initial": initial,
        "medial": medial,
        "final": final,
    }


def _rule(
    char: str,
    name: str,
    base_unicode: str,
    joining_type: str,
    forms: dict[str, str | None],
    dot_count: int = 0,
    dot_placement: str = "none",
    has_hamza: bool = False,
    has_madda: bool = False,
    has_crossbar: bool = False,
    has_inner_mark: bool = False,
    expected_loop_count: int = 0,
) -> dict[str, Any]:
    """Build and validate a single character-rule record."""
    if joining_type not in {"D", "R", "U"}:
        raise ValueError(f"{name}: invalid joining_type {joining_type!r}")
    if dot_placement not in {"above", "below", "inside", "none"}:
        raise ValueError(f"{name}: invalid dot_placement {dot_placement!r}")
    if dot_count not in {0, 1, 2, 3}:
        raise ValueError(f"{name}: invalid dot_count {dot_count!r}")
    if dot_count > 0 and dot_placement == "none":
        raise ValueError(f"{name}: dots require a placement")
    if dot_count == 0 and dot_placement != "none":
        raise ValueError(f"{name}: dot_placement set without dots")
    if joining_type == "D":
        missing = [key for key in ("initial", "medial") if forms.get(key) is None]
        if missing:
            raise ValueError(f"{name}: dual-joining letter missing forms {missing}")
    if joining_type in {"R", "U"}:
        for key in ("initial", "medial"):
            if forms.get(key) is not None:
                raise ValueError(f"{name}: {joining_type} letter must not have {key} form")

    return {
        "char": char,
        "name": name,
        "base_unicode": base_unicode,
        "joining_type": joining_type,
        "forms": {
            "isolated": forms["isolated"],
            "initial": forms["initial"],
            "medial": forms["medial"],
            "final": forms["final"],
        },
        "dot_count": dot_count,
        "dot_placement": dot_placement,
        "has_hamza": has_hamza,
        "has_madda": has_madda,
        "has_crossbar": has_crossbar,
        "has_inner_mark": has_inner_mark,
        "expected_loop_count": expected_loop_count,
    }


# ---------------------------------------------------------------------------
# The 28 basic letters (in standard hijaa' order)
# ---------------------------------------------------------------------------

ARABIC_CHARACTER_RULES: dict[str, dict[str, Any]] = {
    "ا": _rule(
        char="ا",
        name="ARABIC LETTER ALEF",
        base_unicode="0x0627",
        joining_type="R",
        forms=_forms("0xFE8D", final="0xFE8E"),
    ),
    "ب": _rule(
        char="ب",
        name="ARABIC LETTER BEH",
        base_unicode="0x0628",
        joining_type="D",
        forms=_forms("0xFE8F", "0xFE91", "0xFE92", "0xFE90"),
        dot_count=1,
        dot_placement="below",
    ),
    "ت": _rule(
        char="ت",
        name="ARABIC LETTER TEH",
        base_unicode="0x062A",
        joining_type="D",
        forms=_forms("0xFE95", "0xFE97", "0xFE98", "0xFE96"),
        dot_count=2,
        dot_placement="above",
    ),
    "ث": _rule(
        char="ث",
        name="ARABIC LETTER THEH",
        base_unicode="0x062B",
        joining_type="D",
        forms=_forms("0xFE99", "0xFE9B", "0xFE9C", "0xFE9A"),
        dot_count=3,
        dot_placement="above",
    ),
    "ج": _rule(
        char="ج",
        name="ARABIC LETTER JEEM",
        base_unicode="0x062C",
        joining_type="D",
        forms=_forms("0xFE9D", "0xFE9F", "0xFEA0", "0xFE9E"),
        dot_count=1,
        dot_placement="below",
    ),
    "ح": _rule(
        char="ح",
        name="ARABIC LETTER HAH",
        base_unicode="0x062D",
        joining_type="D",
        forms=_forms("0xFEA1", "0xFEA3", "0xFEA4", "0xFEA2"),
    ),
    "خ": _rule(
        char="خ",
        name="ARABIC LETTER KHAH",
        base_unicode="0x062E",
        joining_type="D",
        forms=_forms("0xFEA5", "0xFEA7", "0xFEA8", "0xFEA6"),
        dot_count=1,
        dot_placement="above",
    ),
    "د": _rule(
        char="د",
        name="ARABIC LETTER DAL",
        base_unicode="0x062F",
        joining_type="R",
        forms=_forms("0xFEA9", final="0xFEAA"),
    ),
    "ذ": _rule(
        char="ذ",
        name="ARABIC LETTER THAL",
        base_unicode="0x0630",
        joining_type="R",
        forms=_forms("0xFEAB", final="0xFEAC"),
        dot_count=1,
        dot_placement="above",
    ),
    "ر": _rule(
        char="ر",
        name="ARABIC LETTER REH",
        base_unicode="0x0631",
        joining_type="R",
        forms=_forms("0xFEAD", final="0xFEAE"),
    ),
    "ز": _rule(
        char="ز",
        name="ARABIC LETTER ZAIN",
        base_unicode="0x0632",
        joining_type="R",
        forms=_forms("0xFEAF", final="0xFEB0"),
        dot_count=1,
        dot_placement="above",
    ),
    "س": _rule(
        char="س",
        name="ARABIC LETTER SEEN",
        base_unicode="0x0633",
        joining_type="D",
        forms=_forms("0xFEB1", "0xFEB3", "0xFEB4", "0xFEB2"),
    ),
    "ش": _rule(
        char="ش",
        name="ARABIC LETTER SHEEN",
        base_unicode="0x0634",
        joining_type="D",
        forms=_forms("0xFEB5", "0xFEB7", "0xFEB8", "0xFEB6"),
        dot_count=3,
        dot_placement="above",
    ),
    "ص": _rule(
        char="ص",
        name="ARABIC LETTER SAD",
        base_unicode="0x0635",
        joining_type="D",
        forms=_forms("0xFEB9", "0xFEBB", "0xFEBC", "0xFEBA"),
        expected_loop_count=1,
    ),
    "ض": _rule(
        char="ض",
        name="ARABIC LETTER DAD",
        base_unicode="0x0636",
        joining_type="D",
        forms=_forms("0xFEBD", "0xFEBF", "0xFEC0", "0xFEBE"),
        dot_count=1,
        dot_placement="above",
        expected_loop_count=1,
    ),
    "ط": _rule(
        char="ط",
        name="ARABIC LETTER TAH",
        base_unicode="0x0637",
        joining_type="D",
        forms=_forms("0xFEC1", "0xFEC3", "0xFEC4", "0xFEC2"),
        has_crossbar=True,
        expected_loop_count=1,
    ),
    "ظ": _rule(
        char="ظ",
        name="ARABIC LETTER ZAH",
        base_unicode="0x0638",
        joining_type="D",
        forms=_forms("0xFEC5", "0xFEC7", "0xFEC8", "0xFEC6"),
        dot_count=1,
        dot_placement="above",
        has_crossbar=True,
        expected_loop_count=1,
    ),
    "ع": _rule(
        char="ع",
        name="ARABIC LETTER AIN",
        base_unicode="0x0639",
        joining_type="D",
        forms=_forms("0xFEC9", "0xFECB", "0xFECC", "0xFECA"),
    ),
    "غ": _rule(
        char="غ",
        name="ARABIC LETTER GHAIN",
        base_unicode="0x063A",
        joining_type="D",
        forms=_forms("0xFECD", "0xFECF", "0xFED0", "0xFECE"),
        dot_count=1,
        dot_placement="above",
    ),
    "ف": _rule(
        char="ف",
        name="ARABIC LETTER FEH",
        base_unicode="0x0641",
        joining_type="D",
        forms=_forms("0xFED1", "0xFED3", "0xFED4", "0xFED2"),
        dot_count=1,
        dot_placement="above",
        expected_loop_count=1,
    ),
    "ق": _rule(
        char="ق",
        name="ARABIC LETTER QAF",
        base_unicode="0x0642",
        joining_type="D",
        forms=_forms("0xFED5", "0xFED7", "0xFED8", "0xFED6"),
        dot_count=2,
        dot_placement="above",
        expected_loop_count=1,
    ),
    "ك": _rule(
        char="ك",
        name="ARABIC LETTER KAF",
        base_unicode="0x0643",
        joining_type="D",
        forms=_forms("0xFED9", "0xFEDB", "0xFEDC", "0xFEDA"),
        has_crossbar=True,
        has_inner_mark=True,
    ),
    "ل": _rule(
        char="ل",
        name="ARABIC LETTER LAM",
        base_unicode="0x0644",
        joining_type="D",
        forms=_forms("0xFEDD", "0xFEDF", "0xFEE0", "0xFEDE"),
    ),
    "م": _rule(
        char="م",
        name="ARABIC LETTER MEEM",
        base_unicode="0x0645",
        joining_type="D",
        forms=_forms("0xFEE1", "0xFEE3", "0xFEE4", "0xFEE2"),
        expected_loop_count=1,
    ),
    "ن": _rule(
        char="ن",
        name="ARABIC LETTER NOON",
        base_unicode="0x0646",
        joining_type="D",
        forms=_forms("0xFEE5", "0xFEE7", "0xFEE8", "0xFEE6"),
        dot_count=1,
        dot_placement="above",
    ),
    "ه": _rule(
        char="ه",
        name="ARABIC LETTER HEH",
        base_unicode="0x0647",
        joining_type="D",
        forms=_forms("0xFEE9", "0xFEEB", "0xFEEC", "0xFEEA"),
        expected_loop_count=1,
    ),
    "و": _rule(
        char="و",
        name="ARABIC LETTER WAW",
        base_unicode="0x0648",
        joining_type="R",
        forms=_forms("0xFEED", final="0xFEEE"),
        expected_loop_count=1,
    ),
    "ي": _rule(
        char="ي",
        name="ARABIC LETTER YEH",
        base_unicode="0x064A",
        joining_type="D",
        forms=_forms("0xFEF1", "0xFEF3", "0xFEF4", "0xFEF2"),
        dot_count=2,
        dot_placement="below",
    ),
    # ------------------------------------------------------------------
    # Additional glyphs
    # ------------------------------------------------------------------
    "ة": _rule(
        char="ة",
        name="ARABIC LETTER TEH MARBUTA",
        base_unicode="0x0629",
        joining_type="R",
        forms=_forms("0xFE93", final="0xFE94"),
        dot_count=2,
        dot_placement="above",
        expected_loop_count=1,
    ),
    "ى": _rule(
        char="ى",
        name="ARABIC LETTER ALEF MAKSURA",
        base_unicode="0x0649",
        joining_type="R",
        forms=_forms("0xFEEF", final="0xFEF0"),
    ),
    "ء": _rule(
        char="ء",
        name="ARABIC LETTER HAMZA",
        base_unicode="0x0621",
        joining_type="U",
        forms=_forms("0xFE80"),
        has_hamza=True,
    ),
    "أ": _rule(
        char="أ",
        name="ARABIC LETTER ALEF WITH HAMZA ABOVE",
        base_unicode="0x0623",
        joining_type="R",
        forms=_forms("0xFE83", final="0xFE84"),
        has_hamza=True,
    ),
    "إ": _rule(
        char="إ",
        name="ARABIC LETTER ALEF WITH HAMZA BELOW",
        base_unicode="0x0625",
        joining_type="R",
        forms=_forms("0xFE87", final="0xFE88"),
        has_hamza=True,
    ),
    "آ": _rule(
        char="آ",
        name="ARABIC LETTER ALEF WITH MADDA ABOVE",
        base_unicode="0x0622",
        joining_type="R",
        forms=_forms("0xFE81", final="0xFE82"),
        has_madda=True,
    ),
    # Lam-Alif ligatures: only isolated and final forms exist.
    "لا": _rule(
        char="لا",
        name="ARABIC LIGATURE LAM WITH ALEF",
        base_unicode="0xFEFB",
        joining_type="R",
        forms=_forms("0xFEFB", final="0xFEFC"),
    ),
    "لأ": _rule(
        char="لأ",
        name="ARABIC LIGATURE LAM WITH ALEF WITH HAMZA ABOVE",
        base_unicode="0xFEF7",
        joining_type="R",
        forms=_forms("0xFEF7", final="0xFEF8"),
        has_hamza=True,
    ),
    "لإ": _rule(
        char="لإ",
        name="ARABIC LIGATURE LAM WITH ALEF WITH HAMZA BELOW",
        base_unicode="0xFEF9",
        joining_type="R",
        forms=_forms("0xFEF9", final="0xFEFA"),
        has_hamza=True,
    ),
    "لآ": _rule(
        char="لآ",
        name="ARABIC LIGATURE LAM WITH ALEF WITH MADDA ABOVE",
        base_unicode="0xFEF5",
        joining_type="R",
        forms=_forms("0xFEF5", final="0xFEF6"),
        has_madda=True,
    ),
}


# The 28 basic letters, in hijaa' order.  Kept explicit so tests and callers do
# not have to rely on dictionary insertion order.
BASIC_LETTERS: tuple[str, ...] = (
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

LIGATURES: tuple[str, ...] = ("لا", "لأ", "لإ", "لآ")
ADDITIONAL_GLYPHS: tuple[str, ...] = ("ة", "ى", "ء", "أ", "إ", "آ")

# Repository layout: <repo>/pipeline/src/rules.py
REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_FIXTURE_PATH = REPO_ROOT / "fixtures" / "rules" / "arabic_character_rules.json"


def get_rule(char: str) -> dict[str, Any]:
    """Return the rule record for a single character or ligature.

    Raises ``KeyError`` when the character is not covered by the registry.
    """
    return ARABIC_CHARACTER_RULES[char]


def export_rules_json(path: str | Path | None = None) -> Path:
    """Write the registry to JSON and return the path that was written."""
    target = Path(path) if path is not None else RULES_FIXTURE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(
            ARABIC_CHARACTER_RULES,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        handle.write("\n")
    return target


def load_rules_json(path: str | Path | None = None) -> dict[str, Any]:
    """Load rules from JSON (defaults to the checked-in fixture)."""
    source = Path(path) if path is not None else RULES_FIXTURE_PATH
    with source.open(encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    written = export_rules_json()
    print(f"Wrote {len(ARABIC_CHARACTER_RULES)} rules to {written}")
