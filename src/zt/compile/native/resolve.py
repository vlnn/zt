"""
Classifies what a `PrimRef` turns into under the native backend: data-word pushes, the
handful of constructs the code generator owns, an inlined body or an out-of-line call.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from zt.compile.dictionary import Dictionary
from zt.compile.ir import Cell, ColonRef, PrimRef
from zt.compile.native.primitives import NativePrimitive


class PrimKind(Enum):
    VARIABLE = "variable"
    CONSTANT = "constant"
    EXIT = "exit"
    STRING_PUSH = "lit"
    HALT = "halt"
    EXECUTE = "execute"
    INLINE = "inline"
    OUT_OF_LINE = "out-of-line"


OWNED_BY_CODEGEN = {
    "exit": PrimKind.EXIT,
    "lit": PrimKind.STRING_PUSH,
    "halt": PrimKind.HALT,
    "execute": PrimKind.EXECUTE,
}
DATA_WORD_KINDS = {"variable": PrimKind.VARIABLE, "constant": PrimKind.CONSTANT}
CALLING_KINDS = frozenset({PrimKind.OUT_OF_LINE, PrimKind.EXECUTE})


@dataclass(frozen=True)
class Resolver:
    words: Dictionary
    primitives: Mapping[str, NativePrimitive]

    def word(self, name: str) -> Any | None:
        try:
            return self.words.definition(name)
        except KeyError:
            return None

    def kind(self, name: str) -> PrimKind:
        word = self.word(name)
        if word is not None and word.kind in DATA_WORD_KINDS:
            return DATA_WORD_KINDS[word.kind]
        if name.lower() in OWNED_BY_CODEGEN:
            return OWNED_BY_CODEGEN[name.lower()]
        return PrimKind.INLINE if self.primitive(name).inlines else PrimKind.OUT_OF_LINE

    def primitive(self, name: str) -> NativePrimitive:
        prim = self.primitives.get(name) or self.primitives.get(name.lower())
        if prim is None:
            raise NotImplementedError(
                f"word {name!r} has no native code generator"
            )
        if prim.uses_ix:
            raise NotImplementedError(
                f"primitive {name!r} uses IX, which the native backend reserves "
                f"as its link register"
            )
        return prim

    def makes_call(self, cell: Cell) -> bool:
        if isinstance(cell, ColonRef):
            return True
        return isinstance(cell, PrimRef) and self.kind(cell.name) in CALLING_KINDS
