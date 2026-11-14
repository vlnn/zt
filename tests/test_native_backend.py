"""
Differential tests for the native backend: every program must leave the same data stack,
screen memory and port writes as the threaded build of the same source.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from native_harness import run_both, run_program

PROGRAMS = {
    "literals": ": main 1 2 3 -1 $7FFF halt ;",
    "add-sub": ": main 7 5 + 100 58 - 3 10 - halt ;",
    "multiply": ": main 6 7 * 300 300 * -3 4 * halt ;",
    "unsigned-divide": ": main 100 7 u/mod 65535 256 u/mod halt ;",
    "signed-divide": ": main -17 5 /mod 17 -5 / -17 5 mod halt ;",
    "unary": ": main 5 negate -5 abs 7 1+ 7 1- 7 2* -8 2/ halt ;",
    "min-max": ": main 3 9 min 3 9 max -3 2 min -3 2 max halt ;",
    "bitwise": ": main $F0F0 $0FF0 and $F0F0 $0FF0 or $F0F0 $0FF0 xor 5 invert halt ;",
    "shifts": ": main 1 4 lshift $8000 3 rshift halt ;",
    "equality": ": main 3 3 = 3 4 = 3 3 <> 3 4 <> 0 0= 5 0= halt ;",
    "ordering": ": main 3 4 < 4 3 < 3 4 > 4 3 > -1 0< 1 0< 1 $FFFF u< halt ;",
    "stack-shuffles": ": main 1 2 swap 3 over 4 5 6 rot 7 8 nip 9 10 tuck halt ;",
    "double-cell-shuffles": ": main 1 2 2dup 3 4 2drop 5 6 7 8 2swap halt ;",
    "minus-rot-and-qdup": ": main 1 2 3 -rot 0 ?dup 5 ?dup halt ;",
    "return-stack": ": main 1 2 >r 3 r@ r> + + halt ;",
    "variable": "variable v : main 42 v ! v @ 8 v +! v @ halt ;",
    "two-variables": "variable a variable b : main 1 a ! 2 b ! a @ b @ a @ halt ;",
    "constant": "17 constant k : main k k + halt ;",
    "byte-memory": "create buf 4 allot : main 300 buf c! buf c@ 7 buf 3 + c! buf 3 + c@ halt ;",
    "comma-data": "create t 10 , 20 , 30 , : main t @ t 2 + @ t 4 + @ + + halt ;",
    "c-comma-data": "create t 1 c, 2 c, 3 c, : main t c@ t 1+ c@ t 2 + c@ halt ;",
    "word-array": "w: xs 100 200 300 ; : main xs @ xs 2 + @ xs 6 + @ halt ;",
    "byte-array": "c: xs 7 8 9 ; : main xs @ xs 2 + c@ xs 4 + c@ halt ;",
    "fill-and-cmove": (
        "create a 8 allot create b 8 allot "
        ": main a 8 65 fill a b 8 cmove b c@ b 7 + c@ halt ;"
    ),
    "if-then": ": pick-one if 11 then ; : main 1 pick-one 0 pick-one 99 halt ;",
    "if-else": ": sign 0< if -1 else 1 then ; : main -5 sign 5 sign halt ;",
    "begin-until": ": main 0 begin 1+ dup 10 = until halt ;",
    "begin-while-repeat": ": main 1 begin dup 100 < while 2* repeat halt ;",
    "begin-again-exit": ": count 0 begin 1+ dup 5 = if exit then again ; : main count halt ;",
    "do-loop": ": main 0 10 0 do i + loop halt ;",
    "do-loop-in-callee": ": sum 0 swap 0 do i + loop ; : main 10 sum 100 sum halt ;",
    "plus-loop-up": ": main 0 20 0 do i + 3 +loop halt ;",
    "plus-loop-down": ": main 0 0 10 do i + -2 +loop halt ;",
    "nested-loops": ": main 0 4 0 do 3 0 do i j * + loop loop halt ;",
    "leave": ": main 0 10 0 do i 5 = if leave then i + loop halt ;",
    "unloop-exit": ": find 10 0 do i 6 = if i unloop exit then loop -1 ; : main find halt ;",
    "case": (
        ": name case 1 of 10 endof 2 of 20 endof 99 swap endcase ; "
        ": main 1 name 2 name 3 name halt ;"
    ),
    "recursion": ": fact dup 1 > if dup 1- recurse * then ; : main 6 fact halt ;",
    "double-recursion": (
        ": fib dup 2 < if exit then dup 1- recurse swap 2 - recurse + ; "
        ": main 12 fib halt ;"
    ),
    "call-chain": (
        ": a 1+ ; : b a a ; : c b b * ; : d dup c swap c + ; : main 3 d halt ;"
    ),
    "early-exit-non-leaf": (
        ": big dup * ; : pick dup 3 < if drop 0 exit then big ; "
        ": main 2 pick 9 pick halt ;"
    ),
    "leaf-with-loop": ": tri 0 swap 1+ 0 do i + loop ; : main 4 tri 10 tri halt ;",
    "return-stack-across-call": ": inner 5 ; : outer 7 >r inner r> + ; : main outer halt ;",
    "execute-colon": ": double 2* ; : main 21 ['] double execute halt ;",
    "execute-primitive": ": main 5 ['] dup execute halt ;",
    "execute-out-of-line-primitive": ": main 6 7 ['] * execute halt ;",
    "execute-constant": "33 constant k : main ['] k execute halt ;",
    "execute-variable": "variable v : main 9 v ! ['] v execute @ halt ;",
    "execute-recursive-callback": (
        ": apply execute ; : twice dup apply apply ; "
        ": inc 1+ ; : main 5 ['] inc dup >r apply r> apply halt ;"
    ),
    "tick-table": (
        ": first 11 ; : second 22 ; create table ' first , ' second , "
        ": main table @ execute table 2 + @ execute halt ;"
    ),
    "tick-table-in-array": (
        ": ten 10 ; : twenty 20 ; w: handlers ' ten ' twenty ; "
        ": main handlers 2 + @ execute handlers 4 + @ execute halt ;"
    ),
    "tick-data-pointer": (
        "variable target create ptr ' target , : main 77 target ! ptr @ @ halt ;"
    ),
    "string-type": ': main ." HELLO" 1 halt ;',
    "string-literal": ': main s" ABC" swap c@ halt ;',
    "emit-and-cr": ": main 65 emit cr 66 emit 2 halt ;",
    "number-printing": ": main 123 . -45 . 9 u. halt ;",
    "at-xy": ": main 5 3 at-xy 88 emit halt ;",
    "cls": ": main 2 5 cls 1 halt ;",
    "border": ": main 3 border 5 border halt ;",
    "struct-static-fusion": (
        "0 2 -- .x 2 -- .y 1 -- .hp struct /actor  /actor record hero "
        ": main 10 hero .x + ! 20 hero .y + ! 7 hero .hp + c! "
        "hero .x + @ hero .y + @ hero .hp + c@ halt ;"
    ),
    "struct-dynamic-fusion": (
        "0 2 -- .x 2 -- .y struct /pt  /pt record p "
        ": set-y .y + ! ; : get-y .y + @ ; : main 55 p set-y p get-y halt ;"
    ),
    "struct-sugar": (
        "0 2 -- .x 2 -- .y struct /pt  /pt record p "
        ": main 31 p .y >! p .y >@ halt ;"
    ),
    "force-inline-colon": ":: bump 1+ 1+ ; : main 5 bump bump halt ;",
    "asm-word": "::: triple ( n -- 3n ) ld_d_h ld_e_l add_hl_hl add_hl_de ; : main 7 triple halt ;",
    "asm-word-with-label": (
        "::: clamp8 ( n -- n ) ld_a_h or_a jr_z done 255 ld_hl_nn label done ; "
        ": main 300 clamp8 halt ;"
    ),
    "times-macro": ": main 1 [times] 4 2* halt ;",
    "peephole-forms": ": main 5 1 + 5 1 - 5 2 * 0 1 halt ;",
    "key-query-idle": ": main key? halt ;",
    "deep-data-stack": ": main 20 0 do i loop 0 20 0 do + loop halt ;",
}


@lru_cache(maxsize=None)
def _run(name: str):
    return run_both(PROGRAMS[name])


class TestSameObservableBehaviour:

    @pytest.mark.parametrize("name", PROGRAMS)
    def test_threaded_program_halts(self, name):
        threaded, _ = _run(name)
        assert threaded.halted, f"{name!r} should halt under the threaded reference build"

    @pytest.mark.parametrize("name", PROGRAMS)
    def test_native_leaves_the_same_stack(self, name):
        threaded, native = _run(name)
        assert native.stack == threaded.stack, \
            f"native {name!r} should leave the same data stack as the threaded build"

    @pytest.mark.parametrize("name", PROGRAMS)
    def test_native_draws_the_same_screen(self, name):
        threaded, native = _run(name)
        assert native.screen == threaded.screen, \
            f"native {name!r} should leave identical screen memory"

    @pytest.mark.parametrize("name", PROGRAMS)
    def test_native_writes_the_same_ports(self, name):
        threaded, native = _run(name)
        assert native.port_writes == threaded.port_writes, \
            f"native {name!r} should make the same port writes in the same order"

    @pytest.mark.parametrize("name", PROGRAMS)
    def test_native_halts(self, name):
        _, native = _run(name)
        assert native.halted, f"native {name!r} should reach HALT"


class TestKeyboardInput:

    SOURCE = ": main key key key? halt ;"

    def test_threaded_reference_sees_the_key(self):
        threaded = run_program(self.SOURCE, native=False, input_buffer=b"AB")
        assert threaded.stack[0] == ord("A"), \
            "the threaded reference should read the first buffered key"

    def test_native_reads_the_same_keys(self):
        threaded = run_program(self.SOURCE, native=False, input_buffer=b"AB")
        native = run_program(self.SOURCE, native=True, input_buffer=b"AB")
        assert native.stack == threaded.stack, \
            "native KEY and KEY? should return what the threaded build returns"


class TestNativeIsFaster:

    @pytest.mark.parametrize("name", PROGRAMS)
    def test_native_is_never_slower(self, name):
        threaded, native = _run(name)
        assert native.t_states < threaded.t_states, \
            f"native {name!r} should take fewer T-states than the threaded build"

    @pytest.mark.parametrize("name", [
        "do-loop", "double-recursion", "call-chain", "begin-while-repeat",
    ])
    def test_dispatch_heavy_program_at_least_doubles_in_speed(self, name):
        threaded, native = _run(name)
        assert native.t_states * 2 < threaded.t_states, \
            f"native {name!r} should run in under half the threaded T-states"
