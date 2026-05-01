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

( ----- LDIR-based fill ----- )

( Fill `count` bytes starting at `addr` with `byte`. Seeds the first byte )
( manually, then uses LDIR to propagate the seed across the rest by      )
( pointing HL at the seed and DE one byte ahead. Boundary cases need     )
( explicit guards: LDIR with BC == 0 means 65536, not zero.              )

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

( ----- Bit testing on low byte ----- )

( Returns 1 if low bit of TOS is set, else 0. )
::: bit0? ( n -- flag )
    ld_a_l 1 and_n
    ld_l_a 0 ld_h_n ;
