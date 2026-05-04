"""
Hand-written Z80 bodies for the SP-stream sprite primitives:
LOCK-SPRITES, UNLOCK-SPRITES, BLIT8, BLIT8C, BLIT8X, BLIT8XC, MULTI-BLIT.

All blit primitives assume interrupts are already disabled (the SP register is
redirected to walk the source data, so an ISR firing during a blit would push
its return address onto the source stream and corrupt it). Callers wrap a
batch of blits between LOCK-SPRITES and UNLOCK-SPRITES.

`create_sprite_scratch` reserves the shared 9-byte workspace used by the blit
bodies. It is registered alongside the primitives so the scratch labels are
defined for fixup resolution.
"""
from __future__ import annotations

from zt.assemble.asm import Asm
from zt.assemble.primitive_registry import primitive


@primitive
def create_lock_sprites(a: Asm) -> None:
    """`LOCK-SPRITES ( -- )` — disable interrupts before a batch of sprite blits."""
    a.label("LOCK_SPRITES")
    a.alias("lock-sprites", "LOCK_SPRITES")
    a.di()
    a.dispatch()


@primitive
def create_unlock_sprites(a: Asm) -> None:
    """`UNLOCK-SPRITES ( -- )` — re-enable interrupts after sprite blits."""
    a.label("UNLOCK_SPRITES")
    a.alias("unlock-sprites", "UNLOCK_SPRITES")
    a.ei()
    a.dispatch()


def _emit_next_scanline(a: Asm, done_label: str) -> None:
    a.inc_h()
    a.ld_a_h()
    a.and_n(7)
    a.jr_nz_to(done_label)
    a.ld_a_l()
    a.add_a_n(0x20)
    a.ld_l_a()
    a.jr_c_to(done_label)
    a.ld_a_h()
    a.sub_n(8)
    a.ld_h_a()
    a.label(done_label)


def _emit_screen_addr_from_y_x(a: Asm) -> None:
    """Compute screen address from (_spr_y) and E=x into HL."""
    a.ld_a_ind_nn("_spr_y")
    a.ld_d_a()
    a.and_n(7)
    a.ld_h_a()
    a.ld_a_d()
    a.and_n(0xC0)
    a.rrca()
    a.rrca()
    a.rrca()
    a.or_h()
    a.or_n(0x40)
    a.ld_h_a()
    a.ld_a_d()
    a.and_n(0x38)
    a.rlca()
    a.rlca()
    a.ld_l_a()
    a.ld_a_e()
    a.and_n(0xF8)
    a.rrca()
    a.rrca()
    a.rrca()
    a.or_l()
    a.ld_l_a()


@primitive
def create_blit8(a: Asm) -> None:
    """`BLIT8 ( src col row -- )` — char-aligned BW 8x8 blit via SP-stream.

    `src` points to 8 raw bytes (row 0 first). Caller must DI/LOCK-SPRITES first.
    """
    a.label("BLIT8")
    a.alias("blit8", "BLIT8")
    a.ld_a_l()
    a.pop_hl()
    a.ld_e_l()
    a.pop_hl()
    a.ld_ind_nn_sp("_spr_sp")
    a.ld_sp_hl()
    a.ld_d_a()
    a.and_n(0x18)
    a.or_n(0x40)
    a.ld_h_a()
    a.ld_a_d()
    a.and_n(7)
    a.rrca()
    a.rrca()
    a.rrca()
    a.or_e()
    a.ld_l_a()
    for _ in range(3):
        a.pop_bc()
        a.ld_ind_hl_c()
        a.inc_h()
        a.ld_ind_hl_b()
        a.inc_h()
    a.pop_bc()
    a.ld_ind_hl_c()
    a.inc_h()
    a.ld_ind_hl_b()
    a.ld_sp_ind_nn("_spr_sp")
    a.pop_hl()
    a.dispatch()


@primitive
def create_blit8c(a: Asm) -> None:
    """`BLIT8C ( src attr col row -- )` — char-aligned colored 8x8 blit.

    Writes 8 source bytes via SP-stream and one attr byte. Caller must DI first.
    """
    a.label("BLIT8C")
    a.alias("blit8c", "BLIT8C")
    a.ld_a_l()
    a.pop_hl()
    a.ld_e_l()
    a.pop_hl()
    a.ld_c_l()
    a.pop_hl()
    a.ld_ind_nn_sp("_spr_sp")
    a.ld_sp_hl()
    a.ld_d_a()
    a.and_n(0x18)
    a.rrca()
    a.rrca()
    a.rrca()
    a.or_n(0x58)
    a.ld_h_a()
    a.ld_a_d()
    a.and_n(7)
    a.rrca()
    a.rrca()
    a.rrca()
    a.or_e()
    a.ld_l_a()
    a.ld_ind_hl_c()
    a.ld_a_d()
    a.and_n(0x18)
    a.or_n(0x40)
    a.ld_h_a()
    for _ in range(3):
        a.pop_bc()
        a.ld_ind_hl_c()
        a.inc_h()
        a.ld_ind_hl_b()
        a.inc_h()
    a.pop_bc()
    a.ld_ind_hl_c()
    a.inc_h()
    a.ld_ind_hl_b()
    a.ld_sp_ind_nn("_spr_sp")
    a.pop_hl()
    a.dispatch()


def _emit_blit8x_body(a: Asm, label_prefix: str) -> None:
    """Emit 8 rows × (pop bc; ld (hl),c; inc l; ld (hl),b; dec l) with next-scanline between."""
    for row in range(7):
        a.pop_bc()
        a.ld_ind_hl_c()
        a.inc_l()
        a.ld_ind_hl_b()
        a.dec_l()
        _emit_next_scanline(a, f"{label_prefix}_r{row + 1}")
    a.pop_bc()
    a.ld_ind_hl_c()
    a.inc_l()
    a.ld_ind_hl_b()


@primitive
def create_blit8x(a: Asm) -> None:
    """`BLIT8X ( shifted x y -- )` — pixel-aligned BW 8x8 blit, pre-shifted source.

    `shifted` points to 128 bytes laid out as 8 shifts × 16 bytes; each shift
    holds 8 row pairs (left col byte, right col byte). Caller must DI first.
    """
    a.label("BLIT8X")
    a.alias("blit8x", "BLIT8X")
    a.ld_a_l()
    a.ld_ind_nn_a("_spr_y")
    a.pop_hl()
    a.ld_e_l()
    a.pop_hl()
    a.ld_a_e()
    a.and_n(7)
    a.rlca()
    a.rlca()
    a.rlca()
    a.rlca()
    a.ld_c_a()
    a.ld_b_n(0)
    a.add_hl_bc()
    a.ld_ind_nn_sp("_spr_sp")
    a.ld_sp_hl()
    _emit_screen_addr_from_y_x(a)
    _emit_blit8x_body(a, "_blit8x")
    a.ld_sp_ind_nn("_spr_sp")
    a.pop_hl()
    a.dispatch()


def _emit_attr_addr_for_xc(a: Asm, dst_label: str) -> None:
    """Compute attr addr for (_spr_y), E=x into HL."""
    a.ld_a_ind_nn("_spr_y")
    a.ld_d_a()
    a.and_n(0xC0)
    a.rlca()
    a.rlca()
    a.or_n(0x58)
    a.ld_h_a()
    a.ld_a_d()
    a.and_n(0x38)
    a.rlca()
    a.rlca()
    a.ld_l_a()
    a.ld_a_e()
    a.and_n(0xF8)
    a.rrca()
    a.rrca()
    a.rrca()
    a.or_l()
    a.ld_l_a()


@primitive
def create_blit8xc(a: Asm) -> None:
    """`BLIT8XC ( shifted attr x y -- )` — pixel-aligned colored 8x8 blit.

    Paints up to 4 attr cells covering the 2x2 char-cell footprint of the sprite.
    Caller must DI first.
    """
    a.label("BLIT8XC")
    a.alias("blit8xc", "BLIT8XC")
    a.ld_a_l()
    a.ld_ind_nn_a("_spr_y")
    a.pop_hl()
    a.ld_e_l()
    a.pop_hl()
    a.ld_a_l()
    a.ld_ind_nn_a("_spr_attr")
    a.pop_hl()
    a.ld_a_e()
    a.and_n(7)
    a.rlca()
    a.rlca()
    a.rlca()
    a.rlca()
    a.ld_c_a()
    a.ld_b_n(0)
    a.add_hl_bc()
    a.ld_ind_nn_sp("_spr_sp")
    a.ld_sp_hl()
    _emit_attr_addr_for_xc(a, "_blit8xc")
    a.ld_a_ind_nn("_spr_attr")
    a.ld_c_a()
    a.ld_ind_hl_c()
    a.ld_a_e()
    a.and_n(7)
    a.jr_z_to("_blit8xc_no_xshift_top")
    a.inc_l()
    a.ld_ind_hl_c()
    a.dec_l()
    a.label("_blit8xc_no_xshift_top")
    a.ld_a_ind_nn("_spr_y")
    a.and_n(7)
    a.jr_z_to("_blit8xc_no_yshift")
    a.ld_a_l()
    a.add_a_n(0x20)
    a.ld_l_a()
    a.jr_nc_to("_blit8xc_yshift_no_band")
    a.ld_a_h()
    a.add_a_n(1)
    a.ld_h_a()
    a.label("_blit8xc_yshift_no_band")
    a.ld_ind_hl_c()
    a.ld_a_e()
    a.and_n(7)
    a.jr_z_to("_blit8xc_no_yshift")
    a.inc_l()
    a.ld_ind_hl_c()
    a.label("_blit8xc_no_yshift")
    _emit_screen_addr_from_y_x(a)
    _emit_blit8x_body(a, "_blit8xc")
    a.ld_sp_ind_nn("_spr_sp")
    a.pop_hl()
    a.dispatch()


@primitive
def create_multi_blit(a: Asm) -> None:
    """`MULTI-BLIT ( table x y -- )` — composite sprite from a table of triples.

    Table layout: 1-byte count, then `count` quadruples of (dx i8, dy i8, sprite_lo, sprite_hi).
    Each component is rendered via the BLIT8X core at (x+dx, y+dy). Caller must DI first.
    """
    a.label("MULTI_BLIT")
    a.alias("multi-blit", "MULTI_BLIT")
    a.ld_a_l()
    a.ld_ind_nn_a("_spr_y")
    a.pop_hl()
    a.ld_a_l()
    a.ld_ind_nn_a("_spr_x")
    a.pop_hl()
    a.ld_a_ind_hl()
    a.ld_ind_nn_a("_spr_count")
    a.inc_hl()
    a.ld_ind_nn_hl("_spr_table_ptr")
    a.label("_multi_blit_loop")
    a.ld_a_ind_nn("_spr_count")
    a.or_a()
    a.jp_z("_multi_blit_done")
    a.dec_a()
    a.ld_ind_nn_a("_spr_count")
    a.ld_hl_ind_nn("_spr_table_ptr")
    a.ld_a_ind_hl()
    a.ld_e_a()
    a.ld_a_ind_nn("_spr_x")
    a.add_a_e()
    a.ld_e_a()
    a.inc_hl()
    a.ld_a_ind_hl()
    a.ld_b_a()
    a.ld_a_ind_nn("_spr_y")
    a.add_a_b()
    a.ld_ind_nn_a("_spr_target_y")
    a.inc_hl()
    a.ld_c_ind_hl()
    a.inc_hl()
    a.ld_b_ind_hl()
    a.inc_hl()
    a.ld_ind_nn_hl("_spr_table_ptr")
    a.ld_h_b()
    a.ld_l_c()
    a.ld_a_e()
    a.and_n(7)
    a.rlca()
    a.rlca()
    a.rlca()
    a.rlca()
    a.ld_c_a()
    a.ld_b_n(0)
    a.add_hl_bc()
    a.ld_ind_nn_sp("_spr_sp")
    a.ld_sp_hl()
    a.ld_a_ind_nn("_spr_target_y")
    a.ld_ind_nn_a("_spr_y")
    _emit_screen_addr_from_y_x(a)
    _emit_blit8x_body(a, "_multi_blit")
    a.ld_sp_ind_nn("_spr_sp")
    a.jp("_multi_blit_loop")
    a.label("_multi_blit_done")
    a.pop_hl()
    a.dispatch()


@primitive
def create_sprite_scratch(a: Asm) -> None:
    """Reserve 1- and 2-byte scratch slots used by sprite primitives."""
    a.label("_spr_sp")
    a.byte(0)
    a.byte(0)
    a.label("_spr_y")
    a.byte(0)
    a.label("_spr_x")
    a.byte(0)
    a.label("_spr_attr")
    a.byte(0)
    a.label("_spr_count")
    a.byte(0)
    a.label("_spr_target_y")
    a.byte(0)
    a.label("_spr_table_ptr")
    a.byte(0)
    a.byte(0)
