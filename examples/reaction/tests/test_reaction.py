"""
Structural and integration tests for the reaction-time game example.
Compilation check plus expected words plus behavioural checks of the
pure words.

Big-text rendering (READY..., the digit, GREAT! / WRONG!) is verified
via Forth-side queries that bounce values out through `u.` so we can
read them in the captured output:

- attr@ for the per-cell colour byte (now ink + paper + bright);
- c@ for the pixel-layer byte the renderer wrote, picked from the
  4-entry half-row table ($00, $0F, $F0, $FF).

The simulator's TEST_FONT replicates each char's code 8 times as its
glyph, so the bit pattern of c is also the bit pattern of every row
of c's glyph.  That makes both pixel layers and attribute bytes
predictable from c alone.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler, compile_and_run_with_output


EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"
APP = EXAMPLE_DIR / "app" / "reaction.fs"
LIB_RNG = EXAMPLE_DIR / "lib" / "rng.fs"
LIB_TIMING = EXAMPLE_DIR / "lib" / "timing.fs"
LIB_BIG_TEXT = EXAMPLE_DIR / "lib" / "big-text.fs"


def attr_byte(ink: int, paper: int, bright: bool = True) -> int:
    return ink | (paper << 3) | (64 if bright else 0)


YELLOW_ON_WHITE = attr_byte(6, 7)
CYAN_ON_WHITE = attr_byte(5, 7)
GREEN_ON_WHITE = attr_byte(4, 7)
RED_ON_WHITE = attr_byte(2, 7)


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


class TestFiles:

    @pytest.mark.parametrize("relpath", [
        "main.fs",
        "app/reaction.fs",
        "lib/rng.fs",
        "lib/timing.fs",
        "lib/big-text.fs",
    ])
    def test_example_files_exist(self, relpath):
        assert (EXAMPLE_DIR / relpath).is_file(), (
            f"reaction example should ship {relpath}"
        )


class TestCompiles:

    def test_main_defined(self, built_compiler):
        assert "main" in built_compiler.words, (
            "reaction example should produce a 'main' word"
        )

    @pytest.mark.parametrize("word", [
        "rnd", "rnd-seed", "seed!", "random",
        "ms-per-frame", "frames>ms",
        "glyph-addr", "bit-on?", "leading-blanks",
        "half-row-byte", "cell-bits", "cell-pix-addr", "paint-cell",
        "big-colours", "big-emit", "big-type",
        "digit>char", "pick-digit", "random-delay",
        "pause", "wait-for-key",
        "show-ready", "show-digit", "show-great", "show-wrong",
        "show-verdict",
        "check-key",
        "total-ms", "round-count", "reset-stats",
        "record-round", "avg-ms",
        "print-result", "print-avg", "at-stats",
        "finish-round", "play-round", "game-loop",
    ])
    def test_expected_words_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"reaction example should define '{word}'"
        )

    def test_rnd_seed_is_a_variable(self, built_compiler):
        assert built_compiler.words["rnd-seed"].kind == "variable", (
            "rnd-seed should be a variable"
        )

    def test_ms_per_frame_is_a_constant(self, built_compiler):
        assert built_compiler.words["ms-per-frame"].kind == "constant", (
            "ms-per-frame should be a constant"
        )

    def test_require_dedup_loads_rng_once(self, built_compiler):
        rng_paths = [p for p in built_compiler.include_resolver.seen_paths()
                     if p.name == "rng.fs"]
        assert len(rng_paths) == 1, (
            "rng.fs should be canonicalized to a single include entry"
        )

    def test_verdict_word_no_longer_exists(self, built_compiler):
        assert "verdict" not in built_compiler.words, (
            "the old text-emitting 'verdict' word should have been replaced "
            "by show-verdict"
        )


class TestBehaviour:

    def _run(self, snippet: str, **kw) -> bytes:
        source = f"""
        require {APP}
        : main {snippet} halt ;
        """
        _, out = compile_and_run_with_output(source, stdlib=True, **kw)
        return out

    @pytest.mark.parametrize("frames,expected_ms", [
        (0, b"0 "),
        (1, b"20 "),
        (25, b"500 "),
        (100, b"2000 "),
    ])
    def test_frames_to_ms_prints_expected(self, frames, expected_ms):
        out = self._run(f"{frames} frames>ms u.")
        assert out == expected_ms, (
            f"{frames} frames>ms u. should emit {expected_ms!r}"
        )

    def test_print_result_format(self):
        out = self._run("125 print-result")
        assert out == b"reacted in 125 ms\r", (
            "print-result should emit 'reacted in N ms' with a trailing cr"
        )

    def test_pick_digit_is_always_single_digit(self):
        out = self._run(
            "1 seed! 16 0 do pick-digit digit>char emit loop"
        )
        assert len(out) == 16, "16 calls should emit 16 chars"
        assert all(ch in b"0123456789" for ch in out), (
            "every pick-digit + digit>char output should be an ASCII digit"
        )

    def test_seeded_rnd_is_deterministic(self):
        first = self._run("1 seed! rnd u. rnd u. rnd u.")
        second = self._run("1 seed! rnd u. rnd u. rnd u.")
        assert first == second, (
            "the same seed should produce the same rnd sequence"
        )

    def test_wait_for_key_returns_key_and_frames_when_key_pending(self):
        out = self._run("wait-for-key u. u.", input_buffer=b"X")
        assert out == b"1 88 ", (
            "wait-for-key should return (key frames); with 'X' pending after "
            "one frame this is (88, 1); u. u. prints frames then key"
        )

    def test_avg_ms_reports_running_average(self):
        out = self._run(
            "reset-stats 100 record-round 200 record-round 300 record-round "
            "avg-ms u."
        )
        assert out == b"200 ", (
            "avg-ms over (100, 200, 300) should print 200"
        )

    def test_reset_stats_zeroes_counters(self):
        out = self._run(
            "500 record-round reset-stats "
            "total-ms @ u. round-count @ u."
        )
        assert out == b"0 0 ", (
            "reset-stats should clear both total-ms and round-count"
        )

    @pytest.mark.parametrize("digit,addr,expected", [
        # '5' = 0b00110101, leading=2 → shifted = 0b11010100 = $D4
        # cell-col 0: bits 7,6 = (1,1) → idx 3 → $FF
        # cell-col 1: bits 5,4 = (0,1) → idx 1 → $0F
        # cell-col 2: bits 3,2 = (0,1) → idx 1 → $0F
        # cell-col 3: bits 1,0 = (0,0) → idx 0 → $00
        (5, 0x4000, 0xFF),
        (5, 0x4001, 0x0F),
        (5, 0x4002, 0x0F),
        (5, 0x4003, 0x00),
        # '0' = 0b00110000, leading=2 → shifted = 0b11000000 = $C0
        # cell-col 0 only is lit (idx 3 → $FF); the rest are $00.
        (0, 0x4000, 0xFF),
        (0, 0x4001, 0x00),
    ])
    def test_show_digit_pixel_layer(self, digit, addr, expected):
        out = self._run(f"{digit} show-digit {addr} c@ u.")
        assert out == f"{expected} ".encode(), (
            f"show-digit {digit}: pixel byte at {addr:#06x} should be "
            f"{expected:#04x}"
        )

    def test_show_digit_attribute_is_cyan_on_white(self):
        out = self._run("5 show-digit 0 0 attr@ u.")
        assert out == f"{CYAN_ON_WHITE} ".encode(), (
            "show-digit: every cell of the digit's 4x4 block carries the "
            "ink-cyan / paper-white / bright attribute byte"
        )

    def test_show_digit_attribute_at_far_corner_of_block(self):
        # cell (3, 3) is the bottom-right of the digit's 4x4 block.
        out = self._run("5 show-digit 3 3 attr@ u.")
        assert out == f"{CYAN_ON_WHITE} ".encode(), (
            "show-digit's attribute byte should fill all 16 cells of the "
            "char block, including the bottom-right corner"
        )

    def test_show_digit_does_not_paint_outside_its_block(self):
        # Cell (4, 0) is one cell to the right of the digit's block;
        # untouched memory after fill-attrs(0) stays 0.
        out = self._run("0 fill-attrs 5 show-digit 4 0 attr@ u.")
        assert out == b"0 ", (
            "show-digit at base col 0 should leave column 4 untouched"
        )

    def test_show_ready_paints_first_char_pixels(self):
        # 'R' = 82 = 0b01010010, leading=1 → shifted = 0b10100100 = $A4
        # cell-col 0: bits 7,6 = (1,0) → idx 2 → $F0
        out = self._run("show-ready $4000 c@ u.")
        assert out == b"240 ", (
            "show-ready: first cell of 'R' should write $F0 (= 240) to the "
            "pixel layer at $4000"
        )

    def test_show_ready_attribute_is_yellow_on_white(self):
        out = self._run("show-ready 0 0 attr@ u.")
        assert out == f"{YELLOW_ON_WHITE} ".encode(), (
            "show-ready: each cell carries ink-yellow / paper-white / bright"
        )

    def test_show_ready_fits_on_one_row(self):
        # 'READY...' is 8 chars * 4 cells = 32 cells = full width;
        # the cell at the rightmost column (31) of row 0 should still
        # carry the attribute, and row 4 (just below the block) shouldn't.
        out = self._run("show-ready 31 0 attr@ u.  0 4 attr@ u.")
        assert out == f"{YELLOW_ON_WHITE} 0 ".encode(), (
            "show-ready should occupy cells (0..31, 0..3) and leave row 4 "
            "untouched"
        )

    @pytest.mark.parametrize("correct,expected_attr,name", [
        (-1, GREEN_ON_WHITE, "GREAT! (correct)"),
        (0,  RED_ON_WHITE,   "WRONG! (wrong)"),
    ])
    def test_show_verdict_attribute(self, correct, expected_attr, name):
        out = self._run(f"{correct} show-verdict 0 0 attr@ u.")
        assert out == f"{expected_attr} ".encode(), (
            f"show-verdict {name}: attribute byte should be {expected_attr}"
        )

    def test_show_verdict_correct_first_char_pixels(self):
        # 'G' = 71 = 0b01000111, leading=1 → shifted = 0b10001110 = $8E
        # cell-col 0: bits 7,6 = (1,0) → idx 2 → $F0
        out = self._run("-1 show-verdict $4000 c@ u.")
        assert out == b"240 ", (
            "show-verdict correct: 'G' lights cell-col 0 with $F0 at $4000"
        )

    def test_show_verdict_wrong_first_char_pixels(self):
        # 'W' = 87 = 0b01010111, leading=1 → shifted = 0b10101110 = $AE
        # cell-col 0: bits 7,6 = (1,0) → idx 2 → $F0
        out = self._run("0 show-verdict $4000 c@ u.")
        assert out == b"240 ", (
            "show-verdict wrong: 'W' lights cell-col 0 with $F0 at $4000"
        )

    @pytest.mark.parametrize("digit,key,expected", [
        (0, b"0", -1),
        (5, b"5", -1),
        (9, b"9", -1),
        (3, b"7",  0),
        (0, b"X",  0),
    ])
    def test_check_key_truth_value(self, digit, key, expected):
        out = self._run(f"{digit} key check-key u.", input_buffer=key)
        # `u.` prints unsigned; -1 (true flag) prints as 65535
        expected_str = b"65535 " if expected == -1 else b"0 "
        assert out == expected_str, (
            f"check-key {digit} vs {key!r} should produce flag {expected}"
        )
