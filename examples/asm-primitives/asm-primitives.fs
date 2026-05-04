\ A small library of Forth primitives written in `:::` (assembler colon
\ definitions) that don't ship in primitives.py.  Each one is a real,
\ usable word with a runtime test in tests/test_examples_asm_primitives.py;
\ the file's main job is to show realistic uses of the assembler vocab —
\ what the calling convention guarantees, when manual stack housekeeping
\ is needed, and where a single Z80 instruction earns its keep.


\ Pointer arithmetic
\ ──────────────────
\ TOS lives in HL by convention, so `inc_hl inc_hl` and `dec_hl dec_hl`
\ are all that's needed to move a pointer by one cell.  cell+ / cell-
\ are address-typed; 2+ / 2- are value-typed and assemble identically.

::: cell+ ( addr -- addr+2 )
    inc_hl inc_hl ;

::: cell- ( addr -- addr-2 )
    dec_hl dec_hl ;

::: 2+ ( n -- n+2 )
    inc_hl inc_hl ;

::: 2- ( n -- n-2 )
    dec_hl dec_hl ;


\ Conditional duplicate
\ ─────────────────────
\ ?dup pushes a copy of TOS only when it's non-zero.  `or h` after
\ `ld a, l` sets the zero flag iff both halves of HL are zero, so the
\ jr_z skips the push for the falsy case and falls through otherwise.
\
\ Now that ?dup ships in stdlib/core.fs, this definition is guarded
\ with [defined] [if] so the file can still be loaded after the
\ auto-bundled stdlib without colliding.  The body is still here as
\ the canonical teaching copy referenced from docs/asm-words.md.

[defined] ?dup [if]
[else]
::: ?dup ( n -- 0 | n n )
    ld_a_l or_h
    jr_z skip
    push_hl
    label skip ;
[then]


\ Byte increment in place
\ ───────────────────────
\ TOS is already in HL, so HL-indirect addressing works without first
\ parking the address.  After the bump, pop a fresh TOS off the data
\ stack since this word's effect consumes the address.

::: 1c+! ( addr -- )
    inc_ind_hl
    pop_hl ;

::: 1c-! ( addr -- )
    dec_ind_hl
    pop_hl ;


\ LDIR-based fill
\ ───────────────
\ Fill `count` bytes starting at `addr` with `byte`.  Seeds the first
\ byte manually, then uses LDIR to propagate the seed by pointing HL
\ at the seed and DE one byte ahead — the source slides forward as
\ each write happens, so each subsequent byte sees the previous write.
\ Two boundary guards are required: LDIR with BC == 0 means 65536 (not
\ zero) so we early-exit on count == 0; and seeding then immediately
\ LDIR-ing with BC == 1 would overrun by one, so count == 1 also exits
\ after the seed write.

::: fill-byte  ( addr count byte -- )
    pop_bc
    pop_de
    ld_a_b or_c
    jr_z done
    ld_a_l
    ld_ind_de_a
    dec_bc
    ld_a_b or_c
    jr_z done
    ld_h_d ld_l_e
    inc_de
    ldir
    label done
    pop_hl ;


\ Bit testing
\ ───────────
\ Returns 1 if the low bit of TOS is set, else 0.  `1 and` clears all
\ but bit 0; the result is then placed back in HL with a zeroed high
\ byte to satisfy the cell-width contract on the data stack.

::: bit0? ( n -- flag )
    ld_a_l 1 and_n
    ld_l_a 0 ld_h_n ;
