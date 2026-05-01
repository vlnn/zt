( Examples of primitives written via ::: that don't exist in primitives.py. )
( Each one is a real, useful word with a runtime test in           )
( tests/test_examples_asm_primitives.py.                            )

( ----- Pointer / cell arithmetic ----- )

::: cell+ ( addr -- addr+2 )
    inc_hl inc_hl ;

::: cell- ( addr -- addr-2 )
    dec_hl dec_hl ;

::: 2+ ( n -- n+2 )
    inc_hl inc_hl ;

::: 2- ( n -- n-2 )
    dec_hl dec_hl ;

( ----- Conditional duplicate ----- )

( If TOS is zero, leave it alone. If non-zero, leave a copy underneath. )
::: ?dup ( n -- 0 | n n )
    ld_a_l or_h
    jr_z skip
    push_hl
    label skip ;

( ----- Byte memory increment / decrement at address ----- )

( TOS is already in HL by the calling convention, so HL-indirect addressing )
( works without parking. After the work, pop a fresh TOS from the data )
( stack since this word's effect consumes the address. )

::: 1c+! ( addr -- )
    inc_ind_hl
    pop_hl ;

::: 1c-! ( addr -- )
    dec_ind_hl
    pop_hl ;

( ----- Bit testing on low byte ----- )

( Returns 1 if low bit of TOS is set, else 0. )
::: bit0? ( n -- flag )
    ld_a_l 1 and_n
    ld_l_a 0 ld_h_n ;
