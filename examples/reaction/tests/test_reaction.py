"""
Structural and integration tests for the reaction-time game example.
Compilation check plus expected words plus behavioural checks of the
pure words.

Big-text rendering (READY..., the digit, GREAT! / WRONG!) is verified
via Forth-side `attr@` queries that bounce attribute bytes back out
through `u.` so we can read them in the captured output.

The simulator's TEST_FONT replicates each char's code 8 times as its
glyph, so the bit pattern of c is also the bit pattern of every row
of c's glyph. That makes the lit / unlit cells under the 8x8
attribute block predictable from c alone.
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


BRIGHT_YELLOW_PAPER = (6 << 3) | 64
BRIGHT_CYAN_PAPER = (5 << 3) | 64
BRIGHT_GREEN_PAPER = (4 << 3) | 64
BRIGHT_RED_PAPER = (2 << 3) | 64
WHITE_PAPER = (7 << 3) | 0


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
        "glyph-addr", "bit-on?", "big-colours", "big-emit", "big-type",
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

    @pytest.mark.parametrize("digit,col_in_glyph", [
        # '5' = 0b00110101 → lit at glyph cols 2, 3, 5, 7
        (5, 2),
        (5, 3),
        (5, 5),
        (5, 7),
        # '0' = 0b00110000 → lit at glyph cols 2, 3
        (0, 2),
        (0, 3),
        # '9' = 0b00111001 → lit at glyph cols 2, 3, 4, 7
        (9, 2),
        (9, 4),
    ])
    def test_show_digit_paints_lit_cells_bright_cyan(self, digit, col_in_glyph):
        col = 12 + col_in_glyph
        out = self._run(f"{digit} show-digit {col} 4 attr@ u.")
        assert out == f"{BRIGHT_CYAN_PAPER} ".encode(), (
            f"show-digit {digit}: lit glyph col {col_in_glyph} "
            f"(screen col {col}, row 4) should be bright-cyan paper"
        )

    @pytest.mark.parametrize("digit,col_in_glyph", [
        # '5' = 0b00110101 → unlit at glyph cols 0, 1, 4, 6
        (5, 0),
        (5, 1),
        (5, 4),
        (5, 6),
        # '0' = 0b00110000 → unlit at most cols
        (0, 0),
        (0, 7),
    ])
    def test_show_digit_unlit_cells_blend_with_paper(self, digit, col_in_glyph):
        col = 12 + col_in_glyph
        out = self._run(f"{digit} show-digit {col} 4 attr@ u.")
        assert out == f"{WHITE_PAPER} ".encode(), (
            f"show-digit {digit}: unlit glyph col {col_in_glyph} "
            f"should blend with the white cls paper"
        )

    def test_show_digit_does_not_paint_outside_its_block(self):
        out = self._run("5 show-digit 11 4 attr@ u.")
        assert out == b"0 ", (
            "show-digit at base col 12 should leave column 11 untouched (zero)"
        )

    def test_show_ready_paints_R_lit_cell_yellow(self):
        # 'R' = 82 = 0b01010010 → lit at glyph cols 1, 3, 6
        # show-ready places "READ" at (0, 0): 'R' occupies cols 0-7
        out = self._run("show-ready 1 0 attr@ u.")
        assert out == f"{BRIGHT_YELLOW_PAPER} ".encode(), (
            "show-ready: 'R' at col 0 has a lit pixel at glyph col 1, "
            "which should be bright-yellow paper"
        )

    def test_show_ready_paints_second_line_at_row_8(self):
        # 'Y' = 89 = 0b01011001 → lit at glyph cols 1, 3, 4, 7
        # "Y..." starts at (0, 8): 'Y' occupies cols 0-7
        out = self._run("show-ready 1 8 attr@ u.")
        assert out == f"{BRIGHT_YELLOW_PAPER} ".encode(), (
            "show-ready: 'Y' at row 8 has a lit pixel at glyph col 1, "
            "which should be bright-yellow paper"
        )

    @pytest.mark.parametrize("correct,expected_paper,letter,col_in_block", [
        # 'G' = 71 = 0b01000111 → lit at cols 1, 5, 6, 7
        (-1, BRIGHT_GREEN_PAPER, "G", 5),
        # 'W' = 87 = 0b01010111 → lit at cols 1, 3, 5, 6, 7
        (0,  BRIGHT_RED_PAPER,   "W", 5),
    ])
    def test_show_verdict_uses_correct_colour(
        self, correct, expected_paper, letter, col_in_block
    ):
        # Top line starts at (4, 0).  `correct` is the flag passed to
        # show-verdict — non-zero → GRE..., zero → WRO...
        col = 4 + col_in_block
        out = self._run(f"{correct} show-verdict {col} 0 attr@ u.")
        assert out == f"{expected_paper} ".encode(), (
            f"show-verdict {correct}: lit pixel of '{letter}' at "
            f"col {col} should be paper byte {expected_paper}"
        )

    def test_show_verdict_correct_paints_second_line(self):
        # 'A' = 65 = 0b01000001 → lit at glyph cols 1, 7
        # "AT!" starts at (4, 8): 'A' occupies cols 4..11, lit at col 5
        out = self._run("-1 show-verdict 5 8 attr@ u.")
        assert out == f"{BRIGHT_GREEN_PAPER} ".encode(), (
            "show-verdict correct: second line 'AT!' at row 8 — 'A' lit "
            "pixel should be bright-green paper"
        )

    def test_show_verdict_wrong_paints_second_line(self):
        # 'N' = 78 = 0b01001110 → lit at glyph cols 1, 4, 5, 6
        # "NG!" starts at (4, 8): 'N' lit at col 4+1 = 5
        out = self._run("0 show-verdict 5 8 attr@ u.")
        assert out == f"{BRIGHT_RED_PAPER} ".encode(), (
            "show-verdict wrong: second line 'NG!' at row 8 — 'N' lit "
            "pixel should be bright-red paper"
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
