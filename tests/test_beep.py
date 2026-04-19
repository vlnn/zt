"""Integration tests for BEEP — verifies port $FE writes toggle bit 4."""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler
from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80


def _run(source: str, max_ticks: int = 2_000_000) -> Z80:
    full = f"{source}\n: main beep-test halt ;\n"
    c = Compiler(include_dirs=[])
    c.compile_source(full)
    c.compile_main_call()
    image = c.build()
    m = Z80()
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = c.words["_start"].address
    m.run(max_ticks=max_ticks)
    assert m.halted, "machine should halt within max_ticks"
    return m


def _fe_writes(m: Z80) -> list[int]:
    return [v for port, v in m._outputs if (port & 0xFF) == 0xFE]


class TestBeepPortWrites:

    def test_one_cycle_produces_two_fe_writes(self):
        m = _run(": beep-test  1 20 beep ;")
        assert len(_fe_writes(m)) == 2, (
            "1 cycle should produce one toggle plus the border-restore write"
        )

    def test_two_cycles_produce_three_fe_writes(self):
        m = _run(": beep-test  2 20 beep ;")
        assert len(_fe_writes(m)) == 3, (
            "2 cycles should produce two toggles plus the border-restore write"
        )

    def test_ten_cycles_produce_eleven_fe_writes(self):
        m = _run(": beep-test  10 20 beep ;")
        assert len(_fe_writes(m)) == 11, (
            "10 cycles should produce 10 toggles plus the border-restore write"
        )

    def test_values_alternate_bit_4(self):
        m = _run(": beep-test  4 10 beep ;")
        writes = _fe_writes(m)
        bit4 = [(v >> 4) & 1 for v in writes[:-1]]
        expected = [1, 0, 1, 0]
        assert bit4 == expected, (
            f"bit 4 should alternate starting from high, got {bit4}"
        )

    def test_only_bit_4_changes(self):
        m = _run(": beep-test  4 10 beep ;")
        writes = _fe_writes(m)
        non_bit4_bits = {v & ~0x10 & 0xFF for v in writes}
        assert non_bit4_bits == {0}, (
            f"only bit 4 should vary during BEEP, got {non_bit4_bits}"
        )

    def test_border_restored_to_black_at_end(self):
        m = _run(": beep-test  3 10 beep ;")
        writes = _fe_writes(m)
        assert writes[-1] == 0, (
            f"final FE write should be 0 (border black, speaker off), got {writes[-1]}"
        )

    def test_beep_leaves_stack_clean(self):
        m = _run(": beep-test  99 3 10 beep ;")
        assert m.hl == 99, (
            "BEEP ( c p -- ) should leave the pre-existing stack intact"
        )


class TestBeepWithBorder:

    def test_border_after_beep_takes_effect(self):
        m = _run(": beep-test  1 10 beep 2 border ;")
        writes = _fe_writes(m)
        assert writes[-1] == 2, (
            f"border-2 after BEEP should be the last FE write, got {writes[-1]}"
        )


@pytest.mark.parametrize("cycles,expected_count", [
    (1, 2), (2, 3), (5, 6), (20, 21),
])
def test_cycle_count_to_write_count(cycles, expected_count):
    m = _run(f": beep-test  {cycles} 8 beep ;")
    assert len(_fe_writes(m)) == expected_count, (
        f"{cycles} cycles should yield {expected_count} FE writes"
    )


@pytest.mark.parametrize("period", [5, 20, 50, 100])
def test_period_does_not_affect_write_count(period):
    m = _run(f": beep-test  4 {period} beep ;")
    assert len(_fe_writes(m)) == 5, (
        f"write count should depend on cycles, not period={period}"
    )
