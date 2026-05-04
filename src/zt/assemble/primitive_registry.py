"""
Decorator-based registration for Forth primitive creator functions. `@primitive` appends to `PRIMITIVES` in definition order, preserving the layout the image emitter and simulator iterate over.
"""
from __future__ import annotations

from collections.abc import Callable

from zt.assemble.asm import Asm

Creator = Callable[[Asm], None]
PRIMITIVES: list[Creator] = []


def primitive(fn: Creator) -> Creator:
    PRIMITIVES.append(fn)
    return fn
