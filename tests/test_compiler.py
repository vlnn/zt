from __future__ import annotations

import pytest

from zt.asm import Asm
from zt.compiler import Compiler, CompileError, Word
from zt.primitives import PRIMITIVES
from zt.sim import ForthMachine


def make_compiler(origin: int = 0x8000) -> Compiler:
    return Compiler(origin=origin)


class TestWordDataclass:

    def test_word_fields(self):
        w = Word(name="dup", address=0x8010, kind="prim")
        assert w.name == "dup", "Word should store name"
        assert w.address == 0x8010, "Word should store address"
        assert w.kind == "prim", "Word should store kind"
        assert w.immediate is False, "Word should default to non-immediate"

    def test_word_immediate(self):
        w = Word(name="if", address=0x8020, kind="prim", immediate=True)
        assert w.immediate is True, "Word should accept immediate flag"


class TestRegisterPrimitives:

    def test_known_primitives_registered(self):
        c = make_compiler()
        assert "dup" in c.words, "dup should be registered"
        assert "+" in c.words, "+ should be registered"
        assert "!" in c.words, "! should be registered"
        assert "*" in c.words, "* should be registered"

    def test_primitive_word_kind(self):
        c = make_compiler()
        assert c.words["dup"].kind == "prim", "dup should be a primitive"

    def test_primitive_addresses_are_positive(self):
        c = make_compiler()
        for name, word in c.words.items():
            if word.compile_action is not None:
                continue
            assert word.address >= 0x8000, f"{name} address should be >= origin"

    def test_all_primitives_from_list_registered(self):
        c = make_compiler()
        required = ["dup", "drop", "swap", "over", "+", "-", "*",
                     "@", "!", "=", "<", ">", "0=", "lit", "branch", "halt"]
        for name in required:
            assert name.lower() in c.words or name.upper() in c.words, (
                f"{name} should be registered as a word"
            )


class TestCompileToken:

    def test_colon_starts_compilation(self):
        c = make_compiler()
        c.compile_source(": double dup + ;")
        assert "double" in c.words, ": should create a new word"
        assert c.words["double"].kind == "colon", "colon definition should have kind 'colon'"

    def test_semicolon_returns_to_interpret(self):
        c = make_compiler()
        c.compile_source(": double dup + ;")
        assert c.state == "interpret", "; should return to interpret state"

    def test_nested_colon_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="nested"):
            c.compile_source(": foo : bar ;")

    def test_semicolon_outside_colon_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError):
            c.compile_source(";")

    def test_unknown_word_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unknown"):
            c.compile_source(": foo blarg ;")

    def test_unclosed_colon_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unclosed"):
            c.compile_source(": foo dup +")


class TestNumberParsing:

    @pytest.mark.parametrize("src,expected_value", [
        ("42", 42),
        ("-7", -7),
        ("0", 0),
        ("$ff", 255),
        ("$FF", 255),
        ("%1010", 10),
        ("$4000", 16384),
    ])
    def test_number_in_colon_compiles_literal(self, src, expected_value):
        c = make_compiler()
        c.compile_source(f": test {src} ;")
        assert "test" in c.words, "word should be created"


class TestColonBody:

    def test_colon_body_contains_docol_call(self):
        c = make_compiler()
        c.compile_source(": double dup + ;")
        word = c.words["double"]
        image = c.build()
        offset = word.address - c.origin
        assert image[offset] == 0xCD, "colon word should start with CALL opcode"
        docol_addr = c.words["docol"].address
        assert image[offset + 1] == (docol_addr & 0xFF), "CALL target low byte should be DOCOL"
        assert image[offset + 2] == ((docol_addr >> 8) & 0xFF), "CALL target high byte should be DOCOL"

    def test_colon_body_ends_with_exit(self):
        c = make_compiler()
        c.compile_source(": double dup + ;")
        word = c.words["double"]
        image = c.build()
        offset = word.address - c.origin
        exit_addr = c.words["exit"].address
        body_start = offset + 3
        dup_cell = int.from_bytes(image[body_start:body_start + 2], "little")
        plus_cell = int.from_bytes(image[body_start + 2:body_start + 4], "little")
        exit_cell = int.from_bytes(image[body_start + 4:body_start + 6], "little")
        assert dup_cell == c.words["dup"].address, "first cell should be DUP address"
        assert plus_cell == c.words["+"].address, "second cell should be PLUS address"
        assert exit_cell == exit_addr, "last cell should be EXIT address"


class TestCompileAndRun:

    @pytest.fixture
    def fm(self):
        return ForthMachine()

    def _compile_and_run(self, source: str) -> list[int]:
        c = make_compiler()
        c.compile_source(source)
        c.compile_main_call()
        image = c.build()
        fm = ForthMachine.__new__(ForthMachine)
        fm.origin = c.origin
        fm.data_stack_top = 0xFF00
        fm.return_stack_top = 0xFE00
        fm._prim_asm = c.asm
        fm._prim_code = image
        fm._body_base = c.asm.here

        from zt.sim import Z80, _read_data_stack, SPECTRUM_BORDER_PORT
        m = Z80()
        m.load(c.origin, image)
        start_addr = c.words["_start"].address
        m.pc = start_addr
        m.run()
        if not m.halted:
            raise TimeoutError("execution timed out")
        return _read_data_stack(m, 0xFF00, False)

    @pytest.mark.parametrize("src,expected", [
        (": main 21 dup + halt ;", [42]),
        (": double dup + ; : main 21 double halt ;", [42]),
        (": sq dup * ; : main 7 sq halt ;", [49]),
        (": main 3 4 + halt ;", [7]),
        (": main 10 3 - halt ;", [7]),
        (": main 6 7 * halt ;", [42]),
    ], ids=["dup-plus", "double", "square", "3+4", "10-3", "6*7"])
    def test_compile_and_run(self, src, expected):
        result = self._compile_and_run(src)
        assert result == expected, f"'{src}' should produce {expected}"


class TestVariable:

    def _compile_and_run(self, source: str) -> list[int]:
        return TestCompileAndRun._compile_and_run(None, source)

    def test_variable_creates_word(self):
        c = make_compiler()
        c.compile_source("variable x : main halt ;")
        assert "x" in c.words, "variable should create a word"
        assert c.words["x"].kind == "variable", "variable word should have kind 'variable'"

    def test_variable_store_and_fetch(self):
        result = self._compile_and_run("variable x : main 42 x ! x @ halt ;")
        assert result == [42], "variable should support store and fetch"

    def test_two_variables_independent(self):
        result = self._compile_and_run(
            "variable a variable b : main 10 a ! 20 b ! a @ b @ + halt ;"
        )
        assert result == [30], "two variables should be independent"


class TestConstant:

    def _compile_and_run(self, source: str) -> list[int]:
        return TestCompileAndRun._compile_and_run(None, source)

    def test_constant_creates_word(self):
        c = make_compiler()
        c.compile_source("42 constant answer : main halt ;")
        assert "answer" in c.words, "constant should create a word"
        assert c.words["answer"].kind == "constant", "constant word should have kind 'constant'"

    def test_constant_pushes_value(self):
        result = self._compile_and_run("42 constant answer : main answer halt ;")
        assert result == [42], "constant should push its value"

    def test_constant_used_twice(self):
        result = self._compile_and_run("10 constant ten : main ten ten + halt ;")
        assert result == [20], "constant should push same value each time"

    def test_hex_constant(self):
        result = self._compile_and_run("$ff constant mask : main mask halt ;")
        assert result == [255], "constant should accept hex values"


class TestCreate:

    def _compile_and_run(self, source: str) -> list[int]:
        return TestCompileAndRun._compile_and_run(None, source)

    def test_create_with_comma(self):
        result = self._compile_and_run(
            "create tbl 10 , 20 , 30 , : main tbl @ halt ;"
        )
        assert result == [10], "create + , should lay down accessible data"

    def test_create_with_c_comma(self):
        result = self._compile_and_run(
            "create buf 65 c, 66 c, : main buf c@ halt ;"
        )
        assert result == [65], "create + c, should lay down byte data"

    def test_allot_reserves_space(self):
        c = make_compiler()
        c.compile_source("create buf 10 allot : main halt ;")
        here_before = c.words["buf"].address
        assert c.asm.here > here_before, "allot should advance HERE"


class TestBeginAgain:

    def test_begin_again_compiles(self):
        c = make_compiler()
        c.compile_source(": loop begin dup 1+ again ;")
        assert "loop" in c.words, "begin/again should compile without error"

    def test_begin_again_branch_target(self):
        c = make_compiler()
        c.compile_source(": loop begin dup again ;")
        word = c.words["loop"]
        image = c.build()
        body_offset = word.address - c.origin + 3
        dup_addr = c.words["dup"].address
        branch_addr = c.words["branch"].address
        cell_at = lambda off: int.from_bytes(image[off:off + 2], "little")
        assert cell_at(body_offset) == dup_addr, "first cell should be DUP"
        assert cell_at(body_offset + 2) == branch_addr, "second cell should be BRANCH"
        target = cell_at(body_offset + 4)
        begin_addr = c.origin + body_offset
        assert target == begin_addr, "BRANCH target should point back to BEGIN"

    def test_again_without_begin_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="control stack"):
            c.compile_source(": bad again ;")


class TestLiteralBrackets:

    def test_bracket_switches_state(self):
        c = make_compiler()
        c.compile_source(": test [ ] 42 ;")
        assert "test" in c.words, "[ ] should not break compilation"

    def test_tick_compiles_lit_with_address(self):
        c = make_compiler()
        c.compile_source(": test ['] dup ;")
        word = c.words["test"]
        image = c.build()
        body_offset = word.address - c.origin + 3
        lit_addr = c.words["lit"].address
        dup_addr = c.words["dup"].address
        cell_at = lambda off: int.from_bytes(image[off:off + 2], "little")
        assert cell_at(body_offset) == lit_addr, "['] should compile LIT"
        assert cell_at(body_offset + 2) == dup_addr, "['] should compile target address"

    def test_recurse_compiles_self_reference(self):
        c = make_compiler()
        c.compile_source(": countdown 1- dup recurse ;")
        word = c.words["countdown"]
        image = c.build()
        body_offset = word.address - c.origin + 3
        cell_at = lambda off: int.from_bytes(image[off:off + 2], "little")
        assert cell_at(body_offset + 4) == word.address, "RECURSE should compile own address"

    def test_tick_unknown_word_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unknown"):
            c.compile_source(": test ['] nonexistent ;")
