"""
Tests for the 128K `.sna` writer: total size, 48K-style register header, bank
placement at the three fixed slots, 128K tail (PC/port/TR-DOS), ascending
ordering of remaining banks, the banks-5/2-duplication quirk, defaults, and
validation.
"""
from __future__ import annotations

import pytest

from zt.format.sna import (
    BANK_SIZE,
    SNA_128K_DUPLICATED_SIZE,
    SNA_128K_PC_OFFSET,
    SNA_128K_PORT_OFFSET,
    SNA_128K_TOTAL_SIZE,
    SNA_128K_TRDOS_OFFSET,
    SNA_HEADER_SIZE,
    build_sna_128,
)


BANK5_OFFSET = SNA_HEADER_SIZE
BANK2_OFFSET = SNA_HEADER_SIZE + BANK_SIZE
PAGED_OFFSET = SNA_HEADER_SIZE + 2 * BANK_SIZE
TAIL_BANKS_OFFSET = SNA_128K_TRDOS_OFFSET + 1


def _bank_filled(byte: int) -> bytes:
    return bytes([byte]) * BANK_SIZE


def _all_banks_distinct() -> dict[int, bytes]:
    return {n: _bank_filled(0xA0 + n) for n in range(8)}


def _bank_from_sna(sna: bytes, slot_offset: int) -> bytes:
    return sna[slot_offset:slot_offset + BANK_SIZE]


def _tail_bank(sna: bytes, index: int) -> bytes:
    start = TAIL_BANKS_OFFSET + index * BANK_SIZE
    return sna[start:start + BANK_SIZE]


def _read_word(sna: bytes, offset: int) -> int:
    return sna[offset] | (sna[offset + 1] << 8)


class TestSize:

    @pytest.mark.parametrize("paged_bank", [0, 1, 3, 4, 6, 7])
    def test_normal_case_is_131103(self, paged_bank):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000,
                            paged_bank=paged_bank)
        assert len(sna) == SNA_128K_TOTAL_SIZE, (
            f"128k SNA with paged_bank={paged_bank} should be "
            f"{SNA_128K_TOTAL_SIZE} bytes"
        )

    @pytest.mark.parametrize("paged_bank", [2, 5])
    def test_duplicated_case_is_147487(self, paged_bank):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000,
                            paged_bank=paged_bank)
        assert len(sna) == SNA_128K_DUPLICATED_SIZE, (
            f"128k SNA with paged_bank={paged_bank} should be "
            f"{SNA_128K_DUPLICATED_SIZE} bytes (duplication quirk)"
        )

    def test_size_constants_match_spec(self):
        assert SNA_128K_TOTAL_SIZE == 131_103, (
            "normal 128k size constant should equal the documented 131103"
        )
        assert SNA_128K_DUPLICATED_SIZE == 147_487, (
            "duplicated 128k size constant should equal the documented 147487"
        )


class TestHeaderReusesFortyEightKLayout:

    def test_interrupt_mode_is_one(self):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        assert sna[0x19] == 1, "interrupt mode byte should be IM 1 (Spectrum default)"

    @pytest.mark.parametrize("border", [0, 1, 2, 7])
    def test_border_byte_stored(self, border):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000,
                            paged_bank=0, border=border)
        assert sna[0x1A] == border, f"border byte should be {border}"

    @pytest.mark.parametrize("dstack,expected_sp", [
        (0xFF00, 0xFF00),
        (0xC000, 0xC000),
        (0x8000, 0x8000),
    ])
    def test_sp_is_data_stack_top_verbatim(self, dstack, expected_sp):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000,
                            paged_bank=0, data_stack_top=dstack)
        sp = _read_word(sna, 0x17)
        assert sp == expected_sp, (
            f"128k SP should be data_stack_top={dstack:#06x} unchanged "
            f"(no PC push), got {sp:#06x}"
        )


class TestBankPlacement:

    @pytest.mark.parametrize("paged_bank", [0, 1, 3, 4, 6, 7])
    def test_bank_five_at_first_slot(self, paged_bank):
        banks = _all_banks_distinct()
        sna = build_sna_128(banks, entry=0x8000, paged_bank=paged_bank)
        assert _bank_from_sna(sna, BANK5_OFFSET) == banks[5], (
            f"bank 5 should land at offset {BANK5_OFFSET} regardless of paged_bank"
        )

    @pytest.mark.parametrize("paged_bank", [0, 1, 3, 4, 6, 7])
    def test_bank_two_at_second_slot(self, paged_bank):
        banks = _all_banks_distinct()
        sna = build_sna_128(banks, entry=0x8000, paged_bank=paged_bank)
        assert _bank_from_sna(sna, BANK2_OFFSET) == banks[2], (
            f"bank 2 should land at offset {BANK2_OFFSET} regardless of paged_bank"
        )

    @pytest.mark.parametrize("paged_bank", [0, 1, 3, 4, 6, 7])
    def test_paged_bank_at_third_slot(self, paged_bank):
        banks = _all_banks_distinct()
        sna = build_sna_128(banks, entry=0x8000, paged_bank=paged_bank)
        assert _bank_from_sna(sna, PAGED_OFFSET) == banks[paged_bank], (
            f"paged bank {paged_bank} should land at offset {PAGED_OFFSET}"
        )


class TestTailHeader:

    @pytest.mark.parametrize("entry", [0x4000, 0x8000, 0xC123, 0xFFFE])
    def test_pc_stored_little_endian(self, entry):
        sna = build_sna_128(_all_banks_distinct(), entry=entry, paged_bank=0)
        pc = _read_word(sna, SNA_128K_PC_OFFSET)
        assert pc == entry, (
            f"PC at offset {SNA_128K_PC_OFFSET} should round-trip entry={entry:#06x}"
        )

    @pytest.mark.parametrize("paged_bank", list(range(8)))
    def test_port_default_encodes_paged_bank_with_rom_bit(self, paged_bank):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000,
                            paged_bank=paged_bank)
        port = sna[SNA_128K_PORT_OFFSET]
        assert port & 0x07 == paged_bank, (
            f"port $7FFD low bits should equal paged_bank={paged_bank}"
        )
        assert port & 0x10 == 0, (
            "port $7FFD bit 4 should be CLEAR by default: libspectrum treats "
            "every 128K SNA as Pentagon, where bit 4 = 0 selects BASIC ROM "
            "and bit 4 = 1 selects TR-DOS. We want BASIC at startup."
        )

    def test_port_override_stored_verbatim(self):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000,
                            paged_bank=0, port_7ffd=0x28)
        assert sna[SNA_128K_PORT_OFFSET] == 0x28, (
            "explicit port_7ffd should be stored unchanged"
        )

    def test_trdos_byte_is_zero(self):
        sna = build_sna_128(_all_banks_distinct(), entry=0x8000, paged_bank=0)
        assert sna[SNA_128K_TRDOS_OFFSET] == 0, (
            "TR-DOS ROM paged flag should be 0 for zt snapshots"
        )


class TestRemainingBanksOrdering:

    @pytest.mark.parametrize("paged_bank,expected_tail_banks", [
        (0, [1, 3, 4, 6, 7]),
        (1, [0, 3, 4, 6, 7]),
        (3, [0, 1, 4, 6, 7]),
        (4, [0, 1, 3, 6, 7]),
        (6, [0, 1, 3, 4, 7]),
        (7, [0, 1, 3, 4, 6]),
    ])
    def test_tail_skips_banks_five_two_and_paged(self, paged_bank, expected_tail_banks):
        banks = _all_banks_distinct()
        sna = build_sna_128(banks, entry=0x8000, paged_bank=paged_bank)
        for idx, bank_id in enumerate(expected_tail_banks):
            assert _tail_bank(sna, idx) == banks[bank_id], (
                f"tail slot {idx} should hold bank {bank_id} (ascending, "
                f"skipping 5, 2, and paged_bank={paged_bank})"
            )


class TestDuplicationQuirk:

    @pytest.mark.parametrize("paged_bank", [2, 5])
    def test_paged_bank_duplicated_when_two_or_five(self, paged_bank):
        banks = _all_banks_distinct()
        sna = build_sna_128(banks, entry=0x8000, paged_bank=paged_bank)
        assert _bank_from_sna(sna, PAGED_OFFSET) == banks[paged_bank], (
            f"paged bank {paged_bank} should appear at the paged slot"
        )
        fixed_slot = BANK5_OFFSET if paged_bank == 5 else BANK2_OFFSET
        assert _bank_from_sna(sna, fixed_slot) == banks[paged_bank], (
            f"bank {paged_bank} should also appear at its fixed slot "
            f"(offset {fixed_slot}) — the 128K duplication quirk"
        )

    @pytest.mark.parametrize("paged_bank,expected_tail_banks", [
        (2, [0, 1, 3, 4, 6, 7]),
        (5, [0, 1, 3, 4, 6, 7]),
    ])
    def test_tail_lists_all_non_five_two_banks_when_paged_is_five_or_two(
        self, paged_bank, expected_tail_banks,
    ):
        banks = _all_banks_distinct()
        sna = build_sna_128(banks, entry=0x8000, paged_bank=paged_bank)
        for idx, bank_id in enumerate(expected_tail_banks):
            assert _tail_bank(sna, idx) == banks[bank_id], (
                f"tail slot {idx} should hold bank {bank_id} when paged_bank="
                f"{paged_bank} (the duplication quirk does not shrink the tail)"
            )


class TestSparseBanksDict:

    def test_missing_banks_are_zero_filled(self):
        banks = {2: _bank_filled(0xAA), 5: _bank_filled(0xBB)}
        sna = build_sna_128(banks, entry=0x8000, paged_bank=0)
        assert _bank_from_sna(sna, PAGED_OFFSET) == _bank_filled(0x00), (
            "missing paged bank 0 should be zero-filled"
        )
        assert _tail_bank(sna, 0) == _bank_filled(0x00), (
            "missing tail bank should be zero-filled"
        )

    def test_all_banks_empty_dict(self):
        sna = build_sna_128({}, entry=0x8000, paged_bank=0)
        assert len(sna) == SNA_128K_TOTAL_SIZE, (
            "empty banks dict should still produce a full 131103-byte image"
        )


class TestValidation:

    @pytest.mark.parametrize("paged_bank", [-1, 8, 100])
    def test_rejects_paged_bank_out_of_range(self, paged_bank):
        with pytest.raises(ValueError, match="paged_bank"):
            build_sna_128({}, entry=0x8000, paged_bank=paged_bank)

    @pytest.mark.parametrize("entry", [0x0000, 0x3FFF])
    def test_rejects_entry_below_ram(self, entry):
        with pytest.raises(ValueError, match="entry"):
            build_sna_128({}, entry=entry, paged_bank=0)

    def test_rejects_oversized_bank(self):
        oversized = bytes(BANK_SIZE + 1)
        with pytest.raises(ValueError, match="bank"):
            build_sna_128({0: oversized}, entry=0x8000, paged_bank=0)

    @pytest.mark.parametrize("bank_id", [-1, 8, 99])
    def test_rejects_bank_id_out_of_range(self, bank_id):
        with pytest.raises(ValueError, match="bank"):
            build_sna_128({bank_id: bytes(BANK_SIZE)}, entry=0x8000, paged_bank=0)


class TestShorterBankPaddedToSixteenK:

    def test_short_bank_zero_padded(self):
        banks = {0: b"\xFF\xFF\xFF"}
        sna = build_sna_128(banks, entry=0x8000, paged_bank=0)
        paged = _bank_from_sna(sna, PAGED_OFFSET)
        assert paged[:3] == b"\xFF\xFF\xFF", (
            "short bank contents should appear at the start of the slot"
        )
        assert paged[3:] == bytes(BANK_SIZE - 3), (
            "remainder of short bank should be zero-padded to 16 KB"
        )
