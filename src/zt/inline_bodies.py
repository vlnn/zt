"""
Primitive-body inliner. Decides which primitives (`INLINABLE_PRIMITIVES`) and colon definitions are safe to splice into their callers, and emits the raw Z80 bytes for a resolved inline plan.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from zt.asm import Asm
from zt.ir import Cell, Literal as LiteralCell, PrimRef


CREATE_PREFIX = "create_"
JP_OPCODE = 0xC3
DISPATCH_TAIL_LEN = 3
_JP_TO_NEXT = bytes([JP_OPCODE, 0x00, 0x00])
_DISPATCHER_NAME = "create_next"


INLINABLE_PRIMITIVES: frozenset[str] = frozenset({
    "dup", "drop", "swap", "over", "nip", "rot", "tuck",
    "2dup", "2drop",
    "plus", "minus",
    "one_plus", "one_minus", "two_star", "two_slash",
    "zero", "one",
    "negate",
    "and", "or", "xor", "invert",
    "fetch", "store", "c_fetch", "c_store", "plus_store", "dup_fetch",
    "border",
    "lshift",
    "equals",
})


@dataclass(frozen=True)
class InlineStep:
    kind: Literal["prim", "lit"]
    key: str = ""
    value: int = 0


@dataclass(frozen=True)
class InlineContext:
    registry: dict[str, bytes]
    name_to_key: dict[str, str]

    @classmethod
    def build(cls, creators: Sequence[Callable]) -> "InlineContext":
        registry = build_inline_registry(creators)
        name_to_key = _build_name_to_key_map(creators, registry)
        return cls(registry=registry, name_to_key=name_to_key)


def primitive_name(creator: Callable) -> str:
    return creator.__name__.removeprefix(CREATE_PREFIX)


def extract_inline_body(creator: Callable) -> bytes | None:
    if _is_dispatcher(creator):
        return None
    raw = _try_assemble(creator)
    if raw is None:
        return None
    if not _ends_with_jp_to_next(raw):
        return None
    return bytes(raw[:-DISPATCH_TAIL_LEN])


def build_inline_registry(
    creators: Sequence[Callable],
) -> dict[str, bytes]:
    registry: dict[str, bytes] = {}
    for creator in creators:
        body = extract_inline_body(creator)
        if body is None:
            continue
        registry[primitive_name(creator)] = body
    return registry


def is_primitive_inlinable(name: str) -> bool:
    return name in INLINABLE_PRIMITIVES


def has_mid_body_dispatch(creator: Callable) -> bool:
    if _is_dispatcher(creator):
        return False
    raw = _try_assemble(creator)
    if raw is None:
        return False
    if not _ends_with_jp_to_next(raw):
        return False
    body = raw[:-DISPATCH_TAIL_LEN]
    return _JP_TO_NEXT in body


def has_absolute_jump_in_body(creator: Callable) -> bool:
    if _is_dispatcher(creator):
        return False
    a = Asm(0x0000, inline_next=False)
    a.label("NEXT")
    try:
        creator(a)
        raw = a.resolve()
    except KeyError:
        return False
    if not _ends_with_jp_to_next(raw):
        return False
    body_end = len(raw) - DISPATCH_TAIL_LEN
    return any(offset < body_end for offset, _ in a.fixups)


def plan_colon_inlining(
    word: Any,
    words: dict[str, Any],
    context: InlineContext,
) -> list[InlineStep] | None:
    if getattr(word, "kind", None) != "colon":
        return None
    cells: list[Cell] = getattr(word, "body", None) or []
    if not cells or not _is_exit_cell(cells[-1]):
        return None
    return _plan_cells(cells[:-1], context)


def is_colon_inlinable(
    word: Any,
    words: dict[str, Any],
    context: InlineContext,
) -> bool:
    return plan_colon_inlining(word, words, context) is not None


def emit_inline_plan(
    asm: Asm,
    plan: list[InlineStep],
    context: InlineContext,
) -> None:
    for step in plan:
        if step.kind == "prim":
            asm.code.extend(context.registry[step.key])
        else:
            asm.push_hl()
            asm.ld_hl_nn(step.value & 0xFFFF)
    asm.dispatch()


def _is_exit_cell(cell: Cell) -> bool:
    return isinstance(cell, PrimRef) and cell.name == "exit"


def _plan_cells(
    cells: list[Cell],
    context: InlineContext,
) -> list[InlineStep] | None:
    steps: list[InlineStep] = []
    for cell in cells:
        step = _plan_cell(cell, context)
        if step is None:
            return None
        steps.append(step)
    return steps


def _plan_cell(cell: Cell, context: InlineContext) -> InlineStep | None:
    if isinstance(cell, LiteralCell):
        return InlineStep(kind="lit", value=cell.value)
    if isinstance(cell, PrimRef):
        key = context.name_to_key.get(cell.name.lower())
        if key is None or not is_primitive_inlinable(key):
            return None
        return InlineStep(kind="prim", key=key)
    return None


def _build_name_to_key_map(
    creators: Sequence[Callable],
    registry: dict[str, bytes],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for creator in creators:
        key = primitive_name(creator)
        if key not in registry:
            continue
        labels = _labels_of(creator)
        if labels is None:
            continue
        for label_name in labels:
            if label_name == "NEXT":
                continue
            result[label_name.lower()] = key
    return result


def _labels_of(creator: Callable) -> dict[str, int] | None:
    a = Asm(0x0000, inline_next=False)
    a.label("NEXT")
    creator(a)
    try:
        a.resolve()
    except KeyError:
        return None
    return dict(a.labels)


def _is_dispatcher(creator: Callable) -> bool:
    return creator.__name__ == _DISPATCHER_NAME


def _try_assemble(creator: Callable) -> bytes | None:
    a = Asm(0x0000, inline_next=False)
    a.label("NEXT")
    creator(a)
    try:
        return a.resolve()
    except KeyError:
        return None


def _ends_with_jp_to_next(raw: bytes) -> bool:
    if len(raw) < DISPATCH_TAIL_LEN:
        return False
    return raw[-DISPATCH_TAIL_LEN:] == _JP_TO_NEXT
