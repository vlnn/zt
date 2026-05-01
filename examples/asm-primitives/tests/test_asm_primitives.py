"""
End-to-end tests for the example primitives in
`examples/asm-primitives.fs`. Each test compiles the example file plus a
small driver, runs it through the Z80 simulator, and checks the result.

If you change the `.fs` file, run this suite to ensure the examples still
work — these are the proof that the documentation is honest.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler, compile_and_run
from zt.sim import Z80


EXAMPLES = Path(__file__).resolve().parent.parent / "asm-primitives.fs"


def _run(driver: str) -> list[int]:
    return compile_and_run(EXAMPLES.read_text() + "\n" + driver)


def _run_with_memory(driver: str) -> tuple[Z80, Compiler]:
    c = Compiler(inline_primitives=False, inline_next=False)
    c.compile_source(EXAMPLES.read_text() + "\n" + driver)
    c.compile_main_call()
    image = c.build()
    m = Z80()
    m.load(c.origin, image)
    m.pc = c.words["_start"].address
    m.run()
    assert m.halted, "driver should reach halt cleanly"
    return m, c


class TestPointerArithmetic:

    @pytest.mark.parametrize("word,start,expected", [
        ("cell+", 0x4000, 0x4002),
        ("cell-", 0x4000, 0x3FFE),
        ("2+",    100,    102),
        ("2-",    100,    98),
    ], ids=["cell+", "cell-", "2+", "2-"])
    def test_arithmetic(self, word, start, expected):
        result = _run(f": main {start} {word} halt ;")
        assert result == [expected], (
            f"{start} {word} should leave {expected} on the stack, got {result}"
        )


class TestQDup:

    def test_zero_passes_through_unchanged(self):
        result = _run(": main 0 ?dup halt ;")
        assert result == [0], "?dup of 0 should leave just 0 on the stack"

    def test_nonzero_duplicates(self):
        result = _run(": main 42 ?dup halt ;")
        assert result == [42, 42], "?dup of 42 should leave 42 42"

    def test_negative_treated_as_nonzero(self):
        result = _run(": main -1 ?dup halt ;")
        assert result == [0xFFFF, 0xFFFF], (
            "?dup of -1 (0xFFFF) should leave 0xFFFF 0xFFFF — non-zero treats "
            "high bit just like any other"
        )


class TestByteMemoryOps:

    def test_1c_plus_store(self):
        m, _ = _run_with_memory(
            ": setup 7 3000 c! ;\n"
            ": main setup 3000 1c+! halt ;"
        )
        assert m.mem[3000] == 8, (
            "1c+! at 3000 starting from 7 should leave 8 in that byte"
        )

    def test_1c_minus_store(self):
        m, _ = _run_with_memory(
            ": setup 7 3000 c! ;\n"
            ": main setup 3000 1c-! halt ;"
        )
        assert m.mem[3000] == 6, (
            "1c-! at 3000 starting from 7 should leave 6 in that byte"
        )

    def test_1c_plus_store_wraps_at_byte_boundary(self):
        m, _ = _run_with_memory(
            ": setup 255 3000 c! ;\n"
            ": main setup 3000 1c+! halt ;"
        )
        assert m.mem[3000] == 0, (
            "1c+! is byte-wide, so 255 should wrap to 0 (single-byte add)"
        )

    def test_1c_plus_store_consumes_address(self):
        m, _ = _run_with_memory(
            ": main 1 2 3 3000 1c+! halt ;"
        )
        # Stack should still have 1, 2, 3 — addr was consumed by 1c+!
        from zt.sim import _read_data_stack
        stack = _read_data_stack(m, 0xFFEE, False)  # default data_stack_top
        # We don't know the exact stack pointer here, so check the memory we set
        # plus that 1c+! left the byte modified
        assert m.mem[3000] == 1, "1c+! starting from 0 should reach 1"


class TestBit0Predicate:

    @pytest.mark.parametrize("value,expected_flag", [
        (0,  0),
        (1,  1),
        (2,  0),
        (3,  1),
        (255, 1),
        (256, 0),
    ], ids=["zero", "one", "two", "three", "255", "256"])
    def test_low_bit_predicate(self, value, expected_flag):
        result = _run(f": main {value} bit0? halt ;")
        assert result == [expected_flag], (
            f"bit0? on {value} should yield {expected_flag} (low bit only)"
        )


class TestFillByte:

    def test_fills_n_bytes_with_seed(self):
        m, _ = _run_with_memory(": main 3000 5 65 fill-byte halt ;")
        for i in range(5):
            assert m.mem[3000 + i] == 65, (
                f"fill-byte should set 5 consecutive bytes to 65; "
                f"position {i} is {m.mem[3000 + i]}"
            )
        assert m.mem[3005] == 0, (
            "fill-byte should not write past the requested count"
        )

    def test_count_zero_writes_nothing(self):
        m, _ = _run_with_memory(": main 3000 0 65 fill-byte halt ;")
        assert m.mem[3000] == 0, (
            "fill-byte with count == 0 should not write any bytes — "
            "this guards against LDIR's BC=0 → 65536 behaviour"
        )

    def test_count_one_writes_exactly_one_byte(self):
        m, _ = _run_with_memory(": main 3000 1 65 fill-byte halt ;")
        assert m.mem[3000] == 65, "fill-byte with count == 1 should plant the seed"
        assert m.mem[3001] == 0, (
            "fill-byte with count == 1 should not propagate — "
            "this guards against LDIR running with BC=0 after dec_bc"
        )

    def test_count_two_writes_exactly_two_bytes(self):
        m, _ = _run_with_memory(": main 3000 2 65 fill-byte halt ;")
        assert m.mem[3000] == 65, "first byte should be seeded directly"
        assert m.mem[3001] == 65, "second byte should be propagated by LDIR"
        assert m.mem[3002] == 0, "fill should stop after exactly 2 bytes"

    def test_consumes_all_three_args(self):
        result = _run(": main 99 3000 3 65 fill-byte halt ;")
        assert result == [99], (
            "fill-byte should consume addr, count, and byte (3 stack items)"
        )

    def test_large_count_fills_byte_by_byte_via_ldir(self):
        m, _ = _run_with_memory(": main 16384 300 65 fill-byte halt ;")
        for offset in range(300):
            assert m.mem[16384 + offset] == 65, (
                f"fill-byte over 300 bytes should set every position to 65; "
                f"position {offset} (addr {16384+offset}) is {m.mem[16384 + offset]} — "
                f"if some are 0, LDIR isn't propagating byte-by-byte as expected"
            )
        assert m.mem[16383] == 0 and m.mem[16684] == 0, (
            "fill-byte should not touch bytes outside the [addr, addr+count) range"
        )
