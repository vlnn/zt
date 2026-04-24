"""
Load-side counterpart to `sna`/`mapfile`. Reads a `.sna` snapshot back into a
64K byte array (48K form) or a flat 128 KB `Sna128Image` (128K form), and
parses Fuse / ZEsarUX symbol-map files into a `name → address` dict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from zt.format.sna import (
    BANK_SIZE,
    SNA_128K_DUPLICATED_SIZE,
    SNA_128K_PC_OFFSET,
    SNA_128K_PORT_OFFSET,
    SNA_128K_TOTAL_SIZE,
    SNA_128K_TRDOS_OFFSET,
    SNA_HEADER_SIZE,
    SNA_RAM_BASE,
    SNA_RAM_SIZE,
    SNA_TOTAL_SIZE,
    tail_bank_order,
)


SnaKind = Literal["48k", "128k"]

_SNA_128K_TAIL_OFFSET = SNA_128K_TRDOS_OFFSET + 1


_FUSE_LINE_RE = re.compile(r"^\$?([0-9A-Fa-f]+)\s+(\S+)\s*$")
_ZESARUX_LINE_RE = re.compile(r"^(\S+)\s*=\s*\$?([0-9A-Fa-f]+)\s*$")


@dataclass(frozen=True)
class Sna128Image:
    memory: bytearray
    port_7ffd: int
    pc: int


def load_sna(path: Path) -> bytearray:
    raw = path.read_bytes()
    if len(raw) != SNA_TOTAL_SIZE:
        raise ValueError(
            f"unexpected .sna size {len(raw)}; expected {SNA_TOTAL_SIZE}"
        )
    mem = bytearray(0x10000)
    mem[SNA_RAM_BASE:SNA_RAM_BASE + SNA_RAM_SIZE] = raw[SNA_HEADER_SIZE:]
    return mem


def load_sna_128(path: Path) -> Sna128Image:
    raw = path.read_bytes()
    _validate_128k_size(len(raw))
    port_7ffd = raw[SNA_128K_PORT_OFFSET]
    paged_bank = port_7ffd & 0x07
    pc = raw[SNA_128K_PC_OFFSET] | (raw[SNA_128K_PC_OFFSET + 1] << 8)
    memory = _assemble_128k_memory(raw, paged_bank)
    return Sna128Image(memory=memory, port_7ffd=port_7ffd, pc=pc)


def detect_sna_kind(path: Path) -> SnaKind:
    size = path.stat().st_size
    if size == SNA_TOTAL_SIZE:
        return "48k"
    if size in (SNA_128K_TOTAL_SIZE, SNA_128K_DUPLICATED_SIZE):
        return "128k"
    raise ValueError(
        f"unexpected .sna size {size}; not a recognised 48k or 128k snapshot"
    )


def _validate_128k_size(size: int) -> None:
    if size not in (SNA_128K_TOTAL_SIZE, SNA_128K_DUPLICATED_SIZE):
        raise ValueError(
            f"unexpected 128k .sna size {size}; expected "
            f"{SNA_128K_TOTAL_SIZE} or {SNA_128K_DUPLICATED_SIZE}"
        )


def _assemble_128k_memory(raw: bytes, paged_bank: int) -> bytearray:
    memory = bytearray(8 * BANK_SIZE)
    _place_bank(memory, 5, raw, SNA_HEADER_SIZE)
    _place_bank(memory, 2, raw, SNA_HEADER_SIZE + BANK_SIZE)
    _place_bank(memory, paged_bank, raw, SNA_HEADER_SIZE + 2 * BANK_SIZE)
    for idx, bank_id in enumerate(tail_bank_order(paged_bank)):
        _place_bank(memory, bank_id, raw, _SNA_128K_TAIL_OFFSET + idx * BANK_SIZE)
    return memory


def _place_bank(memory: bytearray, bank_id: int,
                raw: bytes, source_offset: int) -> None:
    dest = bank_id * BANK_SIZE
    memory[dest:dest + BANK_SIZE] = raw[source_offset:source_offset + BANK_SIZE]


def read_map(path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for line in path.read_text().splitlines():
        entry = _parse_map_line(line)
        if entry is not None:
            name, addr = entry
            labels[name] = addr
    return labels


def _parse_map_line(line: str) -> tuple[str, int] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith(";"):
        return None
    m = _FUSE_LINE_RE.match(stripped)
    if m:
        return m.group(2), int(m.group(1), 16)
    m = _ZESARUX_LINE_RE.match(stripped)
    if m:
        return m.group(1), int(m.group(2), 16)
    return None


def default_map_path(image_path: Path) -> Path:
    return image_path.with_suffix(".map")
