from __future__ import annotations

from zt.asm import Asm

SPECTRUM_BORDER_PORT = 0xFE


# -- inner interpreter --

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
    a.alias("exit", "EXIT")
    a.ld_e_iy(0)
    a.ld_d_iy(1)
    a.inc_iy()
    a.inc_iy()
    a.push_de()
    a.pop_ix()
    a.jp("NEXT")


# -- stack operations --

def create_dup(a: Asm) -> None:
    a.label("DUP")
    a.alias("dup", "DUP")
    a.push_hl()
    a.jp("NEXT")


def create_drop(a: Asm) -> None:
    a.label("DROP")
    a.alias("drop", "DROP")
    a.pop_hl()
    a.jp("NEXT")


def create_swap(a: Asm) -> None:
    a.label("SWAP")
    a.alias("swap", "SWAP")
    a.ex_sp_hl()
    a.jp("NEXT")


def create_over(a: Asm) -> None:
    a.label("OVER")
    a.alias("over", "OVER")
    a.pop_de()
    a.push_de()
    a.push_hl()
    a.ex_de_hl()
    a.jp("NEXT")


def create_rot(a: Asm) -> None:
    a.label("ROT")
    a.alias("rot", "ROT")
    # ( a b c -- b c a )  TOS=c, SP: [a, b] (b on top)
    a.pop_de()       # DE=b
    a.pop_bc()       # BC=a
    a.push_de()      # push b
    a.push_hl()      # push c
    a.ld_h_b()
    a.ld_l_c()       # HL=a (new TOS)
    a.jp("NEXT")


def create_nip(a: Asm) -> None:
    a.label("NIP")
    a.alias("nip", "NIP")
    a.pop_de()
    a.jp("NEXT")


def create_tuck(a: Asm) -> None:
    a.label("TUCK")
    a.alias("tuck", "TUCK")
    # ( a b -- b a b )  TOS=b, SP: [a]
    a.pop_de()       # DE=a
    a.push_hl()      # push b
    a.push_de()      # push a
    a.jp("NEXT")     # TOS still b


def create_2dup(a: Asm) -> None:
    a.label("2DUP")
    a.alias("2dup", "2DUP")
    # ( a b -- a b a b )  TOS=b(HL), SP: [..., a]
    # Want: TOS=b(HL), SP: [..., a, b, a]
    a.pop_de()       # DE=a, SP: [...]
    a.push_de()      # SP: [..., a]
    a.push_hl()      # SP: [..., a, b]
    a.push_de()      # SP: [..., a, b, a]
    a.jp("NEXT")     # TOS=b still in HL


def create_2drop(a: Asm) -> None:
    a.label("2DROP")
    a.alias("2drop", "2DROP")
    a.pop_hl()
    a.pop_hl()
    a.jp("NEXT")


def create_2swap(a: Asm) -> None:
    a.label("2SWAP")
    a.alias("2swap", "2SWAP")
    # ( a b c d -- c d a b )  TOS=d(HL), SP: [a, b, c] (c on top)
    # Want: TOS=b(HL), SP: [c, d, a] (a on top)
    a.pop_de()       # DE=c, SP: [a, b]
    a.pop_bc()       # BC=b, SP: [a]
    a.push_de()      # push c, SP: [a, c]
    a.push_hl()      # push d, SP: [a, c, d]
    a.ld_h_b()
    a.ld_l_c()       # HL=b (new TOS)
    a.jp("NEXT")


def create_to_r(a: Asm) -> None:
    a.label(">R")
    a.alias(">r", ">R")
    a.dec_iy()
    a.dec_iy()
    a.ld_iy_l(0)
    a.ld_iy_h(1)
    a.pop_hl()
    a.jp("NEXT")


def create_r_from(a: Asm) -> None:
    a.label("R>")
    a.alias("r>", "R>")
    a.push_hl()
    a.ld_l_iy(0)
    a.ld_h_iy(1)
    a.inc_iy()
    a.inc_iy()
    a.jp("NEXT")


def create_r_fetch(a: Asm) -> None:
    a.label("R@")
    a.alias("r@", "R@")
    a.push_hl()
    a.ld_l_iy(0)
    a.ld_h_iy(1)
    a.jp("NEXT")


# -- arithmetic --

def create_plus(a: Asm) -> None:
    a.label("PLUS")
    a.alias("+", "PLUS")
    a.pop_de()
    a.add_hl_de()
    a.jp("NEXT")


def create_minus(a: Asm) -> None:
    a.label("MINUS")
    a.alias("-", "MINUS")
    a.pop_de()
    a.ex_de_hl()
    a.or_a()
    a.sbc_hl_de()
    a.jp("NEXT")


def create_one_plus(a: Asm) -> None:
    a.label("1+")
    a.inc_hl()
    a.jp("NEXT")


def create_one_minus(a: Asm) -> None:
    a.label("1-")
    a.dec_hl()
    a.jp("NEXT")


def create_two_star(a: Asm) -> None:
    a.label("2*")
    a.add_hl_hl()
    a.jp("NEXT")


def create_two_slash(a: Asm) -> None:
    a.label("2/")
    a.sra_h()
    a.rr_l()
    a.jp("NEXT")


def create_negate(a: Asm) -> None:
    a.label("NEGATE")
    a.alias("negate", "NEGATE")
    a.xor_a()
    a.sub_l()
    a.ld_l_a()
    a.sbc_a_a()
    a.sub_h()
    a.ld_h_a()
    a.jp("NEXT")


def create_abs(a: Asm) -> None:
    a.label("ABS")
    a.alias("abs", "ABS")
    a.bit_7_h()
    a.jp_z("_abs_done")
    a.xor_a()
    a.sub_l()
    a.ld_l_a()
    a.sbc_a_a()
    a.sub_h()
    a.ld_h_a()
    a.label("_abs_done")
    a.jp("NEXT")


def create_min(a: Asm) -> None:
    a.label("MIN")
    a.alias("min", "MIN")
    # ( a b -- min )  unsigned MIN for now
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.add_hl_de()
    a.jr_c_to("_min_done")
    a.ex_de_hl()
    a.label("_min_done")
    a.jp("NEXT")


def create_max(a: Asm) -> None:
    a.label("MAX")
    a.alias("max", "MAX")
    # ( a b -- max )  unsigned MAX for now
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.add_hl_de()
    a.jr_nc_to("_max_done")
    a.ex_de_hl()
    a.label("_max_done")
    a.jp("NEXT")


# -- logic and comparison --

def create_and(a: Asm) -> None:
    a.label("AND")
    a.alias("and", "AND")
    a.pop_de()
    a.ld_a_h()
    a.and_d()
    a.ld_h_a()
    a.ld_a_l()
    a.and_e()
    a.ld_l_a()
    a.jp("NEXT")


def create_or(a: Asm) -> None:
    a.label("OR")
    a.alias("or", "OR")
    a.pop_de()
    a.ld_a_h()
    a.or_d()
    a.ld_h_a()
    a.ld_a_l()
    a.or_e()
    a.ld_l_a()
    a.jp("NEXT")


def create_xor(a: Asm) -> None:
    a.label("XOR")
    a.alias("xor", "XOR")
    a.pop_de()
    a.ld_a_h()
    a.xor_d()
    a.ld_h_a()
    a.ld_a_l()
    a.xor_e()
    a.ld_l_a()
    a.jp("NEXT")


def create_invert(a: Asm) -> None:
    a.label("INVERT")
    a.alias("invert", "INVERT")
    a.ld_a_h()
    a.cpl()
    a.ld_h_a()
    a.ld_a_l()
    a.cpl()
    a.ld_l_a()
    a.jp("NEXT")


def create_lshift(a: Asm) -> None:
    a.label("LSHIFT")
    a.alias("lshift", "LSHIFT")
    # ( a n -- a<<n )  TOS=n, stack has a
    a.pop_de()        # DE=a
    a.ld_a_l()        # A=n (shift count)
    a.ex_de_hl()      # HL=a
    a.or_a()
    a.jr_z_to("_lshift_done")
    a.label("_lshift_loop")
    a.add_hl_hl()
    a.dec_a()
    a.jr_nz_to("_lshift_loop")
    a.label("_lshift_done")
    a.jp("NEXT")


def create_rshift(a: Asm) -> None:
    a.label("RSHIFT")
    a.alias("rshift", "RSHIFT")
    # ( a n -- a>>n )  TOS=n, stack has a
    a.pop_de()        # DE=a
    a.ld_a_l()        # A=n (shift count)
    a.ex_de_hl()      # HL=a
    a.or_a()
    a.jr_z_to("_rshift_done")
    a.label("_rshift_loop")
    a.srl_h()
    a.rr_l()
    a.dec_a()
    a.jr_nz_to("_rshift_loop")
    a.label("_rshift_done")
    a.jp("NEXT")


def create_equals(a: Asm) -> None:
    a.label("EQUALS")
    a.alias("=", "EQUALS")
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.ld_hl_nn(0)
    a.jr_nz_to("_eq_done")
    a.dec_hl()
    a.label("_eq_done")
    a.jp("NEXT")


def create_not_equals(a: Asm) -> None:
    a.label("NOT_EQUALS")
    a.alias("<>", "NOT_EQUALS")
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.ld_hl_nn(0)
    a.jr_z_to("_neq_done")
    a.dec_hl()
    a.label("_neq_done")
    a.jp("NEXT")


def create_less_than(a: Asm) -> None:
    a.label("LESS_THAN")
    a.alias("<", "LESS_THAN")
    # ( a b -- flag )  true if a < b (signed)
    # TOS=b(HL), SP has a
    a.pop_de()       # DE=a
    a.ex_de_hl()     # HL=a, DE=b
    a.or_a()
    a.sbc_hl_de()    # HL=a-b, sign flag set if a<b (no overflow)
    a.ld_hl_nn(0)
    a.jp_p("_lt_done")
    a.dec_hl()
    a.label("_lt_done")
    a.jp("NEXT")


def create_greater_than(a: Asm) -> None:
    a.label("GREATER_THAN")
    a.alias(">", "GREATER_THAN")
    # ( a b -- flag )  true if a > b (signed)
    # TOS=b(HL), SP has a -> compute b-a
    a.pop_de()       # DE=a
    a.or_a()
    a.sbc_hl_de()    # HL=b-a
    a.ld_hl_nn(0)
    a.jp_p("_gt_done")
    a.dec_hl()
    a.label("_gt_done")
    a.jp("NEXT")


def create_zero_equals(a: Asm) -> None:
    a.label("ZERO_EQUALS")
    a.alias("0=", "ZERO_EQUALS")
    a.ld_a_h()
    a.or_l()
    a.ld_hl_nn(0)
    a.jr_nz_to("_zeq_done")
    a.dec_hl()
    a.label("_zeq_done")
    a.jp("NEXT")


def create_zero_less(a: Asm) -> None:
    a.label("ZERO_LESS")
    a.alias("0<", "ZERO_LESS")
    a.bit_7_h()
    a.ld_hl_nn(0)
    a.jr_z_to("_zlt_done")
    a.dec_hl()
    a.label("_zlt_done")
    a.jp("NEXT")


def create_u_less(a: Asm) -> None:
    a.label("U_LESS")
    a.alias("u<", "U_LESS")
    # ( a b -- flag )  true if a < b (unsigned)
    a.pop_de()       # DE=a
    a.ex_de_hl()     # HL=a, DE=b
    a.or_a()
    a.sbc_hl_de()    # carry set if a < b
    a.ld_hl_nn(0)
    a.jr_nc_to("_ult_done")
    a.dec_hl()
    a.label("_ult_done")
    a.jp("NEXT")


# -- memory --

def create_fetch(a: Asm) -> None:
    a.label("FETCH")
    a.alias("@", "FETCH")
    a.ld_e_ind_hl()
    a.inc_hl()
    a.ld_d_ind_hl()
    a.ex_de_hl()
    a.jp("NEXT")


def create_store(a: Asm) -> None:
    a.label("STORE")
    a.alias("!", "STORE")
    a.pop_de()
    a.ld_ind_hl_e()
    a.inc_hl()
    a.ld_ind_hl_d()
    a.pop_hl()
    a.jp("NEXT")


def create_c_fetch(a: Asm) -> None:
    a.label("C_FETCH")
    a.alias("c@", "C_FETCH")
    a.ld_l_ind_hl()
    a.ld_h_n(0)
    a.jp("NEXT")


def create_c_store(a: Asm) -> None:
    a.label("C_STORE")
    a.alias("c!", "C_STORE")
    a.pop_de()
    a.ld_ind_hl_e()
    a.pop_hl()
    a.jp("NEXT")


def create_plus_store(a: Asm) -> None:
    a.label("PLUS_STORE")
    a.alias("+!", "PLUS_STORE")
    # ( n addr -- )  TOS=addr, stack has n
    a.pop_de()        # DE=n
    a.ld_a_ind_hl()
    a.add_a_e()
    a.ld_ind_hl_a()
    a.inc_hl()
    a.ld_a_ind_hl()
    a.adc_a_d()
    a.ld_ind_hl_a()
    a.pop_hl()
    a.jp("NEXT")


def create_cmove(a: Asm) -> None:
    a.label("CMOVE")
    a.alias("cmove", "CMOVE")
    # ( src dst count -- )  TOS=count, stack: dst, src
    a.ld_b_h()
    a.ld_c_l()       # BC=count
    a.pop_de()        # DE=dst
    a.pop_hl()        # HL=src
    a.ld_a_b()
    a.or_c()
    a.jr_z_to("_cmove_skip")
    a.ldir()
    a.label("_cmove_skip")
    a.pop_hl()
    a.jp("NEXT")


def create_fill(a: Asm) -> None:
    a.label("FILL")
    a.alias("fill", "FILL")
    # ( addr count byte -- )  TOS=byte, stack: count, addr
    a.ld_a_l()        # A=byte
    a.pop_bc()         # BC=count
    a.pop_hl()         # HL=addr
    a.ld_ind_hl_a()
    a.ld_d_h()
    a.ld_e_l()
    a.inc_de()         # DE=addr+1
    a.dec_bc()         # BC=count-1
    a.ld_a_b()
    a.or_c()
    a.jr_z_to("_fill_skip")
    a.ldir()
    a.label("_fill_skip")
    a.pop_hl()
    a.jp("NEXT")


# -- threading and literals --

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
    a.alias("border", "BORDER")
    a.ld_a_l()
    a.out_n_a(SPECTRUM_BORDER_PORT)
    a.pop_hl()
    a.jp("NEXT")


PRIMITIVES = [
    create_next, create_docol, create_exit,
    create_dup, create_drop, create_swap, create_over,
    create_rot, create_nip, create_tuck,
    create_2dup, create_2drop, create_2swap,
    create_to_r, create_r_from, create_r_fetch,
    create_plus, create_minus,
    create_one_plus, create_one_minus,
    create_two_star, create_two_slash,
    create_negate, create_abs,
    create_min, create_max,
    create_and, create_or, create_xor, create_invert,
    create_lshift, create_rshift,
    create_equals, create_not_equals,
    create_less_than, create_greater_than,
    create_zero_equals, create_zero_less,
    create_u_less,
    create_fetch, create_store,
    create_c_fetch, create_c_store,
    create_plus_store,
    create_cmove, create_fill,
    create_lit, create_branch, create_halt, create_border,
]
