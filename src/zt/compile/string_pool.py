"""
Pending-string buffer. Allocates `_str_N` labels for `."` / `s"` literals during compilation and flushes them into the image after the dictionary.
"""
from __future__ import annotations

from zt.assemble.asm import Asm


class StringPool:

    def __init__(self) -> None:
        self._pending: list[tuple[str, bytes]] = []
        self._allocations: list[tuple[str, bytes]] = []
        self._counter: int = 0

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def allocations(self) -> list[tuple[str, bytes]]:
        return list(self._allocations)

    def allocate(self, data: bytes) -> str:
        label = f"_str_{self._counter}"
        self._counter += 1
        entry = (label, data)
        self._pending.append(entry)
        self._allocations.append(entry)
        return label

    def flush(self, asm: Asm) -> None:
        for label, data in self._pending:
            asm.label(label)
            for byte_value in data:
                asm.byte(byte_value)
        self._pending.clear()
