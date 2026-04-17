from __future__ import annotations

from collections.abc import Callable, Sequence

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
})


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
