# Task Specification: Milestone 3 — RTL Shaping & Baseline Welding Engine

## Target Files:
1. `pipeline/src/shaper.py` (New module)
2. `pipeline/tests/test_milestone3_welding.py` (New test suite)
3. `fixtures/golden/welded_50_words.json` (New golden fixture)

## Context & Existing Infrastructure:
- Font: `fixtures/fonts/NotoNaskhArabic-Regular.ttf`
- Character rules: `pipeline/src/rules.py` (`ARABIC_CHARACTER_RULES`)
- Extractor: `pipeline/src/extractor.py` (`shape_text(text, font_path)`)
- Directed glyphs: `fixtures/skeletons/directed_glyphs.json` (119 glyph forms with `directed_strokes`, `delayed_strokes`, `anchors`)
- Types & Invariant definitions: `engine/src/types.ts` and `engine/src/validator.ts`

## Mathematical Invariants & Requirements:
1. **PAW Partitioning**:
   - Non-connecting Arabic characters (`ا`, `أ`, `إ`, `آ`, `د`, `ذ`, `ر`, `ز`, `و`, `ء`) break cursive continuity.
   - Any character following a non-connecting character starts a new PAW (Piece of Arabic Word).
   - Spaces and punctuation also create PAW boundaries.

2. **Cursive Baseline Welding**:
   - Within each PAW, letters connect along the baseline from right to left.
   - Letter $i$ ends at `exit_anchor` $[x_e, y_e]$ (in absolute canvas coords).
   - Letter $i+1$ begins at `entry_anchor` $[x_a, y_a]$ (in absolute canvas coords).
   - The weld bridges from Letter $i$'s exit to Letter $i+1$'s entry:
     - If the gap $\Delta = \|[x_e, y_e] - [x_a, y_a]\| > 0.01$, insert a smooth cubic Bézier or tangent-aligned line segment joining $[x_e, y_e]$ to $[x_a, y_a]$ such that $C^0$ continuity has $\Delta < 0.05$ font units.
     - $G^1$ tangent continuity: the outgoing tangent of Letter $i$ at exit and incoming tangent of Letter $i+1$ at entry must satisfy $\Delta \theta < 12^\circ$.
   - **Single-M Invariant**: Each PAW baseline trunk MUST be a single continuous SVG path starting with exactly one `M` command and no subsequent `M` commands.

3. **Delayed-Stroke Scheduling**:
   - Delayed marks (dots, hamza, madda, kaf mark) must be positioned in absolute canvas coordinates matching their parent glyphs.
   - Strictly causal: All delayed marks of a PAW must be scheduled strictly AFTER the PAW baseline trunk completes drawing.
   - Ordered temporally by their attachment point $s_{\text{attach}} \in [0, 1]$ or right-to-left sequence.

4. **50-Word Canonical Arabic Corpus**:
   - `shaper.py` must define a canonical list of 50 diverse Arabic words covering all 28 letters across isolated, initial, medial, and final forms, loop letters, multi-stroke letters (Tah, Zah, Lam-Alef), and multiple PAWs per word.
   - Example words: `كتب`, `محمد`, `العربية`, `جميل`, `صابر`, `طالب`, `استقلال`, `خطاط`, `قلم`, `سماء`, `نستعليق`, `حضارة`, `فجر`, `قرآن`, `تاريخ`, `شروق`, `ذهب`, `زمرد`, `ورد`, `زهرة`, etc.
   - Export welded results to `fixtures/golden/welded_50_words.json`.

5. **Test Suite (`pipeline/tests/test_milestone3_welding.py`)**:
   - Test 1: Every PAW in all 50 words has exactly one `M` command.
   - Test 2: $C^0$ positional continuity on all welded joints has distance $\Delta < 0.05$.
   - Test 3: $G^1$ tangent angle continuity on all welded joints has $\Delta \theta < 12^\circ$.
   - Test 4: Delayed stroke temporal causality (all delayed marks start after trunk finish).
   - Test 5: Golden fixture `fixtures/golden/welded_50_words.json` matches regeneration.
