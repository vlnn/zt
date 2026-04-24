"""
`.z80` v3 snapshot builder for 128K targets. Unlike the 128K `.sna` format,
`.z80` v3 has an explicit hardware-type byte at offset 34 so emulators don't
have to guess between Spectrum 128, Pentagon 128, or +2.
"""
from __future__ import annotations

Z80_V3_BASE_HEADER_SIZE = 30
Z80_V3_EXTRA_HEADER_LENGTH = 54
Z80_V3_HEADER_SIZE = Z80_V3_BASE_HEADER_SIZE + 2 + Z80_V3_EXTRA_HEADER_LENGTH

Z80_V3_HARDWARE_128K = 4
Z80_V3_PORT_7FFD_OFFSET = 35

BANK_SIZE = 16_384
RAM_BASE = 0x4000
UNCOMPRESSED_BLOCK_MARKER = 0xFFFF
_ROM_PAGE_OFFSET = 3


def build_z80_v3(
    banks: dict[int, bytes],
    entry: int,
    paged_bank: int,
    data_stack_top: int = 0xBF00,
    border: int = 7,
    port_7ffd: int | None = None,
) -> bytes:
    _validate(banks, entry, paged_bank)
    padded = {n: _pad_bank(banks.get(n, b"")) for n in range(8)}
    port = paged_bank if port_7ffd is None else port_7ffd
    header = _build_header(entry, data_stack_top, border, port)
    blocks = b"".join(_build_memory_block(n + _ROM_PAGE_OFFSET, padded[n]) for n in range(8))
    return bytes(header) + blocks


def _validate(banks: dict[int, bytes], entry: int, paged_bank: int) -> None:
    if paged_bank not in range(8):
        raise ValueError(f"paged_bank {paged_bank} must be in range 0..7")
    if entry < RAM_BASE:
        raise ValueError(f"entry {entry:#06x} below Spectrum RAM at {RAM_BASE:#06x}")
    if entry > 0xFFFF:
        raise ValueError(f"entry {entry:#06x} exceeds 16-bit range")
    for bank_id, content in banks.items():
        if bank_id not in range(8):
            raise ValueError(f"bank id {bank_id} must be in range 0..7")
        if len(content) > BANK_SIZE:
            raise ValueError(
                f"bank {bank_id} holds {len(content)} bytes; limit is {BANK_SIZE}"
            )


def _pad_bank(content: bytes) -> bytes:
    return bytes(content) + bytes(BANK_SIZE - len(content))


def _build_header(entry: int, sp: int, border: int, port_7ffd: int) -> bytearray:
    header = bytearray(Z80_V3_HEADER_SIZE)
    _poke_word(header, 8, sp)
    header[12] = (border & 0x07) << 1
    header[29] = 0x01
    _poke_word(header, 30, Z80_V3_EXTRA_HEADER_LENGTH)
    _poke_word(header, 32, entry)
    header[34] = Z80_V3_HARDWARE_128K
    header[Z80_V3_PORT_7FFD_OFFSET] = port_7ffd & 0xFF
    return header


def _build_memory_block(page: int, data: bytes) -> bytes:
    return bytes([
        UNCOMPRESSED_BLOCK_MARKER & 0xFF,
        (UNCOMPRESSED_BLOCK_MARKER >> 8) & 0xFF,
        page,
    ]) + data


def _poke_word(buf: bytearray, offset: int, value: int) -> None:
    buf[offset] = value & 0xFF
    buf[offset + 1] = (value >> 8) & 0xFF
