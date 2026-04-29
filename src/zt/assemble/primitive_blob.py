"""
Harvest the body bytes, labels and external dependencies of each primitive by running its `create_*` function into a throwaway `Asm`. The resulting `PrimitiveBlob` is the input to liveness-aware emission in `Compiler.build()`.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import MappingProxyType

from zt.assemble.asm import Asm

Creator = Callable[[Asm], None]


@dataclass(frozen=True, slots=True)
class PrimitiveBlob:
    label_offsets: MappingProxyType[str, int]
    code: bytes
    fixups: tuple[tuple[int, str], ...]
    rel_fixups: tuple[tuple[int, str], ...]
    external_deps: frozenset[str]


def harvest_primitive(creator: Creator, *, inline_next: bool = True) -> PrimitiveBlob:
    asm = Asm(origin=0, inline_next=inline_next)
    creator(asm)
    return _build_blob(asm)


def harvest_primitives(
    creators: Iterable[Creator], *, inline_next: bool = True,
) -> list[PrimitiveBlob]:
    return [harvest_primitive(c, inline_next=inline_next) for c in creators]


def emit_blob(asm: Asm, blob: PrimitiveBlob) -> None:
    base = len(asm.code)
    _bind_blob_labels(asm, blob, base)
    asm.code.extend(blob.code)
    asm.fixups.extend((base + offset, name) for offset, name in blob.fixups)
    asm.rel_fixups.extend((base + offset, name) for offset, name in blob.rel_fixups)


def _bind_blob_labels(asm: Asm, blob: PrimitiveBlob, base: int) -> None:
    for name in blob.label_offsets:
        if name in asm.labels:
            raise ValueError(f"duplicate label: {name}")
    for name, offset in blob.label_offsets.items():
        asm.labels[name] = asm.origin + base + offset


def primitive_dependency_graph(
    blobs: Iterable[PrimitiveBlob],
) -> dict[str, frozenset[str]]:
    graph: dict[str, frozenset[str]] = {}
    for blob in blobs:
        for label_name in blob.label_offsets:
            graph[label_name] = blob.external_deps
    return graph


_IMPLICIT_DEPS = frozenset({"NEXT"})


@dataclass(frozen=True, slots=True)
class BlobRegistry:
    blobs: tuple[PrimitiveBlob, ...]
    creators: tuple[Creator, ...]
    inline_next: bool

    @classmethod
    def from_creators(
        cls, creators: Iterable[Creator], *, inline_next: bool = True,
    ) -> BlobRegistry:
        creators_tuple = tuple(creators)
        blobs = tuple(harvest_primitives(creators_tuple, inline_next=inline_next))
        return cls(blobs=blobs, creators=creators_tuple, inline_next=inline_next)

    def by_label(self, name: str) -> PrimitiveBlob:
        for blob in self.blobs:
            if name in blob.label_offsets:
                return blob
        raise KeyError(name)

    def dependency_graph(self) -> dict[str, frozenset[str]]:
        return primitive_dependency_graph(self.blobs)

    def forth_visible_creators(self) -> dict[str, Creator]:
        result: dict[str, Creator] = {}
        for blob, creator in zip(self.blobs, self.creators):
            if not _is_standalone_resolvable(blob):
                continue
            for label_name in blob.label_offsets:
                if _is_forth_visible(label_name):
                    result[label_name.lower()] = creator
        return result


def _is_standalone_resolvable(blob: PrimitiveBlob) -> bool:
    return blob.external_deps <= _IMPLICIT_DEPS


def _is_forth_visible(label_name: str) -> bool:
    return label_name != "NEXT" and not label_name.startswith("_")


def _build_blob(asm: Asm) -> PrimitiveBlob:
    label_offsets = MappingProxyType(dict(asm.labels))
    fixups = tuple(asm.fixups)
    rel_fixups = tuple(asm.rel_fixups)
    return PrimitiveBlob(
        label_offsets=label_offsets,
        code=bytes(asm.code),
        fixups=fixups,
        rel_fixups=rel_fixups,
        external_deps=_external_deps(label_offsets, fixups, rel_fixups),
    )


def _external_deps(
    label_offsets: MappingProxyType[str, int],
    fixups: tuple[tuple[int, str], ...],
    rel_fixups: tuple[tuple[int, str], ...],
) -> frozenset[str]:
    referenced = {name for _, name in fixups}
    referenced.update(name for _, name in rel_fixups)
    return frozenset(referenced - set(label_offsets))
