\ lib/plot_native.fs — single-pixel plot as a :::-assembler primitive.
\
\ Same stack effect as plot.fs's `plot`, but ~10× faster.  The address
\ math reuses the canonical Spectrum-screen idiom from
\ src/zt/assemble/sprite_primitives.py (_emit_screen_addr_from_y_x);
\ the bit-mask compute is a `$80 → A; rrca×(x&7)` djnz loop.
\
\ Calling convention (see docs/asm-words.md):
\   on entry:  HL = y (TOS), x is on the parameter stack below
\   on exit:   neither x nor y on stack; HL = new TOS

::: plot ( x y -- )
    ld_a_l   ld_d_a                       \ D = y
    pop_hl   ld_a_l   ld_e_a              \ E = x

    \ high byte of screen address → H ──────────────────────────
    ld_a_d   7 and_n   ld_h_a             \ H = low3(y)
    ld_a_d   192 and_n                    \ A = top2(y) at bits 6-7
    rrca rrca rrca                        \ A = top2 at bits 3-4
    or_h   64 or_n                        \ + low3 + $40 ($4000 base)
    ld_h_a

    \ low byte of screen address → L ───────────────────────────
    ld_a_d   56 and_n                     \ A = mid3(y) at bits 3-5
    rlca rlca                             \ A = mid3 at bits 5-7
    ld_l_a
    ld_a_e   248 and_n                    \ A = x & 0xF8
    rrca rrca rrca                        \ A = x >> 3
    or_l   ld_l_a                         \ HL = screen byte address

    \ bit mask = $80 >> (x & 7) ────────────────────────────────
    ld_a_e   7 and_n   ld_b_a             \ B = x & 7
    128 ld_a_n                            \ A = $80 (mask seed)
    inc_b                                 \ B + 1: djnz pre-decrements
    jr cmp
    label mloop   rrca
    label cmp     djnz mloop              \ A = $80 >> (x & 7)

    \ OR mask into screen byte ─────────────────────────────────
    ld_b_a                                \ B = mask
    ld_a_ind_hl   or_b   ld_ind_hl_a

    pop_hl ;                              \ refresh TOS
