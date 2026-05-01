"""
End-to-end tests for opcodes recently added to the OPCODES table.
Each test compiles a tiny ::: word that exercises the opcode, runs it
through the simulator, and verifies observable state.

Both halves of the work get exercised here: the OPCODES entry (otherwise
::: would fail with "unknown asm mnemonic") and the simulator handler
(otherwise the byte would execute but corrupt state).
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler
from zt.sim import Z80


def _run(source: str) -> tuple[Z80, Compiler]:
    c = Compiler(inline_primitives=False, inline_next=False)
    c.compile_source(source)
    c.compile_main_call()
    image = c.build()
    m = Z80()
    m.load(c.origin, image)
    m.pc = c.words["_start"].address
    m.run()
    assert m.halted, "program should halt cleanly"
    return m, c


class TestIndirectStoreToBcAndDe:

    def test_ld_ind_de_a_writes_byte_at_de(self):
        m, _ = _run(
            "::: w ( -- )\n"
            "  3000 ld_de_nn  77 ld_a_n  ld_ind_de_a ;\n"
            ": main w halt ;"
        )
        assert m.mem[3000] == 77, "ld_ind_de_a should store A=77 at DE=3000"

    def test_ld_ind_bc_a_writes_byte_at_bc(self):
        m, _ = _run(
            "::: w ( -- )\n"
            "  3000 ld_bc_nn  88 ld_a_n  ld_ind_bc_a ;\n"
            ": main w halt ;"
        )
        assert m.mem[3000] == 88, "ld_ind_bc_a should store A=88 at BC=3000"


class TestMemoryIncDec:

    def test_inc_ind_hl_increments_byte_in_place(self):
        m, _ = _run(
            ": setup 7 3000 c! ;\n"
            "::: w ( -- )\n"
            "  3000 ld_hl_nn  inc_ind_hl  pop_hl ;\n"
            ": main setup w halt ;"
        )
        assert m.mem[3000] == 8, "inc_ind_hl from 7 should leave 8"

    def test_dec_ind_hl_decrements_byte_in_place(self):
        m, _ = _run(
            ": setup 7 3000 c! ;\n"
            "::: w ( -- )\n"
            "  3000 ld_hl_nn  dec_ind_hl  pop_hl ;\n"
            ": main setup w halt ;"
        )
        assert m.mem[3000] == 6, "dec_ind_hl from 7 should leave 6"

    def test_inc_ind_hl_wraps_at_byte_boundary(self):
        m, _ = _run(
            ": setup 255 3000 c! ;\n"
            "::: w ( -- )\n"
            "  3000 ld_hl_nn  inc_ind_hl  pop_hl ;\n"
            ": main setup w halt ;"
        )
        assert m.mem[3000] == 0, "inc_ind_hl is byte-wide; 255 should wrap to 0"


class TestImmediateAlu:

    def test_xor_n_clears_a_when_xored_with_self(self):
        m, _ = _run(
            "::: w ( -- )\n"
            "  170 ld_a_n  170 xor_n  ld_l_a 0 ld_h_n ;\n"
            ": main w halt ;"
        )
        from zt.sim import _read_data_stack
        stack = _read_data_stack(m, 0xFFEE, False)
        assert stack[-1] == 0, "170 xor_n 170 should leave A=0, hence TOS=0"

    @pytest.mark.parametrize("a_val,n,expected", [
        (10, 5, 16),
        (0, 0, 1),
        (255, 0, 0),
    ], ids=["10+5+1", "0+0+1", "255+0+1-wraps"])
    def test_adc_a_n_uses_carry(self, a_val, n, expected):
        m, _ = _run(
            f"::: w ( -- )\n"
            f"  scf  {a_val} ld_a_n  {n} adc_a_n  ld_l_a 0 ld_h_n ;\n"
            f": main w halt ;"
        )
        from zt.sim import _read_data_stack
        stack = _read_data_stack(m, 0xFFEE, False)
        assert stack[-1] == (expected & 0xFF), (
            f"scf then {a_val} adc {n} should give A={expected & 0xFF}"
        )


class TestRotateThroughCarry:

    def test_rla_rotates_left_through_carry(self):
        m, _ = _run(
            "::: w ( -- )\n"
            "  scf  64 ld_a_n  rla  ld_l_a 0 ld_h_n ;\n"
            ": main w halt ;"
        )
        from zt.sim import _read_data_stack
        stack = _read_data_stack(m, 0xFFEE, False)
        assert stack[-1] == 129, (
            "RLA on A=64 (0b01000000) with carry set should give 0b10000001 = 129"
        )

    def test_rra_rotates_right_through_carry(self):
        m, _ = _run(
            "::: w ( -- )\n"
            "  scf  2 ld_a_n  rra  ld_l_a 0 ld_h_n ;\n"
            ": main w halt ;"
        )
        from zt.sim import _read_data_stack
        stack = _read_data_stack(m, 0xFFEE, False)
        assert stack[-1] == 129, (
            "RRA on A=2 (0b00000010) with carry set should give 0b10000001 = 129"
        )


class TestCcf:

    def test_ccf_complements_carry(self):
        m, _ = _run(
            "::: w ( -- )\n"
            "  scf  ccf\n"
            "  0 ld_a_n  0 adc_a_n  ld_l_a 0 ld_h_n ;\n"
            ": main w halt ;"
        )
        from zt.sim import _read_data_stack
        stack = _read_data_stack(m, 0xFFEE, False)
        assert stack[-1] == 0, (
            "scf then ccf should leave carry clear; 0 + 0 + carry should be 0"
        )
