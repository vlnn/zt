"""
Decides what the native image contains before a byte is emitted: which colon bodies
survive call-site expansion, which words need an executable entry for their xt, and the
calling convention of every emitted word.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zt.compile.ir import Cell, PrimRef, WordLiteral
from zt.compile.liveness import Liveness
from zt.compile.native.analysis import (
    Convention,
    call_graph,
    choose_conventions,
    reachable_from,
    reentrant_words,
)
from zt.compile.native.expand import expand_small_leaves
from zt.compile.native.interrupts import INTERRUPT_PRIMITIVES
from zt.compile.native.labels import xt_wrapper_name
from zt.compile.native.primitives import native_primitive_table
from zt.compile.native.resolve import Resolver
from zt.compile.tree_shake import _reject_unsupported_features

if TYPE_CHECKING:
    from zt.compile.compiler import Compiler

ASM_WORD_REFERENCE = "__word__"


@dataclass(frozen=True)
class NativePlan:
    liveness: Liveness
    resolver: Resolver
    main: str
    bodies: dict[str, list[Cell]]
    conventions: dict[str, Convention]


def plan_native(compiler: Compiler) -> NativePlan:
    _reject_unsupported(compiler)
    liveness = compiler.compute_liveness()
    resolver = Resolver(
        words=compiler.words,
        primitives=native_primitive_table(compiler._primitives, compiler._asm_word_blobs),
    )
    main = compiler.words["main"].name
    raw = _live_colon_bodies(compiler, liveness)
    entries = _xt_entries(compiler, liveness, raw)
    raw.update(_xt_wrappers(entries, raw))
    bodies = _reachable(
        expand_small_leaves(raw, resolver.makes_call), [main, *entries],
    )
    interrupt_entries = entries if _uses_interrupts(liveness) else ()
    conventions = choose_conventions(
        bodies, resolver.makes_call, reentrant_words(bodies, interrupt_entries),
    )
    return NativePlan(liveness, resolver, main, bodies, conventions)


def _reject_unsupported(compiler: Compiler) -> None:
    if compiler.native_control_flow:
        raise NotImplementedError(
            "native_control_flow compiles straight to bytes and leaves no IR to rebuild from"
        )
    _reject_unsupported_features(compiler)


def _live_colon_bodies(compiler: Compiler, liveness: Liveness) -> dict[str, list[Cell]]:
    return {
        word.name: list(word.body)
        for word in compiler.words.values()
        if word.kind == "colon" and word.body and word.name in liveness.words
    }


def _xt_entries(
    compiler: Compiler, liveness: Liveness, bodies: Mapping[str, Sequence[Cell]],
) -> list[str]:
    targets = [
        *_ticked_in_bodies(bodies),
        *_ticked_in_data(compiler, liveness),
        *_called_from_asm_words(compiler, liveness),
    ]
    return list(dict.fromkeys(_entry_name(name, bodies) for name in targets))


def _ticked_in_bodies(bodies: Mapping[str, Sequence[Cell]]) -> Iterable[str]:
    return (
        cell.name for cells in bodies.values() for cell in cells
        if isinstance(cell, WordLiteral)
    )


def _ticked_in_data(compiler: Compiler, liveness: Liveness) -> Iterable[str]:
    return (
        ref.target for ref in compiler._word_address_refs
        if ref.owner in liveness.words
        and compiler.words.definition(ref.target).data_address is None
    )


def _called_from_asm_words(compiler: Compiler, liveness: Liveness) -> Iterable[str]:
    return (
        dep[len(ASM_WORD_REFERENCE):]
        for blob in compiler._asm_word_blobs
        if any(label in liveness.words for label in blob.label_offsets)
        for dep in blob.external_deps
        if dep.startswith(ASM_WORD_REFERENCE)
    )


def _entry_name(name: str, bodies: Mapping[str, Sequence[Cell]]) -> str:
    return name if name in bodies else xt_wrapper_name(name)


def _xt_wrappers(
    entries: Iterable[str], bodies: Mapping[str, Sequence[Cell]],
) -> dict[str, list[Cell]]:
    prefix = xt_wrapper_name("")
    return {
        entry: [PrimRef(entry[len(prefix):]), PrimRef("exit")]
        for entry in entries if entry not in bodies
    }


def _reachable(
    bodies: dict[str, list[Cell]], roots: Iterable[str],
) -> dict[str, list[Cell]]:
    wanted = reachable_from(call_graph(bodies), roots)
    return {name: cells for name, cells in bodies.items() if name in wanted}


def _uses_interrupts(liveness: Liveness) -> bool:
    return any(name in liveness.words for name in INTERRUPT_PRIMITIVES)
