"""
Whole-program analysis for the native backend: the colon call graph, which words can be
re-entered while they are still active, and the calling convention each word can afford.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from enum import Enum

from zt.compile.ir import Cell, ColonRef, PrimRef

Bodies = Mapping[str, Sequence[Cell]]
CallGraph = dict[str, frozenset[str]]


class Convention(Enum):
    LEAF = "leaf"
    STATIC = "static"
    FRAME = "frame"


def choose_conventions(
    bodies: Bodies,
    makes_call: Callable[[Cell], bool],
    reentrant: frozenset[str],
) -> dict[str, Convention]:
    return {
        name: _convention_for(name, cells, makes_call, reentrant)
        for name, cells in bodies.items()
    }


def reentrant_words(
    bodies: Bodies, interrupt_entries: Iterable[str] = (),
) -> frozenset[str]:
    graph = call_graph(bodies)
    executors = {name for name, cells in bodies.items() if _executes(cells)}
    unsafe = {name for name in bodies if _can_reenter(name, graph, executors)}
    for entry in interrupt_entries:
        if entry in graph:
            unsafe |= reachable_from(graph, [entry])
    return frozenset(unsafe)


def call_graph(bodies: Bodies) -> CallGraph:
    return {
        name: frozenset(
            cell.name for cell in cells
            if isinstance(cell, ColonRef) and cell.name in bodies
        )
        for name, cells in bodies.items()
    }


def reachable_from(graph: CallGraph, roots: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(graph.get(name, ()))
    return seen


def is_leaf(cells: Sequence[Cell], makes_call: Callable[[Cell], bool]) -> bool:
    return not any(makes_call(cell) for cell in cells)


def _convention_for(
    name: str,
    cells: Sequence[Cell],
    makes_call: Callable[[Cell], bool],
    reentrant: frozenset[str],
) -> Convention:
    if is_leaf(cells, makes_call):
        return Convention.LEAF
    if name in reentrant:
        return Convention.FRAME
    return Convention.STATIC


def _can_reenter(name: str, graph: CallGraph, executors: set[str]) -> bool:
    callees = reachable_from(graph, graph[name])
    return name in callees or bool((callees | {name}) & executors)


def _executes(cells: Sequence[Cell]) -> bool:
    return any(
        isinstance(cell, PrimRef) and cell.name.lower() == "execute" for cell in cells
    )
