"""
Reachability analysis over the IR. `compute_liveness` walks colon bodies and the primitive dependency graph from a set of root names and returns the live word and string-pool sets used by the tree-shaking pass in `build()`.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from zt.compile.ir import Branch, Cell, ColonRef, Label, Literal, PrimRef, StringRef, WordLiteral


@dataclass(frozen=True, slots=True)
class Liveness:
    words: frozenset[str]
    strings: frozenset[str]


def compute_liveness(
    roots: Iterable[str],
    bodies: Mapping[str, Sequence[Cell]],
    prim_deps: Mapping[str, Iterable[str]],
    data_refs: Mapping[str, Iterable[str]] | None = None,
) -> Liveness:
    refs = data_refs or {}
    words: set[str] = set()
    strings: set[str] = set()
    worklist: list[str] = list(roots)
    while worklist:
        name = worklist.pop()
        if name in words:
            continue
        words.add(name)
        worklist.extend(_dependencies_of(name, bodies, prim_deps, refs, strings))
    return Liveness(words=frozenset(words), strings=frozenset(strings))


def _dependencies_of(
    name: str,
    bodies: Mapping[str, Sequence[Cell]],
    prim_deps: Mapping[str, Iterable[str]],
    data_refs: Mapping[str, Iterable[str]],
    strings: set[str],
) -> Iterable[str]:
    deps: list[str] = []
    if name in bodies:
        deps.extend(_cells_dependencies(bodies[name], strings))
    if name in prim_deps:
        deps.extend(prim_deps[name])
    if name in data_refs:
        deps.extend(data_refs[name])
    return deps


def _cells_dependencies(
    cells: Sequence[Cell], strings: set[str],
) -> list[str]:
    deps: list[str] = []
    for cell in cells:
        _collect_cell_dependency(cell, deps, strings)
    return deps


def _collect_cell_dependency(
    cell: Cell, deps: list[str], strings: set[str],
) -> None:
    match cell:
        case PrimRef(name) | ColonRef(name):
            deps.append(name)
        case Literal():
            deps.append("lit")
        case WordLiteral(name):
            deps.append("lit")
            deps.append(name)
        case Branch(kind=kind):
            deps.append(kind)
        case StringRef(label):
            strings.add(label)
        case Label():
            pass
