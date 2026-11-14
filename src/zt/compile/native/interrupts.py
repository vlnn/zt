"""
Native IM 2 shim. Replaces the threaded shim/thread/exit trio: saves the foreground
registers, CALLs the installed handler xt like any other colon word, restores and returns.
"""
from __future__ import annotations

from zt.assemble.asm import Asm

INTERRUPT_PRIMITIVES = ("im2-handler!", "im2-handler@", "im2-off")
SAVED_REGISTERS = ("af", "hl", "bc", "de", "ix", "iy")


def create_native_im2_shim(a: Asm) -> None:
    a.label("__im2_shim__")
    for register in SAVED_REGISTERS:
        getattr(a, f"push_{register}")()
    a.ld_hl_ind_nn("__im2_thread__")
    a.call("__im2_call__")
    for register in reversed(SAVED_REGISTERS):
        getattr(a, f"pop_{register}")()
    a.ei()
    a.reti()
    a.label("__im2_call__")
    a.jp_hl()
    a.label("__im2_thread__")
    a.word(0)
