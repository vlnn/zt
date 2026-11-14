"""
Call-site expansion of small leaf colon words. A callee that is short, calls nothing and
exits only at its end is pasted into its callers with fresh branch labels, so the call
disappears altogether.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from itertools import count

from zt.compile.ir import Branch, Cell, ColonRef, Label, PrimRef
from zt.compile.native.analysis import is_leaf

SMALL_LEAF_CELL_LIMIT = 10


def expand_small_leaves(
    bodies: Mapping[str, Sequence[Cell]],
    makes_call: Callable[[Cell], bool],
    cell_limit: int = SMALL_LEAF_CELL_LIMIT,
) -> dict[str, list[Cell]]:
    fresh_ids = count(_highest_label_id(bodies) + 1)
    expanded: dict[str, list[Cell]] = {}
    for name, cells in bodies.items():
        expanded[name] = [
            out
            for cell in cells
            for out in _expand_cell(cell, name, expanded, makes_call, cell_limit, fresh_ids)
        ]
    return expanded


def _expand_cell(
    cell: Cell,
    caller: str,
    expanded: Mapping[str, list[Cell]],
    makes_call: Callable[[Cell], bool],
    cell_limit: int,
    fresh_ids: Iterator[int],
) -> list[Cell]:
    if not isinstance(cell, ColonRef) or cell.name == caller:
        return [cell]
    callee = expanded.get(cell.name)
    if callee is None or not _pastes(callee, makes_call, cell_limit):
        return [cell]
    return _with_fresh_labels(callee[:-1], fresh_ids)


def _pastes(
    cells: Sequence[Cell], makes_call: Callable[[Cell], bool], cell_limit: int,
) -> bool:
    return (
        len(cells) <= cell_limit
        and _exits_only_at_end(cells)
        and is_leaf(cells, makes_call)
    )


def _exits_only_at_end(cells: Sequence[Cell]) -> bool:
    exits = [i for i, cell in enumerate(cells) if _is_exit(cell)]
    return exits == [len(cells) - 1]


def _is_exit(cell: Cell) -> bool:
    return isinstance(cell, PrimRef) and cell.name.lower() == "exit"


def _with_fresh_labels(cells: Sequence[Cell], fresh_ids: Iterator[int]) -> list[Cell]:
    renamed: dict[int, Label] = {}

    def fresh(label: Label) -> Label:
        if label.id not in renamed:
            renamed[label.id] = Label(next(fresh_ids))
        return renamed[label.id]

    return [_relabel(cell, fresh) for cell in cells]


def _relabel(cell: Cell, fresh: Callable[[Label], Label]) -> Cell:
    if isinstance(cell, Label):
        return fresh(cell)
    if isinstance(cell, Branch):
        return Branch(cell.kind, fresh(cell.target))
    return cell


def _highest_label_id(bodies: Mapping[str, Sequence[Cell]]) -> int:
    return max(
        (cell.id for cells in bodies.values() for cell in cells if isinstance(cell, Label)),
        default=0,
    )
