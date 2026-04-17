import pytest

from zt.asm import Asm
from zt.compiler import Compiler, CompileError, compile_and_run
from zt.primitives import create_zbranch, create_do_rt, create_loop_rt, create_ploop_rt
from zt.primitives import create_i_index, create_j_index, create_unloop


def make_compiler(origin: int = 0x8000) -> Compiler:
    return Compiler(origin=origin)


def _asm_with_next() -> Asm:
    a = Asm(0x8000)
    a.label("NEXT")
    return a


# ===== Tier 1: 0BRANCH primitive =====


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

    def test_registered_in_compiler(self):
        c = make_compiler()
        assert "0branch" in c.words, "0branch should be registered"


# ===== Tier 1: IF/THEN/ELSE =====


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


# ===== Tier 2: BEGIN/UNTIL, BEGIN/WHILE/REPEAT =====


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


# ===== Tier 2: control flow in colon words =====


class TestControlFlowInColonWords:

    @pytest.mark.parametrize("src,expected,desc", [
        (": abs dup 0< if negate then ; : main -7 abs halt ;", [7],
         "abs of negative should negate"),
        (": abs dup 0< if negate then ; : main 7 abs halt ;", [7],
         "abs of positive should be identity"),
        (": fac dup 1 > if dup 1- recurse * else drop 1 then ;"
         " : main 5 fac halt ;", [120],
         "recursive factorial 5! should be 120"),
    ], ids=["abs-neg", "abs-pos", "fac-5"])
    def test_colon_with_control(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


# ===== Tier 3: DO/LOOP primitives =====


class TestDoRtPrimitive:

    def test_pops_limit_from_stack(self):
        a = _asm_with_next()
        create_do_rt(a)
        out = a.resolve()
        assert out[0] == 0xD1, "(DO) should start with POP DE for limit"

    def test_pushes_to_return_stack(self):
        a = _asm_with_next()
        create_do_rt(a)
        out = a.resolve()
        assert out[1:3] == bytes([0xFD, 0x2B]), "(DO) should DEC IY"

    def test_registered_in_compiler(self):
        c = make_compiler()
        assert "(do)" in c.words, "(do) should be registered"
        assert "(loop)" in c.words, "(loop) should be registered"
        assert "(+loop)" in c.words, "(+loop) should be registered"
        assert "i" in c.words, "i should be registered"
        assert "j" in c.words, "j should be registered"
        assert "unloop" in c.words, "unloop should be registered"


class TestIIndexPrimitive:

    def test_pushes_hl_then_loads_from_iy(self):
        a = _asm_with_next()
        create_i_index(a)
        out = a.resolve()
        assert out[0] == 0xE5, "I should start with PUSH HL"
        assert out[1:4] == bytes([0xFD, 0x6E, 0x00]), "I should LD L,(IY+0)"
        assert out[4:7] == bytes([0xFD, 0x66, 0x01]), "I should LD H,(IY+1)"


class TestJIndexPrimitive:

    def test_reads_from_iy_plus_4(self):
        a = _asm_with_next()
        create_j_index(a)
        out = a.resolve()
        assert out[0] == 0xE5, "J should start with PUSH HL"
        assert out[1:4] == bytes([0xFD, 0x6E, 0x04]), "J should LD L,(IY+4)"
        assert out[4:7] == bytes([0xFD, 0x66, 0x05]), "J should LD H,(IY+5)"


class TestUnloopPrimitive:

    def test_increments_iy_four_times(self):
        a = _asm_with_next()
        create_unloop(a)
        out = a.resolve()
        assert out[0:2] == bytes([0xFD, 0x23]), "UNLOOP should INC IY"
        assert out[2:4] == bytes([0xFD, 0x23]), "UNLOOP should INC IY"
        assert out[4:6] == bytes([0xFD, 0x23]), "UNLOOP should INC IY"
        assert out[6:8] == bytes([0xFD, 0x23]), "UNLOOP should INC IY four times"


# ===== Tier 3: DO/LOOP integration =====


class TestDoLoop:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 0 10 0 do 1+ loop halt ;", [10],
         "DO/LOOP should iterate 10 times"),
        (": main 0 5 0 do i + loop halt ;", [10],
         "I should push loop index (0+1+2+3+4=10)"),
        (": main 0 3 1 do i + loop halt ;", [3],
         "DO with nonzero start should work (1+2=3)"),
    ], ids=["count-10", "sum-i", "nonzero-start"])
    def test_do_loop(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


class TestNestedDoLoop:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 0 3 0 do 3 0 do 1+ loop loop halt ;", [9],
         "nested 3x3 DO/LOOP should iterate 9 times"),
        (": main 0 3 0 do 2 0 do j + loop loop halt ;", [6],
         "J should read outer loop index (0+0+1+1+2+2=6)"),
        (": main 0 2 0 do 3 0 do i j * + loop loop halt ;", [3],
         "I*J in nested loops should sum products"),
    ], ids=["3x3-count", "j-sum", "i-j-product"])
    def test_nested_do_loop(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


class TestPlusLoop:

    @pytest.mark.parametrize("src,expected,desc", [
        (": main 0 10 0 do i + 2 +loop halt ;", [20],
         "+LOOP by 2 should sum even indices (0+2+4+6+8=20)"),
        (": main 0 10 0 do 1+ 3 +loop halt ;", [4],
         "+LOOP by 3 should iterate 4 times (0,3,6,9)"),
        (": main 0 0 10 do 1+ 1 negate +loop halt ;", [11],
         "+LOOP with negative step should count down (10,9,...,0)"),
    ], ids=["step-2-sum", "step-3-count", "negative-step"])
    def test_plus_loop(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc


class TestLeave:

    def test_leave_exits_loop(self):
        src = (
            ": main 0 10 0 do "
            "  i 5 = if leave then "
            "  i + "
            "loop halt ;"
        )
        assert compile_and_run(src) == [10], \
            "LEAVE at i=5 should exit with sum 0+1+2+3+4=10"

    def test_leave_skips_remaining_iterations(self):
        src = (
            ": main 0 100 0 do "
            "  1+ "
            "  dup 3 = if leave then "
            "loop halt ;"
        )
        assert compile_and_run(src) == [3], \
            "LEAVE should exit after 3 iterations"

    def test_leave_inside_nested_if(self):
        src = (
            ": main 0 10 0 do "
            "  i 2 > if "
            "    i 5 < if leave then "
            "  then "
            "  1+ "
            "loop halt ;"
        )
        assert compile_and_run(src) == [3], \
            "LEAVE inside nested IF should exit the DO loop"


# ===== Tier 3: mixed with tiers 1+2 =====


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

    def test_if_inside_do_loop(self):
        src = (
            ": main 0 10 0 do "
            "  i 2 / 2 * i = if 1+ then "
            "loop halt ;"
        )
        # This uses / which isn't available. Use 2/ instead.
        src = (
            ": main 0 10 0 do "
            "  i 2/ 2* i = if 1+ then "
            "loop halt ;"
        )
        assert compile_and_run(src) == [5], \
            "IF inside DO/LOOP should count even numbers 0..9"

    def test_do_loop_inside_begin_until(self):
        src = (
            ": sum5 0 5 0 do i + loop ; "
            ": main 0 begin 1+ dup 3 = until sum5 + halt ;"
        )
        assert compile_and_run(src) == [13], \
            "DO/LOOP inside a word called from BEGIN/UNTIL should work"

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


# ===== Error cases =====


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

    def test_loop_without_do(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack underflow"):
            c.compile_source(": bad loop ;")

    def test_plus_loop_without_do(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack underflow"):
            c.compile_source(": bad 1 +loop ;")

    def test_leave_without_do(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="LEAVE outside DO"):
            c.compile_source(": bad leave ;")

    def test_unclosed_do_in_colon(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unclosed"):
            c.compile_source(": bad 10 0 do i ;")

    def test_loop_with_begin_tag(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="mismatch"):
            c.compile_source(": bad begin loop ;")
