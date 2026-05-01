"""
Tests for Z80 IM-mode opcodes: IM 0/1/2, LD I,A, LD A,I, RETN, RETI, and EI/DI's
effect on iff2. M1 of the IM 2 milestone — opcodes only, no interrupt firing.
"""
from __future__ import annotations

import pytest

from zt.sim import FLAG_C, FLAG_H, FLAG_N, FLAG_PV, FLAG_S, FLAG_Z, Z80


@pytest.fixture
def m():
    return Z80()


def _at(m, addr, *opcode_bytes):
    m.load(addr, bytes(opcode_bytes))
    m.pc = addr


class TestImMode:

    def test_default_im_mode_is_zero(self, m):
        assert m.im_mode == 0, "fresh Z80 should reset to IM 0"

    @pytest.mark.parametrize("opcode,expected", [
        (0x46, 0),
        (0x56, 1),
        (0x5E, 2),
    ], ids=["IM 0", "IM 1", "IM 2"])
    def test_im_opcode_sets_mode(self, m, opcode, expected):
        _at(m, 0x8000, 0xED, opcode)
        m._step()
        assert m.im_mode == expected, \
            f"ED {opcode:#04x} should set im_mode to {expected}"

    @pytest.mark.parametrize("opcode", [0x46, 0x56, 0x5E])
    def test_im_opcode_costs_8_t_states(self, m, opcode):
        _at(m, 0x8000, 0xED, opcode)
        before = m._t_states
        m._step()
        assert m._t_states - before == 8, \
            f"ED {opcode:#04x} should cost 8 T-states"

    @pytest.mark.parametrize("opcode", [0x46, 0x56, 0x5E])
    def test_im_opcode_does_not_change_flags(self, m, opcode):
        _at(m, 0x8000, 0xED, opcode)
        m.f = FLAG_C | FLAG_Z
        m._step()
        assert m.f == (FLAG_C | FLAG_Z), \
            f"ED {opcode:#04x} should not alter the flag register"


class TestLdIRegister:

    def test_default_i_register_is_zero(self, m):
        assert m.i == 0, "fresh Z80 should reset I to 0"

    @pytest.mark.parametrize("a_value", [0x00, 0x01, 0x5A, 0xB9, 0xFF])
    def test_ld_i_a_copies_a_into_i(self, m, a_value):
        _at(m, 0x8000, 0xED, 0x47)
        m.a = a_value
        m._step()
        assert m.i == a_value, \
            f"ED 47 (LD I,A) should copy A={a_value:#04x} into I"

    def test_ld_i_a_does_not_alter_a(self, m):
        _at(m, 0x8000, 0xED, 0x47)
        m.a = 0xB9
        m._step()
        assert m.a == 0xB9, "LD I,A should leave A unchanged"

    def test_ld_i_a_does_not_alter_flags(self, m):
        _at(m, 0x8000, 0xED, 0x47)
        m.a = 0xB9
        m.f = FLAG_C | FLAG_Z
        m._step()
        assert m.f == (FLAG_C | FLAG_Z), "LD I,A should preserve all flags"

    def test_ld_i_a_costs_9_t_states(self, m):
        _at(m, 0x8000, 0xED, 0x47)
        before = m._t_states
        m._step()
        assert m._t_states - before == 9, "ED 47 should cost 9 T-states"

    @pytest.mark.parametrize("i_value", [0x00, 0x10, 0x5A, 0xB9, 0xFF])
    def test_ld_a_i_copies_i_into_a(self, m, i_value):
        _at(m, 0x8000, 0xED, 0x57)
        m.i = i_value
        m._step()
        assert m.a == i_value, \
            f"ED 57 (LD A,I) should copy I={i_value:#04x} into A"

    def test_ld_a_i_does_not_alter_i(self, m):
        _at(m, 0x8000, 0xED, 0x57)
        m.i = 0x5A
        m._step()
        assert m.i == 0x5A, "LD A,I should leave I unchanged"

    def test_ld_a_i_costs_9_t_states(self, m):
        _at(m, 0x8000, 0xED, 0x57)
        before = m._t_states
        m._step()
        assert m._t_states - before == 9, "ED 57 should cost 9 T-states"


class TestLdAIFlags:

    @pytest.mark.parametrize("i_value,sign_set,zero_set", [
        (0x00, False, True),
        (0x01, False, False),
        (0x7F, False, False),
        (0x80, True,  False),
        (0xFF, True,  False),
    ], ids=["zero", "one", "max-positive", "sign-bit", "all-ones"])
    def test_sz_flags_reflect_loaded_value(self, m, i_value, sign_set, zero_set):
        _at(m, 0x8000, 0xED, 0x57)
        m.i = i_value
        m._step()
        assert bool(m.f & FLAG_S) is sign_set, \
            f"S flag for I={i_value:#04x} should be {sign_set}"
        assert bool(m.f & FLAG_Z) is zero_set, \
            f"Z flag for I={i_value:#04x} should be {zero_set}"

    @pytest.mark.parametrize("iff2,pv_set", [
        (True,  True),
        (False, False),
    ])
    def test_pv_flag_mirrors_iff2(self, m, iff2, pv_set):
        _at(m, 0x8000, 0xED, 0x57)
        m.i = 0x10
        m.iff2 = iff2
        m._step()
        assert bool(m.f & FLAG_PV) is pv_set, \
            f"P/V flag should mirror iff2={iff2}"

    def test_h_and_n_are_cleared(self, m):
        _at(m, 0x8000, 0xED, 0x57)
        m.i = 0x10
        m.f = FLAG_H | FLAG_N
        m._step()
        assert not (m.f & FLAG_H), "LD A,I should clear H"
        assert not (m.f & FLAG_N), "LD A,I should clear N"

    def test_carry_is_preserved(self, m):
        _at(m, 0x8000, 0xED, 0x57)
        m.f = FLAG_C
        m.i = 0x10
        m._step()
        assert m.f & FLAG_C, "LD A,I should preserve the carry flag"


class TestReturnFromInterrupt:

    @pytest.mark.parametrize("opcode,name", [
        (0x45, "RETN"),
        (0x4D, "RETI"),
    ])
    def test_pops_saved_pc(self, m, opcode, name):
        m.sp = 0xFF00
        m._push(0x1234)
        _at(m, 0x8000, 0xED, opcode)
        m._step()
        assert m.pc == 0x1234, f"{name} should pop the saved PC from the stack"

    @pytest.mark.parametrize("opcode,name", [
        (0x45, "RETN"),
        (0x4D, "RETI"),
    ])
    def test_restores_sp_after_pop(self, m, opcode, name):
        m.sp = 0xFF00
        m._push(0xABCD)
        _at(m, 0x8000, 0xED, opcode)
        m._step()
        assert m.sp == 0xFF00, f"{name} should leave SP at its pre-push value"

    @pytest.mark.parametrize("opcode", [0x45, 0x4D])
    def test_costs_14_t_states(self, m, opcode):
        m.sp = 0xFF00
        m._push(0x1234)
        _at(m, 0x8000, 0xED, opcode)
        before = m._t_states
        m._step()
        assert m._t_states - before == 14, \
            f"ED {opcode:#04x} should cost 14 T-states"

    def test_retn_copies_iff2_to_iff1(self, m):
        m.sp = 0xFF00
        m._push(0x1234)
        _at(m, 0x8000, 0xED, 0x45)
        m.iff = False
        m.iff2 = True
        m._step()
        assert m.iff is True, "RETN should restore iff1 from iff2"

    def test_retn_leaves_iff2_unchanged(self, m):
        m.sp = 0xFF00
        m._push(0x1234)
        _at(m, 0x8000, 0xED, 0x45)
        m.iff = False
        m.iff2 = True
        m._step()
        assert m.iff2 is True, "RETN should leave iff2 unchanged"

    def test_reti_does_not_touch_iff1(self, m):
        m.sp = 0xFF00
        m._push(0xABCD)
        _at(m, 0x8000, 0xED, 0x4D)
        m.iff = False
        m.iff2 = True
        m._step()
        assert m.iff is False, \
            "RETI should not restore iff1 from iff2 — handler does EI;RETI"


class TestEiDiTouchIff2:

    def test_default_iff2_is_false(self, m):
        assert m.iff2 is False, "fresh Z80 should reset iff2 to False"

    def test_ei_sets_both_iffs(self, m):
        _at(m, 0x8000, 0xFB)
        m.iff = False
        m.iff2 = False
        m._step()
        assert m.iff is True, "EI should set iff1"
        assert m.iff2 is True, "EI should set iff2"

    def test_di_clears_both_iffs(self, m):
        _at(m, 0x8000, 0xF3)
        m.iff = True
        m.iff2 = True
        m._step()
        assert m.iff is False, "DI should clear iff1"
        assert m.iff2 is False, "DI should clear iff2"
