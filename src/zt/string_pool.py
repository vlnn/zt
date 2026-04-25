from __future__ import annotations

from zt.asm import Asm


class StringPool:

    def __init__(self) -> None:
        self._pending: list[tuple[str, bytes]] = []
        self._counter: int = 0

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def allocate(self, data: bytes) -> str:
        label = f"_str_{self._counter}"
        self._counter += 1
        self._pending.append((label, data))
        return label

    def flush(self, asm: Asm) -> None:
        for label, data in self._pending:
            asm.label(label)
            for byte_value in data:
                asm.byte(byte_value)
        self._pending.clear()
