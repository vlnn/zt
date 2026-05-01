"""
Tests for the IM 2 vector table allocator: the 257-byte page filled with
`IM2_VECTOR_BYTE` and the 3-byte `JP` slot at `(V<<8)|V`. Covers the constants,
the byte-level injection helpers for 48K RAM and a 16K bank, and the integration
with `build_sna` / `build_sna_128` gated on `im2_table=True`.
"""
from __future__ import annotations

import pytest

from zt.assemble.im2_table import (
    IM2_HANDLER_SLOT_ADDR,
    IM2_TABLE_ADDR,
    IM2_TABLE_LEN,
    IM2_TABLE_PAGE,
    IM2_VECTOR_BYTE,
    inject_im2_table_into_bank,
    inject_im2_table_into_ram48k,
)
from zt.format.sna import (
    BANK_SIZE,
    SNA_HEADER_SIZE,
    SNA_RAM_BASE,
    build_sna,
    build_sna_128,
)


class TestConstants:

    def test_table_page_is_b8(self):
        assert IM2_TABLE_PAGE == 0xB8, \
            "default IM 2 table page should be 0xB8 (slot 2, away from screen and stack)"

    def test_vector_byte_is_b9(self):
        assert IM2_VECTOR_BYTE == 0xB9, \
            "default vector byte should be 0xB9 so the dispatch vector is 0xB9B9"

    def test_table_addr_is_page_times_256(self):
        assert IM2_TABLE_ADDR == IM2_TABLE_PAGE << 8, \
            "table address should be the page byte shifted into the high byte"

    def test_handler_slot_addr_is_vector_repeated(self):
        assert IM2_HANDLER_SLOT_ADDR == (IM2_VECTOR_BYTE << 8) | IM2_VECTOR_BYTE, \
            "handler slot should sit at (V<<8)|V — the address all 257 bus bytes resolve to"

    def test_table_length_is_257(self):
        assert IM2_TABLE_LEN == 257, \
            "table length must be 257 to defeat the floating-bus byte ambiguity"


class TestInjectIntoRam48k:

    def _empty_ram(self):
        return bytes(0x10000 - SNA_RAM_BASE)

    def test_table_bytes_appear_at_b800(self):
        out = inject_im2_table_into_ram48k(self._empty_ram())
        base = IM2_TABLE_ADDR - SNA_RAM_BASE
        assert out[base:base + IM2_TABLE_LEN] == bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN, \
            "257 bytes of IM2_VECTOR_BYTE should land at $B800 in the RAM image"

    def test_handler_slot_holds_jp_to_zero_placeholder(self):
        out = inject_im2_table_into_ram48k(self._empty_ram())
        slot = IM2_HANDLER_SLOT_ADDR - SNA_RAM_BASE
        assert out[slot:slot + 3] == bytes([0xC3, 0x00, 0x00]), \
            "handler slot should be JP $0000 (placeholder; IM2-HANDLER! overwrites the address)"

    def test_does_not_disturb_other_bytes(self):
        ram = bytearray(self._empty_ram())
        ram[0x100] = 0xAA
        ram[0x4000] = 0xBB
        out = inject_im2_table_into_ram48k(bytes(ram))
        assert out[0x100] == 0xAA, "byte before the table must be preserved"
        assert out[0x4000] == 0xBB, "byte after the table must be preserved"

    def test_input_not_mutated(self):
        ram = self._empty_ram()
        before = bytes(ram)
        inject_im2_table_into_ram48k(ram)
        assert ram == before, "input bytes must not be mutated in place"

    def test_output_size_unchanged(self):
        out = inject_im2_table_into_ram48k(self._empty_ram())
        assert len(out) == 0x10000 - SNA_RAM_BASE, \
            "output must remain a full 48K RAM image (49152 bytes)"


class TestInjectIntoBank:

    def _empty_bank(self):
        return bytes(BANK_SIZE)

    def test_table_bytes_appear_at_offset_in_slot2(self):
        out = inject_im2_table_into_bank(self._empty_bank(), bank_origin=0x8000)
        offset = IM2_TABLE_ADDR - 0x8000
        assert out[offset:offset + IM2_TABLE_LEN] == bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN, \
            "table bytes should appear at the slot-2-relative offset within bank 2"

    def test_handler_slot_holds_jp_zero(self):
        out = inject_im2_table_into_bank(self._empty_bank(), bank_origin=0x8000)
        slot = IM2_HANDLER_SLOT_ADDR - 0x8000
        assert out[slot:slot + 3] == bytes([0xC3, 0x00, 0x00]), \
            "JP $0000 placeholder should appear at the handler slot offset"

    def test_output_size_is_one_bank(self):
        out = inject_im2_table_into_bank(self._empty_bank(), bank_origin=0x8000)
        assert len(out) == BANK_SIZE, \
            "injecting into a 16K bank must yield exactly 16K back"

    def test_rejects_origin_that_does_not_contain_table(self):
        with pytest.raises(ValueError, match="bank_origin"):
            inject_im2_table_into_bank(self._empty_bank(), bank_origin=0x4000)


class TestBuildSnaIntegration48k:

    def _file_offset(self, addr):
        return SNA_HEADER_SIZE + (addr - SNA_RAM_BASE)

    def test_default_does_not_emit_table(self):
        sna = build_sna(b"", origin=0x8000)
        offset = self._file_offset(IM2_TABLE_ADDR)
        assert sna[offset:offset + IM2_TABLE_LEN] == bytes(IM2_TABLE_LEN), \
            "without im2_table=True the SNA must stay zero at $B800 (48K regression safety)"

    def test_im2_table_flag_emits_vector_bytes(self):
        sna = build_sna(b"", origin=0x8000, im2_table=True)
        offset = self._file_offset(IM2_TABLE_ADDR)
        assert sna[offset:offset + IM2_TABLE_LEN] == bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN, \
            "im2_table=True should emit 257 bytes of IM2_VECTOR_BYTE at $B800"

    def test_im2_table_flag_emits_jp_slot(self):
        sna = build_sna(b"", origin=0x8000, im2_table=True)
        offset = self._file_offset(IM2_HANDLER_SLOT_ADDR)
        assert sna[offset:offset + 3] == bytes([0xC3, 0x00, 0x00]), \
            "im2_table=True should emit JP $0000 placeholder at $B9B9"

    def test_im2_table_flag_does_not_disturb_code(self):
        code = bytes([0x3E, 0xFF, 0x00, 0x76])
        sna_plain = build_sna(code, origin=0x8000)
        sna_im2 = build_sna(code, origin=0x8000, im2_table=True)
        code_offset = self._file_offset(0x8000)
        assert sna_plain[code_offset:code_offset + len(code)] == code, \
            "sanity: emitted code should appear at the code offset"
        assert sna_im2[code_offset:code_offset + len(code)] == code, \
            "im2_table=True must not corrupt the code region"


class TestBuildSna128Integration:

    def _bank2_slice(self, sna):
        return sna[SNA_HEADER_SIZE + BANK_SIZE : SNA_HEADER_SIZE + 2 * BANK_SIZE]

    def test_default_does_not_emit_table_into_bank2(self):
        sna = build_sna_128(banks={}, entry=0x8000, paged_bank=0)
        bank2 = self._bank2_slice(sna)
        offset = IM2_TABLE_ADDR - 0x8000
        assert bank2[offset:offset + IM2_TABLE_LEN] == bytes(IM2_TABLE_LEN), \
            "without im2_table=True bank 2 should stay zero at $B800"

    def test_im2_table_flag_emits_into_bank2(self):
        sna = build_sna_128(banks={}, entry=0x8000, paged_bank=0, im2_table=True)
        bank2 = self._bank2_slice(sna)
        offset = IM2_TABLE_ADDR - 0x8000
        assert bank2[offset:offset + IM2_TABLE_LEN] == bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN, \
            "im2_table=True should emit vector bytes into bank 2 at slot-2-relative $B800"

    def test_im2_table_flag_emits_jp_slot_into_bank2(self):
        sna = build_sna_128(banks={}, entry=0x8000, paged_bank=0, im2_table=True)
        bank2 = self._bank2_slice(sna)
        slot = IM2_HANDLER_SLOT_ADDR - 0x8000
        assert bank2[slot:slot + 3] == bytes([0xC3, 0x00, 0x00]), \
            "im2_table=True should emit JP $0000 placeholder in bank 2 at slot-2-relative $B9B9"

    def test_im2_table_flag_does_not_touch_other_banks(self):
        sentinel_bank0 = bytes([0xAA] * BANK_SIZE)
        sna = build_sna_128(
            banks={0: sentinel_bank0}, entry=0x8000, paged_bank=0, im2_table=True,
        )
        paged_offset = SNA_HEADER_SIZE + 2 * BANK_SIZE
        assert sna[paged_offset:paged_offset + BANK_SIZE] == sentinel_bank0, \
            "the paged bank (here bank 0) must remain untouched by the IM 2 table injection"


import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent


def _build_to_sna(tmp_path: Path, source: str, *extra_args: str) -> bytes:
    src = tmp_path / "src.fs"
    src.write_text(source)
    out = tmp_path / "out.sna"
    proc = subprocess.run(
        [sys.executable, "-m", "zt.cli", "build", str(src), "-o", str(out), *extra_args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"CLI build failed: {proc.stderr}"
    return out.read_bytes()


class TestCliAutoEnablesIm2Table:

    def test_source_with_im2_handler_emits_table(self, tmp_path):
        sna = _build_to_sna(tmp_path, ": main 49152 IM2-HANDLER! halt ;\n")
        offset = SNA_HEADER_SIZE + (IM2_TABLE_ADDR - SNA_RAM_BASE)
        assert sna[offset:offset + IM2_TABLE_LEN] == bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN, \
            "a program calling IM2-HANDLER! should auto-trigger im2_table=True at build time"

    def test_source_without_im2_keeps_zeros_at_table(self, tmp_path):
        sna = _build_to_sna(tmp_path, ": main 42 drop halt ;\n")
        offset = SNA_HEADER_SIZE + (IM2_TABLE_ADDR - SNA_RAM_BASE)
        assert sna[offset:offset + IM2_TABLE_LEN] == bytes(IM2_TABLE_LEN), \
            "a program with no IM 2 primitives must not emit the table (48K regression safety)"

    def test_source_using_only_im2_handler_fetch_emits_table(self, tmp_path):
        sna = _build_to_sna(tmp_path, ": main IM2-HANDLER@ drop halt ;\n")
        offset = SNA_HEADER_SIZE + (IM2_TABLE_ADDR - SNA_RAM_BASE)
        assert sna[offset:offset + IM2_TABLE_LEN] == bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN, \
            "any IM 2 primitive in the live image should auto-trigger im2_table=True"

    def test_source_using_im2_off_emits_table(self, tmp_path):
        sna = _build_to_sna(tmp_path, ": main IM2-OFF halt ;\n")
        offset = SNA_HEADER_SIZE + (IM2_TABLE_ADDR - SNA_RAM_BASE)
        assert sna[offset:offset + IM2_TABLE_LEN] == bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN, \
            "IM2-OFF in the live image should also auto-trigger the table emission"
