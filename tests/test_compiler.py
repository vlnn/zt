"""
Unit tests for `Compiler`: primitive registration, number parsing, colon bodies, variables, constants, `CREATE`, data addresses, `BEGIN / AGAIN`.
"""
from __future__ import annotations

import pytest

from zt.compiler import Compiler, CompileError, Word, compile_and_run


def make_compiler(origin: int = 0x8000) -> Compiler:
    return Compiler(origin=origin, inline_primitives=False, inline_next=False)


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

    @pytest.mark.parametrize("src,expected", [
        (": main 21 dup + halt ;", [42]),
        (": double dup + ; : main 21 double halt ;", [42]),
        (": sq dup * ; : main 7 sq halt ;", [49]),
        (": main 3 4 + halt ;", [7]),
        (": main 10 3 - halt ;", [7]),
        (": main 6 7 * halt ;", [42]),
    ], ids=["dup-plus", "double", "square", "3+4", "10-3", "6*7"])
    def test_compile_and_run(self, src, expected):
        assert compile_and_run(src) == expected, f"'{src}' should produce {expected}"


class TestVariable:

    def test_variable_creates_word(self):
        c = make_compiler()
        c.compile_source("variable x : main halt ;")
        assert "x" in c.words, "variable should create a word"
        assert c.words["x"].kind == "variable", "variable word should have kind 'variable'"

    def test_variable_store_and_fetch(self):
        assert compile_and_run("variable x : main 42 x ! x @ halt ;") == [42], \
            "variable should support store and fetch"

    def test_two_variables_independent(self):
        result = compile_and_run(
            "variable a variable b : main 10 a ! 20 b ! a @ b @ + halt ;"
        )
        assert result == [30], "two variables should be independent"


class TestConstant:

    def test_constant_creates_word(self):
        c = make_compiler()
        c.compile_source("42 constant answer : main halt ;")
        assert "answer" in c.words, "constant should create a word"
        assert c.words["answer"].kind == "constant", "constant word should have kind 'constant'"

    def test_constant_pushes_value(self):
        assert compile_and_run("42 constant answer : main answer halt ;") == [42], \
            "constant should push its value"

    def test_constant_used_twice(self):
        assert compile_and_run("10 constant ten : main ten ten + halt ;") == [20], \
            "constant should push same value each time"

    def test_hex_constant(self):
        assert compile_and_run("$ff constant mask : main mask halt ;") == [255], \
            "constant should accept hex values"


class TestCreate:

    def test_create_with_comma(self):
        result = compile_and_run(
            "create tbl 10 , 20 , 30 , : main tbl @ halt ;"
        )
        assert result == [10], "create + , should lay down accessible data"

    def test_create_with_c_comma(self):
        result = compile_and_run(
            "create buf 65 c, 66 c, : main buf c@ halt ;"
        )
        assert result == [65], "create + c, should lay down byte data"

    def test_allot_reserves_space(self):
        c = make_compiler()
        c.compile_source("create buf 10 allot : main halt ;")
        here_before = c.words["buf"].address
        assert c.asm.here > here_before, "allot should advance HERE"


class TestDataAddress:

    @pytest.mark.parametrize("src,name", [
        ("variable x",         "x"),
        ("create buf 10 allot", "buf"),
        ("create tbl 1 , 2 ,",  "tbl"),
    ], ids=["variable", "create-allot", "create-comma"])
    def test_word_with_data_exposes_data_address(self, src, name):
        c = make_compiler()
        c.compile_source(src)
        word = c.words[name]
        assert word.data_address is not None, \
            f"{name!r} should expose data_address so the harness can read its data slot"
        assert word.data_address > word.address, \
            "data_address should sit past the pusher shim, not at or before it"

    @pytest.mark.parametrize("src,name", [
        ("42 constant answer",      "answer"),
        (": double dup + ;",        "double"),
    ], ids=["constant", "colon"])
    def test_word_without_data_has_none(self, src, name):
        c = make_compiler()
        c.compile_source(src)
        assert c.words[name].data_address is None, \
            f"{name!r} has no data slot; data_address should be None"

    def test_primitives_have_none(self):
        c = make_compiler()
        assert c.words["dup"].data_address is None, \
            "primitives have no data slot; data_address should be None"

    def test_variable_data_address_is_writable(self):
        c = make_compiler()
        c.compile_source("variable x : main 42 x ! halt ;")
        word = c.words["x"]
        image = c.build()
        offset = word.data_address - c.origin
        assert image[offset] == 0 and image[offset + 1] == 0, \
            "freshly compiled variable cell should start as 0"

    def test_variable_data_address_is_what_pusher_pushes(self):
        c = make_compiler()
        c.compile_source("variable x")
        word = c.words["x"]
        image = c.build()
        shim_offset = word.address - c.origin
        pushed_low = image[shim_offset + 2]
        pushed_high = image[shim_offset + 3]
        pushed = pushed_low | (pushed_high << 8)
        assert pushed == word.data_address, \
            "the pusher's LD HL,nn literal should equal word.data_address"


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


class TestErrorReporting:

    def test_error_has_line_and_col(self):
        c = make_compiler()
        with pytest.raises(CompileError) as exc_info:
            c.compile_source(": test blarg ;")
        msg = str(exc_info.value)
        assert "<input>:1:8:" in msg, "error should include source:line:col"

    def test_error_on_second_line(self):
        c = make_compiler()
        with pytest.raises(CompileError) as exc_info:
            c.compile_source(": test\n  blarg ;")
        msg = str(exc_info.value)
        assert ":2:" in msg, "error on second line should report line 2"

    def test_error_with_custom_source(self):
        c = make_compiler()
        with pytest.raises(CompileError) as exc_info:
            c.compile_source(": test blarg ;", source="demo.fs")
        msg = str(exc_info.value)
        assert "demo.fs:" in msg, "error should include custom source filename"

    def test_unclosed_colon_reports_word_name(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unclosed.*myword"):
            c.compile_source(": myword dup +")

    def test_missing_main_raises(self):
        c = make_compiler()
        c.compile_source(": notmain 42 ;")
        with pytest.raises(CompileError, match="main"):
            c.compile_main_call()


class TestIntegration:

    @pytest.mark.parametrize("src,expected", [
        (": double dup + ; : quad double double ; : main 10 quad halt ;", [40]),
        (": main 1 2 3 rot + + halt ;", [6]),
        (": main 100 1- 1- 1- halt ;", [97]),
        (": main 5 2* 2* halt ;", [20]),
        ("variable x : main 7 x ! x @ dup * halt ;", [49]),
        ("3 constant n : main n n * n + halt ;", [12]),
        (": main 0 1 2 3 4 drop drop drop drop halt ;", [0]),
        (": main $ff $ff00 or halt ;", [0xFFFF]),
        ("create pair 3 , 7 , : main pair dup @ swap 2 + @ + halt ;", [10]),
    ], ids=[
        "quad", "rot-add", "dec-three", "shift-left-twice",
        "var-square", "const-expr", "drop-chain", "or-hex", "create-pair",
    ])
    def test_programs(self, src, expected):
        assert compile_and_run(src) == expected, f"'{src}' should produce {expected}"


class TestCounterDemo:

    def test_counter_compiles(self):
        from zt.image import build_from_forth
        image = build_from_forth()
        assert len(image) > 100, "compiled counter demo should produce substantial image"

    def test_counter_runs_border_writes(self):
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
        assert len(border_writes) > 5, "counter should produce border writes"
        assert border_writes[:6] == [0, 1, 2, 3, 4, 5], \
            "counter should cycle through border values 0,1,2,..."

    def test_counter_from_fs_file(self):
        from pathlib import Path
        from zt.compiler import Compiler
        from zt.sim import Z80

        fs_path = Path(__file__).parent.parent / "examples" / "counter.fs"
        source = fs_path.read_text()

        c = Compiler()
        c.compile_source(source, source=str(fs_path))
        c.compile_main_call()
        image = c.build()

        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run(max_ticks=50_000)

        border_writes = [v for port, v in m._outputs if (port & 0xFF) == 0xFE]
        assert border_writes[:6] == [0, 1, 2, 3, 4, 5], \
            "counter.fs should produce sequential border writes"

    def test_cli_build_produces_sna(self, tmp_path):
        from pathlib import Path
        from zt.sna import SNA_TOTAL_SIZE, SNA_HEADER_SIZE, SNA_RAM_BASE
        from zt.sim import Z80

        fs_path = Path(__file__).parent.parent / "examples" / "counter.fs"
        sna_path = tmp_path / "counter.sna"

        from zt.cli import main
        import sys
        old_argv = sys.argv
        sys.argv = ["zt", "build", str(fs_path), "-o", str(sna_path)]
        try:
            main()
        finally:
            sys.argv = old_argv

        sna = sna_path.read_bytes()
        assert len(sna) == SNA_TOTAL_SIZE, "CLI should produce valid 48K SNA"

        sp = sna[0x17] | (sna[0x18] << 8)
        pc = sna[SNA_HEADER_SIZE + sp - SNA_RAM_BASE] | \
             (sna[SNA_HEADER_SIZE + sp - SNA_RAM_BASE + 1] << 8)

        m = Z80()
        m.mem[SNA_RAM_BASE:] = sna[SNA_HEADER_SIZE:]
        m.sp = sp + 2
        m.pc = pc
        m.run(max_ticks=50_000)

        border_writes = [v for port, v in m._outputs if (port & 0xFF) == 0xFE]
        assert border_writes[:6] == [0, 1, 2, 3, 4, 5], \
            "SNA built by CLI should run correctly"
