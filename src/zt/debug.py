from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEntry:
    address: int
    source_file: str
    line: int
    col: int
