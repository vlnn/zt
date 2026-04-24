"""
End-to-end acceptance test for the M5 bank-rotator demo: compile under 128K
defaults, run in the 128K simulator, assert the visible banking effects.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    DEFAULT_DATA_STACK_TOP_128K,
    DEFAULT_RETURN_STACK_TOP_128K,
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    is_7ffd_write,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "bank-rotator"
MAIN = EXAMPLE_DIR / "main.fs"


def _build_128k() -> tuple[Compiler, bytes]:
    c = Compiler(
        data_stack_top=DEFAULT_DATA_STACK_TOP_128K,
        return_stack_top=DEFAULT_RETURN_STACK_TOP_128K,
    )
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    image = c.build()
    return c, image


def _run_128k(c: Compiler, image: bytes, max_ticks: int = 500_000) -> Z80:
    m = Z80(mode="128k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = c.words["_start"].address
    m.run(max_ticks=max_ticks)
    return m


def _page_writes(m: Z80) -> list[int]:
    return [v for port, v in m._outputs if is_7ffd_write(port)]


class TestSourceLayout:

    def test_main_fs_exists(self):
        assert MAIN.is_file(), "bank-rotator/main.fs should ship with the example"


class TestCompiles:

    def test_compiles_cleanly_under_128k_defaults(self):
        c, image = _build_128k()
        assert len(image) > 0, "compiled image should be non-empty"
        assert "main" in c.words, "bank-rotator should define 'main'"

    @pytest.mark.parametrize("word", [
        "ensure-128k", "seed-bank", "install-banks",
        "show-bank-at-col", "cycle", "main",
    ])
    def test_defines_each_expected_word(self, word):
        c, _ = _build_128k()
        assert word in c.words, f"bank-rotator should define '{word}'"

    def test_fits_in_bank_2(self):
        c, image = _build_128k()
        assert len(image) <= 0x4000, (
            "bank-rotator should fit in one 16 KB bank (bank 2 is 16 KB); "
            f"image size {len(image)}"
        )


class TestRuntimeEffects:

    def test_install_banks_seeds_each_bank(self):
        c, image = _build_128k()
        m = _run_128k(c, image, max_ticks=200_000)
        for bank, expected in [(0, 0x46), (1, 0x4A), (3, 0x52),
                               (4, 0x61), (6, 0x46), (7, 0x4A)]:
            actual = m.mem_bank(bank)[0]
            assert actual == expected, (
                f"install-banks should seed bank {bank}'s $C000 with "
                f"{expected:#04x}, got {actual:#04x}"
            )

    def test_cycle_writes_to_attribute_row(self):
        c, image = _build_128k()
        m = _run_128k(c, image, max_ticks=500_000)
        expected_attrs = [0x46, 0x4A, 0x52, 0x61, 0x46, 0x4A]
        for col, expected in enumerate(expected_attrs):
            actual = m.mem[0x5800 + col]
            assert actual == expected, (
                f"attribute at col {col} should be {expected:#04x} after "
                f"the cycle loop has run at least once, got {actual:#04x}"
            )

    def test_page_writes_cover_all_six_banks(self):
        c, image = _build_128k()
        m = _run_128k(c, image, max_ticks=500_000)
        page_values = _page_writes(m)
        seen_banks = {v & 0x07 for v in page_values}
        expected = {0, 1, 3, 4, 6, 7}
        assert expected.issubset(seen_banks), (
            f"all six data banks should appear in page_writes; "
            f"expected {expected}, got {seen_banks}"
        )

    def test_stacks_live_in_bank_2(self):
        c, image = _build_128k()
        m = _run_128k(c, image, max_ticks=200_000)
        assert c.data_stack_top < 0xC000, (
            "128K build should use a data stack below $C000"
        )
        assert c.return_stack_top < 0xC000, (
            "128K build should use a return stack below $C000"
        )


class TestDetectionInFortyEightKMode:

    def test_48k_sim_halts_with_red_border(self):
        c = Compiler()
        c.include_stdlib()
        c.compile_source(MAIN.read_text(), source=str(MAIN))
        c.compile_main_call()
        image = c.build()

        m = Z80(mode="48k")
        m.load(c.origin, image)
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.pc = c.words["_start"].address
        m.run(max_ticks=200_000)

        border_writes = [v for port, v in m._outputs if (port & 0xFF) == 0xFE]
        assert 2 in border_writes, (
            "on 48K, ensure-128k should write red ($02) to the border port "
            f"as a visible failure signal; border_writes={border_writes}"
        )
