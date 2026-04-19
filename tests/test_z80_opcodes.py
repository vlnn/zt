from __future__ import annotations

import pytest

from zt.sim import (
    FLAG_C,
    FLAG_H,
    FLAG_N,
    FLAG_PV,
    FLAG_S,
    FLAG_Z,
    Z80,
)


PINNED_DEVIATIONS = """
These are current sim behaviours deliberately locked in by Phase 1 tests.
They are deviations from the Z80 spec, kept bug-for-bug until Phase 3+:

  - ADD HL,rr: does not compute the half-carry flag.
  - AND/OR/XOR (register forms and immediate): parity (P/V) not computed;
    only S/Z (+ H for AND) are touched.
  - LDIR: runs the entire block copy inside a single _step(); _ticks advances
    by 1 regardless of BC size.
  - Conditional JP instructions always fetch the operand word; the branch
    is taken by assigning to pc only when the condition holds.
  - No RLCA (0x07) implemented; only RRCA (0x0F).
  - ED family implements only SBC HL,DE (0x52) and LDIR (0xB0).
  - DD/FD prefixes implement only the subset used by the project assembler.
"""


@pytest.fixture
def z80() -> Z80:
    return Z80()


def _step(cpu: Z80, *program: int) -> None:
    for i, byte in enumerate(program):
        cpu.mem[(cpu.pc + i) & 0xFFFF] = byte
    cpu._step()


def _load(cpu: Z80, addr: int, *bytes_: int) -> None:
    for i, b in enumerate(bytes_):
        cpu.mem[(addr + i) & 0xFFFF] = b


class TestLoadImmediate8:

    @pytest.mark.parametrize("opcode,reg", [
        (0x06, "b"),
        (0x0E, "c"),
        (0x16, "d"),
        (0x1E, "e"),
        (0x26, "h"),
        (0x2E, "l"),
        (0x3E, "a"),
    ], ids=["ld_b_n", "ld_c_n", "ld_d_n", "ld_e_n", "ld_h_n", "ld_l_n", "ld_a_n"])
    def test_loads_immediate_into_register(self, z80, opcode, reg):
        _step(z80, opcode, 0x42)
        assert getattr(z80, reg) == 0x42, f"ld {reg},n should place immediate in {reg}"
        assert z80.pc == 2, f"ld {reg},n should advance pc by 2"

    def test_ld_ind_hl_n_writes_to_hl_address(self, z80):
        z80.hl = 0xC000
        _step(z80, 0x36, 0x99)
        assert z80.mem[0xC000] == 0x99, "ld (hl),n should write immediate to (hl)"


class TestLoadImmediate16:

    @pytest.mark.parametrize("opcode,pair", [
        (0x01, "bc"),
        (0x11, "de"),
        (0x21, "hl"),
        (0x31, "sp"),
    ], ids=["ld_bc_nn", "ld_de_nn", "ld_hl_nn", "ld_sp_nn"])
    def test_loads_16bit_immediate_little_endian(self, z80, opcode, pair):
        _step(z80, opcode, 0xEF, 0xBE)
        assert getattr(z80, pair) == 0xBEEF, f"ld {pair},nn should load LE 16-bit immediate"
        assert z80.pc == 3, f"ld {pair},nn should advance pc by 3"


class TestLoadRegReg:

    @pytest.mark.parametrize("opcode,dst,src,src_val", [
        (0x47, "b", "a", 0x11),
        (0x78, "a", "b", 0x22),
        (0x7A, "a", "d", 0x33),
        (0x6B, "l", "e", 0x44),
        (0x67, "h", "a", 0x55),
        (0x4D, "c", "l", 0x66),
    ], ids=["ld_b_a", "ld_a_b", "ld_a_d", "ld_l_e", "ld_h_a", "ld_c_l"])
    def test_copies_src_register_to_dst(self, z80, opcode, dst, src, src_val):
        setattr(z80, src, src_val)
        _step(z80, opcode)
        assert getattr(z80, dst) == src_val, f"ld {dst},{src} should copy {src} into {dst}"

    def test_ld_ind_hl_a_writes_a_through_hl(self, z80):
        z80.a = 0x55
        z80.hl = 0xC100
        _step(z80, 0x77)
        assert z80.mem[0xC100] == 0x55, "ld (hl),a should write a to (hl)"

    def test_ld_a_ind_hl_reads_through_hl(self, z80):
        z80.mem[0xC200] = 0x99
        z80.hl = 0xC200
        _step(z80, 0x7E)
        assert z80.a == 0x99, "ld a,(hl) should read (hl) into a"


class TestLoadMemoryAbsolute:

    def test_ld_a_ind_de_reads_from_de(self, z80):
        z80.de = 0xC000
        z80.mem[0xC000] = 0xAB
        _step(z80, 0x1A)
        assert z80.a == 0xAB, "ld a,(de) should load (de) into a"

    def test_ld_a_ind_nn_reads_from_absolute(self, z80):
        z80.mem[0xC000] = 0xCD
        _step(z80, 0x3A, 0x00, 0xC0)
        assert z80.a == 0xCD, "ld a,(nn) should load (nn) into a"

    def test_ld_ind_nn_a_writes_to_absolute(self, z80):
        z80.a = 0xEF
        _step(z80, 0x32, 0x34, 0xC0)
        assert z80.mem[0xC034] == 0xEF, "ld (nn),a should write a to (nn)"


class TestPushPop:

    @pytest.mark.parametrize("push_op,pop_op,pair", [
        (0xC5, 0xC1, "bc"),
        (0xD5, 0xD1, "de"),
        (0xE5, 0xE1, "hl"),
        (0xF5, 0xF1, "af"),
    ], ids=["bc", "de", "hl", "af"])
    def test_push_then_pop_round_trip(self, z80, push_op, pop_op, pair):
        z80.sp = 0xFF00
        setattr(z80, pair, 0xBEEF)
        _step(z80, push_op)
        setattr(z80, pair, 0)
        _step(z80, pop_op)
        assert getattr(z80, pair) == 0xBEEF, f"push/pop {pair} should round-trip the value"

    def test_push_decrements_sp_by_two(self, z80):
        z80.sp = 0xFF00
        z80.hl = 0x1234
        _step(z80, 0xE5)
        assert z80.sp == 0xFEFE, "push should decrement sp by 2"

    def test_push_stores_little_endian(self, z80):
        z80.sp = 0xFF00
        z80.hl = 0xBEEF
        _step(z80, 0xE5)
        assert z80.mem[0xFEFE] == 0xEF, "push hl low byte should land at (sp)"
        assert z80.mem[0xFEFF] == 0xBE, "push hl high byte should land at (sp+1)"


class TestExchange:

    def test_ex_de_hl_swaps_pairs(self, z80):
        z80.de, z80.hl = 0x1111, 0x2222
        _step(z80, 0xEB)
        assert (z80.de, z80.hl) == (0x2222, 0x1111), "ex de,hl should swap the two pairs"

    def test_ex_sp_hl_swaps_hl_with_stack_top(self, z80):
        z80.sp = 0xFF00
        z80.mem[0xFF00] = 0xEF
        z80.mem[0xFF01] = 0xBE
        z80.hl = 0x1234
        _step(z80, 0xE3)
        assert z80.hl == 0xBEEF, "ex (sp),hl should place prior (sp) word into hl"
        assert z80.mem[0xFF00] == 0x34, "ex (sp),hl low byte should receive prior hl low"
        assert z80.mem[0xFF01] == 0x12, "ex (sp),hl high byte should receive prior hl high"


class TestInc16Dec16:

    @pytest.mark.parametrize("opcode,pair,start,expected", [
        (0x03, "bc", 0x00FF, 0x0100),
        (0x13, "de", 0xFFFF, 0x0000),
        (0x23, "hl", 0x1234, 0x1235),
        (0x0B, "bc", 0x0100, 0x00FF),
        (0x1B, "de", 0x0000, 0xFFFF),
        (0x2B, "hl", 0x1235, 0x1234),
    ], ids=["inc_bc_carry", "inc_de_wrap", "inc_hl", "dec_bc_borrow", "dec_de_wrap", "dec_hl"])
    def test_16bit_inc_dec_wraps_mod_65536(self, z80, opcode, pair, start, expected):
        setattr(z80, pair, start)
        _step(z80, opcode)
        assert getattr(z80, pair) == expected, (
            f"opcode {opcode:#x} on {pair}={start:#06x} should give {expected:#06x}"
        )

    def test_16bit_inc_does_not_touch_flags(self, z80):
        z80.hl = 0x1234
        z80.f = 0xFF
        _step(z80, 0x23)
        assert z80.f == 0xFF, "inc hl should not modify any flags"


class TestInc8Dec8:

    def test_inc_a_increments(self, z80):
        z80.a = 0x0F
        _step(z80, 0x3C)
        assert z80.a == 0x10, "inc a should advance a"

    def test_inc_a_half_carry_on_low_nibble_overflow(self, z80):
        z80.a = 0x0F
        _step(z80, 0x3C)
        assert z80.f & FLAG_H, "inc a from 0x0F should set half-carry"

    def test_inc_a_zero_flag_on_wrap(self, z80):
        z80.a = 0xFF
        _step(z80, 0x3C)
        assert z80.a == 0x00, "inc a from 0xFF should wrap to 0"
        assert z80.f & FLAG_Z, "inc a wrapping to 0 should set Z"

    def test_inc_a_overflow_at_7f(self, z80):
        z80.a = 0x7F
        _step(z80, 0x3C)
        assert z80.f & FLAG_PV, "inc a from 0x7F should set P/V (signed overflow)"

    def test_dec_a_decrements(self, z80):
        z80.a = 0x10
        _step(z80, 0x3D)
        assert z80.a == 0x0F, "dec a should step back by 1"
        assert z80.f & FLAG_N, "dec a should set N (subtract flag)"

    def test_dec_a_half_borrow(self, z80):
        z80.a = 0x10
        _step(z80, 0x3D)
        assert z80.f & FLAG_H, "dec a from 0x10 should set H (borrow from high nibble)"

    def test_dec_a_overflow_at_80(self, z80):
        z80.a = 0x80
        _step(z80, 0x3D)
        assert z80.f & FLAG_PV, "dec a from 0x80 should set P/V (signed overflow)"

    def test_inc_h_reaches_h_register(self, z80):
        z80.h = 0x20
        _step(z80, 0x24)
        assert z80.h == 0x21, "inc h should advance h"

    def test_dec_e_reaches_e_register(self, z80):
        z80.e = 0x20
        _step(z80, 0x1D)
        assert z80.e == 0x1F, "dec e should step e back"


class TestAddHL:

    @pytest.mark.parametrize("opcode,pair,initial_hl,pair_val,expected_hl,expected_carry", [
        (0x09, "bc", 0x1000, 0x0234, 0x1234, False),
        (0x19, "de", 0x8000, 0x8000, 0x0000, True),
        (0x29, "hl", 0x4321, 0x4321, 0x8642, False),
    ], ids=["add_hl_bc", "add_hl_de_carry", "add_hl_hl"])
    def test_add_hl_rr_result_and_carry(
        self, z80, opcode, pair, initial_hl, pair_val, expected_hl, expected_carry,
    ):
        z80.hl = initial_hl
        if pair != "hl":
            setattr(z80, pair, pair_val)
        _step(z80, opcode)
        assert z80.hl == expected_hl, f"add hl,{pair} should produce {expected_hl:#06x}"
        assert bool(z80.f & FLAG_C) == expected_carry, (
            f"add hl,{pair} carry should be {expected_carry}"
        )


class TestAluRegisterForm:

    def test_add_a_b(self, z80):
        z80.a, z80.b = 0x10, 0x20
        _step(z80, 0x80)
        assert z80.a == 0x30, "add a,b should sum a + b"

    def test_add_a_carry_flag_on_overflow(self, z80):
        z80.a, z80.b = 0xFF, 0x01
        _step(z80, 0x80)
        assert z80.a == 0x00, "add a,b 0xFF + 0x01 should wrap to 0"
        assert z80.f & FLAG_C, "add a,b overflow should set C"
        assert z80.f & FLAG_Z, "add a,b result 0 should set Z"

    def test_sub_sets_n_flag(self, z80):
        z80.a, z80.b = 0x10, 0x03
        _step(z80, 0x90)
        assert z80.a == 0x0D, "sub b should compute a - b"
        assert z80.f & FLAG_N, "sub should set N flag"

    def test_sub_borrow_sets_c(self, z80):
        z80.a, z80.b = 0x00, 0x01
        _step(z80, 0x90)
        assert z80.a == 0xFF, "sub with borrow should wrap modulo 256"
        assert z80.f & FLAG_C, "sub with borrow should set C"

    def test_and_result_and_h_flag(self, z80):
        z80.a, z80.b = 0xF0, 0x0F
        _step(z80, 0xA0)
        assert z80.a == 0x00, "and should bitwise-and a and b"
        assert z80.f & FLAG_Z, "and 0 should set Z"
        assert z80.f & FLAG_H, "and should set H flag"

    def test_xor_clears_h_flag(self, z80):
        z80.a, z80.b = 0xFF, 0x0F
        _step(z80, 0xA8)
        assert z80.a == 0xF0, "xor should bitwise-xor"
        assert not (z80.f & FLAG_H), "xor should clear H"

    def test_or_preserves_carry_semantics(self, z80):
        z80.a, z80.b = 0x55, 0x0A
        _step(z80, 0xB0)
        assert z80.a == 0x5F, "or should combine bits"
        assert not (z80.f & FLAG_C), "or should clear C"

    def test_cp_does_not_change_a(self, z80):
        z80.a, z80.b = 0x10, 0x10
        _step(z80, 0xB8)
        assert z80.a == 0x10, "cp should not modify a"
        assert z80.f & FLAG_Z, "cp equal should set Z"
        assert z80.f & FLAG_N, "cp should set N"


class TestAluImmediate:

    def test_and_n_applies_immediate(self, z80):
        z80.a = 0xCD
        _step(z80, 0xE6, 0x0F)
        assert z80.a == 0x0D, "and n should mask a with immediate"
        assert z80.f & FLAG_H, "and n should set H"

    def test_or_n_applies_immediate(self, z80):
        z80.a = 0x30
        _step(z80, 0xF6, 0x0C)
        assert z80.a == 0x3C, "or n should or immediate into a"

    def test_cp_n_compares_without_modifying_a(self, z80):
        z80.a = 0x20
        _step(z80, 0xFE, 0x20)
        assert z80.a == 0x20, "cp n should not change a"
        assert z80.f & FLAG_Z, "cp n equal should set Z"


class TestAccumulatorOps:

    def test_rrca_rotates_a_right(self, z80):
        z80.a = 0b0000_0001
        _step(z80, 0x0F)
        assert z80.a == 0b1000_0000, "rrca should rotate bit0 into bit7"
        assert z80.f & FLAG_C, "rrca of 0x01 should set C from bit0"

    def test_rrca_of_zero(self, z80):
        z80.a = 0
        _step(z80, 0x0F)
        assert z80.a == 0, "rrca of 0 should stay 0"
        assert not (z80.f & FLAG_C), "rrca of 0 should clear C"

    def test_cpl_inverts_a(self, z80):
        z80.a = 0xA5
        _step(z80, 0x2F)
        assert z80.a == 0x5A, "cpl should invert all bits of a"
        assert z80.f & FLAG_H, "cpl should set H"
        assert z80.f & FLAG_N, "cpl should set N"

    def test_scf_sets_carry(self, z80):
        z80.f = 0
        _step(z80, 0x37)
        assert z80.f & FLAG_C, "scf should set C"
        assert not (z80.f & FLAG_H), "scf should clear H"
        assert not (z80.f & FLAG_N), "scf should clear N"


class TestJumpAbsolute:

    def test_jp_nn_sets_pc_to_target(self, z80):
        _step(z80, 0xC3, 0x00, 0x90)
        assert z80.pc == 0x9000, "jp nn should place nn into pc"

    @pytest.mark.parametrize("opcode,flag_value,taken", [
        (0xCA, FLAG_Z, True),
        (0xCA, 0, False),
        (0xC2, 0, True),
        (0xC2, FLAG_Z, False),
        (0xF2, 0, True),
        (0xF2, FLAG_S, False),
        (0xFA, FLAG_S, True),
        (0xFA, 0, False),
    ], ids=[
        "jp_z_taken", "jp_z_not_taken",
        "jp_nz_taken", "jp_nz_not_taken",
        "jp_p_taken", "jp_p_not_taken",
        "jp_m_taken", "jp_m_not_taken",
    ])
    def test_conditional_jp(self, z80, opcode, flag_value, taken):
        z80.f = flag_value
        _step(z80, opcode, 0x00, 0x90)
        if taken:
            assert z80.pc == 0x9000, f"conditional jp {opcode:#x} should have taken the branch"
        else:
            assert z80.pc == 3, (
                f"conditional jp {opcode:#x} should have fallen through past 3-byte op"
            )


class TestJumpRelative:

    def test_jr_forward(self, z80):
        _step(z80, 0x18, 0x05)
        assert z80.pc == 0x0007, "jr +5 should land at pc_after_instr + 5"

    def test_jr_backward(self, z80):
        z80.pc = 0x0010
        _step(z80, 0x18, 0xFE)
        assert z80.pc == 0x0010, "jr -2 should loop back to itself"

    @pytest.mark.parametrize("opcode,flag,taken", [
        (0x20, 0, True),
        (0x20, FLAG_Z, False),
        (0x28, FLAG_Z, True),
        (0x28, 0, False),
        (0x30, 0, True),
        (0x30, FLAG_C, False),
        (0x38, FLAG_C, True),
        (0x38, 0, False),
    ], ids=[
        "jr_nz_taken", "jr_nz_not_taken",
        "jr_z_taken", "jr_z_not_taken",
        "jr_nc_taken", "jr_nc_not_taken",
        "jr_c_taken", "jr_c_not_taken",
    ])
    def test_conditional_jr(self, z80, opcode, flag, taken):
        z80.f = flag
        _step(z80, opcode, 0x05)
        expected = 0x0007 if taken else 0x0002
        assert z80.pc == expected, (
            f"jr {opcode:#x} with flag={flag:#x} should land pc at {expected:#06x}"
        )


class TestDJNZ:

    def test_djnz_branches_while_b_nonzero(self, z80):
        z80.b = 2
        _step(z80, 0x10, 0xFE)
        assert z80.b == 1, "djnz should decrement b"
        assert z80.pc == 0x0000, "djnz with b>0 after decrement should branch"

    def test_djnz_falls_through_when_b_hits_zero(self, z80):
        z80.b = 1
        _step(z80, 0x10, 0xFE)
        assert z80.b == 0, "djnz should decrement b"
        assert z80.pc == 0x0002, "djnz with b==0 after decrement should fall through"


class TestCallRet:

    def test_call_pushes_return_address_and_jumps(self, z80):
        z80.sp = 0xFF00
        _step(z80, 0xCD, 0x00, 0x90)
        assert z80.pc == 0x9000, "call nn should jump to nn"
        assert z80.sp == 0xFEFE, "call should push a 2-byte return address"
        low = z80.mem[0xFEFE]
        high = z80.mem[0xFEFF]
        assert (high << 8) | low == 0x0003, "return address pushed by call should be pc_after_call"

    def test_ret_pops_pc(self, z80):
        z80.sp = 0xFEFE
        z80.mem[0xFEFE] = 0x34
        z80.mem[0xFEFF] = 0x12
        _step(z80, 0xC9)
        assert z80.pc == 0x1234, "ret should pop stacked word into pc"
        assert z80.sp == 0xFF00, "ret should increment sp by 2"


class TestOutPort:

    def test_out_n_a_appends_to_outputs(self, z80):
        z80.a = 0x55
        _step(z80, 0xD3, 0xFE)
        assert len(z80._outputs) == 1, "out (n),a should append exactly one output entry"
        port, value = z80._outputs[0]
        assert (port & 0xFF) == 0xFE, "out port low byte should equal n"
        assert value == 0x55, "out value should equal a"


class TestInterruptEnable:

    def test_di_clears_iff(self, z80):
        z80.iff = True
        _step(z80, 0xF3)
        assert z80.iff is False, "di should clear iff"

    def test_ei_sets_iff(self, z80):
        z80.iff = False
        _step(z80, 0xFB)
        assert z80.iff is True, "ei should set iff"


class TestCBRotates:

    def test_rl_b_rotates_with_carry(self, z80):
        z80.b = 0x80
        z80.f = 0
        _step(z80, 0xCB, 0x10)
        assert z80.b == 0x00, "rl b with bit7=1 and C=0 should rotate to 0"
        assert z80.f & FLAG_C, "rl b should shift old bit7 into C"
        assert z80.f & FLAG_Z, "rl b result 0 should set Z"

    def test_rl_b_with_carry_in(self, z80):
        z80.b = 0x01
        z80.f = FLAG_C
        _step(z80, 0xCB, 0x10)
        assert z80.b == 0x03, "rl b with C=1 should shift 1 into bit0"

    def test_sla_c_shifts_left_and_carries(self, z80):
        z80.c = 0x81
        _step(z80, 0xCB, 0x21)
        assert z80.c == 0x02, "sla c should shift left zero-filling bit0"
        assert z80.f & FLAG_C, "sla c should push bit7 into C"

    def test_srl_h_shifts_right_zero_fill(self, z80):
        z80.h = 0x81
        _step(z80, 0xCB, 0x3C)
        assert z80.h == 0x40, "srl h should shift right with zero-fill"
        assert z80.f & FLAG_C, "srl h should push bit0 into C"

    def test_sra_h_preserves_sign(self, z80):
        z80.h = 0x80
        _step(z80, 0xCB, 0x2C)
        assert z80.h == 0xC0, "sra h should preserve bit7"


class TestCBBit:

    def test_bit_clears_z_when_bit_set(self, z80):
        z80.h = 0x80
        _step(z80, 0xCB, 0x7C)
        assert not (z80.f & FLAG_Z), "bit 7,h with h=0x80 should clear Z"
        assert z80.f & FLAG_H, "bit test should set H"

    def test_bit_sets_z_when_bit_clear(self, z80):
        z80.h = 0x00
        _step(z80, 0xCB, 0x7C)
        assert z80.f & FLAG_Z, "bit 7,h with h=0x00 should set Z"


class TestED:

    def test_sbc_hl_de_subtracts_with_borrow(self, z80):
        z80.hl = 0x1000
        z80.de = 0x0500
        z80.f = 0
        _step(z80, 0xED, 0x52)
        assert z80.hl == 0x0B00, "sbc hl,de no-carry should give hl - de"
        assert z80.f & FLAG_N, "sbc hl,de should set N"

    def test_sbc_hl_de_with_carry_in(self, z80):
        z80.hl = 0x1000
        z80.de = 0x0500
        z80.f = FLAG_C
        _step(z80, 0xED, 0x52)
        assert z80.hl == 0x0AFF, "sbc hl,de with C=1 should subtract one more"

    def test_sbc_hl_de_borrow_wraps(self, z80):
        z80.hl = 0x0000
        z80.de = 0x0001
        z80.f = 0
        _step(z80, 0xED, 0x52)
        assert z80.hl == 0xFFFF, "sbc hl,de underflow should wrap to 0xFFFF"
        assert z80.f & FLAG_C, "sbc hl,de underflow should set C"

    def test_ldir_copies_block(self, z80):
        _load(z80, 0xC000, 0x11, 0x22, 0x33, 0x44)
        z80.hl = 0xC000
        z80.de = 0xC100
        z80.bc = 4
        _step(z80, 0xED, 0xB0)
        assert bytes(z80.mem[0xC100:0xC104]) == b"\x11\x22\x33\x44", (
            "ldir should copy BC bytes from (HL) to (DE)"
        )
        assert z80.bc == 0, "ldir should leave BC at 0 after the copy"

    def test_ldir_advances_pointers(self, z80):
        z80.hl = 0xC000
        z80.de = 0xC100
        z80.bc = 3
        _step(z80, 0xED, 0xB0)
        assert z80.hl == 0xC003, "ldir should advance hl by the copy count"
        assert z80.de == 0xC103, "ldir should advance de by the copy count"

    def test_ldir_is_one_tick_in_current_impl(self, z80):
        """Pinned: current impl runs whole copy inside one _step().

        Phase 3 will revisit this so each iteration costs T-states.
        """
        _load(z80, 0x0000, 0xED, 0xB0)
        z80.hl = 0xC000
        z80.de = 0xC100
        z80.bc = 10
        z80.run(max_ticks=5)
        assert z80._ticks <= 5, "ldir bulk copy should still respect max_ticks"
        assert z80.bc == 0, "ldir should have finished the copy in the (single) tick"


class TestIxIy:

    def test_ld_ix_nn_loads_immediate(self, z80):
        _step(z80, 0xDD, 0x21, 0xCD, 0xAB)
        assert z80.ix == 0xABCD, "ld ix,nn should load little-endian immediate"

    def test_inc_ix_increments(self, z80):
        z80.ix = 0x00FF
        _step(z80, 0xDD, 0x23)
        assert z80.ix == 0x0100, "inc ix should increment the 16-bit register"

    def test_dec_iy_decrements(self, z80):
        z80.iy = 0x0100
        _step(z80, 0xFD, 0x2B)
        assert z80.iy == 0x00FF, "dec iy should decrement the 16-bit register"

    def test_push_pop_ix_round_trip(self, z80):
        z80.sp = 0xFF00
        z80.ix = 0x1234
        _step(z80, 0xDD, 0xE5)
        z80.ix = 0
        _step(z80, 0xDD, 0xE1)
        assert z80.ix == 0x1234, "push ix then pop ix should round-trip"

    @pytest.mark.parametrize("prefix,reg_name", [(0xDD, "ix"), (0xFD, "iy")])
    def test_ld_e_ix_iy_with_positive_displacement(self, z80, prefix, reg_name):
        setattr(z80, reg_name, 0xC000)
        z80.mem[0xC005] = 0xAB
        _step(z80, prefix, 0x5E, 0x05)
        assert z80.e == 0xAB, f"ld e,({reg_name}+5) should load (addr+5) into e"

    @pytest.mark.parametrize("prefix,reg_name", [(0xDD, "ix"), (0xFD, "iy")])
    def test_ld_ix_iy_plus_d_writes_e(self, z80, prefix, reg_name):
        setattr(z80, reg_name, 0xC000)
        z80.e = 0xCC
        _step(z80, prefix, 0x73, 0x02)
        assert z80.mem[0xC002] == 0xCC, f"ld ({reg_name}+2),e should write e to (addr+2)"

    def test_ld_e_ix_negative_displacement(self, z80):
        z80.ix = 0xC010
        z80.mem[0xC00E] = 0x77
        _step(z80, 0xDD, 0x5E, 0xFE)
        assert z80.e == 0x77, "ld e,(ix-2) should honor signed displacement"

    def test_ex_sp_ix_swaps_ix_with_stack_top(self, z80):
        z80.sp = 0xFF00
        z80.mem[0xFF00] = 0xCD
        z80.mem[0xFF01] = 0xAB
        z80.ix = 0x1234
        _step(z80, 0xDD, 0xE3)
        assert z80.ix == 0xABCD, "ex (sp),ix should place old (sp) into ix"
        assert z80.mem[0xFF00] == 0x34, "ex (sp),ix low byte should come from old ix low"
        assert z80.mem[0xFF01] == 0x12, "ex (sp),ix high byte should come from old ix high"


class TestRunHaltAndBounds:

    def test_halt_terminates_run(self, z80):
        _load(z80, 0x0000, 0x76)
        z80.run(max_ticks=10)
        assert z80.halted, "halt opcode should set halted flag"
        assert z80._ticks == 1, "halt should count as one executed tick"

    def test_max_ticks_bounds_execution_without_halting(self, z80):
        _load(z80, 0x0000, 0x18, 0xFE)
        z80.run(max_ticks=7)
        assert not z80.halted, "tight loop without halt should not set halted"
        assert z80._ticks == 7, "max_ticks should bound executed ticks"

    def test_run_zero_ticks_does_nothing(self, z80):
        _load(z80, 0x0000, 0x3C)
        z80.a = 0
        z80.run(max_ticks=0)
        assert z80.a == 0, "max_ticks=0 should execute no instructions"


class TestKeyHooks:

    def test_call_to_key_query_signals_input_available(self, z80):
        z80.input_buffer = bytearray(b"A")
        _load(z80, 0x0000, 0xCD, 0xE9, 0x15)
        z80._step()
        assert z80.a == 0xFF, "call KEY_QUERY with input should load 0xFF into a"

    def test_call_to_key_query_signals_no_input(self, z80):
        z80.input_buffer = bytearray()
        _load(z80, 0x0000, 0xCD, 0xE9, 0x15)
        z80._step()
        assert z80.a == 0x00, "call KEY_QUERY without input should load 0x00 into a"

    def test_call_to_key_consumes_from_buffer(self, z80):
        z80.input_buffer = bytearray(b"XY")
        _load(z80, 0x0000, 0xCD, 0xE6, 0x15)
        z80._step()
        assert z80.a == ord("X"), "call KEY should return next input byte"
        assert z80._input_pos == 1, "call KEY should advance input position"

    def test_call_to_key_returns_zero_when_exhausted(self, z80):
        z80.input_buffer = bytearray()
        _load(z80, 0x0000, 0xCD, 0xE6, 0x15)
        z80._step()
        assert z80.a == 0, "call KEY on empty buffer should return 0"


class TestUnimplementedOpcodes:

    @pytest.mark.parametrize("program,context", [
        ((0x07,), "main"),
        ((0xED, 0x44), "ed"),
        ((0xDD, 0x7E), "ix/iy"),
    ], ids=["rlca_main", "unimplemented_ed", "unimplemented_ix"])
    def test_unimplemented_opcode_raises(self, z80, program, context):
        _load(z80, 0x0000, *program)
        with pytest.raises(RuntimeError, match="unimplemented"):
            z80._step()


class TestTStatesStartAtZero:

    def test_fresh_z80_has_zero_t_states(self, z80):
        assert z80._t_states == 0, "a fresh Z80 should start with zero T-states"

    def test_run_resets_t_states(self, z80):
        z80._t_states = 999
        _load(z80, 0x0000, 0x76)
        z80.run(max_ticks=1)
        assert z80._t_states == 4, "run() should reset _t_states and count only this run's cycles"


class TestTStatesMainFixed:

    @pytest.mark.parametrize("program,expected_cost", [
        ((0x00,),                4),
        ((0x76,),                4),
        ((0x01, 0x34, 0x12),    10),
        ((0x11, 0x34, 0x12),    10),
        ((0x21, 0x34, 0x12),    10),
        ((0x31, 0x34, 0x12),    10),
        ((0x06, 0x42),           7),
        ((0x0E, 0x42),           7),
        ((0x16, 0x42),           7),
        ((0x1E, 0x42),           7),
        ((0x26, 0x42),           7),
        ((0x2E, 0x42),           7),
        ((0x3E, 0x42),           7),
        ((0x36, 0x42),          10),
        ((0x1A,),                7),
        ((0x3A, 0x00, 0xC0),    13),
        ((0x32, 0x00, 0xC0),    13),
        ((0xEB,),                4),
        ((0xE3,),               19),
        ((0x09,),               11),
        ((0x19,),               11),
        ((0x29,),               11),
        ((0x03,),                6),
        ((0x0B,),                6),
        ((0x13,),                6),
        ((0x1B,),                6),
        ((0x23,),                6),
        ((0x2B,),                6),
        ((0x24,),                4),
        ((0x3C,),                4),
        ((0x3D,),                4),
        ((0x1D,),                4),
        ((0xE6, 0x0F),           7),
        ((0xF6, 0x0F),           7),
        ((0xFE, 0x0F),           7),
        ((0x0F,),                4),
        ((0x2F,),                4),
        ((0x37,),                4),
        ((0xC3, 0x00, 0x90),    10),
        ((0xC9,),               10),
        ((0xD3, 0xFE),          11),
        ((0xF3,),                4),
        ((0xFB,),                4),
    ], ids=[
        "nop", "halt",
        "ld_bc_nn", "ld_de_nn", "ld_hl_nn", "ld_sp_nn",
        "ld_b_n", "ld_c_n", "ld_d_n", "ld_e_n", "ld_h_n", "ld_l_n", "ld_a_n",
        "ld_ind_hl_n",
        "ld_a_ind_de", "ld_a_ind_nn", "ld_ind_nn_a",
        "ex_de_hl", "ex_sp_hl",
        "add_hl_bc", "add_hl_de", "add_hl_hl",
        "inc_bc", "dec_bc", "inc_de", "dec_de", "inc_hl", "dec_hl",
        "inc_h", "inc_a", "dec_a", "dec_e",
        "and_n", "or_n", "cp_n",
        "rrca", "cpl", "scf",
        "jp_nn", "ret", "out_n_a", "di", "ei",
    ])
    def test_fixed_cost(self, z80, program, expected_cost):
        _step(z80, *program)
        assert z80._t_states == expected_cost, (
            f"opcode {program[0]:#04x} should cost {expected_cost} T-states"
        )

    @pytest.mark.parametrize("push_op,pair", [
        (0xC5, "bc"), (0xD5, "de"), (0xE5, "hl"), (0xF5, "af"),
    ], ids=["push_bc", "push_de", "push_hl", "push_af"])
    def test_push_costs_11(self, z80, push_op, pair):
        z80.sp = 0xFF00
        _step(z80, push_op)
        assert z80._t_states == 11, f"push {pair} should cost 11 T-states"

    @pytest.mark.parametrize("pop_op,pair", [
        (0xC1, "bc"), (0xD1, "de"), (0xE1, "hl"), (0xF1, "af"),
    ], ids=["pop_bc", "pop_de", "pop_hl", "pop_af"])
    def test_pop_costs_10(self, z80, pop_op, pair):
        z80.sp = 0xFF00
        _step(z80, pop_op)
        assert z80._t_states == 10, f"pop {pair} should cost 10 T-states"

    def test_call_costs_17(self, z80):
        z80.sp = 0xFF00
        _step(z80, 0xCD, 0x00, 0x90)
        assert z80._t_states == 17, "call nn should cost 17 T-states"


class TestTStatesLdRegReg:

    def test_reg_to_reg_no_hl_costs_4(self, z80):
        _step(z80, 0x47)
        assert z80._t_states == 4, "ld b,a should cost 4 T-states (no (HL) involvement)"

    @pytest.mark.parametrize("opcode", [
        0x46, 0x4E, 0x56, 0x5E, 0x66, 0x6E, 0x7E,
    ], ids=["ld_b_ind_hl", "ld_c_ind_hl", "ld_d_ind_hl", "ld_e_ind_hl",
           "ld_h_ind_hl", "ld_l_ind_hl", "ld_a_ind_hl"])
    def test_ld_r_from_hl_costs_7(self, z80, opcode):
        z80.hl = 0xC000
        _step(z80, opcode)
        assert z80._t_states == 7, f"opcode {opcode:#04x} reading (HL) should cost 7 T-states"

    @pytest.mark.parametrize("opcode", [
        0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x77,
    ], ids=["ld_ind_hl_b", "ld_ind_hl_c", "ld_ind_hl_d", "ld_ind_hl_e",
           "ld_ind_hl_h", "ld_ind_hl_l", "ld_ind_hl_a"])
    def test_ld_hl_from_r_costs_7(self, z80, opcode):
        z80.hl = 0xC000
        _step(z80, opcode)
        assert z80._t_states == 7, f"opcode {opcode:#04x} writing (HL) should cost 7 T-states"


class TestTStatesAluRegister:

    @pytest.mark.parametrize("grp_base,label", [
        (0x80, "add_a"),
        (0x88, "adc_a"),
        (0x90, "sub"),
        (0x98, "sbc_a"),
        (0xA0, "and"),
        (0xA8, "xor"),
        (0xB0, "or"),
        (0xB8, "cp"),
    ])
    def test_alu_register_form_costs_4(self, z80, grp_base, label):
        _step(z80, grp_base)
        assert z80._t_states == 4, f"{label} b should cost 4 T-states"

    @pytest.mark.parametrize("opcode,label", [
        (0x86, "add_a_ind_hl"),
        (0x8E, "adc_a_ind_hl"),
        (0x96, "sub_ind_hl"),
        (0x9E, "sbc_a_ind_hl"),
        (0xA6, "and_ind_hl"),
        (0xAE, "xor_ind_hl"),
        (0xB6, "or_ind_hl"),
        (0xBE, "cp_ind_hl"),
    ])
    def test_alu_ind_hl_costs_7(self, z80, opcode, label):
        z80.hl = 0xC000
        _step(z80, opcode)
        assert z80._t_states == 7, f"{label} should cost 7 T-states"


class TestTStatesBranching:

    def test_jr_unconditional_costs_12(self, z80):
        _step(z80, 0x18, 0x05)
        assert z80._t_states == 12, "jr should always cost 12 T-states"

    @pytest.mark.parametrize("opcode,flag,taken", [
        (0x20, 0,      True),
        (0x20, FLAG_Z, False),
        (0x28, FLAG_Z, True),
        (0x28, 0,      False),
        (0x30, 0,      True),
        (0x30, FLAG_C, False),
        (0x38, FLAG_C, True),
        (0x38, 0,      False),
    ], ids=[
        "jr_nz_taken", "jr_nz_not_taken",
        "jr_z_taken",  "jr_z_not_taken",
        "jr_nc_taken", "jr_nc_not_taken",
        "jr_c_taken",  "jr_c_not_taken",
    ])
    def test_jr_cc_taken_costs_12_not_taken_costs_7(self, z80, opcode, flag, taken):
        z80.f = flag
        _step(z80, opcode, 0x05)
        expected = 12 if taken else 7
        assert z80._t_states == expected, (
            f"jr cc {opcode:#04x} {'taken' if taken else 'not taken'} should cost {expected}"
        )

    def test_djnz_taken_costs_13(self, z80):
        z80.b = 2
        _step(z80, 0x10, 0xFE)
        assert z80._t_states == 13, "djnz taken should cost 13 T-states"

    def test_djnz_not_taken_costs_8(self, z80):
        z80.b = 1
        _step(z80, 0x10, 0xFE)
        assert z80._t_states == 8, "djnz not taken should cost 8 T-states"

    @pytest.mark.parametrize("opcode,flag,condition", [
        (0xCA, FLAG_Z, "z-taken"),
        (0xCA, 0,      "z-not-taken"),
        (0xC2, 0,      "nz-taken"),
        (0xC2, FLAG_Z, "nz-not-taken"),
        (0xF2, 0,      "p-taken"),
        (0xF2, FLAG_S, "p-not-taken"),
        (0xFA, FLAG_S, "m-taken"),
        (0xFA, 0,      "m-not-taken"),
    ], ids=lambda x: str(x))
    def test_jp_cc_always_costs_10(self, z80, opcode, flag, condition):
        z80.f = flag
        _step(z80, opcode, 0x00, 0x90)
        assert z80._t_states == 10, (
            f"jp cc ({condition}) should always cost 10 T-states regardless of branch"
        )


class TestTStatesCB:

    @pytest.mark.parametrize("cb_op,idx_name", [
        (0x10, "b"), (0x11, "c"), (0x12, "d"), (0x13, "e"),
        (0x14, "h"), (0x15, "l"),              (0x17, "a"),
    ], ids=["rl_b", "rl_c", "rl_d", "rl_e", "rl_h", "rl_l", "rl_a"])
    def test_rotate_register_costs_8(self, z80, cb_op, idx_name):
        _step(z80, 0xCB, cb_op)
        assert z80._t_states == 8, f"cb rl {idx_name} should cost 8 T-states"

    def test_rotate_ind_hl_costs_15(self, z80):
        z80.hl = 0xC000
        _step(z80, 0xCB, 0x16)
        assert z80._t_states == 15, "cb rl (hl) should cost 15 T-states"

    def test_bit_register_costs_8(self, z80):
        _step(z80, 0xCB, 0x7C)
        assert z80._t_states == 8, "cb bit 7,h should cost 8 T-states"

    def test_bit_ind_hl_costs_12(self, z80):
        z80.hl = 0xC000
        _step(z80, 0xCB, 0x7E)
        assert z80._t_states == 12, "cb bit 7,(hl) should cost 12 T-states"

    def test_res_register_costs_8(self, z80):
        _step(z80, 0xCB, 0x87)
        assert z80._t_states == 8, "cb res 0,a should cost 8 T-states"

    def test_res_ind_hl_costs_15(self, z80):
        z80.hl = 0xC000
        _step(z80, 0xCB, 0x86)
        assert z80._t_states == 15, "cb res 0,(hl) should cost 15 T-states"

    def test_set_register_costs_8(self, z80):
        _step(z80, 0xCB, 0xC7)
        assert z80._t_states == 8, "cb set 0,a should cost 8 T-states"

    def test_set_ind_hl_costs_15(self, z80):
        z80.hl = 0xC000
        _step(z80, 0xCB, 0xC6)
        assert z80._t_states == 15, "cb set 0,(hl) should cost 15 T-states"


class TestTStatesED:

    def test_sbc_hl_de_costs_15(self, z80):
        _step(z80, 0xED, 0x52)
        assert z80._t_states == 15, "sbc hl,de should cost 15 T-states"

    def test_ldir_zero_count_costs_nothing(self, z80):
        z80.bc = 0
        _step(z80, 0xED, 0xB0)
        assert z80._t_states == 0, "ldir with BC=0 should cost no T-states (current behavior)"

    def test_ldir_single_byte_costs_16(self, z80):
        z80.hl = 0xC000
        z80.de = 0xC100
        z80.bc = 1
        _step(z80, 0xED, 0xB0)
        assert z80._t_states == 16, "ldir copying 1 byte should cost 16 T-states"

    def test_ldir_two_bytes_costs_37(self, z80):
        z80.hl = 0xC000
        z80.de = 0xC100
        z80.bc = 2
        _step(z80, 0xED, 0xB0)
        assert z80._t_states == 37, "ldir 2 bytes should cost 21 + 16 = 37 T-states"

    @pytest.mark.parametrize("count,expected", [
        (1, 16),
        (2, 37),
        (3, 58),
        (4, 79),
        (10, 16 + 21 * 9),
    ])
    def test_ldir_cost_formula(self, z80, count, expected):
        z80.hl = 0xC000
        z80.de = 0xC100
        z80.bc = count
        _step(z80, 0xED, 0xB0)
        assert z80._t_states == expected, (
            f"ldir copying {count} bytes should cost {expected} T-states (16 + 21*(n-1))"
        )


class TestTStatesIxIy:

    @pytest.mark.parametrize("program,expected,label", [
        ((0xDD, 0x21, 0x00, 0x90),  14, "ld_ix_nn"),
        ((0xDD, 0x23),              10, "inc_ix"),
        ((0xFD, 0x2B),              10, "dec_iy"),
        ((0xDD, 0xE5),              15, "push_ix"),
        ((0xDD, 0xE1),              14, "pop_ix"),
        ((0xDD, 0x5E, 0x00),        19, "ld_e_ix"),
        ((0xDD, 0x56, 0x00),        19, "ld_d_ix"),
        ((0xDD, 0x6E, 0x00),        19, "ld_l_ix"),
        ((0xDD, 0x66, 0x00),        19, "ld_h_ix"),
        ((0xDD, 0x75, 0x00),        19, "ld_ix_l"),
        ((0xDD, 0x74, 0x00),        19, "ld_ix_h"),
        ((0xDD, 0x73, 0x00),        19, "ld_ix_e"),
        ((0xDD, 0x72, 0x00),        19, "ld_ix_d"),
        ((0xDD, 0xE3),              23, "ex_sp_ix"),
        ((0xFD, 0x21, 0x00, 0x90),  14, "ld_iy_nn"),
        ((0xFD, 0x23),              10, "inc_iy"),
        ((0xFD, 0x5E, 0x00),        19, "ld_e_iy"),
    ], ids=lambda x: x if isinstance(x, str) else None)
    def test_ix_iy_cost(self, z80, program, expected, label):
        z80.sp = 0xFF00
        z80.ix = 0xC000
        z80.iy = 0xC000
        _step(z80, *program)
        assert z80._t_states == expected, f"{label} should cost {expected} T-states"


class TestTStatesAccumulate:

    def test_multiple_steps_accumulate(self, z80):
        _step(z80, 0x00)
        _step(z80, 0x00)
        _step(z80, 0x00)
        assert z80._t_states == 12, "three NOPs should accumulate to 12 T-states"

    def test_real_sequence_of_primitives(self, z80):
        _step(z80, 0x21, 0x34, 0x12)
        _step(z80, 0x11, 0x78, 0x56)
        _step(z80, 0x19)
        assert z80._t_states == 10 + 10 + 11, (
            "ld hl,nn + ld de,nn + add hl,de should total 31 T-states"
        )
