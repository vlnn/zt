"""
End-to-end test for examples/shadow-flip — the minimal shadow-screen flip
demo that paints two static pictures and alternates them once per second.
Asserts: compiles cleanly, seeds bank 5, paints both screens at runtime,
and toggles bit 3 of $7FFD between the two delays.
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
    SHADOW_SCREEN_BANK,
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    is_7ffd_write,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "shadow-flip"
MAIN = EXAMPLE_DIR / "main.fs"


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
    m.port_7ffd = 0x07  # mirrors what the SNA loader applies
    m.pc = c.words["_start"].address
    return c, m


def _step_until_first_flip(m: Z80, tick_budget: int = 30_000_000) -> None:
    for _ in range(tick_budget):
        if m.halted:
            return
        m._step()
        page_values = [v for p, v in m._outputs if is_7ffd_write(p)]
        if any(v & PORT_7FFD_SCREEN_BIT for v in page_values):
            return
    raise TimeoutError("no screen-select bit flip happened within tick budget")


class TestSourceLayout:

    def test_main_fs_exists(self):
        assert MAIN.is_file(), "shadow-flip/main.fs should ship"


class TestCompiles:

    def test_compiles_cleanly(self):
        c, _ = _build()
        assert "main" in c.words, "shadow-flip should define 'main'"

    @pytest.mark.parametrize("word", [
        "seed-pixels", "seed-attrs",
        "paint-solid", "paint-normal", "paint-shadow",
        "show-normal", "show-shadow",
        "wait-one-second", "main",
    ])
    def test_expected_word_defined(self, word):
        c, _ = _build()
        assert word in c.words, f"shadow-flip should define '{word}'"


class TestBank5Seeded:

    def test_bank_5_has_top_row_pixels(self):
        c, _ = _build()
        bank5 = c.bank_image(NORMAL_SCREEN_BANK)
        top_row = bank5[0:32]
        assert all(b == 0xFF for b in top_row), (
            f"bank 5 top row (first 32 pixel bytes) should be all $FF at "
            f"build time as a 'did this load?' marker; got {top_row.hex()}"
        )

    def test_bank_5_has_top_attr_row(self):
        c, _ = _build()
        bank5 = c.bank_image(NORMAL_SCREEN_BANK)
        attr_row = bank5[6144:6144 + 32]
        assert all(b == 0x44 for b in attr_row), (
            f"bank 5 top attr row should be all $44 (bright green paper) at "
            f"build time; got {attr_row.hex()}"
        )


class TestPaintOverwritesSeed:

    def test_after_paint_normal_attrs_become_bright_white(self):
        c, m = _start_machine()
        _step_until_first_flip(m)
        bank5_attrs = m.mem_bank(NORMAL_SCREEN_BANK)[6144:6144 + 768]
        assert all(b == 0x78 for b in bank5_attrs), (
            "after paint-normal runs, bank 5 attrs should be $78 "
            "(bright white paper, black ink) everywhere"
        )

    def test_after_paint_shadow_attrs_become_bright_red(self):
        c, m = _start_machine()
        _step_until_first_flip(m)
        bank7_attrs = m.mem_bank(SHADOW_SCREEN_BANK)[6144:6144 + 768]
        assert all(b == 0x50 for b in bank7_attrs), (
            "after paint-shadow runs, bank 7 attrs should be $50 "
            "(bright red paper, black ink) everywhere"
        )


class TestFlipToggles:

    def test_bit_3_both_set_and_clear_across_flips(self):
        c, m = _start_machine()
        _step_until_first_flip(m)

        # Run further so we see at least two flips
        target_flips = 3
        start_count = 0
        seen = 0
        for _ in range(100_000_000):
            if m.halted:
                break
            m._step()
            page_values = [v for p, v in m._outputs if is_7ffd_write(p)]
            if len(page_values) - start_count >= target_flips:
                break

        page_values = [v for p, v in m._outputs if is_7ffd_write(p)]
        with_bit3 = sum(1 for v in page_values if v & PORT_7FFD_SCREEN_BIT)
        without_bit3 = sum(1 for v in page_values if not (v & PORT_7FFD_SCREEN_BIT))
        assert with_bit3 >= 1 and without_bit3 >= 1, (
            f"$7FFD should be written both with and without bit 3 set; "
            f"got with={with_bit3}, without={without_bit3}, "
            f"values={[hex(v) for v in page_values[:10]]}"
        )

    def test_bank_7_stays_paged_across_flips(self):
        c, m = _start_machine()
        _step_until_first_flip(m)
        page_values = [v for p, v in m._outputs if is_7ffd_write(p)]
        assert all((v & 0x07) == 7 for v in page_values), (
            f"bits 0-2 of every $7FFD write should stay at 7; "
            f"got {[hex(v) for v in page_values]}"
        )


class TestCliBuild:

    def test_cli_produces_131103_byte_sna(self, tmp_path):
        import subprocess
        import sys
        out = tmp_path / "shadow-flip.sna"
        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "zt.cli", "build",
             str(MAIN), "-o", str(out), "--target", "128k"],
            capture_output=True, text=True, cwd=repo_root,
        )
        assert result.returncode == 0, (
            f"shadow-flip should build via the CLI; stderr={result.stderr}"
        )
        assert out.stat().st_size == 131_103, (
            f"output should be a 131103-byte snapshot; got {out.stat().st_size}"
        )

    def test_cli_default_paged_bank_is_7(self, tmp_path):
        import subprocess
        import sys
        out = tmp_path / "shadow-flip.sna"
        repo_root = Path(__file__).parent.parent
        subprocess.run(
            [sys.executable, "-m", "zt.cli", "build",
             str(MAIN), "-o", str(out), "--target", "128k"],
            capture_output=True, text=True, cwd=repo_root,
        )
        raw = out.read_bytes()
        assert raw[49181] & 0x07 == 7, (
            f"default --target 128k should put bank 7 in slot 3 "
            f"(ensures display wiring is established on Pentagon at load)"
        )
