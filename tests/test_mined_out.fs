include test-lib.fs
require core.fs
require ../examples/mined-out/app/mined.fs


\ -----------------------------------------------------------------------------
\ state.fs — level tables
\ -----------------------------------------------------------------------------

\ paper table matches the BASIC at each level
: test-level-paper-1    1 level-no !  level-paper@   6 assert-eq ;
: test-level-paper-2    2 level-no !  level-paper@   5 assert-eq ;
: test-level-paper-3    3 level-no !  level-paper@   4 assert-eq ;
: test-level-paper-4    4 level-no !  level-paper@   3 assert-eq ;
: test-level-paper-5    5 level-no !  level-paper@   2 assert-eq ;
: test-level-paper-6    6 level-no !  level-paper@   1 assert-eq ;
: test-level-paper-7    7 level-no !  level-paper@   0 assert-eq ;
: test-level-paper-8    8 level-no !  level-paper@   6 assert-eq ;

\ level 8 is the only one that shifts the border
: test-level-border-1   1 level-no !  level-border@  0 assert-eq ;
: test-level-border-7   7 level-no !  level-border@  0 assert-eq ;
: test-level-border-8   8 level-no !  level-border@  2 assert-eq ;

\ mine count climbs per level, dips on 7, resets on 8 (matches BASIC)
: test-level-mines-1    1 level-no !  level-mines@   50 assert-eq ;
: test-level-mines-2    2 level-no !  level-mines@   60 assert-eq ;
: test-level-mines-6    6 level-no !  level-mines@  100 assert-eq ;
: test-level-mines-7    7 level-no !  level-mines@   20 assert-eq ;
: test-level-mines-8    8 level-no !  level-mines@   50 assert-eq ;

\ bonus is a 16-bit cell, not a byte — exercise the 2* in the accessor
: test-level-bonus-1    1 level-no !  level-bonus@      0 assert-eq ;
: test-level-bonus-2    2 level-no !  level-bonus@    250 assert-eq ;
: test-level-bonus-3    3 level-no !  level-bonus@    750 assert-eq ;
: test-level-bonus-4    4 level-no !  level-bonus@   1500 assert-eq ;
: test-level-bonus-5    5 level-no !  level-bonus@   2200 assert-eq ;
: test-level-bonus-6    6 level-no !  level-bonus@   2700 assert-eq ;
: test-level-bonus-7    7 level-no !  level-bonus@   3500 assert-eq ;
: test-level-bonus-8    8 level-no !  level-bonus@   4200 assert-eq ;


\ -----------------------------------------------------------------------------
\ state.fs — progression predicates
\ -----------------------------------------------------------------------------

: test-has-damsels-level-1   1 level-no !  has-damsels?   assert-false ;
: test-has-damsels-level-2   2 level-no !  has-damsels?   assert-true ;
: test-has-damsels-level-8   8 level-no !  has-damsels?   assert-true ;

: test-has-spreader-level-2  2 level-no !  has-spreader?  assert-false ;
: test-has-spreader-level-3  3 level-no !  has-spreader?  assert-true ;

: test-has-bug-level-3       3 level-no !  has-bug?       assert-false ;
: test-has-bug-level-4       4 level-no !  has-bug?       assert-true ;
: test-has-bug-level-8       8 level-no !  has-bug?       assert-true ;


\ -----------------------------------------------------------------------------
\ state.fs — advance-level clamp
\ -----------------------------------------------------------------------------

: test-advance-level-1-to-2   1 level-no !  advance-level   level-no @   2 assert-eq ;
: test-advance-level-7-to-8   7 level-no !  advance-level   level-no @   8 assert-eq ;
: test-advance-level-8-clamps 8 level-no !  advance-level   level-no @   8 assert-eq ;


\ -----------------------------------------------------------------------------
\ board.fs — gap?
\ -----------------------------------------------------------------------------

: test-gap-col-0     0  gap?  assert-false ;
: test-gap-col-14   14  gap?  assert-false ;
: test-gap-col-15   15  gap?  assert-true ;
: test-gap-col-16   16  gap?  assert-true ;
: test-gap-col-17   17  gap?  assert-false ;
: test-gap-col-31   31  gap?  assert-false ;


\ -----------------------------------------------------------------------------
\ board.fs — board-init clears the shadow grid
\ -----------------------------------------------------------------------------

: test-board-init-top-left-empty      board-init  0  0 empty?  assert-true ;
: test-board-init-middle-empty        board-init 15 10 empty?  assert-true ;
: test-board-init-bottom-right-empty  board-init 31 21 empty?  assert-true ;


\ -----------------------------------------------------------------------------
\ board.fs — build-fences respects the gap
\ -----------------------------------------------------------------------------

: test-top-fence-has-tile-at-0
    board-init build-fences
    0 top-fence-row fence?    assert-true ;

: test-top-fence-gap-left-empty
    board-init build-fences
    gap-left top-fence-row empty?    assert-true ;

: test-top-fence-gap-right-empty
    board-init build-fences
    gap-right top-fence-row empty?   assert-true ;

: test-bottom-fence-has-tile-at-31
    board-init build-fences
    31 bottom-fence-row fence?   assert-true ;


\ -----------------------------------------------------------------------------
\ board.fs — try-place-mine
\ -----------------------------------------------------------------------------

: test-try-place-mine-on-empty
    board-init
    5 5 try-place-mine
    5 5 mine?   assert-true ;

: test-try-place-mine-skips-fence
    board-init build-fences
    0 top-fence-row try-place-mine
    0 top-fence-row fence?   assert-true ;

: test-try-place-mine-is-idempotent
    board-init
    5 5 try-place-mine
    5 5 try-place-mine
    5 5 mine?   assert-true ;


\ -----------------------------------------------------------------------------
\ actors.fs — player movement and position
\ -----------------------------------------------------------------------------

\ NOTE: px stores the ROW and py stores the COLUMN in this port (inverted
\ from what the variable names suggest — see apply-input, which adds
\ read-dx to py and read-dy to px).

: test-player-reset-col       player-reset   py @  start-col  assert-eq ;
: test-player-reset-row       player-reset   px @  start-row  assert-eq ;

: test-snapshot-matches-current
    player-reset
    7 px !  3 py !
    snapshot-pos
    oldx @ 7 assert-eq ;

: test-moved-false-after-snapshot
    player-reset
    7 px !  3 py !  snapshot-pos
    moved? assert-false ;

: test-moved-true-when-px-changes
    player-reset
    7 px !  3 py !  snapshot-pos
    8 px !
    moved? assert-true ;

: test-moved-true-when-py-changes
    player-reset
    7 px !  3 py !  snapshot-pos
    4 py !
    moved? assert-true ;


\ -----------------------------------------------------------------------------
\ actors.fs — clamp
\ -----------------------------------------------------------------------------

: test-clamp-col-zero             0 clamp-col   0 assert-eq ;
: test-clamp-col-in-range        15 clamp-col  15 assert-eq ;
: test-clamp-col-at-max          31 clamp-col  31 assert-eq ;
: test-clamp-col-above-max       99 clamp-col  31 assert-eq ;

\ KNOWN QUIRK: stdlib `max` is unsigned, so a negative `n` (e.g. -5 = $FFFB)
\ clamps to board-cols-1 instead of 0. Stepping off col 0 leftward wraps to
\ col 31 in-game. Pin the current behavior until the MAX primitive is fixed.
: test-clamp-col-negative-wraps  -5 clamp-col  31 assert-eq ;

: test-clamp-row-at-max          21 clamp-row  21 assert-eq ;
: test-clamp-row-above-max       99 clamp-row  21 assert-eq ;
: test-clamp-row-negative-wraps  -5 clamp-row  21 assert-eq ;


\ -----------------------------------------------------------------------------
\ actors.fs — adj-count on a synthetic board
\ -----------------------------------------------------------------------------

: test-adj-count-isolated
    board-init
    10 py !  10 px !
    adj-count  0 assert-eq ;

: test-adj-count-one-north
    board-init
    10 py !  10 px !
    10  9 try-place-mine
    adj-count  1 assert-eq ;

: test-adj-count-all-four
    board-init
    10 py !  10 px !
    10  9 try-place-mine   10 11 try-place-mine
     9 10 try-place-mine   11 10 try-place-mine
    adj-count  4 assert-eq ;

: test-adj-count-ignores-diagonal
    board-init
    10 py !  10 px !
     9  9 try-place-mine   11  9 try-place-mine
     9 11 try-place-mine   11 11 try-place-mine
    adj-count  0 assert-eq ;

: test-adj-count-damsel-counts
    board-init
    10 py !  10 px !
    10  9 place-damsel
    adj-count  1 assert-eq ;

: test-adj-count-fence-counts
    board-init build-fences
    2 py !  2 px !           \ col 2, row 2 — one below the top fence
    adj-count  1 assert-eq ;


\ -----------------------------------------------------------------------------
\ actors.fs — damsel rescue
\ -----------------------------------------------------------------------------

: test-rescue-clears-tile
    board-init
    8 10 place-damsel
    2 damsels-alive !   0 score !
    8 10 rescue-damsel
    8 10 empty?  assert-true ;

: test-rescue-decrements-damsels-alive
    board-init
    8 10 place-damsel
    2 damsels-alive !   0 score !
    8 10 rescue-damsel
    damsels-alive @  1 assert-eq ;

: test-rescue-awards-100-points
    board-init
    8 10 place-damsel
    2 damsels-alive !   0 score !
    8 10 rescue-damsel
    score @  100 assert-eq ;

: test-maybe-rescue-noop-on-empty-cell
    board-init
    2 level-no !             \ enable damsels
    2 damsels-alive !   0 score !
    5 py !  5 px !           \ empty cell
    maybe-rescue
    score @  0 assert-eq ;

: test-maybe-rescue-acts-on-damsel
    board-init
    2 level-no !
    2 damsels-alive !   0 score !
    5 10 place-damsel
    5 py !  10 px !          \ py=col, px=row — player stands on the damsel
    maybe-rescue
    score @  100 assert-eq ;

: test-maybe-rescue-skipped-when-no-damsels
    board-init
    1 level-no !             \ level 1 => has-damsels? false
    2 damsels-alive !   0 score !
    5 10 place-damsel
    5 py !  10 px !
    maybe-rescue
    score @  0 assert-eq ;


\ -----------------------------------------------------------------------------
\ actors.fs — spreader motion
\ -----------------------------------------------------------------------------

: test-spreader-step-advances-col
    board-init
    1 spreader-active !   5 spreader-col !   10 spreader-row !
    spreader-step
    spreader-col @  6 assert-eq ;

: test-spreader-step-lays-mine-at-old-col
    board-init
    1 spreader-active !   5 spreader-col !   10 spreader-row !
    spreader-step
    5 10 mine?  assert-true ;

: test-spreader-step-deactivates-past-col-30
    board-init
    1 spreader-active !  30 spreader-col !   10 spreader-row !
    spreader-step
    spreader-active @  0 assert-eq ;

: test-spreader-step-deactivates-on-nonempty-next
    board-init
    1 spreader-active !   5 spreader-col !   10 spreader-row !
    t-mine 6 10 tile!        \ block the next cell
    spreader-step
    spreader-active @  0 assert-eq ;

: test-spreader-step-inactive-noop
    board-init
    0 spreader-active !   5 spreader-col !   10 spreader-row !
    spreader-step
    spreader-col @  5 assert-eq ;


\ -----------------------------------------------------------------------------
\ actors.fs — spreader spawn gating
\ -----------------------------------------------------------------------------

: test-maybe-spawn-spreader-skipped-before-level-3
    2 level-no !   0 spreader-active !   1 seed!
    100 0 do  maybe-spawn-spreader  loop
    spreader-active @  0 assert-eq ;

: test-maybe-spawn-spreader-no-double-activation
    3 level-no !   1 spreader-active !
    99 spreader-col !   1 seed!
    100 0 do  maybe-spawn-spreader  loop
    spreader-col @  99 assert-eq ;


\ -----------------------------------------------------------------------------
\ actors.fs — bug trail-follow
\ -----------------------------------------------------------------------------

: test-bug-visible-false-when-trail-short
    trail-setup
    5 0 do  i i pack-xy trail-push  loop
    bug-visible?  assert-false ;

: test-bug-visible-true-when-trail-long
    trail-setup
    20 0 do  i i pack-xy trail-push  loop
    bug-visible?  assert-true ;

: test-bug-index-is-trail-len-minus-follow-distance
    trail-setup
    20 0 do  i i pack-xy trail-push  loop
    bug-index  8 assert-eq ;

\ bug-index's low-end clamp is only reachable when bug-visible? is true
\ (trail-len > follow-distance), so we don't test short trails directly —
\ the clamp would trip the unsigned-max quirk described above.


\ -----------------------------------------------------------------------------
\ game.fs — win condition and death
\ -----------------------------------------------------------------------------

: test-won-when-px-zero      0 px !  won?  assert-true ;
: test-won-false-at-1        1 px !  won?  assert-false ;
: test-won-false-at-start    start-row px !  won?  assert-false ;

: test-die-sets-alive-zero   1 alive !  die  alive @  0 assert-eq ;

: test-win-sets-alive-zero   1 alive !  1 level-no !  0 score !  win  alive @  0 assert-eq ;

: test-win-awards-level-bonus-plus-100
    1 alive !   2 level-no !   0 score !
    win
    score @  350 assert-eq ;   \ level-2 bonus 250 + the flat 100

: test-award-bonus-level-5
    5 level-no !   0 score !
    award-bonus
    score @  2200 assert-eq ;
