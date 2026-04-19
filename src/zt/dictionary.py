"""
`Dictionary`: the compiler's symbol table (name → `Word`), wrapping a plain dict with the lookup / registration API the compiler uses.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from zt.asm import Asm

if TYPE_CHECKING:
    from zt.compiler import Word


class Dictionary:

    def __init__(self) -> None:
        self._words: dict[str, "Word"] = {}

    def __len__(self) -> int:
        return len(self._words)

    def __contains__(self, name: str) -> bool:
        return name in self._words

    def __getitem__(self, name: str) -> "Word":
        return self._words[name]

    def __setitem__(self, name: str, word: "Word") -> None:
        self._words[name] = word

    def __iter__(self) -> Iterator[str]:
        return iter(self._words)

    def register(self, word: "Word") -> None:
        self._words[word.name] = word

    def get(self, name: str, default: "Word | None" = None) -> "Word | None":
        return self._words.get(name, default)

    def items(self):
        return self._words.items()

    def values(self):
        return self._words.values()

    def keys(self):
        return self._words.keys()

    def register_primitives(self, asm: Asm) -> None:
        from zt.compiler import Word
        for name, addr in asm.labels.items():
            if name.startswith("_"):
                continue
            lower = name.lower()
            if lower in self._words:
                continue
            self._words[lower] = Word(name=lower, address=addr, kind="prim")

    def redefinition_warning(
        self, name: str, source_file: str, source_line: int,
    ) -> str | None:
        previous = self._words.get(name)
        if previous is None or previous.kind != "colon":
            return None
        if previous.source_file is None or previous.source_line is None:
            return None
        here = f"{source_file}:{source_line}"
        there = f"{previous.source_file}:{previous.source_line}"
        return (
            f"{here}: warning: redefining '{name}' "
            f"(first defined at {there})"
        )
