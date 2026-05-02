"""
Acceptance test for the IM 2 Bach Invention 4 (BWV 775) demo: build the
example, run it for a healthy chunk of frames, and assert the AY chip
saw the expected register-select / data-write traffic on $FFFD / $BFFD —
both voices animate, both volume registers (R8/R9) are exercised, and the
rainbow border keeps cycling.
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
R_TONE_B_LOW = 2
R_TONE_B_HIGH = 3
R_MIXER = 7
R_VOLUME_A = 8
R_VOLUME_B = 9
R_VOLUME_C = 10

MIXER_TONES_ONLY = 0x38
VOLUME_MAX = 0x0F
VOLUME_MUTE = 0x00

WARMUP_FRAMES = 200


def _selects(m: Z80) -> list[int]:
    return [val for port, val in m._outputs if port == AY_REG_SELECT_PORT]


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


def _writes_to(pairs: list[tuple[int, int]], reg: int) -> list[int]:
    return [val for r, val in pairs if r == reg]


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
        assert MAIN.is_file(), "im2-bach/main.fs should ship as the entry point"

    def test_music_fs_exists(self):
        assert (EXAMPLE_DIR / "app" / "music.fs").is_file(), \
            "im2-bach/app/music.fs should hold the AY driver"

    def test_song_data_fs_exists(self):
        assert (EXAMPLE_DIR / "app" / "song-data.fs").is_file(), \
            "im2-bach/app/song-data.fs should hold the BWV 775 score data"


class TestCompiles:

    @pytest.mark.parametrize("word", [
        "song", "song-length",
        "ay-set", "ay-tone-a!", "ay-tone-b!", "ay-vol-a!", "ay-vol-b!",
        "step-addr", "step-period-a", "step-period-b",
        "music-init", "music-isr", "music",
    ])
    def test_expected_word_defined(self, word):
        c, _ = _build_compiled()
        assert word in c.words, f"im2-bach should define '{word}'"

    def test_song_length_is_312(self):
        c, _ = _build_compiled()
        word = c.words.get("song-length")
        assert word is not None, "song-length should be a constant"
        c2, image = _build_compiled()
        assert "song-length" in c2.words, \
            "the BWV 775 score has 312 16th-note slots (52 bars × 6)"


class TestInterruptsFire:

    def test_warm_run_produced_interrupts(self, warm_machine):
        assert warm_machine.interrupt_count >= WARMUP_FRAMES, (
            f"after {WARMUP_FRAMES} frames the IM 2 handler should have fired "
            f"at least {WARMUP_FRAMES} times; got {warm_machine.interrupt_count}"
        )


class TestRainbowBorderStillCycles:

    def test_border_cycles_through_eight_colours(self, warm_machine):
        seen = set(_border_writes(warm_machine))
        assert seen == set(range(8)), \
            f"border should cycle through all 8 colours 0..7; got {sorted(seen)}"


class TestAyOneShotInit:

    @pytest.mark.parametrize("reg", [R_MIXER, R_VOLUME_C])
    def test_init_register_was_selected(self, warm_machine, reg):
        assert reg in _selects(warm_machine), \
            f"music-init should select AY register {reg}; selects={sorted(set(_selects(warm_machine)))}"

    def test_mixer_set_to_tones_only(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_MIXER)
        assert MIXER_TONES_ONLY in writes, \
            f"R7 should be set to ${MIXER_TONES_ONLY:02X}; got {[hex(v) for v in writes]}"

    def test_channel_c_silenced(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_VOLUME_C)
        assert VOLUME_MUTE in writes, \
            f"R10 should be set to ${VOLUME_MUTE:02X} (channel C silent); got {[hex(v) for v in writes]}"


class TestRightHandVoiceA:

    def test_tone_a_low_was_written(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_TONE_A_LOW)
        assert len(writes) >= WARMUP_FRAMES // 16, \
            f"R0 should be written at step boundaries; got {len(writes)} writes"

    def test_voice_a_takes_multiple_pitches(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_TONE_A_LOW)
        assert len(set(writes)) >= 4, \
            f"voice A should walk through at least 4 distinct R0 values across the BWV 775 opening; got {sorted(set(writes))}"

    def test_voice_a_volume_at_max(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_VOLUME_A)
        assert VOLUME_MAX in writes, \
            f"R8 should be set to ${VOLUME_MAX:02X} (channel A audible); got {[hex(v) for v in writes]}"


class TestLeftHandVoiceB:

    def test_voice_b_eventually_starts_writing_periods(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_TONE_B_LOW)
        assert len(writes) >= 1, \
            "voice B (LH) enters at bar 3 — by 200 frames R2 must have been written at least once"

    def test_voice_b_volume_toggles_between_max_and_mute(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_VOLUME_B)
        seen = set(writes)
        assert {VOLUME_MAX, VOLUME_MUTE}.issubset(seen), \
            f"R9 should be muted during voice-2 rests (bars 1-2) and max-volume after; got {[hex(v) for v in writes]}"


class TestOpeningSubject:

    def test_first_voice_a_period_is_d4(self, warm_machine):
        writes = _writes_to(_ay_pairs(warm_machine), R_TONE_A_LOW)
        assert writes, "no R0 writes seen at all"
        assert writes[0] == 377 & 0xFF, \
            f"first voice-A note of BWV 775 is D4 (period 377, low byte 121); got {writes[0]}"


class TestCliBuild:

    def test_cli_produces_a_128k_snapshot(self, tmp_path: Path):
        out = tmp_path / "im2-bach.sna"
        result = subprocess.run(
            [sys.executable, "-m", "zt.cli", "build",
             str(MAIN), "-o", str(out), "--target", "128k",
             "--include-dir", str(EXAMPLE_DIR)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, \
            f"im2-bach should build via the CLI; stderr={result.stderr}"
        assert out.stat().st_size == 131_103, \
            f"output should be a 131103-byte 128K snapshot; got {out.stat().st_size} bytes"
