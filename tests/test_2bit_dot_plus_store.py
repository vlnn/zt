"""
Tests for the `2BIT-DOT+!` primitive — accumulating dot product where weights
are 2-bit signed values {0,1,2,3} mapped to {-2,-1,0,+1} (z80ai convention),
packed 4-per-byte LSB-first.

Stack effect: `( wptr aptr count addr -- )`. Adds `dot(weights, activations)`
into the 16-bit cell at `addr`. `count` is the number of weights and must be
a multiple of 4.
"""
import pytest

from zt.assemble.asm import Asm
from zt.assemble.inline_bodies import INLINABLE_PRIMITIVES
from zt.compile.compiler import Compiler, compile_and_run


JP = 0xC3
DISPATCH_LEN = 3


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _compile(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


def _u16(n: int) -> int:
    return n & 0xFFFF


def _bias(raw: int) -> int:
    return raw - 2


def _expected_dot(packed_bytes: list[int], activations: list[int]) -> int:
    weights = []
    for byte in packed_bytes:
        weights.append(_bias(byte & 0x03))
        weights.append(_bias((byte >> 2) & 0x03))
        weights.append(_bias((byte >> 4) & 0x03))
        weights.append(_bias((byte >> 6) & 0x03))
    return sum(w * a for w, a in zip(weights, activations))


def _dot_program(start_acc: int, packed_bytes: list[int], activations: list[int]) -> str:
    wts_defs = " ".join(f"${b:02X} c," for b in packed_bytes)
    acts_defs = " ".join(f"{_u16(a)} ," for a in activations)
    count = len(packed_bytes) * 4
    return (
        f"create wts {wts_defs} "
        f"create acts {acts_defs} "
        f"variable acc "
        f": main "
        f"  {_u16(start_acc)} acc ! "
        f"  wts acts {count} acc 2bit-dot+! "
        f"  acc @ "
        f"  halt ;"
    )


class TestRegistration:

    def test_word_registered(self):
        c = Compiler(origin=0x8000)
        assert "2bit-dot+!" in c.words, \
            "2bit-dot+! should be registered as a Forth word"


class TestByteShape:

    def test_ends_with_jp_next(self):
        from zt.assemble.primitives import create_2bit_dot_plus_store
        out = _compile(create_2bit_dot_plus_store)
        assert JP in out, \
            "2bit-dot+! must contain a JP instruction (NEXT dispatch or internal jump)"


class TestSemanticsSingleByte:

    @pytest.mark.parametrize("byte,acts,desc", [
        (0xFF, [10, 20, 30, 40], "all weights +1: dot = 10+20+30+40"),
        (0x00, [10, 20, 30, 40], "all weights -2: dot = -2*(sum)"),
        (0xAA, [10, 20, 30, 40], "all weights 0: dot = 0"),
        (0x55, [10, 20, 30, 40], "all weights -1: dot = -(sum)"),
        (0x1B, [10, 20, 30, 40], "mixed: bits 11_01_10_11 → +1,-1,0,+1 with bias"),
        (0xE4, [10, 20, 30, 40], "mixed: bits 00_01_10_11 → -2,-1,0,+1"),
        (0xFF, [-10, -20, -30, -40], "all +1 with negative activations"),
        (0x00, [1, 2, 3, 4], "all -2 with small activations"),
        (0xFF, [0, 0, 0, 0], "any weights with zero activations: dot = 0"),
    ])
    def test_dot_against_zero_acc(self, byte, acts, desc):
        expected = _expected_dot([byte], acts)
        src = _dot_program(0, [byte], acts)
        result = compile_and_run(src)
        assert result == [_u16(expected)], \
            f"{desc}: expected dot={expected}, got {result[0] if result else None}"

    @pytest.mark.parametrize("start,byte,acts", [
        (100, 0xFF, [10, 20, 30, 40]),
        (-50, 0x00, [10, 20, 30, 40]),
        (1000, 0x55, [1, 2, 3, 4]),
    ])
    def test_accumulates_into_existing_value(self, start, byte, acts):
        expected = start + _expected_dot([byte], acts)
        src = _dot_program(start, [byte], acts)
        result = compile_and_run(src)
        assert result == [_u16(expected)], \
            f"2bit-dot+! must ADD to existing acc={start}, expected {expected}, got {result[0] if result else None}"


class TestSemanticsMultipleBytes:

    @pytest.mark.parametrize("packed,acts,desc", [
        ([0xFF, 0x00], [1, 2, 3, 4, 5, 6, 7, 8],
         "two bytes: all+1 then all-2"),
        ([0xAA, 0xFF, 0x55], [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3],
         "three bytes: all-zero, all+1, all-1"),
        ([0x1B, 0xE4, 0xFF, 0x00], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
         "four bytes mixed weights, 16 activations"),
    ])
    def test_dot_across_bytes(self, packed, acts, desc):
        expected = _expected_dot(packed, acts)
        src = _dot_program(0, packed, acts)
        result = compile_and_run(src)
        assert result == [_u16(expected)], \
            f"{desc}: expected {expected}, got {result[0] if result else None}"


class TestSemanticsZeroCount:

    def test_count_zero_leaves_acc_unchanged(self):
        src = (
            "create wts $FF c, $FF c, "
            "create acts 100 , 200 , 300 , 400 , "
            "variable acc "
            ": main "
            "  42 acc ! "
            "  wts acts 0 acc 2bit-dot+! "
            "  acc @ halt ;"
        )
        result = compile_and_run(src)
        assert result == [42], \
            f"count=0 must leave acc untouched at 42, got {result[0] if result else None}"


class TestStackEffect:

    def test_consumes_four_cells_leaves_zero(self):
        src = (
            "create wts $FF c, "
            "create acts 1 , 2 , 3 , 4 , "
            "variable acc "
            ": main "
            "  999 "
            "  0 acc ! "
            "  wts acts 4 acc 2bit-dot+! "
            "  halt ;"
        )
        result = compile_and_run(src)
        assert result == [999], \
            f"2bit-dot+! must consume exactly 4 cells leaving the 999 sentinel as TOS, got {result}"


class TestInlineWhitelist:

    def test_2bit_dot_plus_store_is_NOT_inlinable(self):
        assert "2bit_dot_plus_store" not in INLINABLE_PRIMITIVES, \
            "2bit-dot+! has internal jumps and a loop — must not be on the inline whitelist"
