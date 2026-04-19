"""
Milestone-5 tests for the `cls` / `reset-cursor` primitive and its interaction with the hello-world pipeline.
"""
from __future__ import annotations

import pytest

from zt.compiler import Compiler, compile_and_run_with_output
from zt.sim import ForthMachine, SPECTRUM_ATTR_BASE, SPECTRUM_SCREEN_BASE


SPECTRUM_PIXEL_BYTES = 6144
SPECTRUM_ATTR_BYTES = 768


@pytest.fixture
def fm():
    return ForthMachine()


class TestResetCursorPrimitive:

    def test_reset_cursor_word_registered(self, fm):
        assert "RESET_CURSOR" in fm._prim_asm.labels, "RESET_CURSOR label should exist"
        assert "reset-cursor" in fm._prim_asm.labels, "lowercase alias should exist"

    def test_resets_row_and_col_to_zero(self, fm):
        cells = []
        for _ in range(5):
            cells.extend([fm.label("LIT"), 65, fm.label("EMIT")])
        cells.append(fm.label("RESET_CURSOR"))
        fm.run(cells)
        row_addr = fm._prim_asm.labels["_emit_cursor_row"]
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[row_addr] == 0, "reset-cursor should zero row"
        assert fm._last_m.mem[col_addr] == 0, "reset-cursor should zero col"

    def test_next_emit_starts_at_top_left(self, fm):
        cells = [fm.label("LIT"), 88, fm.label("EMIT"), fm.label("RESET_CURSOR"),
                 fm.label("LIT"), 65, fm.label("EMIT")]
        fm.run(cells)
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[col_addr] == 1, (
            "EMIT after reset-cursor should land at col 1 (0, then advance)"
        )


class TestClsForthWord:

    def _build_image(self, source: str):
        c = Compiler()
        c.include_stdlib()
        c.compile_source(source)
        c.compile_main_call()
        return c

    def _run_with_mem(self, source: str):
        from zt.sim import (
            SPECTRUM_FONT_BASE, TEST_FONT, Z80, _read_data_stack,
        )
        c = self._build_image(source)
        image = c.build()
        m = Z80()
        m.load(c.origin, image)
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.pc = c.words["_start"].address
        m.run()
        return m, c

    @pytest.mark.parametrize("paper,ink,expected", [
        (7, 0, 0x38),
        (0, 7, 0x07),
        (1, 5, 0x0D),
        (0, 0, 0x00),
        (7, 7, 0x3F),
    ])
    def test_cls_fills_attr_area(self, paper, ink, expected):
        m, _ = self._run_with_mem(
            f': main {paper} {ink} cls halt ;'
        )
        attrs = m.mem[SPECTRUM_ATTR_BASE:SPECTRUM_ATTR_BASE + SPECTRUM_ATTR_BYTES]
        assert all(b == expected for b in attrs), (
            f"all {SPECTRUM_ATTR_BYTES} attr bytes should be {expected:#04x} after {paper} {ink} cls"
        )

    def test_cls_clears_pixel_area(self):
        source = """
        : main
            65 emit 66 emit 67 emit
            7 0 cls halt ;
        """
        m, _ = self._run_with_mem(source)
        pixels = m.mem[SPECTRUM_SCREEN_BASE:SPECTRUM_SCREEN_BASE + SPECTRUM_PIXEL_BYTES]
        assert all(b == 0 for b in pixels), (
            "cls should zero all 6144 pixel bytes"
        )

    def test_cls_resets_cursor(self):
        source = """
        : main
            65 emit 66 emit 67 emit
            7 0 cls halt ;
        """
        m, c = self._run_with_mem(source)
        row_addr = c.asm.labels["_emit_cursor_row"]
        col_addr = c.asm.labels["_emit_cursor_col"]
        assert m.mem[row_addr] == 0, "cls should leave cursor at row 0"
        assert m.mem[col_addr] == 0, "cls should leave cursor at col 0"

    def test_cls_leaves_stack_clean(self):
        stack, _ = compile_and_run_with_output(
            ': main 42 7 0 cls halt ;', stdlib=True,
        )
        assert stack == [42], "cls should consume (paper ink), nothing more"

    def test_emit_after_cls_works(self):
        source = """
        : main
            65 emit 66 emit
            7 0 cls
            88 emit 89 emit halt ;
        """
        _, out = compile_and_run_with_output(source, stdlib=True)
        assert out == b"XY", (
            "after cls, previous output should be wiped; only post-cls EMITs visible"
        )


class TestHelloWithCls:

    def test_hello_fs_calls_cls(self):
        from pathlib import Path
        hello = (Path(__file__).parent.parent / "examples" / "hello.fs").read_text()
        assert "cls" in hello, (
            "hello.fs should call cls so real-hardware output is visible"
        )
