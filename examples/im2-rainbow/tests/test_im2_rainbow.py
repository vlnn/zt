"""
Acceptance test for the IM 2 rainbow demo: build the example into a 48K .sna,
load it into the simulator, run it for several frames, and assert the border
port saw an 8-colour cycle (one write per frame interrupt).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from zt.format.image_loader import load_sna
from zt.sim import FRAME_T_STATES_48K, Z80


REPO_ROOT = Path(__file__).parent.parent.parent.parent
EXAMPLE = REPO_ROOT / "examples" / "im2-rainbow" / "main.fs"


@pytest.fixture
def built_sna(tmp_path: Path) -> Path:
    out = tmp_path / "rainbow.sna"
    proc = subprocess.run(
        [sys.executable, "-m", "zt.cli", "build", str(EXAMPLE), "-o", str(out)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"demo build failed: {proc.stderr}"
    return out


def _border_writes(m: Z80) -> list[int]:
    return [val & 0x07 for port, val in m._outputs if (port & 0xFF) == 0xFE]


def _load_into_sim(sna_path: Path) -> Z80:
    raw = sna_path.read_bytes()
    sp_in_header = raw[0x17] | (raw[0x18] << 8)
    ram = load_sna(sna_path)
    m = Z80()
    for addr, byte in enumerate(ram):
        m._wb(addr, byte)
    m.sp = sp_in_header
    m.pc = m._rw(m.sp)
    m.sp = (m.sp + 2) & 0xFFFF
    return m


class TestRainbowDemoFires:

    def test_main_runs_long_enough_for_three_frames(self, built_sna):
        m = _load_into_sim(built_sna)
        m.run_until(FRAME_T_STATES_48K * 3 + 5000)
        assert m.interrupt_count == 3, (
            f"3 frames should fire 3 ULA interrupts; got {m.interrupt_count}"
        )

    def test_each_frame_writes_an_advancing_border_value(self, built_sna):
        m = _load_into_sim(built_sna)
        m.run_until(FRAME_T_STATES_48K * 8 + 5000)
        writes = _border_writes(m)
        assert writes == [1, 2, 3, 4, 5, 6, 7, 0], (
            f"8 consecutive frames should produce border writes 1..7,0 "
            f"(border-tick starts at 0 and increments per frame); got {writes}"
        )

    def test_handler_address_landed_in_jp_slot(self, built_sna):
        m = _load_into_sim(built_sna)
        m.run_until(FRAME_T_STATES_48K * 3)
        slot_target = m._rw(0xB9BA)
        assert slot_target != 0, \
            "after IM2-HANDLER! runs, the JP-slot operand at $B9BA must point at the ISR"
