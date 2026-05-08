\ lib/render.fs — render one rotated letter into the back-buffer.
\
\ The whole 8-row × 8-col walk is folded into one :::-Z80 primitive,
\ render-letter.  This eliminates the ~13 K T of Forth-level
\ row-loop dispatch we used to pay per letter (glyph fetch + do/loop +
\ render-row dispatch × 8 rows).
\
\ Per-frame pipeline:
\   1. bake-frame (Forth):  yaw, pitch -> step + base for each axis.
\   2. bake-coords (:::):   walk basis 8× per axis -> x-cache, y-cache.
\   3. render-letter (:::, this file): for each of 8 rows of the glyph,
\      look up ry from y-cache, then walk 8 cols with djnz, plotting
\      each lit bit into letter-buf via byte-offset arithmetic against
\      x-cache and a precomputed y_part.

require ../lib/voxel.fs
require ../lib/buffer.fs
require ../lib/coord_cache.fs

\ Per-row scratch slot: byte offset = ry directly (8-byte buffer is
\ one byte per row).
variable y-part

\ Glyph base address for the letter being rendered ($3D00 + (ch-32)·8).
\ Stashed in memory to free HL for the inner col walk.
variable glyph-ptr

\ Walk frame-base-x by frame-step-x writing 8 integer x's to x-cache,
\ same for y.  See voxel.fs for the basis definitions.
::: bake-coords  ( -- )
    push_hl
    ' frame-base-x  ld_hl_ind_nn
    ' x-cache       ld_de_nn
    8 ld_b_n
    label xloop
        ld_a_h
        ld_ind_de_a
        inc_de
        push_bc
        ' frame-step-x  ld_bc_ind_nn
        add_hl_bc
        pop_bc
        djnz xloop
    ' frame-base-y  ld_hl_ind_nn
    ' y-cache       ld_de_nn
    8 ld_b_n
    label yloop
        ld_a_h
        ld_ind_de_a
        inc_de
        push_bc
        ' frame-step-y  ld_bc_ind_nn
        add_hl_bc
        pop_bc
        djnz yloop
    pop_hl ;

\ render-letter ( ch -- )
\
\ Walks 8 rows × 8 cols of the glyph, plotting set bits into the
\ back-buffer.  Outer state (B = row counter, D = row index) is parked
\ on the data stack across the col walk.
\
\ Register usage during the col walk (matches the old render-row):
\   B = 8 col counter for djnz
\   C = font byte being shifted left
\   HL = walking pointer into x-cache
\   E = saved rx during plot
\   D = ry / scratch
\   A = scratch (mask, byte offset)
::: render-letter  ( ch -- )
    \ ── glyph_base = $3D00 + (ch − 32) · 8 ──────────────────────
    ld_a_l
    32 sub_n
    ld_l_a
    0 ld_h_n                     \ HL = ch − 32
    add_hl_hl                    \ × 2
    add_hl_hl                    \ × 4
    add_hl_hl                    \ × 8
    $3D00 ld_de_nn
    add_hl_de                    \ HL = glyph base
    ' glyph-ptr ld_ind_nn_hl

    \ ── outer loop: B = 8 (counter), D = 0 (current row) ─────────
    8 ld_b_n
    0 ld_d_n
    label rl-row
        \ Save outer state on data stack across the col walk
        push_bc
        push_de

        \ A = mem[glyph_base + D]
        ' glyph-ptr ld_hl_ind_nn
        ld_a_d
        ld_e_l
        add_a_e
        ld_l_a
        ld_a_h
        0 adc_a_n
        ld_h_a
        ld_a_ind_hl              \ A = font byte for this row
        ld_c_a                   \ C = font byte (for SLA C)

        \ ry = y-cache[D]
        ld_a_d
        ld_e_a
        0 ld_d_n                 \ DE = row index
        ' y-cache ld_hl_nn
        add_hl_de
        ld_a_ind_hl              \ A = ry (= byte offset for 8-byte buffer)
        ' y-part ld_ind_nn_a

        \ ── inner col loop: B = 8, HL = &x-cache[0] ──────────────
        8 ld_b_n
        ' x-cache ld_hl_nn
        label rl-col
            sla_c                \ shift font byte; bit 7 → CY
            jr_nc rl-skip

            \ plot path: A = rx
            ld_a_ind_hl
            push_hl              \ save x-cache ptr
            push_bc              \ save B (counter), C (font byte)

            \ ── mask via LUT: B = mask-table[rx & 7] ─────────────────
            \ Skip the high-byte carry handling: mask-table is currently
            \ placed with low byte 0x1b, and 0x1b + 7 = 0x22 never carries
            \ into the high byte.  test-far-corner-last-byte-last-bit
            \ catches any future placement that would break this.
            7 and_n              \ A = rx & 7
            ld_b_a               \ B = rx & 7
            ' mask-table ld_hl_nn
            ld_a_l
            add_a_b
            ld_l_a               \ HL = &mask-table[rx & 7]  (H unchanged)
            ld_a_ind_hl          \ A = mask
            ld_b_a               \ B = mask

            \ ── HL = &letter-buf[ry] (byte offset = ry, no quadrant) ─
            ' y-part ld_a_ind_nn
            ld_l_a   0 ld_h_n
            ' letter-buf ld_de_nn
            add_hl_de            \ HL = &letter-buf[ry]

            \ *HL |= mask
            ld_a_ind_hl   or_b   ld_ind_hl_a

            pop_bc
            pop_hl
        label rl-skip
            inc_hl               \ next x-cache entry
            djnz rl-col

        \ ── advance row, restore outer state ─────────────────────
        pop_de
        pop_bc
        inc_d
        djnz rl-row

    pop_hl ;                      \ refresh TOS

\ Convenience: bake the per-frame basis (run once before any
\ render-letter calls in a frame).
: bake-rotation   ( yaw pitch -- )
    bake-frame
    bake-coords ;

: paint-attrs     ( -- )   $47  $5800 768 rot fill ;
