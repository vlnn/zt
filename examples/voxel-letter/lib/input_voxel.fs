\ lib/input_voxel.fs — direct-port keyboard polling for the voxel demo.
\
\ The stdlib `key-state` walks a 40-entry table to map ASCII to half-row
\ + bit, then reads the port — ~1950 T per call.  poll-keys would call
\ that 8 times per frame (~13.9 K T), which is more than the 70 K T
\ vsync budget can spare with 5 letters rendering.
\
\ Instead, we read the four relevant half-rows directly (one IN per
\ row), then bit-test in-place:
\
\   $EFFE  —  bit 4 = 6, bit 3 = 7, bit 2 = 8, bit 1 = 9
\   $DFFE  —  bit 0 = P, bit 1 = O
\   $FDFE  —  bit 0 = A
\   $FBFE  —  bit 0 = Q
\   $7FFE  —  bit 0 = SPACE          (quit?)
\
\ ZX Spectrum convention: bit clear = key pressed.  We CPL the read so
\ "bit set = pressed" — then a single AND + JR Z is enough.
\
\ Per-frame cost: ~280 T total (5 IN reads + 4 paired key checks +
\ 1 quit check).  Saves ~13 K T vs the Forth-glue version.

variable angle-yaw
variable angle-pitch

\ Every held frame advances the angle by 1 sine-table step (5.625°).
1 constant angle-step

::: poll-keys  ( -- )
    push_hl

    \ Read $EFFE → B  (6,7,8,9)
    $EF ld_a_n   $FE in_a_n   cpl   ld_b_a
    \ Read $DFFE → C  (O,P)
    $DF ld_a_n   $FE in_a_n   cpl   ld_c_a
    \ Read $FDFE → D  (A)
    $FD ld_a_n   $FE in_a_n   cpl   ld_d_a
    \ Read $FBFE → E  (Q)
    $FB ld_a_n   $FE in_a_n   cpl   ld_e_a

    \ pitch-up: 7 (B bit 3) OR Q (E bit 0)  →  angle-pitch -= 1
    ld_a_b   $08 and_n   jr_nz pu-yes
    ld_a_e   $01 and_n   jr_z pu-no
    label pu-yes
        ' angle-pitch ld_hl_ind_nn   dec_hl   ' angle-pitch ld_ind_nn_hl
    label pu-no

    \ pitch-down: 6 (B bit 4) OR A (D bit 0)  →  angle-pitch += 1
    ld_a_b   $10 and_n   jr_nz pd-yes
    ld_a_d   $01 and_n   jr_z pd-no
    label pd-yes
        ' angle-pitch ld_hl_ind_nn   inc_hl   ' angle-pitch ld_ind_nn_hl
    label pd-no

    \ yaw-left: 8 (B bit 2) OR O (C bit 1)  →  angle-yaw -= 1
    ld_a_b   $04 and_n   jr_nz yl-yes
    ld_a_c   $02 and_n   jr_z yl-no
    label yl-yes
        ' angle-yaw ld_hl_ind_nn   dec_hl   ' angle-yaw ld_ind_nn_hl
    label yl-no

    \ yaw-right: 9 (B bit 1) OR P (C bit 0)  →  angle-yaw += 1
    ld_a_b   $02 and_n   jr_nz yr-yes
    ld_a_c   $01 and_n   jr_z yr-no
    label yr-yes
        ' angle-yaw ld_hl_ind_nn   inc_hl   ' angle-yaw ld_ind_nn_hl
    label yr-no

    pop_hl ;

\ quit? — true if SPACE is pressed.  Reading $7FFE directly keeps it
\ off the slow key-state path.
::: quit?  ( -- f )
    push_hl                       \ save old TOS to data stack
    $7F ld_a_n   $FE in_a_n
    cpl
    $01 and_n                     \ A = 1 if pressed, 0 otherwise (Z flag set if not)
    0 ld_hl_nn                    \ HL = 0  (does not affect flags)
    jr_z q-no
    dec_hl                        \ HL = $FFFF = true
    label q-no ;