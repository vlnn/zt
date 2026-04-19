"""
Hand-written Z80 bodies for all Forth primitives (`DUP`, `DROP`, `+`, `@`, `BRANCH`, `DO`, `KEY`, …). Each `create_*` function appends its primitive's code to an `Asm` and the registered set is exported as `PRIMITIVES`.
"""
from __future__ import annotations

from zt.assemble.asm import Asm

SPECTRUM_BORDER_PORT = 0xFE
SPECTRUM_KEYBOARD_PORT_LOW = 0xFE
EMIT_FONT_BASE_MINUS_0X100 = 0x3C00


def create_next(a: Asm) -> None:
    """Emit `NEXT` — the threaded-interpreter dispatcher targeted by every primitive tail."""
    a.label("NEXT")
    a.emit_next_body()


def create_docol(a: Asm) -> None:
    """Emit `DOCOL` — the runtime entry prologue for every colon definition."""
    a.label("DOCOL")
    a.ex_sp_ix()
    a.pop_de()
    a.dec_iy()
    a.dec_iy()
    a.ld_iy_e(0)
    a.ld_iy_d(1)
    a.dispatch()


def create_exit(a: Asm) -> None:
    """`EXIT ( -- )` — pop the return stack into IX and return to the caller's threaded context."""
    a.label("EXIT")
    a.alias("exit", "EXIT")
    a.ld_e_iy(0)
    a.ld_d_iy(1)
    a.inc_iy()
    a.inc_iy()
    a.push_de()
    a.pop_ix()
    a.dispatch()


def create_dup(a: Asm) -> None:
    """`DUP ( x -- x x )`"""
    a.label("DUP")
    a.alias("dup", "DUP")
    a.push_hl()
    a.dispatch()


def create_drop(a: Asm) -> None:
    """`DROP ( x -- )`"""
    a.label("DROP")
    a.alias("drop", "DROP")
    a.pop_hl()
    a.dispatch()


def create_swap(a: Asm) -> None:
    """`SWAP ( x1 x2 -- x2 x1 )`"""
    a.label("SWAP")
    a.alias("swap", "SWAP")
    a.ex_sp_hl()
    a.dispatch()


def create_over(a: Asm) -> None:
    """`OVER ( x1 x2 -- x1 x2 x1 )`"""
    a.label("OVER")
    a.alias("over", "OVER")
    a.pop_de()
    a.push_de()
    a.push_hl()
    a.ex_de_hl()
    a.dispatch()


def create_rot(a: Asm) -> None:
    """`ROT ( x1 x2 x3 -- x2 x3 x1 )`"""
    a.label("ROT")
    a.alias("rot", "ROT")
    a.pop_de()
    a.pop_bc()
    a.push_de()
    a.push_hl()
    a.ld_h_b()
    a.ld_l_c()
    a.dispatch()


def create_nip(a: Asm) -> None:
    """`NIP ( x1 x2 -- x2 )`"""
    a.label("NIP")
    a.alias("nip", "NIP")
    a.pop_de()
    a.dispatch()


def create_tuck(a: Asm) -> None:
    """`TUCK ( x1 x2 -- x2 x1 x2 )`"""
    a.label("TUCK")
    a.alias("tuck", "TUCK")
    a.pop_de()
    a.push_hl()
    a.push_de()
    a.dispatch()


def create_2dup(a: Asm) -> None:
    """`2DUP ( x1 x2 -- x1 x2 x1 x2 )`"""
    a.label("2DUP")
    a.alias("2dup", "2DUP")
    a.pop_de()
    a.push_de()
    a.push_hl()
    a.push_de()
    a.dispatch()


def create_2drop(a: Asm) -> None:
    """`2DROP ( x1 x2 -- )`"""
    a.label("2DROP")
    a.alias("2drop", "2DROP")
    a.pop_hl()
    a.pop_hl()
    a.dispatch()


def create_2swap(a: Asm) -> None:
    """`2SWAP ( x1 x2 x3 x4 -- x3 x4 x1 x2 )`"""
    a.label("2SWAP")
    a.alias("2swap", "2SWAP")
    a.ex_de_hl()
    a.pop_hl()
    a.pop_bc()
    a.ex_sp_hl()
    a.push_de()
    a.push_hl()
    a.ld_h_b()
    a.ld_l_c()
    a.dispatch()


def create_to_r(a: Asm) -> None:
    """`>R ( x -- ) ( R: -- x )` — move TOS to the return stack."""
    a.label(">R")
    a.alias(">r", ">R")
    a.dec_iy()
    a.dec_iy()
    a.ld_iy_l(0)
    a.ld_iy_h(1)
    a.pop_hl()
    a.dispatch()


def create_r_from(a: Asm) -> None:
    """`R> ( -- x ) ( R: x -- )` — pull TOS from the return stack."""
    a.label("R>")
    a.alias("r>", "R>")
    a.push_hl()
    a.ld_l_iy(0)
    a.ld_h_iy(1)
    a.inc_iy()
    a.inc_iy()
    a.dispatch()


def create_r_fetch(a: Asm) -> None:
    """`R@ ( -- x ) ( R: x -- x )` — copy the top of the return stack."""
    a.label("R@")
    a.alias("r@", "R@")
    a.push_hl()
    a.ld_l_iy(0)
    a.ld_h_iy(1)
    a.dispatch()


def create_plus(a: Asm) -> None:
    """`+ ( x1 x2 -- x1+x2 )`"""
    a.label("PLUS")
    a.alias("+", "PLUS")
    a.pop_de()
    a.add_hl_de()
    a.dispatch()


def create_minus(a: Asm) -> None:
    """`- ( x1 x2 -- x1-x2 )`"""
    a.label("MINUS")
    a.alias("-", "MINUS")
    a.pop_de()
    a.ex_de_hl()
    a.or_a()
    a.sbc_hl_de()
    a.dispatch()


def create_one_plus(a: Asm) -> None:
    """`1+ ( x -- x+1 )`"""
    a.label("1+")
    a.inc_hl()
    a.dispatch()


def create_one_minus(a: Asm) -> None:
    """`1- ( x -- x-1 )`"""
    a.label("1-")
    a.dec_hl()
    a.dispatch()


def create_two_star(a: Asm) -> None:
    """`2* ( x -- x*2 )`"""
    a.label("2*")
    a.add_hl_hl()
    a.dispatch()


def create_two_slash(a: Asm) -> None:
    """`2/ ( x -- x/2 )` — arithmetic shift right by one."""
    a.label("2/")
    a.sra_h()
    a.rr_l()
    a.dispatch()


def create_zero(a: Asm) -> None:
    """`ZERO ( -- 0 )`"""
    a.label("ZERO")
    a.alias("zero", "ZERO")
    a.push_hl()
    a.ld_hl_nn(0)
    a.dispatch()


def create_one(a: Asm) -> None:
    """`ONE ( -- 1 )`"""
    a.label("ONE")
    a.alias("one", "ONE")
    a.push_hl()
    a.ld_hl_nn(1)
    a.dispatch()


def create_negate(a: Asm) -> None:
    """`NEGATE ( x -- -x )` — two's-complement negation."""
    a.label("NEGATE")
    a.alias("negate", "NEGATE")
    a.xor_a()
    a.sub_l()
    a.ld_l_a()
    a.sbc_a_a()
    a.sub_h()
    a.ld_h_a()
    a.dispatch()


def create_abs(a: Asm) -> None:
    """`ABS ( x -- |x| )`"""
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
    a.dispatch()


def create_min(a: Asm) -> None:
    """`MIN ( x1 x2 -- min )` — signed minimum.

    Flags after `SBC HL,DE` reflect `x2 - x1`; `ADD HL,DE` restores HL to x2
    without touching S, so we can branch on S afterwards and keep the
    "16-bit subtract preserves sign when there is no overflow" behavior
    shared with `<` and `>`.
    """
    a.label("MIN")
    a.alias("min", "MIN")
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.add_hl_de()
    a.jp_m("_min_done")
    a.ex_de_hl()
    a.label("_min_done")
    a.dispatch()


def create_max(a: Asm) -> None:
    """`MAX ( x1 x2 -- max )` — signed maximum."""
    a.label("MAX")
    a.alias("max", "MAX")
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.add_hl_de()
    a.jp_p("_max_done")
    a.ex_de_hl()
    a.label("_max_done")
    a.dispatch()


def create_and(a: Asm) -> None:
    """`AND ( x1 x2 -- x1&x2 )` — bitwise AND."""
    a.label("AND")
    a.alias("and", "AND")
    a.pop_de()
    a.ld_a_h()
    a.and_d()
    a.ld_h_a()
    a.ld_a_l()
    a.and_e()
    a.ld_l_a()
    a.dispatch()


def create_or(a: Asm) -> None:
    """`OR ( x1 x2 -- x1|x2 )` — bitwise OR."""
    a.label("OR")
    a.alias("or", "OR")
    a.pop_de()
    a.ld_a_h()
    a.or_d()
    a.ld_h_a()
    a.ld_a_l()
    a.or_e()
    a.ld_l_a()
    a.dispatch()


def create_xor(a: Asm) -> None:
    """`XOR ( x1 x2 -- x1^x2 )` — bitwise exclusive-OR."""
    a.label("XOR")
    a.alias("xor", "XOR")
    a.pop_de()
    a.ld_a_h()
    a.xor_d()
    a.ld_h_a()
    a.ld_a_l()
    a.xor_e()
    a.ld_l_a()
    a.dispatch()


def create_invert(a: Asm) -> None:
    """`INVERT ( x -- ~x )` — bitwise one's complement."""
    a.label("INVERT")
    a.alias("invert", "INVERT")
    a.ld_a_h()
    a.cpl()
    a.ld_h_a()
    a.ld_a_l()
    a.cpl()
    a.ld_l_a()
    a.dispatch()


def create_lshift(a: Asm) -> None:
    """`LSHIFT ( x u -- x<<u )` — logical shift left by u bits."""
    a.label("LSHIFT")
    a.alias("lshift", "LSHIFT")
    a.pop_de()
    a.ld_a_l()
    a.ex_de_hl()
    a.or_a()
    a.jr_z_to("_lshift_done")
    a.label("_lshift_loop")
    a.add_hl_hl()
    a.dec_a()
    a.jr_nz_to("_lshift_loop")
    a.label("_lshift_done")
    a.dispatch()


def create_rshift(a: Asm) -> None:
    """`RSHIFT ( x u -- x>>u )` — logical shift right by u bits."""
    a.label("RSHIFT")
    a.alias("rshift", "RSHIFT")
    a.pop_de()
    a.ld_a_l()
    a.ex_de_hl()
    a.or_a()
    a.jr_z_to("_rshift_done")
    a.label("_rshift_loop")
    a.srl_h()
    a.rr_l()
    a.dec_a()
    a.jr_nz_to("_rshift_loop")
    a.label("_rshift_done")
    a.dispatch()


def create_equals(a: Asm) -> None:
    """`= ( x1 x2 -- flag )` — true (-1) if equal, false (0) otherwise."""
    a.label("EQUALS")
    a.alias("=", "EQUALS")
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.ld_hl_nn(0)
    a.jr_nz_to("_eq_done")
    a.dec_hl()
    a.label("_eq_done")
    a.dispatch()


def create_not_equals(a: Asm) -> None:
    """`<> ( x1 x2 -- flag )` — true if the two values differ."""
    a.label("NOT_EQUALS")
    a.alias("<>", "NOT_EQUALS")
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.ld_hl_nn(0)
    a.jr_z_to("_neq_done")
    a.dec_hl()
    a.label("_neq_done")
    a.dispatch()


def create_less_than(a: Asm) -> None:
    """`< ( x1 x2 -- flag )` — signed less-than."""
    a.label("LESS_THAN")
    a.alias("<", "LESS_THAN")
    a.pop_de()
    a.ex_de_hl()
    a.or_a()
    a.sbc_hl_de()
    a.ld_hl_nn(0)
    a.jp_p("_lt_done")
    a.dec_hl()
    a.label("_lt_done")
    a.dispatch()


def create_greater_than(a: Asm) -> None:
    """`> ( x1 x2 -- flag )` — signed greater-than."""
    a.label("GREATER_THAN")
    a.alias(">", "GREATER_THAN")
    a.pop_de()
    a.or_a()
    a.sbc_hl_de()
    a.ld_hl_nn(0)
    a.jp_p("_gt_done")
    a.dec_hl()
    a.label("_gt_done")
    a.dispatch()


def create_zero_equals(a: Asm) -> None:
    """`0= ( x -- flag )` — true if x is zero."""
    a.label("ZERO_EQUALS")
    a.alias("0=", "ZERO_EQUALS")
    a.ld_a_h()
    a.or_l()
    a.ld_hl_nn(0)
    a.jr_nz_to("_zeq_done")
    a.dec_hl()
    a.label("_zeq_done")
    a.dispatch()


def create_zero_less(a: Asm) -> None:
    """`0< ( x -- flag )` — true if x is negative."""
    a.label("ZERO_LESS")
    a.alias("0<", "ZERO_LESS")
    a.bit_7_h()
    a.ld_hl_nn(0)
    a.jr_z_to("_zlt_done")
    a.dec_hl()
    a.label("_zlt_done")
    a.dispatch()


def create_u_less(a: Asm) -> None:
    """`U< ( u1 u2 -- flag )` — unsigned less-than."""
    a.label("U_LESS")
    a.alias("u<", "U_LESS")
    a.pop_de()
    a.ex_de_hl()
    a.or_a()
    a.sbc_hl_de()
    a.ld_hl_nn(0)
    a.jr_nc_to("_ult_done")
    a.dec_hl()
    a.label("_ult_done")
    a.dispatch()


def create_fetch(a: Asm) -> None:
    """`@ ( addr -- x )` — read a 16-bit cell from memory."""
    a.label("FETCH")
    a.alias("@", "FETCH")
    a.ld_e_ind_hl()
    a.inc_hl()
    a.ld_d_ind_hl()
    a.ex_de_hl()
    a.dispatch()


def create_dup_fetch(a: Asm) -> None:
    """`DUP@ ( addr -- addr x )` — fused `dup` and `@`, a common idiom."""
    a.label("DUP_FETCH")
    a.alias("dup@", "DUP_FETCH")
    a.push_hl()
    a.ld_e_ind_hl()
    a.inc_hl()
    a.ld_d_ind_hl()
    a.ex_de_hl()
    a.dispatch()


def create_store(a: Asm) -> None:
    """`! ( x addr -- )` — write a 16-bit cell to memory."""
    a.label("STORE")
    a.alias("!", "STORE")
    a.pop_de()
    a.ld_ind_hl_e()
    a.inc_hl()
    a.ld_ind_hl_d()
    a.pop_hl()
    a.dispatch()


def create_c_fetch(a: Asm) -> None:
    """`C@ ( addr -- c )` — read a byte from memory, zero-extended to a cell."""
    a.label("C_FETCH")
    a.alias("c@", "C_FETCH")
    a.ld_l_ind_hl()
    a.ld_h_n(0)
    a.dispatch()


def create_c_store(a: Asm) -> None:
    """`C! ( c addr -- )` — write the low byte of c to memory."""
    a.label("C_STORE")
    a.alias("c!", "C_STORE")
    a.pop_de()
    a.ld_ind_hl_e()
    a.pop_hl()
    a.dispatch()


def create_plus_store(a: Asm) -> None:
    """`+! ( x addr -- )` — add x to the cell at addr."""
    a.label("PLUS_STORE")
    a.alias("+!", "PLUS_STORE")
    a.pop_de()
    a.ld_a_ind_hl()
    a.add_a_e()
    a.ld_ind_hl_a()
    a.inc_hl()
    a.ld_a_ind_hl()
    a.adc_a_d()
    a.ld_ind_hl_a()
    a.pop_hl()
    a.dispatch()


def create_cmove(a: Asm) -> None:
    """`CMOVE ( src dst n -- )` — copy n bytes from src to dst (low-to-high)."""
    a.label("CMOVE")
    a.alias("cmove", "CMOVE")
    a.ld_b_h()
    a.ld_c_l()
    a.pop_de()
    a.pop_hl()
    a.ld_a_b()
    a.or_c()
    a.jr_z_to("_cmove_skip")
    a.ldir()
    a.label("_cmove_skip")
    a.pop_hl()
    a.dispatch()


def create_fill(a: Asm) -> None:
    """`FILL ( addr n c -- )` — write byte c to n consecutive addresses starting at addr."""
    a.label("FILL")
    a.alias("fill", "FILL")
    a.ld_a_l()
    a.pop_bc()
    a.pop_hl()
    a.ld_ind_hl_a()
    a.ld_d_h()
    a.ld_e_l()
    a.inc_de()
    a.dec_bc()
    a.ld_a_b()
    a.or_c()
    a.jr_z_to("_fill_skip")
    a.ldir()
    a.label("_fill_skip")
    a.pop_hl()
    a.dispatch()


def create_lit(a: Asm) -> None:
    """`LIT` — push the 16-bit cell following the threaded IP and skip past it."""
    a.label("LIT")
    a.push_hl()
    a.ld_l_ix(0)
    a.ld_h_ix(1)
    a.inc_ix()
    a.inc_ix()
    a.dispatch()


def create_branch(a: Asm) -> None:
    """`BRANCH` — unconditional threaded jump, using the next inline cell as the target IP."""
    a.label("BRANCH")
    a.ld_e_ix(0)
    a.ld_d_ix(1)
    a.push_de()
    a.pop_ix()
    a.dispatch()


def create_zbranch(a: Asm) -> None:
    """`0BRANCH` — threaded jump taken when TOS is zero; falls through otherwise."""
    a.label("ZBRANCH")
    a.alias("0branch", "ZBRANCH")
    a.ld_a_h()
    a.or_l()
    a.pop_hl()
    a.jr_nz_to("_zbranch_skip")
    a.ld_e_ix(0)
    a.ld_d_ix(1)
    a.push_de()
    a.pop_ix()
    a.dispatch()
    a.label("_zbranch_skip")
    a.inc_ix()
    a.inc_ix()
    a.dispatch()


def create_do_rt(a: Asm) -> None:
    """Runtime for `DO` — move limit and index from the data stack onto the return stack."""
    a.label("DO_RT")
    a.alias("(do)", "DO_RT")
    a.pop_de()
    a.dec_iy()
    a.dec_iy()
    a.ld_iy_e(0)
    a.ld_iy_d(1)
    a.dec_iy()
    a.dec_iy()
    a.ld_iy_l(0)
    a.ld_iy_h(1)
    a.pop_hl()
    a.dispatch()


def create_loop_rt(a: Asm) -> None:
    """Runtime for `LOOP` — increment the index; branch back unless it has reached the limit."""
    a.label("LOOP_RT")
    a.alias("(loop)", "LOOP_RT")
    a.push_hl()
    a.ld_e_iy(0)
    a.ld_d_iy(1)
    a.inc_de()
    a.ld_iy_e(0)
    a.ld_iy_d(1)
    a.ld_l_iy(2)
    a.ld_h_iy(3)
    a.or_a()
    a.sbc_hl_de()
    a.pop_hl()
    a.jr_z_to("_loop_exit")
    a.ld_e_ix(0)
    a.ld_d_ix(1)
    a.push_de()
    a.pop_ix()
    a.dispatch()
    a.label("_loop_exit")
    a.inc_ix()
    a.inc_ix()
    a.inc_iy()
    a.inc_iy()
    a.inc_iy()
    a.inc_iy()
    a.dispatch()


def create_ploop_rt(a: Asm) -> None:
    """Runtime for `+LOOP` — add TOS to the index; branch back unless the limit has been crossed."""
    a.label("PLOOP_RT")
    a.alias("(+loop)", "PLOOP_RT")
    a.ld_e_iy(0)
    a.ld_d_iy(1)
    a.add_hl_de()
    a.ld_iy_l(0)
    a.ld_iy_h(1)
    a.push_hl()
    a.ld_l_iy(2)
    a.ld_h_iy(3)
    a.ex_de_hl()
    a.or_a()
    a.sbc_hl_de()
    a.ex_sp_hl()
    a.or_a()
    a.sbc_hl_de()
    a.pop_de()
    a.ld_a_h()
    a.xor_d()
    a.pop_hl()
    a.jp_m("_ploop_exit")
    a.ld_e_ix(0)
    a.ld_d_ix(1)
    a.push_de()
    a.pop_ix()
    a.dispatch()
    a.label("_ploop_exit")
    a.inc_ix()
    a.inc_ix()
    a.inc_iy()
    a.inc_iy()
    a.inc_iy()
    a.inc_iy()
    a.dispatch()


def create_i_index(a: Asm) -> None:
    """`I ( -- n )` — push the innermost loop's current index."""
    a.label("I_INDEX")
    a.alias("i", "I_INDEX")
    a.push_hl()
    a.ld_l_iy(0)
    a.ld_h_iy(1)
    a.dispatch()


def create_j_index(a: Asm) -> None:
    """`J ( -- n )` — push the next-outer loop's current index."""
    a.label("J_INDEX")
    a.alias("j", "J_INDEX")
    a.push_hl()
    a.ld_l_iy(4)
    a.ld_h_iy(5)
    a.dispatch()


def create_unloop(a: Asm) -> None:
    """`UNLOOP ( R: limit idx -- )` — discard the innermost loop frame from the return stack."""
    a.label("UNLOOP")
    a.alias("unloop", "UNLOOP")
    a.inc_iy()
    a.inc_iy()
    a.inc_iy()
    a.inc_iy()
    a.dispatch()


def create_halt(a: Asm) -> None:
    """`HALT` — emit a Z80 `halt` and fall through (no dispatch, execution stops)."""
    a.label("HALT")
    a.halt()


def create_border(a: Asm) -> None:
    """`BORDER ( n -- )` — set the Spectrum border colour via port 0xFE."""
    a.label("BORDER")
    a.alias("border", "BORDER")
    a.ld_a_l()
    a.out_n_a(SPECTRUM_BORDER_PORT)
    a.pop_hl()
    a.dispatch()

def _mul_step(a: Asm, skip_label: str) -> None:
    """Emit one shift-and-add iteration of the `MULTIPLY` loop."""
    a.add_hl_hl()
    a.sla_c()
    a.rl_b()
    a.jr_nc_to(skip_label)
    a.add_hl_de()
    a.label(skip_label)


def create_multiply(a: Asm) -> None:
    """`* ( x1 x2 -- x1*x2 )` — 16-bit by 16-bit multiply (full 16 shift-and-add rounds)."""
    a.label("MULTIPLY")
    a.alias("*", "MULTIPLY")
    a.pop_de()
    a.ld_b_h()
    a.ld_c_l()
    a.ld_hl_nn(0)
    for i in range(16):
        _mul_step(a, f"_mul_s{i}")
    a.dispatch()


def _emit_glyph_source(a: Asm) -> None:
    """Compute the glyph's source address in ROM font from the character code in A and leave it in DE."""
    a.ld_h_n(0)
    a.add_hl_hl()
    a.add_hl_hl()
    a.add_hl_hl()
    a.ld_bc_nn(EMIT_FONT_BASE_MINUS_0X100)
    a.add_hl_bc()
    a.ex_de_hl()


def _emit_screen_dest(a: Asm) -> None:
    """Compute the screen destination address for the current (row, col) cursor and leave it in HL."""
    a.ld_a_ind_nn("_emit_cursor_row")
    a.and_n(0x18)
    a.or_n(0x40)
    a.ld_h_a()
    a.ld_a_ind_nn("_emit_cursor_row")
    a.and_n(0x07)
    a.rrca()
    a.rrca()
    a.rrca()
    a.ld_b_a()
    a.ld_a_ind_nn("_emit_cursor_col")
    a.or_b()
    a.ld_l_a()


def _emit_copy_glyph(a: Asm) -> None:
    """Copy 8 glyph rows from (DE) into the 8 scan lines of the current cell at (HL)."""
    a.ld_b_n(8)
    a.label("_emit_copy")
    a.ld_a_ind_de()
    a.ld_ind_hl_a()
    a.inc_de()
    a.inc_h()
    a.djnz_to("_emit_copy")


def _emit_advance_cursor_core(a: Asm) -> None:
    """Advance the cursor one column; wrap to the next row on col==32 and to row 0 on row==24."""
    a.ld_a_ind_nn("_emit_cursor_col")
    a.inc_a()
    a.cp_n(32)
    a.jr_c_to("_emit_core_store_col")
    a.xor_a()
    a.ld_ind_nn_a("_emit_cursor_col")
    a.ld_a_ind_nn("_emit_cursor_row")
    a.inc_a()
    a.cp_n(24)
    a.jr_c_to("_emit_core_store_row")
    a.xor_a()
    a.label("_emit_core_store_row")
    a.ld_ind_nn_a("_emit_cursor_row")
    a.ret()
    a.label("_emit_core_store_col")
    a.ld_ind_nn_a("_emit_cursor_col")
    a.ret()


def _emit_cr_core_path(a: Asm) -> None:
    """Carriage-return path shared by EMIT: reset the column and advance the row with wrap."""
    a.label("_emit_cr_core")
    a.xor_a()
    a.ld_ind_nn_a("_emit_cursor_col")
    a.ld_a_ind_nn("_emit_cursor_row")
    a.inc_a()
    a.cp_n(24)
    a.jr_c_to("_emit_cr_core_store")
    a.xor_a()
    a.label("_emit_cr_core_store")
    a.ld_ind_nn_a("_emit_cursor_row")
    a.ret()


def create_emit(a: Asm) -> None:
    """`EMIT ( c -- )` — draw character c at the current cursor and advance; CR on c==13."""
    a.label("EMIT")
    a.alias("emit", "EMIT")
    a.ld_a_l()
    a.call("_emit_char_core")
    a.pop_hl()
    a.dispatch()

    a.label("_emit_char_core")
    a.ld_l_a()
    a.cp_n(13)
    a.jp_z("_emit_cr_core")
    _emit_glyph_source(a)
    _emit_screen_dest(a)
    _emit_copy_glyph(a)
    _emit_advance_cursor_core(a)
    _emit_cr_core_path(a)

    a.label("_emit_cursor_row")
    a.byte(0)
    a.label("_emit_cursor_col")
    a.byte(0)


def create_type(a: Asm) -> None:
    """`TYPE ( addr n -- )` — emit n characters from the byte string at addr."""
    a.label("TYPE")
    a.alias("type", "TYPE")
    a.pop_de()
    a.ld_a_l()
    a.or_h()
    a.jp_z("_type_done")
    a.ld_b_l()
    a.label("_type_loop")
    a.push_bc()
    a.push_de()
    a.ld_a_ind_de()
    a.call("_emit_char_core")
    a.pop_de()
    a.pop_bc()
    a.inc_de()
    a.djnz_to("_type_loop")
    a.label("_type_done")
    a.pop_hl()
    a.dispatch()


def create_key(a: Asm) -> None:
    """`KEY ( -- c )` — poll the Spectrum keyboard matrix and return one ASCII code (0 if no key)."""
    a.label("KEY")
    a.alias("key", "KEY")
    a.push_hl()
    a.ld_d_n(0)
    a.ld_e_n(0xFE)
    a.label("_key_row")
    a.ld_a_e()
    a.in_a_n(SPECTRUM_KEYBOARD_PORT_LOW)
    a.cpl()
    a.and_n(0x1F)
    a.jr_nz_to("_key_found")
    a.inc_d()
    a.ld_a_d()
    a.cp_n(8)
    a.jr_z_to("_key_none")
    a.rlc_e()
    a.jr_to("_key_row")
    a.label("_key_none")
    a.ld_hl_nn(0)
    a.jr_to("_key_exit")
    a.label("_key_found")
    a.ld_b_n(0)
    a.label("_key_bit")
    a.rrca()
    a.jr_c_to("_key_decode")
    a.inc_b()
    a.jr_to("_key_bit")
    a.label("_key_decode")
    a.ld_a_d()
    a.add_a_a()
    a.add_a_d()
    a.add_a_d()
    a.add_a_d()
    a.add_a_b()
    a.ld_e_a()
    a.ld_d_n(0)
    a.ld_hl_nn("_key_table")
    a.add_hl_de()
    a.ld_a_ind_hl()
    a.ld_l_a()
    a.ld_h_n(0)
    a.label("_key_exit")
    a.dispatch()
    a.label("_key_table")
    for byte in _SPECTRUM_KEY_TABLE:
        a.byte(byte)


def create_key_query(a: Asm) -> None:
    """`KEY? ( -- flag )` — true if any key on the full keyboard is currently pressed."""
    a.label("KEY_QUERY")
    a.alias("key?", "KEY_QUERY")
    a.push_hl()
    a.ld_a_n(0)
    a.in_a_n(SPECTRUM_KEYBOARD_PORT_LOW)
    a.cpl()
    a.and_n(0x1F)
    a.ld_hl_nn(0)
    a.jr_z_to("_kq_done")
    a.ld_hl_nn(0xFFFF)
    a.label("_kq_done")
    a.dispatch()


def create_key_state(a: Asm) -> None:
    """`KEY-STATE ( c -- flag )` — true if the key with ASCII code c is currently held down."""
    a.label("KEY_STATE")
    a.alias("key-state", "KEY_STATE")
    a.ld_a_l()
    a.ld_b_n(40)
    a.ld_hl_nn("_key_table")
    a.label("_ks_search")
    a.cp_ind_hl()
    a.jr_z_to("_ks_found")
    a.inc_hl()
    a.dec_b()
    a.jr_nz_to("_ks_search")
    a.ld_hl_nn(0)
    a.jr_to("_ks_exit")
    a.label("_ks_found")
    a.ld_a_n(40)
    a.sub_b()
    a.ld_b_n(0)
    a.label("_ks_div")
    a.cp_n(5)
    a.jr_c_to("_ks_div_done")
    a.sub_n(5)
    a.inc_b()
    a.jr_to("_ks_div")
    a.label("_ks_div_done")
    a.ld_c_a()
    a.ld_a_n(0xFE)
    a.label("_ks_rot")
    a.dec_b()
    a.jp_m("_ks_read")
    a.rlca()
    a.jr_to("_ks_rot")
    a.label("_ks_read")
    a.in_a_n(SPECTRUM_KEYBOARD_PORT_LOW)
    a.cpl()
    a.ld_b_c()
    a.label("_ks_shift")
    a.dec_b()
    a.jp_m("_ks_test")
    a.rrca()
    a.jr_to("_ks_shift")
    a.label("_ks_test")
    a.and_n(1)
    a.ld_hl_nn(0)
    a.jr_z_to("_ks_exit")
    a.ld_hl_nn(0xFFFF)
    a.label("_ks_exit")
    a.dispatch()


_SPECTRUM_KEY_TABLE: tuple[int, ...] = (
    0x00, 0x5A, 0x58, 0x43, 0x56,
    0x41, 0x53, 0x44, 0x46, 0x47,
    0x51, 0x57, 0x45, 0x52, 0x54,
    0x31, 0x32, 0x33, 0x34, 0x35,
    0x30, 0x39, 0x38, 0x37, 0x36,
    0x50, 0x4F, 0x49, 0x55, 0x59,
    0x0D, 0x4C, 0x4B, 0x4A, 0x48,
    0x20, 0x00, 0x4D, 0x4E, 0x42,
)


def create_u_mod_div(a: Asm) -> None:
    """`U/MOD ( u1 u2 -- rem quot )` — unsigned 16-bit division by restoring shift-subtract."""
    a.label("U_MOD_DIV")
    a.alias("u/mod", "U_MOD_DIV")
    a.pop_de()
    a.ex_de_hl()
    a.ld_bc_nn(0)
    a.ld_a_n(16)
    a.label("_umod_loop")
    a.add_hl_hl()
    a.rl_c()
    a.rl_b()
    a.push_hl()
    a.ld_h_b()
    a.ld_l_c()
    a.or_a()
    a.sbc_hl_de()
    a.jr_c_to("_umod_no_sub")
    a.ld_b_h()
    a.ld_c_l()
    a.pop_hl()
    a.inc_hl()
    a.jr_to("_umod_next")
    a.label("_umod_no_sub")
    a.pop_hl()
    a.label("_umod_next")
    a.dec_a()
    a.jr_nz_to("_umod_loop")
    a.ld_e_c()
    a.ld_d_b()
    a.push_de()
    a.dispatch()


def create_reset_cursor(a: Asm) -> None:
    """`RESET-CURSOR` — zero the EMIT cursor row and column."""
    a.label("RESET_CURSOR")
    a.alias("reset-cursor", "RESET_CURSOR")
    a.xor_a()
    a.ld_ind_nn_a("_emit_cursor_row")
    a.ld_ind_nn_a("_emit_cursor_col")
    a.dispatch()

def create_scroll_attr(a: Asm) -> None:
    """`SCROLL-ATTR ( dx dy -- )` — shift the Spectrum attribute page by (dx, dy) with row/column wrap."""
    a.label("SCROLL_ATTR")
    a.alias("scroll-attr", "SCROLL_ATTR")

    a.ld_de_nn(24)

    a.label("_sa_nd_neg")
    a.bit_7_h()
    a.jr_z_to("_sa_nd_neg_done")
    a.add_hl_de()
    a.jr_to("_sa_nd_neg")
    a.label("_sa_nd_neg_done")

    a.label("_sa_nd_pos")
    a.or_a()
    a.sbc_hl_de()
    a.jr_nc_to("_sa_nd_pos")
    a.add_hl_de()

    a.ld_a_l()
    a.ld_ind_nn_a("_sa_dy")

    a.pop_de()
    a.ld_a_e()
    a.and_n(31)
    a.ld_ind_nn_a("_sa_dx")
    a.ld_l_a()
    a.ld_a_n(32)
    a.sub_l()
    a.ld_ind_nn_a("_sa_kx")

    a.pop_hl()
    a.push_hl()

    a.ld_a_ind_nn("_sa_dx")
    a.or_a()
    a.jp_z("_sa_after_h")

    a.ld_a_n(24)
    a.ld_ind_nn_a("_sa_rows")
    a.ld_hl_nn(0x5800)

    a.label("_sa_h_row")
    a.push_hl()

    a.ld_de_nn("_sa_scratch")
    a.ld_a_ind_nn("_sa_dx")
    a.ld_c_a()
    a.ld_b_n(0)
    a.ldir()

    a.pop_de()
    a.push_de()
    a.ld_a_ind_nn("_sa_kx")
    a.ld_c_a()
    a.ld_b_n(0)
    a.ldir()

    a.ld_hl_nn("_sa_scratch")
    a.ld_a_ind_nn("_sa_dx")
    a.ld_c_a()
    a.ld_b_n(0)
    a.ldir()

    a.pop_hl()
    a.ld_de_nn(32)
    a.add_hl_de()

    a.ld_a_ind_nn("_sa_rows")
    a.dec_a()
    a.ld_ind_nn_a("_sa_rows")
    a.jp_nz("_sa_h_row")

    a.label("_sa_after_h")

    a.ld_a_ind_nn("_sa_dy")
    a.or_a()
    a.jp_z("_sa_done")

    a.cp_n(13)
    a.jr_nc_to("_sa_v_flip")

    a.label("_sa_v_up")
    a.ld_hl_nn(0x5800)
    a.ld_de_nn("_sa_scratch")
    a.ld_bc_nn(32)
    a.ldir()

    a.ld_hl_nn(0x5820)
    a.ld_de_nn(0x5800)
    a.ld_bc_nn(23 * 32)
    a.ldir()

    a.ld_hl_nn("_sa_scratch")
    a.ld_de_nn(0x5AE0)
    a.ld_bc_nn(32)
    a.ldir()

    a.ld_a_ind_nn("_sa_dy")
    a.dec_a()
    a.ld_ind_nn_a("_sa_dy")
    a.jp_nz("_sa_v_up")
    a.jp("_sa_done")

    a.label("_sa_v_flip")
    a.ld_l_a()
    a.ld_a_n(24)
    a.sub_l()
    a.ld_ind_nn_a("_sa_dy")

    a.label("_sa_v_down")
    a.ld_hl_nn(0x5AE0)
    a.ld_de_nn("_sa_scratch")
    a.ld_bc_nn(32)
    a.ldir()

    a.ld_a_n(23)
    a.ld_ind_nn_a("_sa_rows")
    a.ld_hl_nn(0x5AC0)
    a.ld_de_nn(0x5AE0)

    a.label("_sa_v_down_row")
    a.ld_bc_nn(32)
    a.ldir()
    a.ld_bc_nn(0xFFC0)
    a.add_hl_bc()
    a.ex_de_hl()
    a.add_hl_bc()
    a.ex_de_hl()
    a.ld_a_ind_nn("_sa_rows")
    a.dec_a()
    a.ld_ind_nn_a("_sa_rows")
    a.jp_nz("_sa_v_down_row")

    a.ld_hl_nn("_sa_scratch")
    a.ld_de_nn(0x5800)
    a.ld_bc_nn(32)
    a.ldir()

    a.ld_a_ind_nn("_sa_dy")
    a.dec_a()
    a.ld_ind_nn_a("_sa_dy")
    a.jp_nz("_sa_v_down")

    a.label("_sa_done")
    a.pop_hl()
    a.dispatch()

    a.label("_sa_dx")
    a.byte(0)
    a.label("_sa_dy")
    a.byte(0)
    a.label("_sa_kx")
    a.byte(0)
    a.label("_sa_rows")
    a.byte(0)
    a.label("_sa_scratch")
    for _ in range(32):
        a.byte(0)

def create_at_xy(a: Asm) -> None:
    """`AT-XY ( col row -- )` — move the EMIT cursor to (col, row)."""
    a.label("AT_XY")
    a.alias("at-xy", "AT_XY")
    a.ld_a_l()
    a.ld_ind_nn_a("_emit_cursor_row")
    a.pop_hl()
    a.ld_a_l()
    a.ld_ind_nn_a("_emit_cursor_col")
    a.pop_hl()
    a.dispatch()


def create_beep(a: Asm) -> None:
    """`BEEP ( cycles period -- )` — square-wave tone on port $FE bit 4.

    Toggles the speaker for `cycles` half-periods, each separated by a delay
    of `period` counts. Higher `period` = lower pitch. Border flickers to
    black during playback; restore it with `BORDER` after.
    """
    a.label("BEEP")
    a.alias("beep", "BEEP")
    a.pop_de()
    a.xor_a()
    a.ld_ind_nn_a("_beep_phase")
    a.label("_beep_outer")
    a.push_hl()
    a.push_de()
    a.ld_a_ind_nn("_beep_phase")
    a.ld_e_n(0x10)
    a.xor_e()
    a.ld_ind_nn_a("_beep_phase")
    a.out_n_a(SPECTRUM_BORDER_PORT)
    a.pop_de()
    a.pop_hl()
    a.push_hl()
    a.label("_beep_delay")
    a.dec_hl()
    a.ld_a_h()
    a.or_l()
    a.jr_nz_to("_beep_delay")
    a.pop_hl()
    a.dec_de()
    a.ld_a_d()
    a.or_e()
    a.jr_nz_to("_beep_outer")
    a.xor_a()
    a.out_n_a(SPECTRUM_BORDER_PORT)
    a.pop_hl()
    a.dispatch()
    a.label("_beep_phase")
    a.byte(0)


def create_wait_frame(a: Asm) -> None:
    """`WAIT-FRAME` — block until the Spectrum frame interrupt fires (one-frame vsync)."""
    a.label("WAIT_FRAME")
    a.alias("wait-frame", "WAIT_FRAME")
    a.push_iy()
    a.ld_iy_nn(0x5C3A)
    a.ei()
    a.halt()
    a.di()
    a.pop_iy()
    a.dispatch()

PRIMITIVES = [
    create_next, create_docol, create_exit,
    create_dup, create_drop, create_swap, create_over,
    create_rot, create_nip, create_tuck,
    create_2dup, create_2drop, create_2swap,
    create_to_r, create_r_from, create_r_fetch,
    create_plus, create_minus,
    create_one_plus, create_one_minus,
    create_two_star, create_two_slash,
    create_zero, create_one,
    create_negate, create_abs,
    create_min, create_max,
    create_and, create_or, create_xor, create_invert,
    create_lshift, create_rshift,
    create_equals, create_not_equals,
    create_less_than, create_greater_than,
    create_zero_equals, create_zero_less,
    create_u_less,
    create_fetch, create_store,
    create_dup_fetch,
    create_c_fetch, create_c_store,
    create_plus_store,
    create_cmove, create_fill,
    create_lit, create_branch, create_zbranch,
    create_do_rt, create_loop_rt, create_ploop_rt,
    create_i_index, create_j_index, create_unloop,
    create_halt, create_border,
    create_multiply,
    create_u_mod_div,
    create_emit,
    create_type,
    create_key,
    create_key_query,
    create_key_state,
    create_reset_cursor,
    create_scroll_attr,
    create_at_xy,
    create_beep,
    create_wait_frame,
]
