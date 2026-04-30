"""
Structural and integration tests for the reaction-time game example.
Mirrors the shape of test_examples_plasma.py: compilation check plus expected
words. Behavioural checks target pure words that don't depend on `wait-frame`
(which halts the simulator).
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
        "digit>char", "show-digit", "pick-digit",
        "random-delay", "pause", "wait-for-key",
        "check-key", "verdict",
        "total-ms", "round-count", "reset-stats",
        "record-round", "avg-ms",
        "print-result", "print-avg",
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


class TestBehaviour:

    def _run(self, snippet: str, **kw) -> bytes:
        source = f"""
        require {APP}
        : main {snippet} halt ;
        """
        _, out = compile_and_run_with_output(source, stdlib=True, **kw)
        return out

    @pytest.mark.parametrize("digit,char", [
        (0, b"0"), (1, b"1"), (5, b"5"), (9, b"9"),
    ])
    def test_show_digit_emits_ascii(self, digit, char):
        out = self._run(f"{digit} show-digit")
        assert out == char, f"show-digit {digit} should emit {char!r}"

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
        out = self._run("1 seed! 16 0 do pick-digit show-digit loop")
        assert len(out) == 16, "16 calls should emit 16 chars"
        assert all(ch in b"0123456789" for ch in out), (
            "every pick-digit output should be an ASCII digit"
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

    @pytest.mark.parametrize("digit,key,expected", [
        (0, b"0", b"correct! "),
        (5, b"5", b"correct! "),
        (9, b"9", b"correct! "),
        (3, b"7", b"wrong! "),
        (0, b"X", b"wrong! "),
    ])
    def test_verdict_matches_digit_against_typed_key(self, digit, key, expected):
        out = self._run(f"{digit} key check-key verdict", input_buffer=key)
        assert out == expected, (
            f"typing {key!r} when {digit} is shown should print {expected!r}"
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
