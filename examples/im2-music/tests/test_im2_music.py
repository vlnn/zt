"""
Acceptance test for the IM 2 AY-music demo: build the example into a 128K
.sna, load it into the simulator, run for a healthy chunk of frames, and
assert the AY chip saw the expected register-select / data-write traffic
on ports $FFFD and $BFFD — while the rainbow border keeps cycling.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from zt.assemble.im2_table import (
    IM2_HANDLER_SLOT_ADDR,
    IM2_TABLE_ADDR,
    IM2_TABLE_LEN,
    IM2_VECTOR_BYTE,
)
from zt.compile.compiler import Compiler
from zt.sim import (
    DEFAULT_DATA_STACK_TOP_128K,
    DEFAULT_RETURN_STACK_TOP_128K,
    FRAME_T_STATES_128K,
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
)


REPO_ROOT = Path(__file__).parent.parent.parent.parent
EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"

AY_REG_SELECT_PORT = 0xFFFD
AY_DATA_PORT = 0xBFFD
BORDER_PORT_LOW = 0xFE

R_TONE_A_LOW = 0
R_TONE_A_HIGH = 1
R_MIXER = 7
R_VOLUME_A = 8

MIXER_TONES_ONLY = 0x38
VOLUME_MAX = 0x0F

WARMUP_FRAMES = 80


def _selects(m: Z80) -> list[int]:
    return [val for port, val in m._outputs if port == AY_REG_SELECT_PORT]


def _writes(m: Z80) -> list[int]:
    return [val for port, val in m._outputs if port == AY_DATA_PORT]


def _border_writes(m: Z80) -> list[int]:
    return [val & 0x07 for port, val in m._outputs if (port & 0xFF) == BORDER_PORT_LOW]


def _ay_pairs(m: Z80) -> list[tuple[int, int]]:
    pairs = []
    pending_reg = None
    for port, val in m._outputs:
        if port == AY_REG_SELECT_PORT:
            pending_reg = val
        elif port == AY_DATA_PORT and pending_reg is not None:
            pairs.append((pending_reg, val))
            pending_reg = None
    return pairs


def _build_compiled() -> tuple[Compiler, bytes]:
    c = Compiler(
        data_stack_top=DEFAULT_DATA_STACK_TOP_128K,
        return_stack_top=DEFAULT_RETURN_STACK_TOP_128K,
        include_dirs=[EXAMPLE_DIR],
    )
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    return c, c.build()


def _inject_im2_table(m: Z80) -> None:
    for i in range(IM2_TABLE_LEN):
        m._wb(IM2_TABLE_ADDR + i, IM2_VECTOR_BYTE)
    m._wb(IM2_HANDLER_SLOT_ADDR, 0xC3)
    m._wb(IM2_HANDLER_SLOT_ADDR + 1, 0x00)
    m._wb(IM2_HANDLER_SLOT_ADDR + 2, 0x00)


def _start_machine() -> Z80:
    c, image = _build_compiled()
    m = Z80(mode="128k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    for bank, data in c.banks().items():
        m.load_bank(bank, data)
    _inject_im2_table(m)
    m.pc = c.words["_start"].address
    return m


@pytest.fixture
def warm_machine() -> Z80:
    m = _start_machine()
    m.run_until(FRAME_T_STATES_128K * WARMUP_FRAMES + 5_000)
    return m


class TestSourceLayout:

    def test_main_fs_exists(self):
        assert MAIN.is_file(), "im2-music/main.fs should ship as the entry point"

    def test_music_fs_exists(self):
        assert (EXAMPLE_DIR / "app" / "music.fs").is_file(), (
            "im2-music/app/music.fs should hold the AY driver"
        )


class TestCompiles:

    def test_compiles_cleanly(self):
        c, _ = _build_compiled()
        assert "main" in c.words, "im2-music should define 'main'"

    @pytest.mark.parametrize("word", [
        "tone-table", "tone-period", "ay-set",
        "music-init", "music-isr", "music",
    ])
    def test_expected_word_defined(self, word):
        c, _ = _build_compiled()
        assert word in c.words, f"im2-music should define '{word}'"


class TestInterruptsFire:

    def test_warm_run_produced_interrupts(self, warm_machine):
        assert warm_machine.interrupt_count >= WARMUP_FRAMES, (
            f"after {WARMUP_FRAMES} frames the IM 2 handler should have fired "
            f"at least {WARMUP_FRAMES} times; got {warm_machine.interrupt_count}"
        )


class TestRainbowBorderStillCycles:

    def test_border_cycles_through_eight_colours(self, warm_machine):
        seen = set(_border_writes(warm_machine))
        assert seen == set(range(8)), (
            f"border should cycle through all 8 colours 0..7; got {sorted(seen)}"
        )


class TestAyRegistersInitialised:

    @pytest.mark.parametrize("reg", [R_MIXER, R_VOLUME_A])
    def test_init_register_was_selected(self, warm_machine, reg):
        assert reg in _selects(warm_machine), (
            f"music-init should select AY register {reg}; "
            f"selects seen={sorted(set(_selects(warm_machine)))}"
        )

    def test_mixer_set_to_tones_only(self, warm_machine):
        pairs = _ay_pairs(warm_machine)
        mixer_writes = [val for reg, val in pairs if reg == R_MIXER]
        assert MIXER_TONES_ONLY in mixer_writes, (
            f"R7 should be set to ${MIXER_TONES_ONLY:02X} (tones A/B/C on, noise off); "
            f"got writes={[hex(v) for v in mixer_writes]}"
        )

    def test_volume_a_set_to_max(self, warm_machine):
        pairs = _ay_pairs(warm_machine)
        volume_writes = [val for reg, val in pairs if reg == R_VOLUME_A]
        assert VOLUME_MAX in volume_writes, (
            f"R8 should be set to ${VOLUME_MAX:02X} (channel A volume max, no envelope); "
            f"got writes={[hex(v) for v in volume_writes]}"
        )


class TestNoteIsPlayedAndChanges:

    def test_tone_a_low_period_was_written_each_frame(self, warm_machine):
        pairs = _ay_pairs(warm_machine)
        tone_low = [val for reg, val in pairs if reg == R_TONE_A_LOW]
        assert len(tone_low) >= WARMUP_FRAMES // 2, (
            f"R0 should be written from the ISR every frame; "
            f"after {WARMUP_FRAMES} frames got {len(tone_low)} writes"
        )

    def test_tone_a_high_period_was_written_each_frame(self, warm_machine):
        pairs = _ay_pairs(warm_machine)
        tone_high = [val for reg, val in pairs if reg == R_TONE_A_HIGH]
        assert len(tone_high) >= WARMUP_FRAMES // 2, (
            f"R1 should be written from the ISR every frame; "
            f"after {WARMUP_FRAMES} frames got {len(tone_high)} writes"
        )

    def test_note_actually_changes_over_time(self, warm_machine):
        pairs = _ay_pairs(warm_machine)
        tone_low = [val for reg, val in pairs if reg == R_TONE_A_LOW]
        assert len(set(tone_low)) >= 2, (
            f"R0 should take on at least 2 different values across {WARMUP_FRAMES} "
            f"frames so the demo plays a tune, not a single sustained note; "
            f"got distinct values={sorted(set(tone_low))}"
        )


class TestCliBuild:

    def test_cli_produces_a_128k_snapshot(self, tmp_path: Path):
        out = tmp_path / "im2-music.sna"
        result = subprocess.run(
            [sys.executable, "-m", "zt.cli", "build",
             str(MAIN), "-o", str(out), "--target", "128k",
             "--include-dir", str(EXAMPLE_DIR)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"im2-music should build via the CLI; stderr={result.stderr}"
        )
        assert out.stat().st_size == 131_103, (
            f"output should be a 131103-byte 128K snapshot; "
            f"got {out.stat().st_size} bytes"
        )
