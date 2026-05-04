\ Double-buffered plasma using the Spectrum 128's shadow screen.  Bank 5
\ at $4000 and bank 7 (paged into slot 3 at $C000) each hold a full
\ display; bit 3 of port $7FFD picks which one the ULA reads.  By
\ keeping bank 7 paged into slot 3 for the whole program, both screens'
\ attribute areas — $5800 and $D800 — remain writable at the same time.
\ The render loop always writes to the *hidden* buffer, then flips bit
\ 3 in one OUT to swap visible and hidden atomically: zero-copy, no
\ tearing even if drawing took multiple ULA frames.

require ./lib/math.fs
require array.fs


\ Pages and addresses
\ ───────────────────
\ The two $7FFD values share bank 7 in slot 3 (bit 4 = 0 = Pentagon
\ BASIC ROM); only bit 3 differs.  $5800 is bank 5's attribute base;
\ $D800 is bank 7's.

$07 constant page-normal-visible
$0F constant page-shadow-visible

$5800 constant normal-attrs
$D800 constant shadow-attrs

32    constant scr-cols
24    constant scr-rows


\ The plasma colour function
\ ──────────────────────────
\ wave is a 32-entry triangle (0..7..0..0..7..0); plasma-attr XORs the
\ wave at column-plus-phase against the wave at row-plus-phase to get
\ a 0..7 paper colour, shifts it into the paper bits, and ORs the
\ bright bit so the result is fully saturated.  Ink stays 0 (black),
\ pixels stay 0 — every cell is solid paper colour.

c: wave
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
;

variable phase

: wave@  ( i -- n )  mod32 wave swap a-byte@ ;

: plasma-attr  ( col row -- attr )
    phase @ + wave@
    swap phase @ + wave@
    xor
    3 lshift
    $40 or ;


\ Drawing into the hidden buffer
\ ──────────────────────────────
\ shadow-visible? records which buffer the ULA is showing right now;
\ hidden-attrs returns the base address of the *other* one.  draw-plasma
\ walks the 32×24 grid and writes every cell, leaving the visible
\ buffer untouched until the flip.

variable shadow-visible?

: attr-offset  ( col row -- offset )  scr-cols * + ;

: hidden-attrs  ( -- attrs-base )
    shadow-visible? @ if normal-attrs else shadow-attrs then ;

: draw-plasma  ( -- )
    hidden-attrs
    scr-rows 0 do
        scr-cols 0 do
            i j plasma-attr
            over i j attr-offset + c!
        loop
    loop
    drop ;


\ Page flipping
\ ─────────────
\ One OUT to $7FFD swaps which screen the ULA reads — the rest of the
\ system state survives because both pages keep bank 7 in slot 3 and
\ leave every other bit alone.  shadow-visible? mirrors the bit so the
\ next call to hidden-attrs targets the right buffer.

: flip  ( -- )
    shadow-visible? @ if
        page-normal-visible raw-bank!
        0 shadow-visible? !
    else
        page-shadow-visible raw-bank!
        1 shadow-visible? !
    then ;

: step  ( -- )  1 phase +! ;


\ Main loop
\ ─────────
\ One-time setup pages bank 7 into slot 3 and aligns shadow-visible?
\ with the initial $7FFD = $07 (normal visible).  Then draw, flip,
\ step, forever.

: main
    7 bank!
    0 shadow-visible? !
    0 phase !
    begin
        draw-plasma
        flip
        step
    again ;
