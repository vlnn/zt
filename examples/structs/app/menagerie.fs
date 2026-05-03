require core.fs

\ ── Struct definition ────────────────────────────────────────────────────
\
\ /actor is 6 bytes: two 16-bit position cells, then two 8-bit stat bytes.
\ Mixing widths is fine; offsets are accumulated across `--` regardless.

0
2 -- .x          \ cell:  horizontal position
2 -- .y          \ cell:  vertical position
1 -- .hp         \ byte:  hit points (0..255)
1 -- .mp         \ byte:  magic points (0..255)
STRUCT /actor

\ ── /boss extends /actor ────────────────────────────────────────────────
\
\ Inheritance is just stack arithmetic: re-open the layout at /actor
\ (= 6 bytes), keep accumulating, finalize as /boss. A /boss IS-A /actor
\ — the .x / .y / .hp / .mp accessors all still work on it.

/actor
2 -- .rage       \ cell:  fury counter, drives boss-only behaviour
STRUCT /boss


\ ── Named instances (static-instance fusion will fire on these) ──────────

/actor record hero
/actor record goblin
/boss  record troll          \ /boss is 8 bytes; .rage at offset 6


\ ── Generic accessors (dynamic-instance fusion fires inside these) ───────
\
\ Each one is a tiny colon body whose IR collapses to a single
\ NativeOffsetFetch / NativeOffsetStore cell. The instance is whatever
\ was on the stack at the call site — these accessors work on hero,
\ goblin, troll, or anything else of compatible shape.

: actor-x      ( actor -- x )      .x  >@  ;
: actor-y      ( actor -- y )      .y  >@  ;
: actor-hp     ( actor -- hp )     .hp >c@ ;
: actor-mp     ( actor -- mp )     .mp >c@ ;
: boss-rage    ( boss  -- rage )   .rage >@ ;

: set-actor-x  ( x  actor -- )     .x  >!  ;
: set-actor-y  ( y  actor -- )     .y  >!  ;
: set-actor-hp ( hp actor -- )     .hp >c! ;
: set-boss-rage ( rage boss -- )   .rage >!  ;


\ ── Predicates and small helpers using the dynamic accessors ─────────────

: take-damage  ( amount actor -- )
    \ Saturating subtract: hp <- max(0, hp - amount).
    dup actor-hp           ( amt actor cur-hp )
    rot - 0 max            ( actor new-hp )
    swap set-actor-hp ;


\ ── Setup uses static-instance fusion (named record + known offset) ──────
\
\ Each line below is exactly one NativeFetch / NativeStore IR cell after
\ fusion. `42 hero .x >!` becomes the four bytes  (!abs)_addr addr_of_x ;
\ no DOCOL, no per-cell NEXT dispatch, no offset arithmetic at runtime.

: setup-actors
  100 hero  .x  >!
  50 hero   .y  >!
  250 hero  .hp >c!
  120 hero  .mp >c!

  50 goblin .x  >!
  60 goblin .y  >!
  30 goblin .hp >c!
  0 goblin .mp >c!

  200 troll  .x  >!
  150 troll  .y  >!
  80 troll  .hp >c!
  0 troll  .mp >c!
  5 troll  .rage >!  ;


\ ── Combat round mixes static and dynamic fusion ─────────────────────────

: fight-one-round
    \ Hero hacks at goblin: the operand is a static expression (a literal
    \ amount, a named record), so static fusion fires on the .hp field.
    25 goblin take-damage

    \ Goblin retaliates against hero — same shape.
    10 hero  take-damage

    \ Troll smashes hero. Two more direct hits would finish hero off, but
    \ one round is enough to verify the math.
    30 hero  take-damage ;


\ ── Output ───────────────────────────────────────────────────────────────

: show-actor   ( actor -- )
    dup actor-hp u.            ." hp  "
    actor-mp     u.            ." mp" cr ;

: print-results
    7 0 cls
    ." after one round:" cr cr
    ." hero:   " hero   show-actor
    ." goblin: " goblin show-actor
    ." troll:  " troll  show-actor
    cr ." troll rage: " troll boss-rage u. cr ;
