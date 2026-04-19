"""
Tests for `build_sna`: total size, header layout, stack pointer placement, border byte, code at origin, pushed PC, and range-error handling.
"""
import pytest

from zt.format.sna import (
    build_sna,
    SNA_HEADER_SIZE, SNA_RAM_BASE, SNA_TOTAL_SIZE,
)


def test_sna_total_size_is_49179():
    sna = build_sna(b"\x00", origin=0x8000)
    assert len(sna) == SNA_TOTAL_SIZE, "48K SNA must be exactly 49179 bytes"


def test_sna_header_is_27_bytes():
    assert SNA_HEADER_SIZE == 27, "SNA header is 27 bytes per spec"


@pytest.mark.parametrize("data_stack_top,expected_sp", [
    (0xFF00, 0xFEFE),
    (0xC000, 0xBFFE),
    (0x8002, 0x8000),
])
def test_sna_sp_in_header_is_dstack_minus_two(data_stack_top, expected_sp):
    sna = build_sna(b"\x00", origin=0x8000, data_stack_top=data_stack_top)
    sp = sna[0x17] | (sna[0x18] << 8)
    assert sp == expected_sp, f"SP should be {expected_sp:#06x} for dstack {data_stack_top:#06x}"


def test_sna_interrupt_mode_is_one():
    sna = build_sna(b"\x00", origin=0x8000)
    assert sna[0x19] == 1, "interrupt mode should be IM 1 (Spectrum default)"


@pytest.mark.parametrize("border", [0, 1, 2, 7])
def test_sna_border_byte_stored(border):
    sna = build_sna(b"\x00", origin=0x8000, border=border)
    assert sna[0x1A] == border, f"border byte should be {border}"


def test_sna_code_appears_at_correct_ram_offset():
    code = b"\xAB\xCD\xEF"
    sna = build_sna(code, origin=0x8000)
    file_offset = SNA_HEADER_SIZE + (0x8000 - SNA_RAM_BASE)
    assert sna[file_offset:file_offset + 3] == code, "code should land at file offset for origin"


def test_sna_pc_pushed_at_sp_in_ram():
    sna = build_sna(b"\x00", origin=0x8000, data_stack_top=0xFF00)
    sp_ram_offset = SNA_HEADER_SIZE + (0xFEFE - SNA_RAM_BASE)
    assert sna[sp_ram_offset] == 0x00, "low byte of PC=0x8000 should be at SP"
    assert sna[sp_ram_offset + 1] == 0x80, "high byte of PC=0x8000 should be at SP+1"


def test_sna_rejects_origin_below_ram():
    with pytest.raises(ValueError, match="below"):
        build_sna(b"\x00", origin=0x3FFF)


def test_sna_rejects_image_overflowing_64k():
    huge = b"\x00" * 0x100
    with pytest.raises(ValueError, match="overflows"):
        build_sna(huge, origin=0xFF80)
