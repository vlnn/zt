"""
Native view of the primitive set. Every primitive is re-harvested with linked dispatch
(`JP (IX)` in place of NEXT); small self-contained bodies are spliced at their call sites,
the rest are emitted once and called through the IX link register.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from zt.assemble.asm import Asm
from zt.assemble.primitive_blob import PrimitiveBlob, _build_blob
from zt.compile.native.interrupts import create_native_im2_shim

Creator = Callable[[Asm], None]

JP_IX = bytes((0xDD, 0xE9))
IX_PREFIX = 0xDD
INLINE_BYTE_LIMIT = 12
INLINE_REGARDLESS_OF_SIZE = frozenset({"(do)"})


@dataclass(frozen=True, slots=True)
class NativePrimitive:
    label: str
    blob: PrimitiveBlob
    creator: Creator | None
    inline_size: int | None
    uses_ix: bool

    @property
    def relocatable(self) -> bool:
        return self.inline_size is not None

    @property
    def inlines(self) -> bool:
        if self.inline_size is None:
            return False
        return self.inline_size <= INLINE_BYTE_LIMIT or self._always_inlined

    @property
    def _always_inlined(self) -> bool:
        return any(
            name.lower() in INLINE_REGARDLESS_OF_SIZE for name in self.blob.label_offsets
        )


def native_primitive_table(
    creators: Iterable[Creator], asm_word_blobs: Iterable[PrimitiveBlob],
) -> dict[str, NativePrimitive]:
    table: dict[str, NativePrimitive] = {}
    for creator in creators:
        _register(table, _harvest(creator))
    _register(table, _harvest(create_native_im2_shim), override=True)
    for blob in asm_word_blobs:
        _register(table, _from_asm_word(blob), override=True)
    return table


def splice_inline(prim: NativePrimitive, asm: Asm) -> None:
    if prim.creator is None or not prim.relocatable:
        raise ValueError(f"primitive {prim.label!r} cannot be inlined")
    scratch = Asm(origin=asm.here, linked=True)
    prim.creator(scratch)
    asm.code.extend(scratch.resolve()[:-len(JP_IX)])


def _register(
    table: dict[str, NativePrimitive], prim: NativePrimitive, *, override: bool = False,
) -> None:
    for label in prim.blob.label_offsets:
        entry = replace(prim, label=label)
        if override or label not in table:
            table[label] = entry
        table.setdefault(label.lower(), entry)


def _harvest(creator: Creator) -> NativePrimitive:
    asm = Asm(origin=0, linked=True)
    creator(asm)
    blob = _build_blob(asm)
    uses_ix = _touches_ix(blob.code)
    return NativePrimitive(
        label=next(iter(blob.label_offsets), creator.__name__),
        blob=blob,
        creator=creator,
        inline_size=_inline_size(asm, blob, uses_ix),
        uses_ix=uses_ix,
    )


def _inline_size(asm: Asm, blob: PrimitiveBlob, uses_ix: bool) -> int | None:
    single_tail = asm.dispatch_count == 1 and blob.code.endswith(JP_IX)
    if uses_ix or blob.external_deps or not single_tail:
        return None
    return len(blob.code) - len(JP_IX)


def _touches_ix(code: bytes) -> bool:
    return IX_PREFIX in code.replace(JP_IX, b"")


def _from_asm_word(blob: PrimitiveBlob) -> NativePrimitive:
    relinked = _relink(blob)
    return NativePrimitive(
        label=next(iter(relinked.label_offsets)),
        blob=relinked,
        creator=None,
        inline_size=None,
        uses_ix=_touches_ix(relinked.code),
    )


def _relink(blob: PrimitiveBlob) -> PrimitiveBlob:
    if blob.dispatch_tail == 0:
        raise NotImplementedError("::: word without a recorded dispatch tail")
    body_len = len(blob.code) - blob.dispatch_tail
    fixups = tuple(f for f in blob.fixups if f[0] < body_len)
    rel_fixups = tuple(f for f in blob.rel_fixups if f[0] < body_len)
    referenced = {name for _, name in fixups + rel_fixups}
    return PrimitiveBlob(
        label_offsets=blob.label_offsets,
        code=blob.code[:body_len] + JP_IX,
        fixups=fixups,
        rel_fixups=rel_fixups,
        external_deps=frozenset(referenced - set(blob.label_offsets)),
    )
