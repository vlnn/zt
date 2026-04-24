"""
Tests for the 128K `.sna` loader: round-trip with `build_sna_128`, flat
128 KB memory layout indexed by `bank * 0x4000 + offset`, port/PC/kind
detection, and rejection of mismatched file sizes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.format.image_loader import (
    Sna128Image,
    detect_sna_kind,
    load_sna,
    load_sna_128,
)
from zt.format.sna import (
    BANK_SIZE,
    SNA_128K_DUPLICATED_SIZE,
    SNA_128K_TOTAL_SIZE,
    SNA_TOTAL_SIZE,
    build_sna,
    build_sna_128,
)


def _bank_filled(byte: int) -> bytes:
    return bytes([byte]) * BANK_SIZE


def _all_banks_distinct() -> dict[int, bytes]:
    return {n: _bank_filled(0xA0 + n) for n in range(8)}


def _bank_slice(mem: bytearray, bank_id: int) -> bytes:
    start = bank_id * BANK_SIZE
    return bytes(mem[start:start + BANK_SIZE])


def _write(tmp_path: Path, data: bytes, name: str = "test.sna") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


class TestLoadSna128ReturnsImage:

    def test_returns_sna_128_image(self, tmp_path: Path):
        path = _write(tmp_path, build_sna_128({}, entry=0x8000, paged_bank=0))
        image = load_sna_128(path)
        assert isinstance(image, Sna128Image), (
            "load_sna_128 should return an Sna128Image dataclass"
        )

    def test_memory_is_128k_bytearray(self, tmp_path: Path):
        path = _write(tmp_path, build_sna_128({}, entry=0x8000, paged_bank=0))
        image = load_sna_128(path)
        assert isinstance(image.memory, bytearray), (
            "image.memory should be a bytearray for in-place simulator use"
        )
        assert len(image.memory) == 8 * BANK_SIZE, (
            f"image.memory should be {8 * BANK_SIZE} bytes (8 banks of 16 KB)"
        )


class TestBankPlacementFlat:

    @pytest.mark.parametrize("paged_bank", [0, 1, 3, 4, 6, 7])
    def test_each_bank_appears_at_flat_offset(self, tmp_path: Path, paged_bank):
        banks = _all_banks_distinct()
        path = _write(tmp_path, build_sna_128(banks, entry=0x8000,
                                              paged_bank=paged_bank))
        image = load_sna_128(path)
        for bank_id in range(8):
            assert _bank_slice(image.memory, bank_id) == banks[bank_id], (
                f"bank {bank_id} should appear at flat offset "
                f"{bank_id * BANK_SIZE:#x} (paged_bank={paged_bank})"
            )

    @pytest.mark.parametrize("paged_bank", [2, 5])
    def test_duplicated_bank_loads_consistently(self, tmp_path: Path, paged_bank):
        banks = _all_banks_distinct()
        path = _write(tmp_path, build_sna_128(banks, entry=0x8000,
                                              paged_bank=paged_bank))
        image = load_sna_128(path)
        assert _bank_slice(image.memory, paged_bank) == banks[paged_bank], (
            f"duplicated paged_bank={paged_bank} should land correctly "
            f"despite appearing twice in the file"
        )
        for bank_id in range(8):
            assert _bank_slice(image.memory, bank_id) == banks[bank_id], (
                f"bank {bank_id} should appear at flat offset "
                f"{bank_id * BANK_SIZE:#x} (duplicated-case paged_bank={paged_bank})"
            )


class TestPcRoundtrip:

    @pytest.mark.parametrize("entry", [0x4000, 0x8000, 0xC123, 0xFFFE])
    def test_pc_matches_entry(self, tmp_path: Path, entry):
        path = _write(tmp_path, build_sna_128({}, entry=entry, paged_bank=0))
        image = load_sna_128(path)
        assert image.pc == entry, (
            f"pc should round-trip entry={entry:#06x}, got {image.pc:#06x}"
        )


class TestPort7ffdRoundtrip:

    @pytest.mark.parametrize("paged_bank", list(range(8)))
    def test_default_port_roundtrips(self, tmp_path: Path, paged_bank):
        path = _write(tmp_path, build_sna_128({}, entry=0x8000,
                                              paged_bank=paged_bank))
        image = load_sna_128(path)
        assert image.port_7ffd & 0x07 == paged_bank, (
            f"port_7ffd low bits should equal paged_bank={paged_bank}"
        )
        assert image.port_7ffd & 0x10 == 0, (
            "default port_7ffd should have bit 4 CLEAR (Pentagon BASIC ROM)"
        )

    def test_explicit_port_roundtrips(self, tmp_path: Path):
        path = _write(tmp_path, build_sna_128({}, entry=0x8000,
                                              paged_bank=0, port_7ffd=0x28))
        image = load_sna_128(path)
        assert image.port_7ffd == 0x28, (
            "explicit port_7ffd should round-trip unchanged"
        )


class TestSizeValidation:

    def test_rejects_48k_sized_file(self, tmp_path: Path):
        path = _write(tmp_path, build_sna(b"\x00", origin=0x8000))
        with pytest.raises(ValueError, match="128"):
            load_sna_128(path)

    def test_rejects_arbitrary_size(self, tmp_path: Path):
        path = _write(tmp_path, b"\x00" * 100)
        with pytest.raises(ValueError, match="128"):
            load_sna_128(path)

    def test_load_sna_still_rejects_128k_file(self, tmp_path: Path):
        path = _write(tmp_path, build_sna_128({}, entry=0x8000, paged_bank=0))
        with pytest.raises(ValueError, match="unexpected .sna size"):
            load_sna(path)


class TestDetectSnaKind:

    def test_48k_file(self, tmp_path: Path):
        path = _write(tmp_path, build_sna(b"\x00", origin=0x8000))
        assert detect_sna_kind(path) == "48k", (
            f"a {SNA_TOTAL_SIZE}-byte file should be detected as 48k"
        )

    @pytest.mark.parametrize("paged_bank", [0, 1, 3, 4, 6, 7])
    def test_128k_normal_size(self, tmp_path: Path, paged_bank):
        path = _write(tmp_path, build_sna_128({}, entry=0x8000,
                                              paged_bank=paged_bank))
        assert detect_sna_kind(path) == "128k", (
            f"a {SNA_128K_TOTAL_SIZE}-byte file should be detected as 128k"
        )

    @pytest.mark.parametrize("paged_bank", [2, 5])
    def test_128k_duplicated_size(self, tmp_path: Path, paged_bank):
        path = _write(tmp_path, build_sna_128({}, entry=0x8000,
                                              paged_bank=paged_bank))
        assert detect_sna_kind(path) == "128k", (
            f"a {SNA_128K_DUPLICATED_SIZE}-byte file should also be detected "
            f"as 128k (duplication quirk when paged_bank={paged_bank})"
        )

    @pytest.mark.parametrize("size", [0, 100, 49178, 49180, 131102, 131104])
    def test_rejects_unknown_size(self, tmp_path: Path, size):
        path = _write(tmp_path, b"\x00" * size)
        with pytest.raises(ValueError, match="sna"):
            detect_sna_kind(path)


class TestFullRoundtripAllBanks:

    @pytest.mark.parametrize("paged_bank", list(range(8)))
    def test_build_then_load_preserves_every_byte(self, tmp_path: Path, paged_bank):
        banks = {n: bytes((i ^ n) & 0xFF for i in range(BANK_SIZE)) for n in range(8)}
        path = _write(tmp_path, build_sna_128(banks, entry=0xABCD,
                                              paged_bank=paged_bank))
        image = load_sna_128(path)
        for bank_id in range(8):
            assert _bank_slice(image.memory, bank_id) == banks[bank_id], (
                f"bank {bank_id} should round-trip byte-for-byte "
                f"(paged_bank={paged_bank})"
            )
        assert image.pc == 0xABCD, "pc should round-trip"
        assert image.port_7ffd & 0x07 == paged_bank, "port should encode paged_bank"
