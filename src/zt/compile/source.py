"""
`SourceEntry` dataclass: one row in the `address → (source_file, line, col)` map the compiler builds for debug symbol output (Fuse, ZEsarUX, SLD).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEntry:
    address: int
    source_file: str
    line: int
    col: int
