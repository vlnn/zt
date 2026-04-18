from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from zt.asm import Asm


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
    a = Asm(0x0000)
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
    exit_addr = _addr_of("exit", words)
    lit_addr = _addr_of("lit", words)
    if exit_addr is None or lit_addr is None:
        return None
    body = getattr(word, "body", None) or []
    if not body or body[-1] != exit_addr:
        return None
    return _plan_cells(body[:-1], words, context, lit_addr)


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


def _plan_cells(
    cells: list,
    words: dict[str, Any],
    context: InlineContext,
    lit_addr: int,
) -> list[InlineStep] | None:
    steps: list[InlineStep] = []
    i = 0
    while i < len(cells):
        cell = cells[i]
        if not isinstance(cell, int):
            return None
        if cell == lit_addr:
            if i + 1 >= len(cells):
                return None
            value = cells[i + 1]
            if not isinstance(value, int):
                return None
            steps.append(InlineStep(kind="lit", value=value))
            i += 2
            continue
        key = _resolve_primitive_key(cell, words, context)
        if key is None:
            return None
        steps.append(InlineStep(kind="prim", key=key))
        i += 1
    return steps


def _resolve_primitive_key(
    addr: int,
    words: dict[str, Any],
    context: InlineContext,
) -> str | None:
    for name, w in words.items():
        if getattr(w, "address", None) != addr:
            continue
        if getattr(w, "kind", None) != "prim":
            continue
        key = context.name_to_key.get(name.lower())
        if key is None:
            continue
        if is_primitive_inlinable(key):
            return key
    return None


def _addr_of(name: str, words: dict[str, Any]) -> int | None:
    word = words.get(name)
    if word is None:
        return None
    return getattr(word, "address", None)


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
    a = Asm(0x0000)
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
    a = Asm(0x0000)
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
