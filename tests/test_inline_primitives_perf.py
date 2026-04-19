"""
Benchmarks asserting that the primitive inliner actually reduces tick counts for inlinable colons and leaves non-inlinable ones unchanged.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import DEFAULT_ORIGIN, Compiler
from zt.sim import Z80, _read_data_stack


_BENCH_SOURCE = ": inc 1+ ; : main 0 500 0 do inc loop halt ;"
_BENCH_EXPECTED_STACK = [500]


def _compile_and_count_ticks(
    source: str, **flags,
) -> tuple[list[int], int]:
    c = Compiler(origin=DEFAULT_ORIGIN, **flags)
    c.compile_source(source)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(DEFAULT_ORIGIN, image)
    m.pc = c.words["_start"].address
    m.run(max_ticks=10_000_000)
    if not m.halted:
        raise TimeoutError("benchmark program did not halt within tick budget")
    stack = _read_data_stack(m, c.data_stack_top, False)
    return stack, m._ticks


def _ticks(source: str, **flags) -> int:
    _, ticks = _compile_and_count_ticks(source, **flags)
    return ticks


def _stack(source: str, **flags) -> list[int]:
    stack, _ = _compile_and_count_ticks(source, **flags)
    return stack


class TestBenchmarkSanity:

    def test_threaded_run_leaves_expected_stack(self):
        assert _stack(_BENCH_SOURCE) == _BENCH_EXPECTED_STACK, \
            f"threaded bench should leave {_BENCH_EXPECTED_STACK} on the stack"

    def test_inlined_run_leaves_same_stack(self):
        threaded = _stack(_BENCH_SOURCE, inline_primitives=False)
        inlined = _stack(_BENCH_SOURCE, inline_primitives=True)
        assert threaded == inlined, (
            f"inline_primitives must preserve semantics; "
            f"threaded={threaded}, inlined={inlined}"
        )


class TestInlinedRunsFewerTicks:

    def test_inlined_strictly_faster_than_threaded(self):
        threaded = _ticks(_BENCH_SOURCE, inline_primitives=False)
        inlined = _ticks(_BENCH_SOURCE, inline_primitives=True)
        assert inlined < threaded, (
            f"inline_primitives should strictly reduce tick count on a tight loop; "
            f"threaded={threaded}, inlined={inlined}"
        )

    def test_inlined_at_least_30_percent_faster(self):
        threaded = _ticks(_BENCH_SOURCE, inline_primitives=False)
        inlined = _ticks(_BENCH_SOURCE, inline_primitives=True)
        speedup_pct = 100 * (threaded - inlined) / threaded
        assert speedup_pct >= 30, (
            f"inline_primitives should deliver >=30% speedup on a tight 1+ loop; "
            f"got {speedup_pct:.1f}% (threaded={threaded}, inlined={inlined})"
        )


class TestSpeedupGeneralisesAcrossInlinableColons:

    @pytest.mark.parametrize("source,expected_stack", [
        (": inc 1+ ; : main 0 500 0 do inc loop halt ;",
         [500]),
        (": dbl dup + ; : main 1 300 0 do dbl drop 1 loop drop halt ;",
         []),
        (": quad dup + dup + ; : main 1 200 0 do quad drop 1 loop drop halt ;",
         []),
        (": add2 1+ 1+ ; : main 0 250 0 do add2 loop halt ;",
         [500]),
    ], ids=["one-plus", "double", "quadruple", "add-two"])
    def test_inlined_faster_for_various_inlinable_bodies(
        self, source, expected_stack,
    ):
        threaded_stack, threaded_ticks = _compile_and_count_ticks(
            source, inline_primitives=False,
        )
        inlined_stack, inlined_ticks = _compile_and_count_ticks(
            source, inline_primitives=True,
        )
        assert threaded_stack == expected_stack, (
            f"threaded run of {source!r} should leave {expected_stack}, "
            f"got {threaded_stack}"
        )
        assert inlined_stack == threaded_stack, (
            f"inlined run of {source!r} must match threaded result; "
            f"threaded={threaded_stack}, inlined={inlined_stack}"
        )
        assert inlined_ticks < threaded_ticks, (
            f"inline_primitives should reduce ticks for {source!r}; "
            f"threaded={threaded_ticks}, inlined={inlined_ticks}"
        )


class TestOrthogonalitySpeedup:

    def test_inline_primitives_reduces_ticks_on_top_of_inline_next(self):
        next_only = _ticks(
            _BENCH_SOURCE, inline_next=True, inline_primitives=False,
        )
        both = _ticks(
            _BENCH_SOURCE, inline_next=True, inline_primitives=True,
        )
        assert both < next_only, (
            "stacking --inline-primitives on --inline-next should further reduce ticks; "
            f"next_only={next_only}, both={both}"
        )

    def test_inline_primitives_reduces_ticks_with_optimizer_off(self):
        threaded = _ticks(
            _BENCH_SOURCE, optimize=False, inline_primitives=False,
        )
        inlined = _ticks(
            _BENCH_SOURCE, optimize=False, inline_primitives=True,
        )
        assert inlined < threaded, (
            "inline_primitives should still help when peephole optimizer is off; "
            f"threaded={threaded}, inlined={inlined}"
        )


class TestNonInlinableColonSeesNoSpeedup:

    def test_colon_with_do_loop_inside_is_not_inlinable(self):
        src = ": main 0 500 0 do 1+ loop halt ;"
        threaded = _ticks(src, inline_primitives=False)
        inlined = _ticks(src, inline_primitives=True)
        assert threaded == inlined, (
            "a main consisting only of DO/LOOP (not inlinable, no inlinable callees) "
            "should produce identical tick counts with and without inline_primitives; "
            f"threaded={threaded}, inlined={inlined}"
        )
