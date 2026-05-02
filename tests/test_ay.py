"""
Port-level tests for stdlib/ay.fs. Forth cannot observe `OUT` writes, so
these run a small program in the simulator and inspect `Z80._outputs`.

AY register select goes to port $FFFD, data follows on port $BFFD.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler
from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80


AY_REG_SELECT_PORT = 0xFFFD
AY_DATA_PORT = 0xBFFD


def _ay_pairs(m: Z80) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    pending_reg: int | None = None
    for port, val in m._outputs:
        if port == AY_REG_SELECT_PORT:
            pending_reg = val
        elif port == AY_DATA_PORT and pending_reg is not None:
            pairs.append((pending_reg, val))
            pending_reg = None
    return pairs


def _run(source: str) -> Z80:
    full = "include ay.fs\n" + source + "\n"
    c = Compiler()
    c.compile_source(full)
    c.compile_main_call()
    image = c.build()
    m = Z80()
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = c.words["_start"].address
    m.run(max_ticks=200_000)
    assert m.halted, "ay.fs test program should halt"
    return m


class TestAySet:

    @pytest.mark.parametrize("val,reg", [
        (0x38, 7),
        (0x0F, 8),
        (0x00, 0),
        (0xFF, 13),
    ])
    def test_ay_set_writes_pair(self, val, reg):
        m = _run(f": main {val} {reg} ay-set halt ;")
        assert _ay_pairs(m) == [(reg, val)], (
            f"ay-set {val} {reg} should produce one (reg, val) pair on the AY ports"
        )


class TestAyMixerAndNoise:

    def test_ay_mixer_writes_register_7(self):
        m = _run(": main ay-mixer-tones-only ay-mixer! halt ;")
        assert _ay_pairs(m) == [(7, 0x38)], (
            "ay-mixer! should write its arg to AY register 7"
        )

    def test_ay_noise_writes_register_6(self):
        m = _run(": main 16 ay-noise! halt ;")
        assert _ay_pairs(m) == [(6, 16)], (
            "ay-noise! should write its arg to AY register 6"
        )


class TestAyToneChannels:

    @pytest.mark.parametrize("word,r_lo,r_hi", [
        ("ay-tone-a!", 0, 1),
        ("ay-tone-b!", 2, 3),
        ("ay-tone-c!", 4, 5),
    ])
    def test_tone_writes_lo_then_hi(self, word, r_lo, r_hi):
        m = _run(f": main 424 {word} halt ;")
        assert _ay_pairs(m) == [(r_lo, 424 & 0xFF), (r_hi, 424 >> 8)], (
            f"{word} 424 should write low-byte to R{r_lo} then high-byte to R{r_hi}"
        )

    @pytest.mark.parametrize("period,expected_lo,expected_hi", [
        (0x000, 0x00, 0x00),
        (0x0FF, 0xFF, 0x00),
        (0x100, 0x00, 0x01),
        (0xABC, 0xBC, 0x0A),
    ])
    def test_tone_a_byte_split(self, period, expected_lo, expected_hi):
        m = _run(f": main {period} ay-tone-a! halt ;")
        assert _ay_pairs(m) == [(0, expected_lo), (1, expected_hi)], (
            f"ay-tone-a! ${period:03X} should split into lo=${expected_lo:02X} hi=${expected_hi:02X}"
        )


class TestAyVolumeChannels:

    @pytest.mark.parametrize("word,reg", [
        ("ay-vol-a!", 8),
        ("ay-vol-b!", 9),
        ("ay-vol-c!", 10),
    ])
    def test_vol_writes_correct_register(self, word, reg):
        m = _run(f": main 12 {word} halt ;")
        assert _ay_pairs(m) == [(reg, 12)], (
            f"{word} 12 should write 12 to AY register {reg}"
        )
