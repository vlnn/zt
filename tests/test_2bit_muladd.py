"""
Tests for the `2BITMULADD` primitive — the z80ai signed-2-bit multiply-and-add.

Stack effect: `( raw act addr -- )`. The raw weight 0..3 is mapped internally
to {-2,-1,0,+1} (z80ai convention) and applied to `*addr += weight*act` with
a 4-way branch — never going through general 16x16 multiply.
"""
import pytest

from zt.assemble.asm import Asm
from zt.assemble.inline_bodies import INLINABLE_PRIMITIVES
from zt.compile.compiler import Compiler, compile_and_run


JP = 0xC3
DISPATCH_LEN = 3
POP_DE = 0xD1
POP_BC = 0xC1
ACC_ADDR = 0x7FF0


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _compile(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


def _make_compiler() -> Compiler:
    return Compiler(origin=0x8000)


def _u16(n: int) -> int:
    return n & 0xFFFF


def _muladd_program(start_acc: int, raw: int, act: int) -> str:
    return (
        f": main "
        f"  {_u16(start_acc)} ${ACC_ADDR:04X} ! "
        f"  {raw} {_u16(act)} ${ACC_ADDR:04X} 2bitmuladd "
        f"  ${ACC_ADDR:04X} @ "
        f"  halt ;"
    )


class TestRegistration:

    def test_word_registered(self):
        c = _make_compiler()
        assert "2bitmuladd" in c.words, \
            "2bitmuladd should be registered as a Forth word"


class TestByteShape:

    def test_starts_by_popping_act_then_raw(self):
        from zt.assemble.primitives import create_2bit_muladd
        out = _compile(create_2bit_muladd)
        assert out[0] == POP_DE, "2bitmuladd should start with POP DE (act)"
        assert out[1] == POP_BC, "2bitmuladd should next POP BC (raw weight code)"

    def test_contains_sub_n_2(self):
        from zt.assemble.primitives import create_2bit_muladd
        out = _compile(create_2bit_muladd)
        assert bytes([0xD6, 0x02]) in out, \
            "2bitmuladd should `SUB 2` to map raw 0..3 to signed -2..+1"

    def test_ends_with_jp_next(self):
        from zt.assemble.primitives import create_2bit_muladd
        out = _compile(create_2bit_muladd)
        assert out[-DISPATCH_LEN] == JP, \
            "2bitmuladd should end with JP NEXT in non-inline mode"


class TestSemanticsThreaded:

    @pytest.mark.parametrize("start,raw,act,expected_cell,desc", [
        (0,    2,  100,    0, "raw=2 → weight=0: cell unchanged from 0"),
        (42,   2,  -99,   42, "raw=2 → weight=0: cell unchanged from 42"),
        (0,    3,  100,  100, "raw=3 → weight=+1: cell += act (0 + 100)"),
        (50,   3,   25,   75, "raw=3 → weight=+1: cell += act (50 + 25)"),
        (10,   3,  -30,  -20, "raw=3 → weight=+1: cell += act with negative act"),
        (0,    1,  100, -100, "raw=1 → weight=-1: cell -= act (0 - 100)"),
        (50,   1,   25,   25, "raw=1 → weight=-1: cell -= act (50 - 25)"),
        (10,   1,  -30,   40, "raw=1 → weight=-1: cell -= act with negative act"),
        (0,    0,  100, -200, "raw=0 → weight=-2: cell -= 2*act (0 - 200)"),
        (1000, 0,  100,  800, "raw=0 → weight=-2: cell -= 2*act (1000 - 200)"),
        (10,   0,  -30,   70, "raw=0 → weight=-2: cell -= 2*act with negative act"),
    ])
    def test_each_weight_path(self, start, raw, act, expected_cell, desc):
        src = _muladd_program(start, raw, act)
        result = compile_and_run(src)
        assert result == [_u16(expected_cell)], \
            f"{desc}: program should leave cell value [{_u16(expected_cell)}], got {result}"

    @pytest.mark.parametrize("start,act", [(0, 1), (0, -1), (100, 50), (-100, 50)])
    def test_zero_weight_truly_idempotent(self, start, act):
        src = _muladd_program(start, 2, act)
        result = compile_and_run(src)
        assert result == [_u16(start)], \
            f"raw=2 (weight=0) must never modify cell, regardless of act; got {result}"


class TestSemanticsForceInline:

    @pytest.mark.parametrize("start,raw,act,expected", [
        (0,  3,  100,  100),
        (0,  1,  100, -100),
        (0,  0,  100, -200),
        (0,  2,  100,    0),
    ])
    def test_splices_into_double_colon(self, start, raw, act, expected):
        src = (
            f":: main "
            f"  {_u16(start)} ${ACC_ADDR:04X} ! "
            f"  {raw} {_u16(act)} ${ACC_ADDR:04X} 2bitmuladd "
            f"  ${ACC_ADDR:04X} @ "
            f"  halt ;"
        )
        result = compile_and_run(src)
        assert result == [_u16(expected)], \
            f":: 2bitmuladd raw={raw} act={act} should match threaded result {_u16(expected)}"


class TestInlineWhitelist:

    def test_2bit_muladd_is_NOT_inlinable(self):
        assert "2bit_muladd" not in INLINABLE_PRIMITIVES, \
            "2bitmuladd uses absolute `jp_m` for the negative-weight branch; relocation-unsafe " \
            "to paste, so off the whitelist. Still callable from `::` bodies via normal dispatch."
