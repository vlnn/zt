"""
`Dictionary`: the compiler's symbol table (name → `Word`), wrapping a plain dict with the lookup / registration API the compiler uses.

Every definition has its own identity (`Word.name`). Looking a source name up returns its
latest definition; a redefinition that shadows a word IR may still refer to is stored
under a fresh identity, and the shadowed one stays reachable through `definition()`.
"""
from __future__ import annotations

from itertools import count
from typing import TYPE_CHECKING, Iterator

from zt.assemble.asm import Asm

if TYPE_CHECKING:
    from zt.compile.compiler import Word


SHADOW_SEPARATOR = "@"


def _is_compile_time_only(word: "Word") -> bool:
    return word.immediate and word.compile_action is not None


class Dictionary:

    def __init__(self) -> None:
        self._words: dict[str, "Word"] = {}
        self._latest: dict[str, str] = {}

    def __len__(self) -> int:
        return len(self._words)

    def __contains__(self, name: str) -> bool:
        return self._identity(name) in self._words

    def __getitem__(self, name: str) -> "Word":
        return self._words[self._identity(name)]

    def __setitem__(self, name: str, word: "Word") -> None:
        self._words[name] = word

    def __delitem__(self, name: str) -> None:
        del self._words[name]
        self._latest = {
            source: identity for source, identity in self._latest.items()
            if identity != name
        }

    def __iter__(self) -> Iterator[str]:
        return iter(self._words)

    def register(self, word: "Word") -> None:
        self._words[word.name] = word

    def define(self, word: "Word") -> None:
        source_name = word.name
        shadowed = self.get(source_name)
        if shadowed is None or _is_compile_time_only(shadowed):
            self._words[self._identity(source_name)] = word
            return
        word.name = self._fresh_identity(source_name)
        self._words[word.name] = word
        self._latest[source_name] = word.name

    def definition(self, identity: str) -> "Word":
        return self._words[identity]

    def get(self, name: str, default: "Word | None" = None) -> "Word | None":
        return self._words.get(self._identity(name), default)

    def _identity(self, name: str) -> str:
        return self._latest.get(name, name)

    def _fresh_identity(self, source_name: str) -> str:
        candidates = (f"{source_name}{SHADOW_SEPARATOR}{n}" for n in count(1))
        return next(c for c in candidates if c not in self._words)

    def items(self):
        return self._words.items()

    def values(self):
        return self._words.values()

    def keys(self):
        return self._words.keys()

    def register_primitives(self, asm: Asm) -> None:
        from zt.compile.compiler import Word
        for name, addr in asm.labels.items():
            if name.startswith("_"):
                continue
            lower = name.lower()
            if lower in self._words:
                continue
            self._words[lower] = Word(name=lower, address=addr, kind="prim")

    def redefinition_warning(
        self, name: str, source_file: str, source_line: int,
        *, force_inline: bool = False,
    ) -> str | None:
        previous = self.get(name)
        if previous is None or previous.kind != "colon":
            return None
        if previous.source_file is None or previous.source_line is None:
            return None
        here = f"{source_file}:{source_line}"
        there = f"{previous.source_file}:{previous.source_line}"
        prev_kind = "::" if getattr(previous, "force_inline", False) else ":"
        new_kind = "::" if force_inline else ":"
        if prev_kind == new_kind:
            return (
                f"{here}: warning: redefining '{name}' "
                f"(first defined at {there})"
            )
        return (
            f"{here}: warning: redefining '{name}' as {new_kind} "
            f"(was {prev_kind} at {there})"
        )
