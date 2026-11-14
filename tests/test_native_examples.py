"""
Whole-program differential tests for the native backend: bundled examples and the
compute benchmarks must behave exactly like their threaded builds, only faster.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from native_harness import compile_program, run_both, run_file

REPO_ROOT = Path(__file__).parent.parent
EXAMPLES = REPO_ROOT / "examples"
BENCHMARKS = Path(__file__).parent / "benchmarks"

HALTING_EXAMPLES = [
    "reaction/bench.fs",
    "sierpinski/main.fs",
    "structs/main.fs",
    "sprite-demo/main.fs",
    "asm-primitives/main.fs",
]
SLOW_HALTING_EXAMPLES = ["arkanoid/main.fs"]
BENCHMARK_SPEEDUPS = {"sieve": 3.0, "fib": 3.0, "gcd": 3.0, "bubble": 4.0}
DISPATCH_HEAVY_EXAMPLES = {"reaction/bench.fs": 3.0, "sierpinski/main.fs": 2.2}

BANKED_PROGRAM = """
0 in-bank create weights $11 c, $22 c, $33 c, end-bank
3 in-bank create biases  $44 c, $55 c, end-bank
variable sum
: weight@  ( i -- b )  0 bank!  weights + c@ ;
: bias@    ( i -- b )  3 bank!  biases + c@ ;
: main  0 weight@ 2 weight@ 1 bias@ + + sum !  sum @ halt ;
"""


@lru_cache(maxsize=None)
def _both(path: Path, max_ticks: int = 60_000_000):
    options = {"include_dirs": (EXAMPLES,), "max_ticks": max_ticks}
    return (
        run_file(path, native=False, **options),
        run_file(path, native=True, **options),
    )


class TestHaltingExamples:

    @pytest.mark.parametrize("example", HALTING_EXAMPLES)
    def test_threaded_example_halts(self, example):
        threaded, _ = _both(EXAMPLES / example)
        assert threaded.halted, f"{example} should halt under the threaded reference build"

    @pytest.mark.parametrize("example", HALTING_EXAMPLES)
    def test_native_example_is_indistinguishable(self, example):
        threaded, native = _both(EXAMPLES / example)
        assert native.observable == threaded.observable, \
            f"native {example} should leave the same stack, screen and port writes"

    @pytest.mark.parametrize("example", HALTING_EXAMPLES)
    def test_native_example_is_faster(self, example):
        threaded, native = _both(EXAMPLES / example)
        assert native.t_states < threaded.t_states, \
            f"native {example} should take fewer T-states than the threaded build"

    @pytest.mark.parametrize("example,floor", DISPATCH_HEAVY_EXAMPLES.items())
    def test_dispatch_heavy_example_meets_speedup_floor(self, example, floor):
        threaded, native = _both(EXAMPLES / example)
        assert threaded.t_states >= floor * native.t_states, \
            f"native {example} should be at least {floor}x faster than threaded"


@pytest.mark.slow
class TestSlowHaltingExamples:

    @pytest.mark.parametrize("example", SLOW_HALTING_EXAMPLES)
    def test_native_example_is_indistinguishable(self, example):
        threaded, native = _both(EXAMPLES / example)
        assert native.observable == threaded.observable, \
            f"native {example} should leave the same stack, screen and port writes"

    @pytest.mark.parametrize("example", SLOW_HALTING_EXAMPLES)
    def test_native_example_at_least_triples_in_speed(self, example):
        threaded, native = _both(EXAMPLES / example)
        assert threaded.t_states >= 3 * native.t_states, \
            f"native {example} should be at least 3x faster than threaded"


class TestBenchmarks:

    @pytest.mark.parametrize("name", BENCHMARK_SPEEDUPS)
    def test_benchmark_result_is_identical(self, name):
        threaded, native = _both(BENCHMARKS / f"{name}.fs")
        assert native.observable == threaded.observable, \
            f"native {name} benchmark should compute the same result"

    @pytest.mark.parametrize("name", BENCHMARK_SPEEDUPS)
    def test_benchmark_halts(self, name):
        _, native = _both(BENCHMARKS / f"{name}.fs")
        assert native.halted, f"native {name} benchmark should run to completion"

    @pytest.mark.parametrize("name,floor", BENCHMARK_SPEEDUPS.items())
    def test_benchmark_meets_speedup_floor(self, name, floor):
        threaded, native = _both(BENCHMARKS / f"{name}.fs")
        assert threaded.t_states >= floor * native.t_states, \
            f"native {name} should be at least {floor}x faster than threaded " \
            f"({threaded.t_states} vs {native.t_states} T-states)"


class TestBankedData:

    def test_native_reads_banked_data_like_threaded(self):
        threaded, native = run_both(BANKED_PROGRAM, mode="128k")
        assert native.observable == threaded.observable, \
            "native 128K build should read banked data exactly like the threaded build"

    def test_banked_program_computes_expected_sum(self):
        _, native = run_both(BANKED_PROGRAM, mode="128k")
        assert native.stack == (0x11 + 0x33 + 0x55,), \
            "native build should sum the bytes fetched from banks 0 and 3"

    def test_native_leaves_bank_images_untouched(self):
        compiler = compile_program(BANKED_PROGRAM, mode="128k")
        before = compiler.banks()
        compiler.build_native()
        assert compiler.banks() == before, \
            "the native build should not move or rewrite banked data"


class TestUnsupportedPrograms:

    @pytest.mark.parametrize("source,reason", [
        ("0 in-bank : banked 1 ; end-bank : main banked halt ;", "banked colon"),
        (": target 1 ; ' target constant xt : main xt execute halt ;", "tick"),
        ("::: grab push_ix pop_ix ; : main grab halt ;", "IX"),
    ], ids=["banked-colon", "tick-as-constant", "asm-word-using-ix"])
    def test_unsupported_program_is_rejected_not_miscompiled(self, source, reason):
        compiler = compile_program(source, mode="128k")
        with pytest.raises(NotImplementedError, match=reason):
            compiler.build_native()
