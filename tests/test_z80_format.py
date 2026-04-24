"""
Tests for the Z80 v3 128K writer: header layout (30-byte base + 2-byte
length + 54-byte extended), memory-block framing (`len:2 page:1 data`),
uncompressed 16K blocks flagged by length=0xFFFF, bank-to-page mapping
(RAM bank N → page N + 3), `$7FFD` at offset 35, and the hardware mode
byte at offset 34 = 4 (Spectrum 128).
"""
from __future__ import annotations

import pytest

from zt.format.z80 import (
    Z80_V3_HARDWARE_128K,
    Z80_V3_HEADER_SIZE,
    Z80_V3_PORT_7FFD_OFFSET,
    build_z80_v3,
)


BANK_SIZE = 16_384


def _all_banks_distinct() -> dict[int, bytes]:
    return {n: bytes([0xA0 + n]) * BANK_SIZE for n in range(8)}


def _read_word(buf: bytes, offset: int) -> int:
    return buf[offset] | (buf[offset + 1] << 8)


def _find_page(buf: bytes, page_num: int, start: int = Z80_V3_HEADER_SIZE) -> tuple[int, int]:
    offset = start
    while offset < len(buf):
        length = _read_word(buf, offset)
        page = buf[offset + 2]
        data_size = 16_384 if length == 0xFFFF else length
        if page == page_num:
            return offset + 3, data_size
        offset += 3 + data_size
    raise ValueError(f"page {page_num} not found in z80 image")


class TestHeaderConstants:

    def test_header_size_is_86_bytes(self):
        assert Z80_V3_HEADER_SIZE == 86, (
            "v3 z80 header is 30-byte base + 2-byte length + 54-byte extended = 86"
        )

    def test_hardware_128k_is_4(self):
        assert Z80_V3_HARDWARE_128K == 4, (
            "Spectrum 128K hardware mode byte is 4 per the v3 spec"
        )

    def test_port_7ffd_offset_is_35(self):
        assert Z80_V3_PORT_7FFD_OFFSET == 35, (
            "last OUT to $7FFD lives at offset 35 in the v3 extended header"
        )


class TestBaseHeader:

    def test_pc_in_base_header_is_zero(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        pc_in_base = _read_word(out, 6)
        assert pc_in_base == 0, (
            "base-header PC=0 signals v2/v3 extended format; actual PC goes at offset 32"
        )

    def test_a_f_registers_zero_by_default(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        assert out[0] == 0 and out[1] == 0, (
            "A and F registers should default to zero"
        )

    @pytest.mark.parametrize("sp", [0xBF00, 0x8000, 0xBE00])
    def test_sp_in_base_header(self, sp):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000,
                           paged_bank=0, data_stack_top=sp)
        assert _read_word(out, 8) == sp, (
            f"SP at offset 8 should match data_stack_top={sp:#06x}"
        )

    def test_interrupt_mode_is_im1_by_default(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        im_bits = out[29] & 0x03
        assert im_bits == 1, (
            "interrupt mode bits (byte 29 bits 0-1) should default to IM 1"
        )

    def test_data_not_compressed_flag(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        assert out[12] & 0x20 == 0, (
            "flag byte 12 bit 5 (compressed) must be 0 for v3 (v3 uses block headers)"
        )

    @pytest.mark.parametrize("border", [0, 1, 2, 7])
    def test_border_in_flag_byte(self, border):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000,
                           paged_bank=0, border=border)
        assert (out[12] >> 1) & 0x07 == border, (
            f"flag byte bits 1-3 should hold border colour {border}"
        )


class TestExtendedHeader:

    def test_extra_header_length_is_54_for_v3(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        assert _read_word(out, 30) == 54, (
            "word at offset 30 should be 54 for v3 extended header"
        )

    @pytest.mark.parametrize("entry", [0x4000, 0x8000, 0xC123, 0xFFFE])
    def test_pc_in_extended_header(self, entry):
        out = build_z80_v3(_all_banks_distinct(), entry=entry, paged_bank=0)
        assert _read_word(out, 32) == entry, (
            f"extended-header PC at offset 32 should match entry={entry:#06x}"
        )

    def test_hardware_mode_is_128(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        assert out[34] == Z80_V3_HARDWARE_128K, (
            "hardware mode byte 34 should be 4 = Spectrum 128"
        )

    @pytest.mark.parametrize("paged_bank", list(range(8)))
    def test_port_7ffd_encodes_paged_bank(self, paged_bank):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000,
                           paged_bank=paged_bank)
        assert out[Z80_V3_PORT_7FFD_OFFSET] & 0x07 == paged_bank, (
            f"byte 35 low 3 bits should equal paged_bank={paged_bank}"
        )

    def test_port_7ffd_override(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000,
                           paged_bank=0, port_7ffd=0x18)
        assert out[Z80_V3_PORT_7FFD_OFFSET] == 0x18, (
            "explicit port_7ffd should be stored unchanged"
        )


class TestMemoryBlocks:

    def test_all_eight_banks_emitted(self):
        banks = _all_banks_distinct()
        out = build_z80_v3(banks, entry=0x8000, paged_bank=0)
        for bank in range(8):
            page = bank + 3
            data_offset, size = _find_page(out, page)
            assert size == BANK_SIZE, (
                f"page {page} (RAM bank {bank}) should be 16 KB, got {size}"
            )
            assert out[data_offset:data_offset + BANK_SIZE] == banks[bank], (
                f"page {page} should hold RAM bank {bank} bytes"
            )

    def test_uncompressed_blocks_use_0xffff_length_marker(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        data_offset, _ = _find_page(out, 3)
        length_word = _read_word(out, data_offset - 3)
        assert length_word == 0xFFFF, (
            "uncompressed 16K blocks must signal with length=0xFFFF per v3 spec"
        )

    def test_missing_banks_zero_filled(self):
        sparse = {2: bytes([0xAA]) * BANK_SIZE, 5: bytes([0xBB]) * BANK_SIZE}
        out = build_z80_v3(sparse, entry=0x8000, paged_bank=0)
        data_offset, _ = _find_page(out, 3)
        assert out[data_offset:data_offset + BANK_SIZE] == bytes(BANK_SIZE), (
            "missing bank 0 should emit 16 KB of zeros"
        )


class TestRoundTrip:

    def test_total_size_is_header_plus_eight_framed_blocks(self):
        out = build_z80_v3(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        expected = Z80_V3_HEADER_SIZE + 8 * (3 + BANK_SIZE)
        assert len(out) == expected, (
            f"total size should be header ({Z80_V3_HEADER_SIZE}) + "
            f"8 banks * (3 byte frame + 16 KB) = {expected}"
        )


class TestValidation:

    @pytest.mark.parametrize("paged_bank", [-1, 8, 99])
    def test_rejects_out_of_range_paged_bank(self, paged_bank):
        with pytest.raises(ValueError, match="paged_bank"):
            build_z80_v3({}, entry=0x8000, paged_bank=paged_bank)

    @pytest.mark.parametrize("entry", [0x0000, 0x3FFF])
    def test_rejects_entry_below_ram(self, entry):
        with pytest.raises(ValueError, match="entry"):
            build_z80_v3({}, entry=entry, paged_bank=0)

    def test_rejects_oversized_bank(self):
        with pytest.raises(ValueError, match="bank"):
            build_z80_v3({0: bytes(BANK_SIZE + 1)}, entry=0x8000, paged_bank=0)
