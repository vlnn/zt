"""
`.sna` snapshot builder. `build_sna` emits the 48K form (27-byte header +
49152-byte RAM image with PC pushed at SP). `build_sna_128` emits the 128K
extension: the same 48K image for banks 5/2/paged, then PC/port/TR-DOS and
the remaining RAM banks in ascending order.
"""
from __future__ import annotations

SNA_HEADER_SIZE = 27
SNA_RAM_SIZE = 49152
SNA_RAM_BASE = 0x4000
SNA_TOTAL_SIZE = SNA_HEADER_SIZE + SNA_RAM_SIZE

BANK_SIZE = 16_384
SNA_128K_PC_OFFSET = 49_179
SNA_128K_PORT_OFFSET = 49_181
SNA_128K_TRDOS_OFFSET = 49_182
SNA_128K_TOTAL_SIZE = 131_103
SNA_128K_DUPLICATED_SIZE = 147_487

BANKM_SHADOW_ADDR = 0x5B5C
_BANKM_SHADOW_OFFSET_IN_BANK_5 = BANKM_SHADOW_ADDR - 0x4000

_BANK_AT_SLOT_4000 = 5
_BANK_AT_SLOT_8000 = 2


def _poke_word(buf: bytearray, offset: int, value: int) -> None:
    buf[offset] = value & 0xFF
    buf[offset + 1] = (value >> 8) & 0xFF


def _build_sna_header(sp: int, border: int) -> bytearray:
    header = bytearray(SNA_HEADER_SIZE)
    _poke_word(header, 0x17, sp)
    header[0x19] = 1
    header[0x1A] = border & 7
    return header


def _build_sna_ram(code: bytes, origin: int, sp: int, entry: int) -> bytearray:
    ram = bytearray(SNA_RAM_SIZE)
    ram[origin - SNA_RAM_BASE : origin - SNA_RAM_BASE + len(code)] = code
    _poke_word(ram, sp - SNA_RAM_BASE, entry)
    return ram


def build_sna(code: bytes, origin: int,
              data_stack_top: int = 0xFF00,
              border: int = 7,
              entry: int | None = None) -> bytes:
    if origin < SNA_RAM_BASE:
        raise ValueError(f"origin {origin:#06x} below Spectrum RAM at {SNA_RAM_BASE:#06x}")
    if origin + len(code) > 0x10000:
        raise ValueError(f"image of {len(code)} bytes at {origin:#06x} overflows 64K")
    sp = data_stack_top - 2
    if sp < SNA_RAM_BASE or sp + 1 > 0xFFFF:
        raise ValueError(f"data_stack_top {data_stack_top:#06x} leaves no room for PC push")
    if entry is None:
        entry = origin
    return bytes(_build_sna_header(sp, border)) + bytes(_build_sna_ram(code, origin, sp, entry))


def build_sna_128(
    banks: dict[int, bytes],
    entry: int,
    paged_bank: int,
    data_stack_top: int = 0xFF00,
    border: int = 7,
    port_7ffd: int | None = None,
) -> bytes:
    _validate_128k_inputs(banks, entry, paged_bank)
    padded = _pad_all_banks(banks)
    port = (paged_bank | 0x10) if port_7ffd is None else port_7ffd
    padded = _set_bankm_shadow(padded, port)
    header = _build_sna_header(data_stack_top, border)
    initial = _initial_48k_image(padded, paged_bank)
    tail = _tail_128k(padded, paged_bank, entry, port)
    return bytes(header) + initial + tail


def _validate_128k_inputs(banks: dict[int, bytes], entry: int, paged_bank: int) -> None:
    if paged_bank not in range(8):
        raise ValueError(f"paged_bank {paged_bank} must be in range 0..7")
    if entry < SNA_RAM_BASE:
        raise ValueError(
            f"entry {entry:#06x} below Spectrum RAM at {SNA_RAM_BASE:#06x}"
        )
    if entry > 0xFFFF:
        raise ValueError(f"entry {entry:#06x} exceeds 16-bit range")
    for bank_id, content in banks.items():
        if bank_id not in range(8):
            raise ValueError(f"bank id {bank_id} must be in range 0..7")
        if len(content) > BANK_SIZE:
            raise ValueError(
                f"bank {bank_id} holds {len(content)} bytes; "
                f"limit is {BANK_SIZE}"
            )


def _pad_all_banks(banks: dict[int, bytes]) -> dict[int, bytes]:
    return {n: _pad_to_bank_size(banks.get(n, b"")) for n in range(8)}


def _pad_to_bank_size(content: bytes) -> bytes:
    return bytes(content) + bytes(BANK_SIZE - len(content))


def _set_bankm_shadow(padded: dict[int, bytes], port: int) -> dict[int, bytes]:
    """Initialize the BANKM shadow at $5B5C (bank 5) to match port $7FFD.

    BANK! reads this byte to preserve the upper bits (ROM select, screen
    select, lock) when changing the paged-in bank. If left as zero, the
    very first BANK! call clears bit 4 and pages in the 128K editor ROM,
    which lacks the standard glyph font at $3D00 — every subsequent EMIT
    then renders garbage on real hardware.
    """
    bank5 = bytearray(padded[5])
    bank5[_BANKM_SHADOW_OFFSET_IN_BANK_5] = port & 0xFF
    return {**padded, 5: bytes(bank5)}


def _initial_48k_image(padded: dict[int, bytes], paged_bank: int) -> bytes:
    return padded[_BANK_AT_SLOT_4000] + padded[_BANK_AT_SLOT_8000] + padded[paged_bank]


def _tail_128k(padded: dict[int, bytes], paged_bank: int,
               entry: int, port_7ffd: int) -> bytes:
    tail_ids = tail_bank_order(paged_bank)
    tail_banks = b"".join(padded[n] for n in tail_ids)
    pc_bytes = bytes([entry & 0xFF, (entry >> 8) & 0xFF])
    meta_bytes = bytes([port_7ffd & 0xFF, 0])
    return pc_bytes + meta_bytes + tail_banks


def tail_bank_order(paged_bank: int) -> list[int]:
    excluded = {_BANK_AT_SLOT_4000, _BANK_AT_SLOT_8000, paged_bank}
    return [n for n in range(8) if n not in excluded]
