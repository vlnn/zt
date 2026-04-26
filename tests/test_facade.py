"""Tests for `zt.test_facade.Run`, the inspection layer over `ForthResult`.

The facade lets pytest-level tests assert on the post-run state of a
`ForthMachine` without reaching into Z80 register names, bare addresses,
or `_last_m`.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitives import PRIMITIVES
from zt.sim import (
    SPECTRUM_ATTR_BASE,
    ForthMachine,
    decode_screen_cell,
    screen_addr,
)
from zt.test_facade import Run


@pytest.fixture
def fm() -> ForthMachine:
    return ForthMachine()


@pytest.fixture
def fm128() -> ForthMachine:
    return ForthMachine(mode="128k")


def _run_cells(fm: ForthMachine, cells, **kwargs) -> Run:
    result = fm.run(cells, **kwargs)
    return Run(machine=fm, result=result)


class TestStack:

    @pytest.mark.parametrize("values, expected_top", [
        ([42], 42),
        ([1, 2, 3], 3),
        ([0xFFFF], 0xFFFF),
    ])
    def test_top_returns_tos(self, fm, values, expected_top):
        cells = []
        for v in values:
            cells.extend(["LIT", v])
        run = _run_cells(fm, cells)
        assert run.top() == expected_top, (
            f"top() should return TOS after pushing {values}"
        )

    def test_stack_returns_full_stack_bottom_first(self, fm):
        run = _run_cells(fm, ["LIT", 10, "LIT", 20, "LIT", 30])
        assert run.stack() == (10, 20, 30), (
            "stack() should return all cells, bottom-first"
        )

    def test_top_on_empty_stack_raises(self, fm):
        run = _run_cells(fm, [])
        with pytest.raises(IndexError, match="empty"):
            run.top()

    def test_depth_counts_cells(self, fm):
        run = _run_cells(fm, ["LIT", 1, "LIT", 2, "LIT", 3, "LIT", 4])
        assert run.depth() == 4, "depth() should count all values on stack"


class TestEmitCursor:

    def test_cursor_starts_at_origin(self, fm):
        run = _run_cells(fm, [])
        assert run.cursor() == (0, 0), (
            "cursor() should be (0, 0) before any emit"
        )

    def test_cursor_advances_on_emit(self, fm):
        run = _run_cells(fm, ["LIT", ord("A"), "EMIT"])
        assert run.cursor() == (0, 1), (
            "cursor() should advance one column after emitting one char"
        )

    def test_chars_out_returns_emitted_text(self, fm):
        cells = []
        for ch in "HI":
            cells.extend(["LIT", ord(ch), "EMIT"])
        run = _run_cells(fm, cells)
        assert run.chars_out() == b"HI", (
            "chars_out() should return what was EMIT-ted, in order"
        )


class TestScreen:

    def test_screen_reads_decoded_cell(self, fm):
        run = _run_cells(fm, [])
        for line in range(8):
            run.machine._last_m.mem[screen_addr(0, 0, line)] = ord("Z")
        assert run.screen(0, 0) == ord("Z"), (
            "screen(0, 0) should decode the cell painted at row 0 col 0"
        )

    @pytest.mark.parametrize("row, col", [(0, 0), (5, 3), (23, 31)])
    def test_screen_decodes_arbitrary_cell(self, fm, row, col):
        run = _run_cells(fm, [])
        for line in range(8):
            run.machine._last_m.mem[screen_addr(row, col, line)] = ord("X")
        assert run.screen(row, col) == ord("X"), (
            f"screen({row}, {col}) should decode the painted cell"
        )

    def test_attr_reads_attribute_byte(self, fm):
        run = _run_cells(fm, [])
        run.machine._last_m.mem[SPECTRUM_ATTR_BASE + 0] = 0x47
        assert run.attr(0, 0) == 0x47, (
            "attr(0, 0) should return the byte at SPECTRUM_ATTR_BASE"
        )

    @pytest.mark.parametrize("row, col, expected_offset", [
        (0, 0, 0),
        (0, 31, 31),
        (1, 0, 32),
        (23, 31, 23 * 32 + 31),
    ])
    def test_attr_addresses_full_screen(self, fm, row, col, expected_offset):
        run = _run_cells(fm, [])
        run.machine._last_m.mem[SPECTRUM_ATTR_BASE + expected_offset] = 0x12
        assert run.attr(row, col) == 0x12, (
            f"attr({row}, {col}) should map to attr base + {expected_offset}"
        )


class TestBorder:

    def test_border_writes_starts_empty(self, fm):
        run = _run_cells(fm, [])
        assert run.border_writes() == (), (
            "border_writes() should be empty when no border port hit"
        )

    def test_border_writes_records_each_write(self, fm):
        run = _run_cells(fm, ["LIT", 2, "BORDER", "LIT", 4, "BORDER"])
        assert run.border_writes() == (2, 4), (
            "border_writes() should record each port-$FE write in order"
        )


class TestBanks:

    def test_bank_requires_128k(self, fm):
        run = _run_cells(fm, [])
        with pytest.raises(RuntimeError, match="128k"):
            run.bank(0)

    @pytest.mark.parametrize("bank_id", [0, 1, 3, 4, 6, 7])
    def test_bank_reads_paged_or_unpaged(self, fm128, bank_id):
        run = _run_cells(fm128, [])
        run.machine._last_m.load_bank(bank_id, bytes([bank_id]) * 16)
        assert run.bank(bank_id)[:16] == bytes([bank_id]) * 16, (
            f"bank({bank_id}) should return that bank's contents"
        )

    def test_bank_returns_16k_byte_block(self, fm128):
        run = _run_cells(fm128, [])
        assert len(run.bank(3)) == 0x4000, (
            "bank() should return exactly 16 KB"
        )

    def test_page_writes_records_7ffd_writes(self, fm128):
        run = _run_cells(fm128, ["LIT", 3, "BANK!", "LIT", 5, "BANK!"])
        writes = run.page_writes()
        assert len(writes) >= 2, (
            "page_writes() should record each $7FFD write"
        )
        bank_ids = [w & 0x07 for w in writes[-2:]]
        assert bank_ids == [3, 5], (
            "page_writes() last two should reflect the BANK! sequence"
        )


class TestPagingState:

    @pytest.mark.parametrize("bank_id", [0, 3, 5, 7])
    def test_paged_bank_returns_low_three_bits(self, fm128, bank_id):
        fm128.run([fm128.label("LIT"), bank_id, fm128.label("BANK!")])
        run = Run.of(fm128)
        assert run.paged_bank() == bank_id, (
            f"paged_bank() should be {bank_id} after BANK! {bank_id}"
        )

    def test_paged_bank_requires_128k(self, fm):
        fm.run([])
        run = Run.of(fm)
        with pytest.raises(RuntimeError, match="128k"):
            run.paged_bank()

    def test_port_7ffd_returns_full_byte(self, fm128):
        fm128.run([fm128.label("LIT"), 0x17, fm128.label("RAW-BANK!")])
        run = Run.of(fm128)
        assert run.port_7ffd() == 0x17, (
            "port_7ffd() should return the full byte including upper bits"
        )

    def test_bank_shadow_reads_5b5c(self, fm128):
        fm128.run([fm128.label("LIT"), 5, fm128.label("BANK!")])
        run = Run.of(fm128)
        assert run.bank_shadow() == run.port_7ffd(), (
            "bank_shadow() should match the live port_7ffd value"
        )


class TestRawAccess:

    def test_byte_reads_one_byte(self, fm):
        run = _run_cells(fm, [])
        run.machine._last_m.mem[0x9000] = 0xAB
        assert run.byte(0x9000) == 0xAB, (
            "byte(addr) should read one byte from memory"
        )

    def test_word_reads_little_endian_word(self, fm):
        run = _run_cells(fm, [])
        run.machine._last_m.mem[0x9000] = 0xCD
        run.machine._last_m.mem[0x9001] = 0xAB
        assert run.word(0x9000) == 0xABCD, (
            "word(addr) should read 16-bit little-endian"
        )

    def test_byte_rejects_out_of_range(self, fm):
        run = _run_cells(fm, [])
        with pytest.raises(ValueError, match="address"):
            run.byte(-1)


class TestRunOfWithoutResult:
    """`Run.of(fm)` after a bare `fm.run(...)` — supports tests that don't
    capture the ForthResult, only inspect post-run state."""

    def test_cursor_works_without_result(self, fm):
        fm.run([])
        run = Run.of(fm)
        assert run.cursor() == (0, 0), (
            "cursor() should work without a captured ForthResult"
        )

    def test_screen_works_without_result(self, fm):
        fm.run([])
        run = Run.of(fm)
        for line in range(8):
            fm._last_m.mem[screen_addr(0, 0, line)] = ord("Q")
        assert run.screen(0, 0) == ord("Q"), (
            "screen() should work without a captured ForthResult"
        )

    def test_top_without_result_raises_with_helpful_message(self, fm):
        fm.run([])
        run = Run.of(fm)
        with pytest.raises(RuntimeError, match="captured ForthResult"):
            run.top()

    def test_chars_out_without_result_raises(self, fm):
        fm.run([])
        run = Run.of(fm)
        with pytest.raises(RuntimeError, match="captured ForthResult"):
            run.chars_out()

    def test_border_writes_derived_from_machine(self, fm):
        fm.run(["LIT", 5, "BORDER"])
        run = Run.of(fm)
        assert run.border_writes() == (5,), (
            "border_writes() should derive from machine outputs when no result"
        )
