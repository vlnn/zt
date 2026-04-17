import pytest

from zt.asm import Asm
from zt.compiler import Compiler, CompileError, compile_and_run
from zt.primitives import create_zbranch


def make_compiler(origin: int = 0x8000) -> Compiler:
    return Compiler(origin=origin)


def _asm_with_next() -> Asm:
    a = Asm(0x8000)
    a.label("NEXT")
    return a


class TestZbranchPrimitive:

    def test_starts_with_test_hl(self):
        a = _asm_with_next()
        create_zbranch(a)
        out = a.resolve()
        assert out[0] == 0x7C, "0BRANCH should start with LD A,H"
        assert out[1] == 0xB5, "0BRANCH should follow with OR L"

    def test_pops_new_tos(self):
        a = _asm_with_next()
        create_zbranch(a)
        out = a.resolve()
        assert out[2] == 0xE1, "0BRANCH should POP HL for new TOS"

    def test_has_conditional_skip(self):
        a = _asm_with_next()
        create_zbranch(a)
        out = a.resolve()
        assert out[3] == 0x20, "0BRANCH should JR NZ to skip path"

    def test_take_path_loads_target_from_ix(self):
        a = _asm_with_next()
        create_zbranch(a)
        out = a.resolve()
        take_start = 5
        assert out[take_start:take_start + 3] == bytes([0xDD, 0x5E, 0x00]), \
            "0BRANCH take path should LD E,(IX+0)"
        assert out[take_start + 3:take_start + 6] == bytes([0xDD, 0x56, 0x01]), \
            "0BRANCH take path should LD D,(IX+1)"

    def test_skip_path_advances_ix_twice(self):
        a = _asm_with_next()
        create_zbranch(a)
        out = a.resolve()
        jr_offset = out[4]
        skip_start = 5 + jr_offset
        assert out[skip_start:skip_start + 2] == bytes([0xDD, 0x23]), \
            "0BRANCH skip path should INC IX"
        assert out[skip_start + 2:skip_start + 4] == bytes([0xDD, 0x23]), \
            "0BRANCH skip path should INC IX again"

    def test_registered_in_compiler(self):
        c = make_compiler()
        assert "0branch" in c.words, "0branch should be registered"
        assert c.words["0branch"].address >= 0x8000, \
            "0branch should have a valid address"


class TestIfThen:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 1 if 42 then halt ;", [42],
         "true IF should execute body"),
        (": main 0 if 42 then halt ;", [],
         "false IF should skip body"),
        (": main 1 if 42 then 99 halt ;", [42, 99],
         "code after THEN should always run on true"),
        (": main 0 if 42 then 99 halt ;", [99],
         "false IF should skip to THEN then continue"),
    ], ids=["true-if", "false-if", "after-then-true", "after-then-false"])
    def test_if_then(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc

    def test_compiles_zbranch_cell(self):
        c = make_compiler()
        c.compile_source(": test if 42 then ;")
        word = c.words["test"]
        image = c.build()
        body_offset = word.address - c.origin + 3
        cell_at = lambda off: int.from_bytes(image[off:off + 2], "little")
        assert cell_at(body_offset) == c.words["0branch"].address, \
            "IF should compile 0BRANCH as first cell"

    def test_patches_forward_to_after_body(self):
        c = make_compiler()
        c.compile_source(": test if 42 then ;")
        word = c.words["test"]
        image = c.build()
        body_offset = word.address - c.origin + 3
        cell_at = lambda off: int.from_bytes(image[off:off + 2], "little")
        zbranch_target = cell_at(body_offset + 2)
        exit_offset = body_offset + 8
        assert cell_at(exit_offset) == c.words["exit"].address, \
            "last cell should be EXIT"
        assert zbranch_target == c.origin + exit_offset, \
            "0BRANCH target should point past the IF body"


class TestIfElseThen:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 1 if 10 else 20 then halt ;", [10],
         "true IF should take true branch"),
        (": main 0 if 10 else 20 then halt ;", [20],
         "false IF should take ELSE branch"),
        (": main 1 if 10 else 20 then 99 halt ;", [10, 99],
         "code after THEN runs after true branch"),
        (": main 0 if 10 else 20 then 99 halt ;", [20, 99],
         "code after THEN runs after false branch"),
    ], ids=["true-branch", "false-branch", "after-true", "after-false"])
    def test_if_else_then(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


class TestNestedIf:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 1 if 1 if 42 then then halt ;", [42],
         "nested true-true should reach inner body"),
        (": main 1 if 0 if 42 then then halt ;", [],
         "nested true-false should skip inner body"),
        (": main 0 if 1 if 42 then then halt ;", [],
         "nested false-X should skip everything"),
        (": main 1 if 0 if 42 else 99 then then halt ;", [99],
         "nested IF/ELSE should take inner ELSE on false"),
        (": main 1 if 1 if 42 else 99 then then halt ;", [42],
         "nested IF/ELSE should take inner IF on true"),
    ], ids=["true-true", "true-false", "false-any", "inner-else-false", "inner-else-true"])
    def test_nested_if(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


class TestBeginUntil:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 0 begin 1+ dup 5 = until halt ;", [5],
         "should loop until condition is true"),
        (": main 10 begin 1- dup 0= until halt ;", [0],
         "should count down to zero"),
        (": main 1 begin 2* dup 64 > until halt ;", [128],
         "should double until > 64"),
    ], ids=["count-up-5", "count-down-0", "double-to-128"])
    def test_begin_until(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc

    def test_compiles_zbranch_back(self):
        c = make_compiler()
        c.compile_source(": test begin dup until ;")
        word = c.words["test"]
        image = c.build()
        body_offset = word.address - c.origin + 3
        cell_at = lambda off: int.from_bytes(image[off:off + 2], "little")
        begin_addr = c.origin + body_offset
        assert cell_at(body_offset) == c.words["dup"].address, \
            "first cell should be DUP"
        assert cell_at(body_offset + 2) == c.words["0branch"].address, \
            "UNTIL should compile 0BRANCH"
        assert cell_at(body_offset + 4) == begin_addr, \
            "UNTIL target should point back to BEGIN"


class TestBeginWhileRepeat:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 0 begin dup 5 < while 1+ repeat halt ;", [5],
         "should loop while condition holds"),
        (": main 10 begin dup 0 > while 1- repeat halt ;", [0],
         "should count down to 0"),
        (": main 0 begin dup 0 < while 1+ repeat halt ;", [0],
         "false on first pass should skip body"),
    ], ids=["count-up-5", "count-down-0", "skip-body"])
    def test_begin_while_repeat(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


class TestControlFlowInColonWords:

    @pytest.mark.parametrize("src,expected,desc", [
        (": abs dup 0< if negate then ; : main -7 abs halt ;", [7],
         "abs of negative should negate"),
        (": abs dup 0< if negate then ; : main 7 abs halt ;", [7],
         "abs of positive should be identity"),
        (": max 2dup < if swap then drop ; : main 3 7 max halt ;", [7],
         "max should return the larger value"),
        (": max 2dup < if swap then drop ; : main 9 2 max halt ;", [9],
         "max with first larger should return first"),
        (": fac dup 1 > if dup 1- recurse * else drop 1 then ;"
         " : main 5 fac halt ;", [120],
         "recursive factorial 5! should be 120"),
        (": fac dup 1 > if dup 1- recurse * else drop 1 then ;"
         " : main 1 fac halt ;", [1],
         "factorial of 1 should be 1"),
    ], ids=["abs-neg", "abs-pos", "max-second", "max-first", "fac-5", "fac-1"])
    def test_colon_with_control(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


class TestMixedControlFlow:

    def test_if_inside_begin_until(self):
        src = (
            ": main 0 "
            "  begin "
            "    1+ dup 2 = if 100 swap then "
            "    dup 5 = "
            "  until halt ;"
        )
        assert compile_and_run(src) == [100, 5], \
            "IF inside BEGIN/UNTIL should work correctly"

    def test_if_inside_begin_while_repeat(self):
        src = (
            ": even? dup 2/ 2* = ; "
            ": main 0 0 "
            "  begin dup 6 < while "
            "    dup even? if swap 1+ swap then "
            "    1+ "
            "  repeat drop halt ;"
        )
        assert compile_and_run(src) == [3], \
            "IF inside WHILE loop should count even numbers in 0..5"

    def test_begin_until_inside_if(self):
        src = (
            ": main 1 if "
            "  0 begin 1+ dup 3 = until "
            "then halt ;"
        )
        assert compile_and_run(src) == [3], \
            "BEGIN/UNTIL nested inside IF should work"

    def test_begin_again_still_works(self):
        from zt.compiler import Compiler
        from zt.sim import Z80

        c = Compiler()
        c.compile_source(": main 0 begin dup border 1+ again ;")
        c.compile_main_call()
        image = c.build()

        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run(max_ticks=50_000)

        border_writes = [v for port, v in m._outputs if (port & 0xFF) == 0xFE]
        assert border_writes[:4] == [0, 1, 2, 3], \
            "BEGIN/AGAIN should still work after refactor"


class TestControlFlowErrors:

    def test_then_without_if(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack underflow"):
            c.compile_source(": bad then ;")

    def test_else_without_if(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack underflow"):
            c.compile_source(": bad else ;")

    def test_until_without_begin(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack underflow"):
            c.compile_source(": bad 1 until ;")

    def test_repeat_without_begin(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control"):
            c.compile_source(": bad begin repeat ;")

    def test_while_without_begin(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack underflow"):
            c.compile_source(": bad 1 while ;")

    def test_again_with_if_tag(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="mismatch"):
            c.compile_source(": bad if again ;")

    def test_until_with_if_tag(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="mismatch"):
            c.compile_source(": bad if 1 until ;")

    def test_unclosed_if_in_colon(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unclosed"):
            c.compile_source(": bad if 42 ;")

    def test_unclosed_begin_in_colon(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unclosed"):
            c.compile_source(": bad begin 42 ;")

    def test_again_without_begin(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack underflow"):
            c.compile_source(": bad again ;")
