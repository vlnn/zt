"""
End-to-end acceptance test for the M4b bank-table demo: uses compile-time
`in-bank` CREATE to place byte tables directly into RAM banks 0, 1, 3, 4.
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
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "bank-table"
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


class TestSourceLayout:

    def test_main_fs_exists(self):
        assert MAIN.is_file(), "bank-table/main.fs should ship with the example"


class TestBankTablesPopulatedAtCompileTime:

    def test_compiles_cleanly(self):
        c, image = _build_128k()
        assert "main" in c.words, "bank-table should define 'main'"

    @pytest.mark.parametrize("color_word,bank,expected_byte", [
        ("color-0", 0, 0x46),
        ("color-1", 1, 0x4A),
        ("color-3", 3, 0x52),
        ("color-4", 4, 0x61),
    ])
    def test_color_constant_lives_in_right_bank(
        self, color_word, bank, expected_byte,
    ):
        c, _ = _build_128k()
        addr = c.words[color_word].data_address
        assert 0xC000 <= addr < 0x10000, (
            f"{color_word} should have a paged-slot data_address, got {addr:#06x}"
        )
        image = c.bank_image(bank)
        offset = addr - 0xC000
        assert image[offset] == expected_byte, (
            f"{color_word} should hold {expected_byte:#04x} in bank {bank}"
        )


class TestRuntimeBehaviour:

    def test_cycle_writes_correct_attributes(self):
        c, image = _build_128k()
        m = Z80(mode="128k")
        m.load(c.origin, image)
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        for bank, data in c.banks().items():
            m.load_bank(bank, data)
        m.pc = c.words["_start"].address
        m.run(max_ticks=500_000)

        expected = [0x46, 0x4A, 0x52, 0x61]
        for col, want in enumerate(expected):
            got = m.mem[0x5800 + col]
            assert got == want, (
                f"attribute at col {col} should be {want:#04x} after cycle, "
                f"got {got:#04x}"
            )
