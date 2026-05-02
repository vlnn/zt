\ stdlib/ay.fs — AY-3-8912 sound chip helpers (Spectrum 128 only).
\
\ All writes go to ports $FFFD (register select) followed by $BFFD (data).
\ On 48K these are floating-bus writes — silent but harmless.
\
\ Channel registers:
\   tone period: R0/R1 (A), R2/R3 (B), R4/R5 (C) — 12-bit period
\   noise period: R6 — 5-bit
\   mixer: R7 — bits 0-2 disable tones, 3-5 disable noise (1 = OFF)
\   volume: R8 (A), R9 (B), R10 (C) — 4-bit fixed level, bit 4 = use envelope
\   envelope: R11/R12 period, R13 shape

\ Write `val` to AY register `reg`.
::: ay-set  ( val reg -- )
    pop_de
    $FFFD ld_bc_nn
    ld_a_l
    out_c_a
    $BFFD ld_bc_nn
    ld_a_e
    out_c_a
    pop_hl ;

\ Mixer enable pattern: tones on for all three channels, noise/IO off.
$38 constant ay-mixer-tones-only
\ Maximum fixed channel volume.
$0F constant ay-volume-max
\ Silent channel volume.
0   constant ay-volume-mute

: ay-mixer!   ( bits -- )      7 ay-set ;
: ay-noise!   ( period -- )    6 ay-set ;

: ay-tone-a!  ( period -- )    dup 255 and 0 ay-set  8 rshift 1 ay-set ;
: ay-tone-b!  ( period -- )    dup 255 and 2 ay-set  8 rshift 3 ay-set ;
: ay-tone-c!  ( period -- )    dup 255 and 4 ay-set  8 rshift 5 ay-set ;

: ay-vol-a!   ( level -- )     8 ay-set ;
: ay-vol-b!   ( level -- )     9 ay-set ;
: ay-vol-c!   ( level -- )    10 ay-set ;
