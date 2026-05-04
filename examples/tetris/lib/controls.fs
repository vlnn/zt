\ Three input methods OR'd together so the player can use whichever's
\ wired up.  Kempston reads port $1F directly via a tiny ::: primitive;
\ Sinclair joystick (Interface 2 P1) maps to keys 6/7/8/0; the keyboard
\ uses O/P/A/M (M for rotate is the de facto standard on Spectrum
\ tetris ports).
\
\ Bits returned by Kempston port $1F: 0=right 1=left 2=down 3=up 4=fire.
\ Rotate is wired to "up" on Kempston and to "fire" (key 0) on Sinclair —
\ both are the natural rotate buttons on those interfaces.

require core.fs


\ Kempston
\ ────────
\ One-instruction read of port $1F into A, masked to the five active
\ bits.  When no joystick is attached, the data bus floats high and
\ reads as $FF (so the masked value is $1F = all-on, an impossible
\ physical state) — kempston filters that case to 0 so a missing
\ joystick can't phantom-press every direction at once.

::: kempston-raw ( -- bits )
    push_hl
    $1F in_a_n
    $1F and_n
    ld_l_a
    0 ld_h_n ;

: kempston ( -- bits )
    kempston-raw  dup $1F = if drop 0 then ;

: kempston-right? ( -- flag )    kempston  1 and 0= 0= ;
: kempston-left?  ( -- flag )    kempston  2 and 0= 0= ;
: kempston-down?  ( -- flag )    kempston  4 and 0= 0= ;
: kempston-up?    ( -- flag )    kempston  8 and 0= 0= ;
: kempston-fire?  ( -- flag )    kempston 16 and 0= 0= ;


\ Sinclair joystick (P1 on Interface 2)
\ ─────────────────────────────────────
\ 6 = left, 7 = right, 8 = soft drop, 0 = rotate.

54 constant key-6
55 constant key-7
56 constant key-8
48 constant key-0

: sinclair-left?    ( -- flag )    key-6 key-state ;
: sinclair-right?   ( -- flag )    key-7 key-state ;
: sinclair-down?    ( -- flag )    key-8 key-state ;
: sinclair-rotate?  ( -- flag )    key-0 key-state ;


\ Keyboard
\ ────────
\ O = left, P = right, A = soft drop, M = rotate.

79 constant key-O
80 constant key-P
65 constant key-A
77 constant key-M

: kb-left?      ( -- flag )    key-O key-state ;
: kb-right?     ( -- flag )    key-P key-state ;
: kb-down?      ( -- flag )    key-A key-state ;
: kb-rotate?    ( -- flag )    key-M key-state ;


\ Combined
\ ────────
\ Each direction OR's all three input methods.  Rotate is "up" on
\ Kempston (the conventional rotate button) and "fire" on Sinclair
\ (likewise).

: any3 ( a b c -- flag )    or or ;

: in-left?    ( -- flag )    kempston-left?  sinclair-left?    kb-left?    any3 ;
: in-right?   ( -- flag )    kempston-right? sinclair-right?   kb-right?   any3 ;
: in-down?    ( -- flag )    kempston-down?  sinclair-down?    kb-down?    any3 ;
: in-rotate?  ( -- flag )    kempston-up?    sinclair-rotate?  kb-rotate?  any3 ;
