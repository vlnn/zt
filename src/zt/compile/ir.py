"""
Intermediate-representation cell types (`PrimRef`, `ColonRef`, `Literal`, `Label`, `Branch`, `StringRef`) plus `resolve()` which lowers a cell list to Z80 bytes and JSON round-trip helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class PrimRef:
    name: str


@dataclass(frozen=True)
class ColonRef:
    name: str


@dataclass(frozen=True)
class Literal:
    value: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 0xFFFF:
            raise ValueError(
                f"Literal value {self.value} is out of 16-bit unsigned range [0, 0xFFFF]"
            )


@dataclass(frozen=True)
class Label:
    id: int


@dataclass(frozen=True)
class Branch:
    kind: str
    target: Label

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("Branch kind must be a non-empty primitive name")


@dataclass(frozen=True)
class StringRef:
    label: str


Cell = Union[PrimRef, ColonRef, Literal, Label, Branch, StringRef]


def resolve(
    cells: list[Cell],
    word_addrs: dict[str, int],
    base_address: int = 0,
) -> bytes:
    label_addrs = _compute_label_addresses(cells, base_address)
    return b"".join(_emit(c, word_addrs, label_addrs) for c in cells)


def cell_size(cell: Cell) -> int:
    match cell:
        case Label():
            return 0
        case PrimRef() | ColonRef() | StringRef():
            return 2
        case Literal() | Branch():
            return 4
    raise TypeError(f"unknown cell type: {type(cell).__name__}")


def _compute_label_addresses(cells: list[Cell], base_address: int) -> dict[int, int]:
    addrs: dict[int, int] = {}
    offset = 0
    for cell in cells:
        if isinstance(cell, Label):
            if cell.id in addrs:
                raise ValueError(f"duplicate label definition: Label(id={cell.id})")
            addrs[cell.id] = base_address + offset
            continue
        offset += cell_size(cell)
    return addrs


def _emit(
    cell: Cell,
    word_addrs: dict[str, int],
    label_addrs: dict[int, int],
) -> bytes:
    match cell:
        case Label():
            return b""
        case PrimRef(name) | ColonRef(name):
            return _word16(_lookup_word(word_addrs, name))
        case StringRef(label):
            return _word16(_lookup_word(word_addrs, label))
        case Literal(value):
            return _word16(_lookup_word(word_addrs, "lit")) + _word16(value)
        case Branch(kind, target):
            target_addr = _lookup_label(target, label_addrs)
            return _word16(_lookup_word(word_addrs, kind)) + _word16(target_addr)
    raise TypeError(f"unknown cell type: {type(cell).__name__}")


def _lookup_word(word_addrs: dict[str, int], name: str) -> int:
    if name not in word_addrs:
        raise KeyError(f"unresolved word reference: {name!r}")
    return word_addrs[name]


def _lookup_label(label: Label, label_addrs: dict[int, int]) -> int:
    if label.id not in label_addrs:
        known = sorted(label_addrs) if label_addrs else "none"
        raise KeyError(
            f"unresolved label: Label(id={label.id}); defined labels: {known}"
        )
    return label_addrs[label.id]


def _word16(value: int) -> bytes:
    return bytes([value & 0xFF, (value >> 8) & 0xFF])


def cells_to_json(cells: list[Cell]) -> list[list]:
    return [_cell_to_json(c) for c in cells]


def cells_from_json(data: list[list]) -> list[Cell]:
    return [_cell_from_json(item) for item in data]


def _cell_to_json(cell: Cell) -> list:
    match cell:
        case PrimRef(name):
            return ["prim", name]
        case ColonRef(name):
            return ["colon", name]
        case Literal(value):
            return ["lit", value]
        case Label(id=label_id):
            return ["label", label_id]
        case Branch(kind, target):
            return ["branch", kind, target.id]
        case StringRef(label):
            return ["str", label]
    raise TypeError(f"unknown cell type: {type(cell).__name__}")


def _cell_from_json(item: list) -> Cell:
    tag = item[0]
    if tag == "prim":
        return PrimRef(name=item[1])
    if tag == "colon":
        return ColonRef(name=item[1])
    if tag == "lit":
        return Literal(value=item[1])
    if tag == "label":
        return Label(id=item[1])
    if tag == "branch":
        return Branch(kind=item[1], target=Label(id=item[2]))
    if tag == "str":
        return StringRef(label=item[1])
    raise ValueError(f"unknown cell tag: {tag!r}")
