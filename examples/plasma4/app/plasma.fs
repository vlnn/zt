\ Animated plasma effect on the Spectrum's 32×24 attribute grid.  The
\ pattern is generated once by XORing two phase tables — one indexed by
\ column, one indexed by row — into per-cell paper colours.  After the
\ initial draw, every frame just scrolls the whole attribute area in
\ response to direction keys; the plasma itself never re-renders, so
\ animation is essentially free.

require ../lib/math.fs
require ../lib/screen.fs
require ../lib/timing.fs
require array.fs


\ The wave table
\ ──────────────
\ 32 entries: ramp 0..7, drop 7..0, ramp 0..7, drop 7..0.  A coarse
\ sine in eighth-of-a-period steps, used to map a phase index to a
\ paper colour.  mod32 wraps any column or row offset into range.

c: wave
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
;

variable phase

create phased 32 allot

: wave@       ( i -- n )        mod32 wave swap a-byte@ ;
: phased@     ( i -- n )        phased + c@ ;
: paper-attr  ( paper -- attr ) 3 lshift 64 or ;


\ Drawing the plasma
\ ──────────────────
\ rephase fills the 32-entry phased buffer with one wave-table value
\ per column, offset by `phase`.  draw-row then reuses that same buffer
\ indexed by row (the 24 row positions all fall within the 32-entry
\ window) to read the row's phase, and XORs row-phase against each
\ column-phase to pick the cell's paper colour.  The XOR is what makes
\ this a plasma rather than a stripe — every (col, row) gets a colour
\ derived from both axes.

: rephase  ( -- )
    scr-cols 0 do
        i phase @ + wave@
        phased i + c!
    loop ;

: draw-row  ( row -- )
    dup phased@
    swap row-addr
    scr-cols 0 do
        over i phased@ xor
        paper-attr
        over c!  1+
    loop
    2drop ;

: draw  ( -- )
    rephase
    scr-rows 0 do i draw-row loop ;

: plasma-init  ( -- )  0 phase !  draw ;


\ Input
\ ─────
\ Two parallel key schemes drive movement: QAOP (Sinclair-style — Q up,
\ A down, O left, P right) and 9/8/6/7 mirroring it.  dx and dy fold
\ the four predicates into ±1 deltas for one frame of scrolling.

81 constant k-q
65 constant k-a
79 constant k-o
80 constant k-p
57 constant k-9
56 constant k-8
55 constant k-7
54 constant k-6

: up?     ( -- f )  k-q key-state  k-9 key-state  or ;
: down?   ( -- f )  k-a key-state  k-8 key-state  or ;
: left?   ( -- f )  k-o key-state  k-6 key-state  or ;
: right?  ( -- f )  k-p key-state  k-7 key-state  or ;

: dx      ( -- n )  right? left? - ;
: dy      ( -- n )  down?  up?   - ;


\ Animation
\ ─────────
\ The plasma is drawn once.  Every frame, react reads the current key
\ deltas and calls scroll-attr (from the bundled stdlib) to shift the
\ entire attribute area by one cell — fast enough to feel like motion
\ without recomputing the pattern.

: react   ( -- )  dx dy scroll-attr ;

: animate ( -- )
    plasma-init
    begin wait-frame react again ;
