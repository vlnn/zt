"""
Tests for the IM 2 control primitives: `IM2-HANDLER!`, `IM2-HANDLER@`, `IM2-OFF`.
Covers byte-level encoding, single-call execution effects on Z80 state, and the
end-to-end loop of install → fire → handler → RETI → caller continues.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.im2_table import (
    IM2_HANDLER_SLOT_ADDR,
    IM2_TABLE_PAGE,
)
from zt.assemble.primitives import (
    create_im2_handler_fetch,
    create_im2_handler_store,
    create_im2_off,
)
from zt.sim import FRAME_T_STATES_48K, ForthMachine


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    a.label("__im2_thread__")
    a.label("__im2_shim__")
    a.label("__im2_exit__")
    return a


def _compile(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


_DISPATCH_TO_NEXT = bytes([0xC3, 0x00, 0x80])
_PLACEHOLDER_ADDR = 0x8000


class TestIm2HandlerStoreBytes:

    def test_first_byte_is_di(self):
        out = _compile(create_im2_handler_store)
        assert out[0] == 0xF3, "IM2-HANDLER! must start with DI to install atomically"

    def test_then_writes_xt_to_thread_cell_zero(self):
        out = _compile(create_im2_handler_store)
        assert out[1] == 0x22, \
            "after DI, expect LD (nn),HL writing the user xt into __im2_thread__ cell 0"
        assert (out[2] | (out[3] << 8)) == _PLACEHOLDER_ADDR, \
            "operand should be the address of __im2_thread__ (placeholder $8000 in this asm)"

    def test_then_loads_shim_address_into_hl(self):
        out = _compile(create_im2_handler_store)
        assert out[4] == 0x21, "next: LD HL,nn loading the shim address (opcode 0x21)"
        assert (out[5] | (out[6] << 8)) == _PLACEHOLDER_ADDR, \
            "operand should be the address of __im2_shim__ (placeholder $8000 in this asm)"

    def test_then_writes_shim_into_jp_slot_operand(self):
        out = _compile(create_im2_handler_store)
        operand_addr = IM2_HANDLER_SLOT_ADDR + 1
        assert out[7] == 0x22, \
            "next: LD (nn),HL writing the shim address into the JP-slot operand at $B9BA"
        assert (out[8] | (out[9] << 8)) == operand_addr, \
            f"operand should be {operand_addr:#06x} ($B9BA)"

    def test_then_loads_table_page_into_a(self):
        out = _compile(create_im2_handler_store)
        assert out[10] == 0x3E, "expect LD A,n (opcode 0x3E)"
        assert out[11] == IM2_TABLE_PAGE, \
            f"immediate byte should be IM2_TABLE_PAGE = {IM2_TABLE_PAGE:#04x}"

    def test_then_copies_a_into_i(self):
        out = _compile(create_im2_handler_store)
        assert out[12:14] == bytes([0xED, 0x47]), \
            "expect LD I,A (ED 47) after loading the page byte"

    def test_then_switches_to_im_2(self):
        out = _compile(create_im2_handler_store)
        assert out[14:16] == bytes([0xED, 0x5E]), \
            "expect IM 2 (ED 5E) right after LD I,A"

    def test_then_pops_fresh_tos_and_dispatches(self):
        out = _compile(create_im2_handler_store)
        assert out[16] == 0xE1, "expect POP HL to load fresh TOS after consuming xt"
        assert out[17:20] == _DISPATCH_TO_NEXT, "then JP NEXT"

    def test_total_length_is_20(self):
        out = _compile(create_im2_handler_store)
        assert len(out) == 20, (
            "IM2-HANDLER! should be DI + LD(thread),HL + LD HL,shim + LD(slot+1),HL "
            "+ LD A,n + LD I,A + IM 2 + POP HL + dispatch = 20 bytes"
        )

    def test_does_not_emit_ei(self):
        out = _compile(create_im2_handler_store)
        assert 0xFB not in out, \
            "IM2-HANDLER! must not emit EI — caller controls when interrupts re-enable"


class TestIm2HandlerStoreExecution:

    @pytest.fixture
    def fm(self):
        return ForthMachine()

    def _install(self, fm, xt):
        fm.run([fm.label("LIT"), xt, fm.label("IM2-HANDLER!"), fm.label("HALT")])

    def test_writes_xt_to_thread_cell_zero(self, fm):
        self._install(fm, 0xC123)
        m = fm._last_m
        thread_addr = fm.label("__im2_thread__")
        assert m._rw(thread_addr) == 0xC123, (
            "IM2-HANDLER! should store the user xt into the first cell of __im2_thread__"
        )

    def test_writes_shim_address_into_jp_slot_operand(self, fm):
        self._install(fm, 0xC123)
        m = fm._last_m
        shim_addr = fm.label("__im2_shim__")
        assert m._rw(IM2_HANDLER_SLOT_ADDR + 1) == shim_addr, (
            f"IM2-HANDLER! should patch the JP slot operand at $B9BA so the IM 2 "
            f"vector dispatches into __im2_shim__ ({shim_addr:#06x}); "
            f"got {m._rw(IM2_HANDLER_SLOT_ADDR + 1):#06x}"
        )

    def test_does_not_overwrite_thread_cell_one(self, fm):
        self._install(fm, 0xC123)
        m = fm._last_m
        thread_addr = fm.label("__im2_thread__")
        assert m._rw(thread_addr + 2) == fm.label("__im2_exit__"), (
            "cell 1 of the thread must keep pointing at __im2_exit__ — "
            "IM2-HANDLER! only writes cell 0"
        )

    def test_sets_i_register_to_table_page(self, fm):
        self._install(fm, 0xC000)
        assert fm._last_m.i == IM2_TABLE_PAGE, \
            f"IM2-HANDLER! should set I to the table page ({IM2_TABLE_PAGE:#04x})"

    def test_sets_im_mode_to_2(self, fm):
        self._install(fm, 0xC000)
        assert fm._last_m.im_mode == 2, "IM2-HANDLER! should put the CPU into IM 2"

    def test_disables_interrupts(self, fm):
        self._install(fm, 0xC000)
        assert fm._last_m.iff is False, \
            "IM2-HANDLER! should leave iff disabled — caller must EI explicitly"


class TestIm2HandlerFetchBytes:

    def test_starts_with_push_hl(self):
        out = _compile(create_im2_handler_fetch)
        assert out[0] == 0xE5, "IM2-HANDLER@ must PUSH HL first to preserve current TOS"

    def test_then_loads_thread_cell_zero_into_hl(self):
        out = _compile(create_im2_handler_fetch)
        assert out[1] == 0x2A, "expect LD HL,(nn) (opcode 0x2A)"
        assert (out[2] | (out[3] << 8)) == _PLACEHOLDER_ADDR, (
            "operand should be the address of __im2_thread__ (placeholder $8000 in this asm)"
        )

    def test_then_dispatches(self):
        out = _compile(create_im2_handler_fetch)
        assert out[4:7] == _DISPATCH_TO_NEXT, "JP NEXT after HL is loaded"

    def test_total_length_is_7(self):
        out = _compile(create_im2_handler_fetch)
        assert len(out) == 7, \
            "IM2-HANDLER@ should be PUSH HL + LD HL,(nn) + dispatch = 7 bytes"


class TestIm2HandlerFetchExecution:

    def test_returns_address_previously_installed(self):
        fm = ForthMachine()
        result = fm.run([
            fm.label("LIT"), 0xABCD, fm.label("IM2-HANDLER!"),
            fm.label("IM2-HANDLER@"),
            fm.label("HALT"),
        ])
        assert result.data_stack == [0xABCD], \
            "after install of $ABCD, IM2-HANDLER@ should leave $ABCD on the data stack"


class TestIm2OffBytes:

    def test_starts_with_di(self):
        out = _compile(create_im2_off)
        assert out[0] == 0xF3, "IM2-OFF must start with DI"

    def test_then_switches_to_im_1(self):
        out = _compile(create_im2_off)
        assert out[1:3] == bytes([0xED, 0x56]), \
            "expect IM 1 (ED 56) so a stray IRQ goes to $0038, not via the vector table"

    def test_then_dispatches(self):
        out = _compile(create_im2_off)
        assert out[3:6] == _DISPATCH_TO_NEXT, "JP NEXT — HL not touched, no POP needed"

    def test_total_length_is_6(self):
        out = _compile(create_im2_off)
        assert len(out) == 6, "IM2-OFF should be DI + IM 1 + dispatch = 6 bytes"

    def test_does_not_touch_i_register(self):
        out = _compile(create_im2_off)
        assert 0x47 not in [out[i+1] for i in range(len(out) - 1) if out[i] == 0xED], \
            "IM2-OFF should not emit LD I,A — I stays whatever it was"


class TestIm2OffExecution:

    def test_disables_interrupts(self):
        fm = ForthMachine()
        fm.run([fm.label("LIT"), 0xC000, fm.label("IM2-HANDLER!"),
                fm.label("IM2-OFF"),
                fm.label("HALT")])
        assert fm._last_m.iff is False, "IM2-OFF should leave iff disabled"

    def test_restores_im_1(self):
        fm = ForthMachine()
        fm.run([fm.label("LIT"), 0xC000, fm.label("IM2-HANDLER!"),
                fm.label("IM2-OFF"),
                fm.label("HALT")])
        assert fm._last_m.im_mode == 1, "IM2-OFF should switch back to IM 1"


class TestIm2EndToEndHandlerRuns:

    def _install_then_loop(self, handler_addr: int) -> bytes:
        a = Asm(0x8000, inline_next=False)
        a.ld_hl_nn(handler_addr)
        a.di()
        a.ld_ind_nn_hl(IM2_HANDLER_SLOT_ADDR + 1)
        a.ld_a_n(IM2_TABLE_PAGE)
        a.ld_i_a()
        a.im_2()
        a.ei()
        a.label("halt_loop")
        a.halt()
        a.jr_to("halt_loop")
        return a.resolve()

    def _attribute_increment_isr(self) -> bytes:
        a = Asm(0xC000, inline_next=False)
        a.push_af()
        a.ld_a_ind_nn(0x5800)
        a.inc_a()
        a.ld_ind_nn_a(0x5800)
        a.pop_af()
        a.ei()
        a.reti()
        return a.resolve()

    def test_handler_runs_each_frame_and_reti_resumes_main(self):
        from zt.assemble.im2_table import IM2_TABLE_ADDR, IM2_TABLE_LEN, IM2_VECTOR_BYTE
        from zt.sim import Z80
        m = Z80()
        m.sp = 0xFF00
        m.load(0x8000, self._install_then_loop(handler_addr=0xC000))
        m.load(IM2_TABLE_ADDR, bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN)
        m._wb(IM2_HANDLER_SLOT_ADDR, 0xC3)
        m.load(0xC000, self._attribute_increment_isr())
        m._wb(0x5800, 0)
        m.pc = 0x8000
        m.run_until(FRAME_T_STATES_48K * 3 + 5000)
        assert m._rb(0x5800) == 3, (
            f"handler should have incremented $5800 once per frame across 3 frames, "
            f"got {m._rb(0x5800)}"
        )
        assert m.interrupt_count == 3, \
            "exactly 3 interrupts should have fired in 3 frames"
        assert m.i == IM2_TABLE_PAGE, \
            "I register should still point at the IM 2 table page after RETIs"
