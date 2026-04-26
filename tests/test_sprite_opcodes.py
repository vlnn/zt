"""
Tests for the new Z80 opcodes added to support SP-stream sprite primitives:
ld_sp_hl, ld_sp_ind_nn, ld_ind_nn_sp, ld_ind_hl_b, ld_ind_hl_c, inc_l, dec_l, add_a_n.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.opcodes import OPCODES
from zt.sim import Z80


def _step(cpu: Z80, *program: int) -> None:
    for i, byte in enumerate(program):
        cpu.mem[(cpu.pc + i) & 0xFFFF] = byte
    cpu._step()


@pytest.fixture
def z80() -> Z80:
    return Z80()


class TestAsmEmissionForNewOpcodes:

    @pytest.mark.parametrize("mnemonic,expected_bytes", [
        ("ld_sp_hl",       [0xF9]),
        ("ld_ind_hl_b",    [0x70]),
        ("ld_ind_hl_c",    [0x71]),
        ("inc_l",          [0x2C]),
        ("dec_l",          [0x2D]),
    ])
    def test_no_operand_emission(self, mnemonic, expected_bytes):
        a = Asm(0x8000, inline_next=False)
        getattr(a, mnemonic)()
        assert bytes(a.code) == bytes(expected_bytes), (
            f"Asm.{mnemonic}() should emit {expected_bytes}"
        )

    def test_add_a_n_emission(self):
        a = Asm(0x8000, inline_next=False)
        a.add_a_n(0x20)
        assert bytes(a.code) == bytes([0xC6, 0x20]), (
            "Asm.add_a_n(0x20) should emit C6 20"
        )

    @pytest.mark.parametrize("mnemonic,expected_prefix", [
        ("ld_sp_ind_nn",   [0xED, 0x7B]),
        ("ld_ind_nn_sp",   [0xED, 0x73]),
    ])
    def test_ed_prefixed_nn_emission(self, mnemonic, expected_prefix):
        a = Asm(0x8000, inline_next=False)
        getattr(a, mnemonic)(0x5BFF)
        expected = bytes([*expected_prefix, 0xFF, 0x5B])
        assert bytes(a.code) == expected, (
            f"Asm.{mnemonic}(0x5BFF) should emit {list(expected)}"
        )


class TestNewOpcodesPresentInTable:

    @pytest.mark.parametrize("mnemonic", [
        "ld_sp_hl", "ld_sp_ind_nn", "ld_ind_nn_sp",
        "ld_ind_hl_b", "ld_ind_hl_c",
        "inc_l", "dec_l", "add_a_n",
    ])
    def test_mnemonic_listed(self, mnemonic):
        names = {spec.mnemonic for spec in OPCODES}
        assert mnemonic in names, f"{mnemonic} should appear in OPCODES"


class TestLdSpHl:

    def test_loads_hl_into_sp(self, z80):
        z80.hl = 0xBEEF
        z80.sp = 0xFFFF
        _step(z80, 0xF9)
        assert z80.sp == 0xBEEF, "ld sp,hl should copy HL into SP"
        assert z80.pc == 1, "ld sp,hl should advance pc by 1"


class TestLdIndNnSp:

    def test_writes_sp_low_then_high(self, z80):
        z80.sp = 0x1234
        _step(z80, 0xED, 0x73, 0x00, 0xC0)
        assert z80.mem[0xC000] == 0x34, "ld (nn),sp should store SP low at nn"
        assert z80.mem[0xC001] == 0x12, "ld (nn),sp should store SP high at nn+1"
        assert z80.pc == 4, "ld (nn),sp should advance pc by 4"


class TestLdSpIndNn:

    def test_reads_low_then_high_into_sp(self, z80):
        z80.mem[0xC000] = 0xCD
        z80.mem[0xC001] = 0xAB
        _step(z80, 0xED, 0x7B, 0x00, 0xC0)
        assert z80.sp == 0xABCD, "ld sp,(nn) should load SP from nn (little endian)"
        assert z80.pc == 4, "ld sp,(nn) should advance pc by 4"


class TestLdIndHlR:

    @pytest.mark.parametrize("opcode,reg,value", [
        (0x70, "b", 0xAA),
        (0x71, "c", 0x55),
    ])
    def test_writes_register_to_hl_address(self, z80, opcode, reg, value):
        z80.hl = 0xC000
        setattr(z80, reg, value)
        _step(z80, opcode)
        assert z80.mem[0xC000] == value, (
            f"ld (hl),{reg} should store {reg} at (hl)"
        )


class TestIncDecL:

    def test_inc_l_increments_low_byte(self, z80):
        z80.hl = 0x4001
        _step(z80, 0x2C)
        assert z80.l == 0x02, "inc l should increment L"
        assert z80.h == 0x40, "inc l should not touch H"

    def test_inc_l_wraps_within_byte(self, z80):
        z80.hl = 0x40FF
        _step(z80, 0x2C)
        assert z80.l == 0x00, "inc l should wrap from 0xFF to 0x00"
        assert z80.h == 0x40, "inc l should not propagate carry into H"

    def test_dec_l_decrements_low_byte(self, z80):
        z80.hl = 0x4005
        _step(z80, 0x2D)
        assert z80.l == 0x04, "dec l should decrement L"

    def test_dec_l_wraps_within_byte(self, z80):
        z80.hl = 0x4000
        _step(z80, 0x2D)
        assert z80.l == 0xFF, "dec l should wrap from 0x00 to 0xFF"
        assert z80.h == 0x40, "dec l should not borrow from H"


class TestAddAN:

    @pytest.mark.parametrize("a_in,n,expected", [
        (0x10, 0x20, 0x30),
        (0xF0, 0x20, 0x10),
        (0x00, 0x00, 0x00),
        (0xFF, 0x01, 0x00),
    ])
    def test_adds_immediate(self, z80, a_in, n, expected):
        z80.a = a_in
        _step(z80, 0xC6, n)
        assert z80.a == expected, (
            f"add a,{n:#x} with A={a_in:#x} should yield A={expected:#x}"
        )
