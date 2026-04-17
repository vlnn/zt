from __future__ import annotations

from zt.asm import Asm
from zt.primitives import PRIMITIVES

SPECTRUM_ATTR_BASE = 0x5800


def create_start(a: Asm, data_stack_top: int, return_stack_top: int) -> None:
    a.label("START")
    a.ld_sp_nn(data_stack_top)
    a.ld_iy_nn(return_stack_top)
    a.ld_ix_nn("MAIN")
    a.jp("NEXT")


def create_demo_double(a: Asm) -> None:
    a.label("DOUBLE")
    a.call("DOCOL")
    a.word("DUP")
    a.word("PLUS")
    a.word("EXIT")


def create_demo_main(a: Asm) -> None:
    a.label("MAIN")
    a.word("LIT")
    a.word(0)
    a.label("LOOP")
    a.word("DUP")
    a.word("BORDER")
    a.word("DUP")
    a.word("LIT")
    a.word(SPECTRUM_ATTR_BASE)
    a.word("STORE")
    a.word("LIT")
    a.word(1)
    a.word("PLUS")
    a.word("BRANCH")
    a.word("LOOP")


def build_image(origin: int = 0x8000,
                data_stack_top: int = 0xFF00,
                return_stack_top: int = 0xFE00) -> bytes:
    a = Asm(origin)
    create_start(a, data_stack_top, return_stack_top)
    for creator in PRIMITIVES:
        creator(a)
    create_demo_double(a)
    create_demo_main(a)
    return a.resolve()
