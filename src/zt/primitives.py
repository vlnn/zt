from __future__ import annotations

from zt.asm import Asm

SPECTRUM_BORDER_PORT = 0xFE


def create_next(a: Asm) -> None:
    a.label("NEXT")
    a.ld_e_ix(0)
    a.ld_d_ix(1)
    a.inc_ix()
    a.inc_ix()
    a.push_de()
    a.ret()


def create_docol(a: Asm) -> None:
    a.label("DOCOL")
    a.push_ix()
    a.pop_de()
    a.dec_iy()
    a.dec_iy()
    a.ld_iy_e(0)
    a.ld_iy_d(1)
    a.pop_ix()
    a.jp("NEXT")


def create_exit(a: Asm) -> None:
    a.label("EXIT")
    a.ld_e_iy(0)
    a.ld_d_iy(1)
    a.inc_iy()
    a.inc_iy()
    a.push_de()
    a.pop_ix()
    a.jp("NEXT")


def create_dup(a: Asm) -> None:
    a.label("DUP")
    a.push_hl()
    a.jp("NEXT")


def create_drop(a: Asm) -> None:
    a.label("DROP")
    a.pop_hl()
    a.jp("NEXT")


def create_swap(a: Asm) -> None:
    a.label("SWAP")
    a.ex_sp_hl()
    a.jp("NEXT")


def create_over(a: Asm) -> None:
    a.label("OVER")
    a.pop_de()
    a.push_de()
    a.push_hl()
    a.ex_de_hl()
    a.jp("NEXT")


def create_plus(a: Asm) -> None:
    a.label("PLUS")
    a.pop_de()
    a.add_hl_de()
    a.jp("NEXT")


def create_minus(a: Asm) -> None:
    a.label("MINUS")
    a.pop_de()
    a.ex_de_hl()
    a.or_a()
    a.sbc_hl_de()
    a.jp("NEXT")


def create_fetch(a: Asm) -> None:
    a.label("FETCH")
    a.ld_e_ind_hl()
    a.inc_hl()
    a.ld_d_ind_hl()
    a.ex_de_hl()
    a.jp("NEXT")


def create_store(a: Asm) -> None:
    a.label("STORE")
    a.pop_de()
    a.ld_ind_hl_e()
    a.inc_hl()
    a.ld_ind_hl_d()
    a.pop_hl()
    a.jp("NEXT")


def create_lit(a: Asm) -> None:
    a.label("LIT")
    a.push_hl()
    a.ld_l_ix(0)
    a.ld_h_ix(1)
    a.inc_ix()
    a.inc_ix()
    a.jp("NEXT")


def create_branch(a: Asm) -> None:
    a.label("BRANCH")
    a.ld_e_ix(0)
    a.ld_d_ix(1)
    a.push_de()
    a.pop_ix()
    a.jp("NEXT")


def create_halt(a: Asm) -> None:
    a.label("HALT")
    a.halt()


def create_border(a: Asm) -> None:
    a.label("BORDER")
    a.ld_a_l()
    a.out_n_a(SPECTRUM_BORDER_PORT)
    a.pop_hl()
    a.jp("NEXT")


PRIMITIVES = [
    create_next, create_docol, create_exit,
    create_dup, create_drop, create_swap, create_over,
    create_plus, create_minus,
    create_fetch, create_store,
    create_lit, create_branch, create_halt, create_border,
]
