from __future__ import annotations

SNA_HEADER_SIZE = 27
SNA_RAM_SIZE = 49152
SNA_RAM_BASE = 0x4000
SNA_TOTAL_SIZE = SNA_HEADER_SIZE + SNA_RAM_SIZE


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
