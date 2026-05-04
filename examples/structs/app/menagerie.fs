\ The actor types and their fights.  Demonstrates the full struct
\ vocabulary: layout, inheritance, named instances, generic accessors,
\ and both flavours of fusion (static when the instance and offset are
\ both compile-time constants, dynamic when only the offset is).

require core.fs


\ The /actor layout
\ ─────────────────
\ Six bytes total: two 16-bit cells for position, then two 8-bit bytes
\ for stats.  Mixing cell and byte widths is fine — `--` accumulates
\ raw byte offsets and the access words pick @/c@ based on the field's
\ declared size.

0
2 -- .x
2 -- .y
1 -- .hp
1 -- .mp
STRUCT /actor


\ /boss extends /actor
\ ────────────────────
\ Inheritance is just stack arithmetic.  Re-open the layout at /actor
\ (= 6 bytes), keep accumulating fields, finalize as /boss.  A /boss
\ IS-A /actor: every accessor defined for /actor still works on it,
\ and the new .rage field sits at offset 6.

/actor
2 -- .rage
STRUCT /boss


\ Named instances
\ ───────────────
\ `record` allots a struct's bytes and gives the address a name.
\ Because both the address and the field offsets are known at compile
\ time, every access through these names triggers static-instance
\ fusion: `hero .hp >c!` collapses to one IR cell.

/actor record hero
/actor record goblin
/boss  record troll


\ Generic accessors
\ ─────────────────
\ These work on *any* instance whose layout has the named field — the
\ instance arrives on the stack at the call site.  The `>@` / `>c@` /
\ `>!` / `>c!` postfix operators trigger dynamic-instance fusion:
\ inside the colon body, the IR collapses to a single
\ NativeOffsetFetch / NativeOffsetStore even though the address itself
\ is a runtime value.

: actor-x       ( actor -- x )      .x   >@  ;
: actor-y       ( actor -- y )      .y   >@  ;
: actor-hp      ( actor -- hp )     .hp  >c@ ;
: actor-mp      ( actor -- mp )     .mp  >c@ ;
: boss-rage     ( boss  -- rage )   .rage >@ ;

: set-actor-x   ( x  actor -- )     .x   >!  ;
: set-actor-y   ( y  actor -- )     .y   >!  ;
: set-actor-hp  ( hp actor -- )     .hp  >c! ;
: set-boss-rage ( rage boss -- )    .rage >! ;


\ Combat helpers
\ ──────────────
\ take-damage saturates: hp drops to zero rather than wrapping.  Built
\ entirely from the generic accessors above, so it works on both /actor
\ instances (hero, goblin) and /boss instances (troll) without
\ re-declaring anything.

: take-damage  ( amount actor -- )
    dup actor-hp
    rot - 0 max
    swap set-actor-hp ;


\ Setup
\ ─────
\ Every line below combines a literal value, a named record, and a
\ known field — the textbook conditions for static-instance fusion.
\ Each `>!` or `>c!` compiles to one IR cell; no runtime offset
\ arithmetic, no DOCOL dispatch.

: setup-actors
  100 hero  .x  >!
  50  hero  .y  >!
  250 hero  .hp >c!
  120 hero  .mp >c!

  50  goblin .x  >!
  60  goblin .y  >!
  30  goblin .hp >c!
  0   goblin .mp >c!

  200 troll  .x  >!
  150 troll  .y  >!
  80  troll  .hp >c!
  0   troll  .mp >c!
  5   troll  .rage >! ;


\ One round of combat
\ ───────────────────
\ Three damage events per round.  Each call passes a literal amount and
\ a named record into take-damage, so the static path through the
\ accessor lights up — exactly the mix of static and dynamic fusion the
\ struct system was built to support.

: fight-one-round
    25 goblin take-damage
    10 hero   take-damage
    30 hero   take-damage ;


\ Reporting
\ ─────────
\ show-actor uses the dynamic accessors so it can be reused for any
\ instance.  print-results assembles the post-round summary; the troll
\ also prints its boss-only rage value.

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
