\ lib/buffer.fs — 8-byte (one char cell) RAM back-buffer for one letter.
\
\ Buffer layout: 8 bytes, one per scanline.  rx, ry both in [0, 7]:
\   byte_offset = ry
\   bit_mask    = $80 >> rx
\
\ flush-letter does ONE BLIT8 instead of four — possible because voxel
\ positions are half-integer and project into a single 8-pixel column
\ regardless of rotation angle (see voxel.fs).
\
\ mask-table here so plot-buf and render.fs's render-letter can share it.

create letter-buf  8 allot

\ $80 >> i for i in 0..7.  Replaces the ~105 T/plot djnz-rotate inside
\ the inner col walk with a ~55 T/plot table fetch.
create mask-table  $80 c, $40 c, $20 c, $10 c, $08 c, $04 c, $02 c, $01 c,

::: clear-buffer  ( -- )
    push_hl
    xor_a
    ' letter-buf ld_hl_nn
    ld_ind_hl_a   inc_hl   ld_ind_hl_a   inc_hl
    ld_ind_hl_a   inc_hl   ld_ind_hl_a   inc_hl
    ld_ind_hl_a   inc_hl   ld_ind_hl_a   inc_hl
    ld_ind_hl_a   inc_hl   ld_ind_hl_a
    pop_hl ;

\ plot-buf — buffer-relative pixel plot, kept for tests and the
\ reference render path.  rx, ry both in [0, 7].
::: plot-buf  ( rx ry -- )
    ld_a_l   ld_d_a                       \ D = ry
    pop_hl   ld_a_l                        \ A = rx

    \ mask = mask-table[rx & 7]; stored in B for the OR step.
    \ No carry handling — see render.fs for the placement constraint.
    7 and_n   ld_b_a                       \ B = rx & 7
    ' mask-table ld_hl_nn
    ld_a_l   add_a_b   ld_l_a              \ HL = &mask-table[rx & 7]
    ld_a_ind_hl
    ld_b_a                                 \ B = mask

    \ HL = letter-buf + ry  (D = ry, clobbered by ld_de_nn but already consumed)
    ld_a_d   ld_l_a   0 ld_h_n
    ' letter-buf  ld_de_nn
    add_hl_de

    \ *HL |= mask
    ld_a_ind_hl   or_b   ld_ind_hl_a

    pop_hl ;

\ flush-letter — paint the 8-byte buffer onto a single char cell.
\ BLIT8 uses SP-stream so the caller must have interrupts disabled.
: flush-letter    ( cell-col cell-row -- )
    >r  letter-buf swap  r>  blit8 ;
