\ examples/im2-music/app/music.fs
\
\ AY-3-8912 chip music driver, frame-locked to the IM 2 ULA interrupt.
\ Plays an 8-note C-major arpeggio on channel A while the foreground
\ thread (rainbow border + random letters) keeps running uninterrupted.
\
\ Tone periods are computed from the Spectrum 128's AY clock of
\ 1.77345 MHz: period N produces frequency clock / (16 * N).
\
\ Layout:
\   tone-table                - 8 cells, C4..C5 tone periods
\   tone-period               - ( index -- period ), masked & 7
\   ay-set                    - ( val reg -- ), low-level AY register write
\   music-init                - one-shot mixer + volume setup
\   music-isr                 - IM 2 handler, advances border + plays note
\   music                     - install handler, ei, run foreground spew
\
\ 128K-only: writes are addressed to AY ports $FFFD (register select) and
\ $BFFD (data). On 48K these become floating-bus writes — silent but harmless.

require rand.fs

create tone-table
    424 ,  377 ,  336 ,  317 ,  283 ,  252 ,  224 ,  212 ,

: tone-period  ( index -- period )
    7 and  2*  tone-table +  @ ;

variable border-tick
variable music-tick

$38 constant ay-mixer-tones-only
$0F constant ay-volume-max

::: ay-set  ( val reg -- )
    pop_de
    $FFFD ld_bc_nn
    ld_a_l
    out_c_a
    $BFFD ld_bc_nn
    ld_a_e
    out_c_a
    pop_hl ;

: enable-tones  ( -- )   ay-mixer-tones-only 7 ay-set ;
: max-volume-a  ( -- )   ay-volume-max 8 ay-set ;
: music-init    ( -- )   enable-tones max-volume-a ;

::: music-isr  ( -- )
    push_af  push_hl  push_bc  push_de

    ' border-tick ld_a_ind_nn
    inc_a
    7 and_n
    $FE out_n_a
    ' border-tick ld_ind_nn_a

    ' music-tick ld_a_ind_nn
    inc_a
    ' music-tick ld_ind_nn_a

    rrca  rrca  rrca
    7 and_n
    add_a_a
    ld_e_a
    0 ld_d_n
    ' tone-table ld_hl_nn
    add_hl_de

    ld_a_ind_hl
    ld_e_a
    inc_hl
    ld_a_ind_hl
    ld_d_a

    $FFFD ld_bc_nn
    0 ld_a_n
    out_c_a
    $BFFD ld_bc_nn
    ld_a_e
    out_c_a

    $FFFD ld_bc_nn
    1 ld_a_n
    out_c_a
    $BFFD ld_bc_nn
    ld_a_d
    out_c_a

    pop_de  pop_bc  pop_hl  pop_af
    ei
    reti ;

: random-letter   ( -- ch )
    27 random  dup 26 = if  drop 32  else  65 +  then ;

: random-position  ( -- col row )    32 random  24 random ;

: music  ( -- )
    ['] music-isr im2-handler!
    ei
    begin random-position at-xy random-letter emit again ;
