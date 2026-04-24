"""
Tests for the banked-memory simulator path: 128K mode construction, `$7FFD`
partial-decode port matching, paging swaps mem[$C000:], bit-5 lock, bank
inspection helpers, `OUT (C),A` (ED 79), and the no-regression guarantee for
48K mode.
"""
from __future__ import annotations

import pytest

from zt.sim import Z80, is_7ffd_write


class TestConstruction:

    def test_48k_is_default(self):
        m = Z80()
        assert m.mode == "48k", "default construction should be 48K mode"

    def test_48k_mem_is_64k_bytearray(self):
        m = Z80(mode="48k")
        assert isinstance(m.mem, bytearray), "m.mem should remain a bytearray"
        assert len(m.mem) == 0x10000, "48K m.mem should be exactly 64 KB"

    def test_128k_mode_accepted(self):
        m = Z80(mode="128k")
        assert m.mode == "128k", "128K mode should set m.mode='128k'"

    def test_128k_mem_is_still_64k_view(self):
        m = Z80(mode="128k")
        assert isinstance(m.mem, bytearray), (
            "128K m.mem should stay a bytearray (live 64K view)"
        )
        assert len(m.mem) == 0x10000, "128K m.mem should be exactly 64 KB"

    def test_128k_starts_with_bank_zero_paged(self):
        m = Z80(mode="128k")
        assert m.port_7ffd == 0, "port $7FFD should initialise to 0"


class TestIs7ffdWrite:

    @pytest.mark.parametrize("port", [0x7FFD, 0x7DFD, 0x4000, 0x0000])
    def test_matches_a15_low_a1_low(self, port):
        assert is_7ffd_write(port), (
            f"port {port:#06x} with A15=0 and A1=0 should match $7FFD decode"
        )

    @pytest.mark.parametrize("port", [0xFFFD, 0xBFFD, 0x8000, 0xF000])
    def test_rejects_a15_high(self, port):
        assert not is_7ffd_write(port), (
            f"port {port:#06x} with A15=1 should NOT match $7FFD decode"
        )

    @pytest.mark.parametrize("port", [0x7FFF, 0x0002, 0x7F02])
    def test_rejects_a1_high(self, port):
        assert not is_7ffd_write(port), (
            f"port {port:#06x} with A1=1 should NOT match $7FFD decode"
        )


class TestPagingFromOutNA:

    def test_out_to_7ffd_updates_port_byte(self):
        m = Z80(mode="128k")
        m.load(0x8000, bytes([0xD3, 0xFD]))
        m.a = 0x7F
        m.pc = 0x8000
        m._step()
        assert m.port_7ffd == 0x7F, (
            "OUT ($FD),A with A=$7F should land in $7FFD and update port"
        )

    def test_paging_swaps_c000_region(self):
        m = Z80(mode="128k")
        m.mem[0xC000] = 0xAA
        m.page_bank(1)
        m.mem[0xC000] = 0xBB
        m.page_bank(0)
        assert m.mem[0xC000] == 0xAA, (
            "bank 0 should retain 0xAA after paging out to bank 1 and back"
        )
        m.page_bank(1)
        assert m.mem[0xC000] == 0xBB, (
            "bank 1 should retain 0xBB after paging out to bank 0 and back"
        )

    @pytest.mark.parametrize("bank", [0, 1, 3, 4, 6, 7])
    def test_each_bank_holds_independent_bytes(self, bank):
        m = Z80(mode="128k")
        for b in range(8):
            m.page_bank(b)
            m.mem[0xC000] = b + 0x20
        m.page_bank(bank)
        assert m.mem[0xC000] == bank + 0x20, (
            f"bank {bank} should hold its own byte independently of others"
        )

    def test_4000_8000_always_bank_5(self):
        m = Z80(mode="128k")
        m.mem[0x4000] = 0x55
        m.page_bank(3)
        assert m.mem[0x4000] == 0x55, (
            "writes to $4000 are bank 5, which is always mapped regardless of paging"
        )

    def test_8000_c000_always_bank_2(self):
        m = Z80(mode="128k")
        m.mem[0x8000] = 0x22
        m.page_bank(7)
        assert m.mem[0x8000] == 0x22, (
            "writes to $8000 are bank 2, which is always mapped regardless of paging"
        )


class TestLock:

    def test_lock_bit_freezes_paging(self):
        m = Z80(mode="128k")
        m.page_bank(3)
        m._write_port_7ffd(0x20 | 3)
        m._write_port_7ffd(5)
        assert m.port_7ffd & 0x07 == 3, (
            "after lock bit is set, further paging writes must be ignored"
        )

    def test_lock_persists_across_writes(self):
        m = Z80(mode="128k")
        m._write_port_7ffd(0x20)
        for attempted in range(8):
            m._write_port_7ffd(attempted)
        assert m.port_7ffd & 0x07 == 0, (
            "lock bit should block every subsequent paging change"
        )


class TestOutCARegisterViaEd79:

    def test_out_c_a_captures_full_port(self):
        m = Z80(mode="48k")
        m.load(0x8000, bytes([0xED, 0x79]))
        m.bc = 0x7FFD
        m.a = 0x42
        m.pc = 0x8000
        m._step()
        assert m._outputs[-1] == (0x7FFD, 0x42), (
            "OUT (C),A should record (BC, A) in _outputs"
        )

    def test_out_c_a_pages_in_128k_mode(self):
        m = Z80(mode="128k")
        m.load(0x8000, bytes([0xED, 0x79]))
        m.bc = 0x7FFD
        m.a = 0x04
        m.pc = 0x8000
        m._step()
        assert m.port_7ffd == 0x04, (
            "OUT (C),A with BC=$7FFD should page bank via 128K latch"
        )

    def test_out_c_a_ignored_in_48k_mode(self):
        m = Z80(mode="48k")
        m.load(0x8000, bytes([0xED, 0x79]))
        m.bc = 0x7FFD
        m.a = 0x04
        m.pc = 0x8000
        m._step()
        assert not hasattr(m, "_banks") or m._banks is None, (
            "48K simulator should not gain banks when ED 79 runs"
        )


class TestBankInspection:

    def test_mem_bank_returns_bank_storage(self):
        m = Z80(mode="128k")
        m.page_bank(4)
        m.mem[0xC000] = 0x99
        m.page_bank(0)
        bank4 = m.mem_bank(4)
        assert bank4[0] == 0x99, (
            "mem_bank(4) should expose bank 4's byte after paging out"
        )

    def test_mem_bank_for_active_paged_reflects_live_writes(self):
        m = Z80(mode="128k")
        m.page_bank(3)
        m.mem[0xC000] = 0x77
        bank3 = m.mem_bank(3)
        assert bank3[0] == 0x77, (
            "mem_bank(n) for the currently paged bank should reflect live writes"
        )

    def test_mem_bank_five_reflects_slot_one(self):
        m = Z80(mode="128k")
        m.mem[0x4000] = 0x55
        bank5 = m.mem_bank(5)
        assert bank5[0] == 0x55, (
            "mem_bank(5) should mirror mem[$4000:$8000]"
        )

    def test_mem_bank_two_reflects_slot_two(self):
        m = Z80(mode="128k")
        m.mem[0x8000] = 0x22
        bank2 = m.mem_bank(2)
        assert bank2[0] == 0x22, (
            "mem_bank(2) should mirror mem[$8000:$C000]"
        )

    @pytest.mark.parametrize("bank", list(range(8)))
    def test_mem_bank_in_48k_mode_raises(self, bank):
        m = Z80(mode="48k")
        with pytest.raises(RuntimeError, match="128k"):
            m.mem_bank(bank)


class TestFortyEightKRegression:

    def test_out_to_7ffd_in_48k_does_not_page(self):
        m = Z80(mode="48k")
        m.load(0x8000, bytes([0xED, 0x79]))
        m.bc = 0x7FFD
        m.a = 0x05
        m.pc = 0x8000
        m.mem[0xC000] = 0xEE
        m._step()
        assert m.mem[0xC000] == 0xEE, (
            "48K simulator must not swap memory when paging port is written"
        )

    def test_out_to_7ffd_in_48k_still_recorded_in_outputs(self):
        m = Z80(mode="48k")
        m.load(0x8000, bytes([0xED, 0x79]))
        m.bc = 0x7FFD
        m.a = 0x05
        m.pc = 0x8000
        m._step()
        assert (0x7FFD, 0x05) in m._outputs, (
            "48K simulator should still log the OUT in _outputs even though it's a no-op"
        )
