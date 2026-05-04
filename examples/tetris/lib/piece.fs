\ The active piece: id, rotation, and (col, row) position in playfield
\ coordinates.  All movement is "try" — piece-fits? checks bounds and
\ playfield collisions for a hypothetical (id, rot, col, row); only on
\ success do we update the cur-* state.

require core.fs
require grid.fs
require rand.fs
require pieces.fs
require playfield.fs

variable piece-cur-id
variable piece-cur-rot
variable piece-cur-col
variable piece-cur-row
variable piece-next-id
variable piece-locked

3 constant piece-spawn-col
0 constant piece-spawn-row


\ Fit testing
\ ───────────
\ piece-fits? scans the 4x4 bounding box; for each filled piece cell it
\ translates to playfield coords and tests against in-bounds + occupancy.
\ All four candidate values are stashed in _fits-* so the inner loop's
\ stack stays clean (no 4-cell juggle).

variable _fits-id
variable _fits-rot
variable _fits-col
variable _fits-row
variable _fits-result

: cur-piece-cell? ( br bc -- flag )
    >r >r _fits-id @ _fits-rot @ r> r> piece-cell? ;

: piece-cell-blocks? ( br bc -- flag )
    2dup cur-piece-cell? 0= if 2drop 0 exit then
    _fits-col @ +
    swap _fits-row @ +
    2dup in-bounds? 0= if 2drop -1 exit then
    pf@ cell-empty? 0= ;

: scan-piece-cells ( -- )
    piece-rows 0 do
        piece-cols 0 do
            j i piece-cell-blocks? if 0 _fits-result ! then
        loop
    loop ;

: piece-fits? ( id rot col row -- flag )
    _fits-row ! _fits-col ! _fits-rot ! _fits-id !
    -1 _fits-result !
    scan-piece-cells
    _fits-result @ ;


\ Try-place
\ ─────────
\ piece-try-place atomically tests fit and commits to cur-*.  All
\ movement and rotation builds on this: every motion is a candidate
\ proposal, accepted only if it fits.

variable _cand-id
variable _cand-rot
variable _cand-col
variable _cand-row

: piece-commit-cand ( -- )
    _cand-id  @ piece-cur-id  !
    _cand-rot @ piece-cur-rot !
    _cand-col @ piece-cur-col !
    _cand-row @ piece-cur-row ! ;

: piece-try-place ( id rot col row -- moved? )
    _cand-row ! _cand-col ! _cand-rot ! _cand-id !
    _cand-id  @ _cand-rot @ _cand-col @ _cand-row @ piece-fits? if
        piece-commit-cand -1
    else 0 then ;

: piece-try-move   ( dc dr -- moved? )
    piece-cur-row @ + swap piece-cur-col @ + swap
    piece-cur-id @ piece-cur-rot @ 2swap piece-try-place ;

: piece-try-rotate ( -- moved? )
    piece-cur-id @
    piece-cur-rot @ 1+ 3 and
    piece-cur-col @ piece-cur-row @ piece-try-place ;


\ Spawning
\ ────────
\ The next-id buffer drives the NEXT preview.  piece-spawn places
\ piece-next-id at the spawn position; on success we roll a fresh next.
\ A spawn that doesn't fit is the game-over signal — caller checks the
\ return flag.

: piece-advance-next ( -- )
    7 random piece-next-id ! ;

: piece-spawn ( -- ok? )
    piece-next-id @  0  piece-spawn-col  piece-spawn-row  piece-try-place
    dup if piece-advance-next then ;


\ Stamping (lock-down)
\ ────────────────────
\ When a piece can't drop further, its filled cells are stamped into
\ the playfield grid.  Stamped cells carry the piece's own attribute,
\ which the playfield's drawing path uses verbatim.

: piece-stamp-cell ( br bc -- )
    piece-cur-col @ +
    swap piece-cur-row @ +
    piece-cur-id @ piece-attr -rot pf! ;

: piece-stamp ( -- )
    piece-rows 0 do
        piece-cols 0 do
            piece-cur-id @ piece-cur-rot @ j i piece-cell? if
                j i piece-stamp-cell
            then
        loop
    loop ;


\ Drawing the live piece
\ ──────────────────────
\ piece-paint and piece-erase walk the same 4x4 footprint.  paint draws
\ block-tile with the piece's attr; erase paints empty-tile.  Cells of
\ the bounding box that are off the playfield (e.g. row -1 during a
\ rotation kick) are skipped.

: piece-cell-screen ( br bc -- scol srow )
    piece-cur-col @ +
    swap piece-cur-row @ +
    pf-screen-of ;

: piece-on-pf? ( br bc -- flag )
    piece-cur-col @ +
    swap piece-cur-row @ +
    in-bounds? ;

: paint-cur-cell ( br bc -- )
    2dup piece-on-pf? 0= if 2drop exit then
    piece-cell-screen
    piece-cur-id @ piece-attr -rot draw-filled-cell ;

: erase-cur-cell ( br bc -- )
    2dup piece-on-pf? 0= if 2drop exit then
    piece-cell-screen draw-empty-cell ;

: piece-paint ( -- )
    piece-rows 0 do
        piece-cols 0 do
            piece-cur-id @ piece-cur-rot @ j i piece-cell? if
                j i paint-cur-cell
            then
        loop
    loop ;

: piece-erase ( -- )
    piece-rows 0 do
        piece-cols 0 do
            piece-cur-id @ piece-cur-rot @ j i piece-cell? if
                j i erase-cur-cell
            then
        loop
    loop ;


\ Gravity step
\ ────────────
\ One row down on success; otherwise mark locked.  Caller (game.fs)
\ reads piece-locked after gravity to decide whether to stamp/clear.

: piece-gravity-step ( -- )
    0 1 piece-try-move 0= if -1 piece-locked ! then ;
