"""
Load-side counterpart to `sna`/`mapfile`. Reads a `.sna` snapshot back into a 64K byte array and parses Fuse / ZEsarUX symbol-map files into a `name → address` dict.
"""
from __future__ import annotations

import re
from pathlib import Path

from zt.sna import SNA_HEADER_SIZE, SNA_RAM_BASE, SNA_RAM_SIZE, SNA_TOTAL_SIZE


_FUSE_LINE_RE = re.compile(r"^\$?([0-9A-Fa-f]+)\s+(\S+)\s*$")
_ZESARUX_LINE_RE = re.compile(r"^(\S+)\s*=\s*\$?([0-9A-Fa-f]+)\s*$")


def load_sna(path: Path) -> bytearray:
    raw = path.read_bytes()
    if len(raw) != SNA_TOTAL_SIZE:
        raise ValueError(
            f"unexpected .sna size {len(raw)}; expected {SNA_TOTAL_SIZE}"
        )
    mem = bytearray(0x10000)
    mem[SNA_RAM_BASE:SNA_RAM_BASE + SNA_RAM_SIZE] = raw[SNA_HEADER_SIZE:]
    return mem


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
