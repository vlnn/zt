"""
IM 2 vector table layout. The 257-byte page is filled with `IM2_VECTOR_BYTE`
so that whichever floating-bus byte the ULA puts on D0–D7 during interrupt
acknowledge, both reads of `(I<<8)|bus_byte` and `(I<<8)|bus_byte+1` return
the same value, dispatching to `(V<<8)|V` for any bus byte.

The 3-byte JP slot at the dispatch address sits unused as `JP $0000` until a
runtime `IM2-HANDLER!` overwrites the operand with the user's handler.
"""
from __future__ import annotations

from zt.format.sna import BANK_SIZE, SNA_RAM_BASE

IM2_TABLE_PAGE = 0xB8
IM2_VECTOR_BYTE = 0xB9
IM2_TABLE_LEN = 257
IM2_TABLE_ADDR = IM2_TABLE_PAGE << 8
IM2_HANDLER_SLOT_ADDR = (IM2_VECTOR_BYTE << 8) | IM2_VECTOR_BYTE

_JP_PLACEHOLDER = bytes([0xC3, 0x00, 0x00])
_TABLE_BYTES = bytes([IM2_VECTOR_BYTE]) * IM2_TABLE_LEN


def inject_im2_table_into_ram48k(ram: bytes) -> bytes:
    return _patch(ram, base=SNA_RAM_BASE)


def inject_im2_table_into_bank(bank: bytes, bank_origin: int) -> bytes:
    if not _bank_contains_table(bank_origin):
        raise ValueError(
            f"bank_origin {bank_origin:#06x} does not contain $B800–$B9BB; "
            f"the IM 2 table must live in a slot whose origin is "
            f"{IM2_TABLE_ADDR & 0xC000:#06x}"
        )
    if len(bank) != BANK_SIZE:
        raise ValueError(f"bank must be {BANK_SIZE} bytes, got {len(bank)}")
    return _patch(bank, base=bank_origin)


def _bank_contains_table(bank_origin: int) -> bool:
    return bank_origin <= IM2_TABLE_ADDR and IM2_HANDLER_SLOT_ADDR + 3 <= bank_origin + BANK_SIZE


def _patch(image: bytes, base: int) -> bytes:
    buf = bytearray(image)
    table_offset = IM2_TABLE_ADDR - base
    slot_offset = IM2_HANDLER_SLOT_ADDR - base
    buf[table_offset:table_offset + IM2_TABLE_LEN] = _TABLE_BYTES
    buf[slot_offset:slot_offset + 3] = _JP_PLACEHOLDER
    return bytes(buf)
