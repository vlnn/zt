"""
End-to-end acceptance test for examples/plasma-128k: double-buffered plasma
using the ZX 128 shadow screen. Asserts that:
  - The program runs and flips the screen-select bit (bit 3 of $7FFD).
  - The shadow screen (bank 7) receives attribute writes before a flip.
  - Toggling bit 3 changes what `Z80.displayed_screen()` returns, with no
    CMOVE in sight — the whole point of this demo is the flip is free.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    DEFAULT_DATA_STACK_TOP_128K,
    DEFAULT_RETURN_STACK_TOP_128K,
    NORMAL_SCREEN_BANK,
    PORT_7FFD_SCREEN_BIT,
    SCREEN_ATTRS_SIZE,
    SCREEN_BITMAP_SIZE,
    SHADOW_SCREEN_BANK,
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    is_7ffd_write,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "plasma-128k"
MAIN = EXAMPLE_DIR / "main.fs"
PLASMA_MATH = Path(__file__).parent.parent / "examples" / "plasma" / "lib" / "math.fs"


def _build() -> tuple[Compiler, bytes]:
    c = Compiler(
        data_stack_top=DEFAULT_DATA_STACK_TOP_128K,
        return_stack_top=DEFAULT_RETURN_STACK_TOP_128K,
        include_dirs=[EXAMPLE_DIR],
    )
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    image = c.build()
    return c, image


def _start_machine() -> tuple[Compiler, Z80]:
    c, image = _build()
    m = Z80(mode="128k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    for bank, data in c.banks().items():
        m.load_bank(bank, data)
    m.pc = c.words["_start"].address
    return c, m


def _step_until_page_count(m: Z80, target_writes: int,
                            tick_budget: int = 50_000_000) -> None:
    seen = 0
    watched = 0
    for _ in range(tick_budget):
        if m.halted:
            return
        m._step()
        while watched < len(m._outputs):
            port, _ = m._outputs[watched]
            watched += 1
            if is_7ffd_write(port):
                seen += 1
                if seen >= target_writes:
                    return
    raise TimeoutError(
        f"simulator did not produce {target_writes} port writes within budget"
    )


def _step_until_both_screens_drawn(m: Z80, tick_budget: int = 80_000_000) -> None:
    for _ in range(tick_budget):
        if m.halted:
            return
        m._step()
        bank5 = m.mem_bank(NORMAL_SCREEN_BANK)
        bank7 = m.mem_bank(SHADOW_SCREEN_BANK)
        n5 = sum(1 for b in bank5[SCREEN_BITMAP_SIZE:SCREEN_BITMAP_SIZE + SCREEN_ATTRS_SIZE] if b != 0)
        n7 = sum(1 for b in bank7[SCREEN_BITMAP_SIZE:SCREEN_BITMAP_SIZE + SCREEN_ATTRS_SIZE] if b != 0)
        if n5 > 100 and n7 > 100:
            return
    raise TimeoutError(
        "simulator did not draw plasma into both screens within budget"
    )


class TestSourceLayout:

    def test_main_fs_exists(self):
        assert MAIN.is_file(), "plasma-128k/main.fs should ship"

    def test_reuses_plasma_math_lib(self):
        assert PLASMA_MATH.is_file(), (
            "plasma-128k is expected to require ../plasma/lib/math.fs; "
            "shared helper should stay put"
        )


class TestCompiles:

    def test_compiles_cleanly(self):
        c, _ = _build()
        assert "main" in c.words, "plasma-128k should define 'main'"

    @pytest.mark.parametrize("word", [
        "wave", "phase", "plasma-attr",
        "hidden-attrs", "draw-plasma", "flip", "step", "main",
    ])
    def test_expected_word_defined(self, word):
        c, _ = _build()
        assert word in c.words, f"plasma-128k should define '{word}'"


class TestShadowScreenReceivesWrites:

    def test_both_screens_receive_plasma_data(self):
        c, m = _start_machine()
        _step_until_both_screens_drawn(m)
        bank5 = m.mem_bank(NORMAL_SCREEN_BANK)
        bank7 = m.mem_bank(SHADOW_SCREEN_BANK)
        n5 = sum(1 for b in bank5[SCREEN_BITMAP_SIZE:SCREEN_BITMAP_SIZE + SCREEN_ATTRS_SIZE] if b != 0)
        n7 = sum(1 for b in bank7[SCREEN_BITMAP_SIZE:SCREEN_BITMAP_SIZE + SCREEN_ATTRS_SIZE] if b != 0)
        assert n5 > 100, (
            f"normal screen (bank 5) should be drawn to at some point; "
            f"{n5} non-zero attr bytes"
        )
        assert n7 > 100, (
            f"shadow screen (bank 7) should be drawn to at some point; "
            f"{n7} non-zero attr bytes — this is the whole point of the demo"
        )

    def test_flip_toggles_bit_3_between_draws(self):
        c, m = _start_machine()
        _step_until_both_screens_drawn(m)
        page_values = [v for port, v in m._outputs if is_7ffd_write(port)]
        with_bit3 = [v for v in page_values if v & PORT_7FFD_SCREEN_BIT]
        without_bit3 = [v for v in page_values if not (v & PORT_7FFD_SCREEN_BIT)]
        assert with_bit3 and without_bit3, (
            f"$7FFD should have been written both with and without bit 3 set; "
            f"got {len(with_bit3)} with, {len(without_bit3)} without"
        )

    def test_bank_7_stays_paged_through_every_flip(self):
        c, m = _start_machine()
        _step_until_both_screens_drawn(m)
        page_values = [v for port, v in m._outputs if is_7ffd_write(port)]
        flips = [v for v in page_values if v & PORT_7FFD_SCREEN_BIT or not (v & PORT_7FFD_SCREEN_BIT)]
        flip_values = [v for v in page_values if (v != page_values[0]) or v]
        assert all((v & 0x07) == 7 for v in page_values[1:]), (
            f"after the initial bank-in write, bits 0-2 of every $7FFD write "
            f"should stay at 7 so bank 7 remains in slot 3; got {[hex(v) for v in page_values]}"
        )


class TestDisplayedScreenHelperReflectsBit3:

    def test_default_shows_normal(self):
        m = Z80(mode="128k")
        assert m.displayed_screen_bank() == NORMAL_SCREEN_BANK, (
            "after init, bit 3 is clear so the ULA shows bank 5 (normal screen)"
        )

    def test_raw_bank_store_of_0x18_flips_to_shadow(self):
        m = Z80(mode="128k")
        m._write_port_7ffd(0x18)
        assert m.displayed_screen_bank() == SHADOW_SCREEN_BANK, (
            "$7FFD bit 3 set should route the ULA to bank 7 (shadow screen)"
        )

    def test_displayed_screen_returns_the_live_bank(self):
        m = Z80(mode="128k")
        m.load_bank(SHADOW_SCREEN_BANK, b"\xAB" * (SCREEN_BITMAP_SIZE + SCREEN_ATTRS_SIZE))
        m._write_port_7ffd(0x18)
        bitmap, attrs = m.displayed_screen()
        assert set(bitmap) == {0xAB}, (
            "displayed_screen() should return bank 7's bitmap when bit 3 is set"
        )
        assert set(attrs) == {0xAB}, (
            "displayed_screen() should return bank 7's attrs when bit 3 is set"
        )


class TestCliBuild:

    def test_cli_produces_131103_byte_sna(self, tmp_path):
        import subprocess
        import sys
        out = tmp_path / "plasma-128k.sna"
        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "zt.cli", "build",
             str(MAIN), "-o", str(out), "--target", "128k"],
            capture_output=True, text=True, cwd=repo_root,
        )
        assert result.returncode == 0, (
            f"plasma-128k should build via the CLI; stderr={result.stderr}"
        )
        assert out.stat().st_size == 131_103, (
            f"output should be a 131103-byte 128K snapshot; "
            f"got {out.stat().st_size}"
        )
