"""
Tests for IM 2 interrupt firing: explicit `fire_interrupt()`, frame-rate auto-fire
in `run_until`, HALT-aware waiting, and the EI-deferred-by-one-instruction quirk.
M2 of the IM 2 milestone.
"""
from __future__ import annotations

import pytest

from zt.sim import FRAME_T_STATES_48K, FRAME_T_STATES_128K, Z80


@pytest.fixture
def m():
    m = Z80()
    m.sp = 0xFF00
    return m


@pytest.fixture
def m128():
    m = Z80(mode="128k")
    m.sp = 0xFF00
    return m


def _fill_vector_table(m, page, value):
    base = page << 8
    for offset in range(257):
        m._wb(base + offset, value)


def _install_jp(m, addr, target):
    m._wb(addr, 0xC3)
    m._wb(addr + 1, target & 0xFF)
    m._wb(addr + 2, (target >> 8) & 0xFF)


class TestFrameTStatesConstants:

    def test_48k_frame_is_69888(self):
        assert FRAME_T_STATES_48K == 69888, \
            "48K frame should be exactly 69888 T-states"

    def test_128k_frame_is_70908(self):
        assert FRAME_T_STATES_128K == 70908, \
            "128K frame should be exactly 70908 T-states"

    def test_z80_picks_frame_constant_by_mode(self, m, m128):
        assert m.t_states_per_frame == FRAME_T_STATES_48K, \
            "48K Z80 should select FRAME_T_STATES_48K"
        assert m128.t_states_per_frame == FRAME_T_STATES_128K, \
            "128K Z80 should select FRAME_T_STATES_128K"


class TestDefaultInterruptState:

    def test_default_bus_byte_is_ff(self, m):
        assert m.bus_byte == 0xFF, "fresh Z80 should default bus_byte to 0xFF"

    def test_default_interrupt_count_is_zero(self, m):
        assert m.interrupt_count == 0, "fresh Z80 should report 0 fires"

    def test_default_deadline_is_one_frame(self, m):
        assert m._next_int_at == FRAME_T_STATES_48K, \
            "fresh 48K Z80 should defer first interrupt by exactly one frame"

    def test_default_deadline_for_128k(self, m128):
        assert m128._next_int_at == FRAME_T_STATES_128K, \
            "fresh 128K Z80 should defer first interrupt by exactly one frame"


class TestFireInterruptIffGate:

    def test_no_fire_when_iff_false(self, m):
        m.iff = False
        m.im_mode = 1
        m.pc = 0x9000
        m.fire_interrupt()
        assert m.pc == 0x9000, "fire with iff=False should not change PC"
        assert m.interrupt_count == 0, "fire with iff=False should not be counted"


class TestFireInterruptIm1:

    def _arm(self, m):
        m.iff = True
        m.iff2 = True
        m.im_mode = 1
        m.pc = 0x9000

    def test_jumps_to_0038(self, m):
        self._arm(m)
        m.fire_interrupt()
        assert m.pc == 0x0038, "IM 1 fire should jump PC to $0038"

    def test_pushes_old_pc(self, m):
        self._arm(m)
        m.fire_interrupt()
        assert m.sp == 0xFEFE, "IM 1 fire should decrement SP by 2"
        assert m._rw(m.sp) == 0x9000, \
            "IM 1 fire should push the old PC as the return address"

    def test_clears_both_iffs(self, m):
        self._arm(m)
        m.fire_interrupt()
        assert m.iff is False, "interrupt acknowledge should clear iff1"
        assert m.iff2 is False, "interrupt acknowledge should clear iff2"

    def test_costs_13_t_states(self, m):
        self._arm(m)
        before = m._t_states
        m.fire_interrupt()
        assert m._t_states - before == 13, \
            "IM 1 acknowledge should cost 13 T-states"

    def test_increments_interrupt_count(self, m):
        self._arm(m)
        m.fire_interrupt()
        m.iff = True
        m.fire_interrupt()
        assert m.interrupt_count == 2, \
            "two fires should record 2 in interrupt_count"


class TestFireInterruptIm2:

    def _arm(self, m, page=0xB8, value=0xB9):
        _fill_vector_table(m, page=page, value=value)
        m.iff = True
        m.im_mode = 2
        m.i = page
        m.pc = 0x9000

    @pytest.mark.parametrize("bus_byte", [0x00, 0x55, 0xAA, 0xFE, 0xFF])
    def test_dispatches_via_vector_regardless_of_bus_byte(self, m, bus_byte):
        self._arm(m)
        m.bus_byte = bus_byte
        m.fire_interrupt()
        assert m.pc == 0xB9B9, (
            f"IM 2 with bus_byte={bus_byte:#04x}, i=0xB8, table=0xB9 "
            f"should always land at $B9B9"
        )

    def test_pushes_old_pc(self, m):
        self._arm(m)
        m.fire_interrupt()
        assert m._rw(m.sp) == 0x9000, \
            "IM 2 fire should push old PC same as IM 1"

    def test_clears_both_iffs(self, m):
        self._arm(m)
        m.iff2 = True
        m.fire_interrupt()
        assert m.iff is False, "IM 2 acknowledge should clear iff1"
        assert m.iff2 is False, "IM 2 acknowledge should clear iff2"

    def test_costs_19_t_states(self, m):
        self._arm(m)
        before = m._t_states
        m.fire_interrupt()
        assert m._t_states - before == 19, \
            "IM 2 acknowledge should cost 19 T-states"


class TestFireInterruptUnhalts:

    def test_halted_machine_unhalts(self, m):
        m.halted = True
        m.iff = True
        m.im_mode = 1
        m.pc = 0x9001
        m.fire_interrupt()
        assert m.halted is False, "fire_interrupt should clear the halted flag"
        assert m.pc == 0x0038, "PC should reach handler address after unhalt"

    def test_pushed_pc_is_post_halt_address(self, m):
        m.halted = True
        m.iff = True
        m.im_mode = 1
        m.pc = 0x9001
        m.fire_interrupt()
        assert m._rw(m.sp) == 0x9001, \
            "pushed return address should be the post-HALT instruction"


class TestRunUntilFrameRateFire:

    def _setup_im1_handler_loop(self, m):
        _install_jp(m, 0x0038, 0x9000)
        m._wb(0x9000, 0xFB)
        m._wb(0x9001, 0xED)
        m._wb(0x9002, 0x4D)
        m._wb(0x8000, 0x76)
        m._wb(0x8001, 0x18)
        m._wb(0x8002, 0xFD)
        m.pc = 0x8000
        m.iff = True
        m.iff2 = True
        m.im_mode = 1

    @pytest.mark.parametrize("frames", [1, 3, 5])
    def test_fires_once_per_frame(self, m, frames):
        self._setup_im1_handler_loop(m)
        m.run_until(FRAME_T_STATES_48K * frames)
        assert m.interrupt_count == frames, (
            f"running {frames} frames should fire exactly {frames} interrupts, "
            f"got {m.interrupt_count}"
        )

    def test_128k_uses_128k_frame_budget(self, m128):
        self._setup_im1_handler_loop(m128)
        m128.run_until(FRAME_T_STATES_128K * 4)
        assert m128.interrupt_count == 4, \
            "128K frame should be the cadence on a 128K Z80"

    def test_no_fires_when_iff_false(self, m):
        m._wb(0x8000, 0x76)
        m.pc = 0x8000
        m.iff = False
        m.run_until(FRAME_T_STATES_48K * 3)
        assert m.interrupt_count == 0, "iff=False should produce zero fires"

    def test_di_prevents_firing(self, m):
        m._wb(0x8000, 0xF3)
        m._wb(0x8001, 0x76)
        m.pc = 0x8000
        m.iff = True
        m.im_mode = 1
        m.run_until(FRAME_T_STATES_48K * 3)
        assert m.interrupt_count == 0, "DI should prevent any auto-fire"


class TestRunUntilHaltSemantics:

    def test_halt_with_iff_false_breaks_out_early(self, m):
        m._wb(0x8000, 0x76)
        m.pc = 0x8000
        m.iff = False
        m.run_until(FRAME_T_STATES_48K * 5)
        assert m._t_states < FRAME_T_STATES_48K * 5, (
            "HALT with iff=False should exit run_until before the time budget"
        )

    def test_halt_with_iff_true_waits_for_interrupt(self, m):
        _install_jp(m, 0x0038, 0x9000)
        m._wb(0x9000, 0x18)
        m._wb(0x9001, 0xFE)
        m._wb(0x8000, 0x76)
        m.pc = 0x8000
        m.iff = True
        m.iff2 = True
        m.im_mode = 1
        m.run_until(FRAME_T_STATES_48K * 2)
        assert m.interrupt_count >= 1, \
            "HALT with iff=True must keep ticking until at least one fire"


class TestEiPendingDelay:

    def test_nop_after_ei_executes_before_interrupt(self, m):
        m._wb(0x8000, 0xFB)
        m._wb(0x8001, 0x00)
        m._wb(0x8002, 0x76)
        _install_jp(m, 0x0038, 0x9000)
        m._wb(0x9000, 0x76)
        m.pc = 0x8000
        m.iff = False
        m.im_mode = 1
        m._next_int_at = 0
        m.run_until(1000)
        assert m.interrupt_count == 1, \
            f"exactly one fire expected after deadline-zero, got {m.interrupt_count}"
        assert m._rw(m.sp) == 0x8002, (
            f"NOP after EI must execute before fire — return address should be "
            f"$8002 (post-NOP), got {m._rw(m.sp):#06x}"
        )

    def test_default_ei_pending_is_false(self, m):
        assert m._ei_pending is False, \
            "fresh Z80 should reset _ei_pending to False"

    def test_ei_sets_ei_pending(self, m):
        m.load(0x8000, bytes([0xFB]))
        m.pc = 0x8000
        m._step()
        assert m._ei_pending is True, \
            "EI should set _ei_pending to defer the next auto-fire check"
