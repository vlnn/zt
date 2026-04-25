"""
Tests for the bit-unpacking primitives `UNPACK-NIBBLES` and `UNPACK-2BITS`.
Both decode a single byte (TOS, low byte) into its sub-byte fields and leave
them on the stack with the lowest-bit field on top. Both are pure straight-line
Z80, so they must splice cleanly into `::` bodies.
"""
import pytest

from zt.assemble.asm import Asm
from zt.assemble.inline_bodies import INLINABLE_PRIMITIVES
from zt.compile.compiler import Compiler, compile_and_run


PUSH_HL = 0xE5
LD_B_L = 0x45
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


def _make_compiler() -> Compiler:
    return Compiler(origin=0x8000)


def _expected_nibbles(byte: int) -> tuple[int, int]:
    return (byte >> 4) & 0x0F, byte & 0x0F


def _expected_2bits(byte: int) -> tuple[int, int, int, int]:
    return (
        (byte >> 6) & 0x03,
        (byte >> 4) & 0x03,
        (byte >> 2) & 0x03,
        byte & 0x03,
    )


_INTERESTING_BYTES = [0x00, 0xFF, 0xF0, 0x0F, 0xA5, 0x5A, 0xE5, 0x12, 0x80, 0x01]


class TestUnpackNibblesByteShape:

    def test_starts_by_saving_byte_into_b(self):
        from zt.assemble.primitives import create_unpack_nibbles
        out = _compile(create_unpack_nibbles)
        assert out[0] == LD_B_L, "UNPACK-NIBBLES should start by saving byte (L) to B"

    def test_contains_and_low_nibble_mask(self):
        from zt.assemble.primitives import create_unpack_nibbles
        out = _compile(create_unpack_nibbles)
        assert bytes([0xE6, 0x0F]) in out, \
            "UNPACK-NIBBLES should mask with $0F to extract a nibble"

    def test_pushes_exactly_one_value_to_stack(self):
        from zt.assemble.primitives import create_unpack_nibbles
        out = _compile(create_unpack_nibbles)
        body = out[: -DISPATCH_LEN]
        assert body.count(PUSH_HL) == 1, \
            "UNPACK-NIBBLES should PUSH HL exactly once (one extra value beneath TOS)"

    def test_ends_with_jp_next(self):
        from zt.assemble.primitives import create_unpack_nibbles
        out = _compile(create_unpack_nibbles)
        assert out[-DISPATCH_LEN] == JP, \
            "UNPACK-NIBBLES should end with JP NEXT in non-inline mode"


class TestUnpack2BitsByteShape:

    def test_starts_by_saving_byte_into_b(self):
        from zt.assemble.primitives import create_unpack_2bits
        out = _compile(create_unpack_2bits)
        assert out[0] == LD_B_L, "UNPACK-2BITS should start by saving byte (L) to B"

    def test_contains_and_2bit_mask(self):
        from zt.assemble.primitives import create_unpack_2bits
        out = _compile(create_unpack_2bits)
        assert bytes([0xE6, 0x03]) in out, \
            "UNPACK-2BITS should mask with $03 to extract 2-bit fields"

    def test_pushes_exactly_three_values_to_stack(self):
        from zt.assemble.primitives import create_unpack_2bits
        out = _compile(create_unpack_2bits)
        body = out[: -DISPATCH_LEN]
        assert body.count(PUSH_HL) == 3, \
            "UNPACK-2BITS should PUSH HL exactly three times (three values beneath TOS)"

    def test_ends_with_jp_next(self):
        from zt.assemble.primitives import create_unpack_2bits
        out = _compile(create_unpack_2bits)
        assert out[-DISPATCH_LEN] == JP, \
            "UNPACK-2BITS should end with JP NEXT in non-inline mode"


class TestRegistration:

    def test_unpack_nibbles_word_is_registered(self):
        c = _make_compiler()
        assert "unpack-nibbles" in c.words, \
            "unpack-nibbles should be registered as a Forth word"

    def test_unpack_2bits_word_is_registered(self):
        c = _make_compiler()
        assert "unpack-2bits" in c.words, \
            "unpack-2bits should be registered as a Forth word"


class TestUnpackNibblesSemantics:

    @pytest.mark.parametrize("byte", _INTERESTING_BYTES)
    def test_threaded_stack_effect(self, byte):
        src = f": main ${byte:02X} unpack-nibbles halt ;"
        result = compile_and_run(src)
        hi, lo = _expected_nibbles(byte)
        assert result == [hi, lo], \
            f"unpack-nibbles ${byte:02X} should leave [hi={hi}, lo={lo}] (lo on top)"

    @pytest.mark.parametrize("byte", _INTERESTING_BYTES)
    def test_lo_on_top_of_stack(self, byte):
        src = f": main ${byte:02X} unpack-nibbles drop halt ;"
        result = compile_and_run(src)
        hi, _ = _expected_nibbles(byte)
        assert result == [hi], \
            f"after drop, stack should hold hi={hi} alone for byte ${byte:02X}"

    @pytest.mark.parametrize("byte", _INTERESTING_BYTES)
    def test_round_trip_via_recombination(self, byte):
        src = f": main ${byte:02X} unpack-nibbles swap 4 lshift or halt ;"
        result = compile_and_run(src)
        assert result == [byte], \
            f"recombining hi<<4 | lo should give back ${byte:02X}, got {result}"


class TestUnpack2BitsSemantics:

    @pytest.mark.parametrize("byte", _INTERESTING_BYTES)
    def test_threaded_stack_effect(self, byte):
        src = f": main ${byte:02X} unpack-2bits halt ;"
        result = compile_and_run(src)
        u3, u2, u1, u0 = _expected_2bits(byte)
        assert result == [u3, u2, u1, u0], \
            f"unpack-2bits ${byte:02X} should leave [u3,u2,u1,u0]={[u3,u2,u1,u0]} (u0 on top)"

    @pytest.mark.parametrize("byte", _INTERESTING_BYTES)
    def test_u0_on_top_of_stack(self, byte):
        src = f": main ${byte:02X} unpack-2bits drop drop drop halt ;"
        result = compile_and_run(src)
        u3, _, _, _ = _expected_2bits(byte)
        assert result == [u3], \
            f"after dropping three, stack should hold u3={u3} alone for byte ${byte:02X}"

    @pytest.mark.parametrize("byte", _INTERESTING_BYTES)
    def test_z80ai_signed_mapping(self, byte):
        src = (
            f": bias4  2 - >r 2 - >r 2 - >r 2 - r> r> r> ; "
            f": main ${byte:02X} unpack-2bits bias4 halt ;"
        )
        result = compile_and_run(src)
        u3, u2, u1, u0 = _expected_2bits(byte)
        as_u16 = lambda n: n & 0xFFFF
        expected = [as_u16(u3 - 2), as_u16(u2 - 2), as_u16(u1 - 2), as_u16(u0 - 2)]
        assert result == expected, \
            f"applying `2 -` to each field should map 0..3 to z80ai's -2,-1,0,+1 weights for byte ${byte:02X}"


class TestUnpackPrimitivesInsideForceInline:

    @pytest.mark.parametrize("byte", [0x00, 0xFF, 0xA5, 0xE5])
    def test_unpack_nibbles_splices_into_double_colon(self, byte):
        src = f":: main ${byte:02X} unpack-nibbles halt ;"
        result = compile_and_run(src)
        hi, lo = _expected_nibbles(byte)
        assert result == [hi, lo], \
            f":: unpack-nibbles ${byte:02X} should match threaded result [hi,lo]={[hi,lo]}"

    @pytest.mark.parametrize("byte", [0x00, 0xFF, 0xA5, 0xE5])
    def test_unpack_2bits_splices_into_double_colon(self, byte):
        src = f":: main ${byte:02X} unpack-2bits halt ;"
        result = compile_and_run(src)
        u3, u2, u1, u0 = _expected_2bits(byte)
        assert result == [u3, u2, u1, u0], \
            f":: unpack-2bits ${byte:02X} should match threaded result {[u3,u2,u1,u0]}"


class TestInliningWhitelist:

    def test_unpack_nibbles_is_inlinable(self):
        assert "unpack_nibbles" in INLINABLE_PRIMITIVES, \
            "unpack-nibbles should be on the inline whitelist (pure straight-line, no jumps)"

    def test_unpack_2bits_is_inlinable(self):
        assert "unpack_2bits" in INLINABLE_PRIMITIVES, \
            "unpack-2bits should be on the inline whitelist (pure straight-line, no jumps)"
