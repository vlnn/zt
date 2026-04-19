"""
Milestone-7 tests for `decompile`: basic colon words, literals, structured `begin`/`if`/`do` loops, early exit, and string literals with an image.
"""
import pytest

from zt.compile.compiler import Compiler
from zt.inspect.fsym import to_dict
from zt.inspect.decompile import decompile


def compile_and_dump(source: str) -> tuple[dict, bytes]:
    c = Compiler()
    c.compile_source(source)
    if "main" in c.words:
        c.compile_main_call()
    image = c.build()
    return to_dict(c), image


class TestDecompileBasics:
    def test_empty_program_produces_empty_output(self):
        d = {"origin": 0x8000, "words": {}}
        assert decompile(d) == "", "empty fsym should produce empty decompile"

    def test_colon_word_renders_as_colon_definition(self):
        d, _ = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        assert out.startswith(": double"), \
            "decompile should start with ': <n>' for the colon word"

    def test_header_includes_address(self):
        d, _ = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        addr = d["words"]["double"]["address"]
        assert f"${addr:04X}" in out, \
            "decompile header should include the word's hex address"

    def test_body_contains_primitive_names(self):
        d, _ = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        assert "dup" in out and "+" in out, \
            "decompile body should name the primitives dup and +"

    def test_exit_renders_as_semicolon(self):
        d, _ = compile_and_dump(": x 1 ;\n")
        out = decompile(d)
        assert out.rstrip().endswith(";"), \
            "decompiled word should end with ;"

    def test_primitives_are_not_decompiled(self):
        d, _ = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        assert ": dup" not in out, \
            "primitive dup should not be decompiled as a colon definition"

    @pytest.mark.parametrize("forth_op,spelled_out", [
        ("+", "plus"),
        ("-", "minus"),
        ("*", "star"),
        ("=", "equals"),
    ])
    def test_forth_alias_preferred_over_spelled_out_name(self, forth_op, spelled_out):
        d, _ = compile_and_dump(f": f {forth_op} ;\n")
        out = decompile(d)
        if spelled_out in d["words"]:
            assert spelled_out not in out, \
                f"decompile should prefer '{forth_op}' over its '{spelled_out}' alias"
            assert forth_op in out, \
                f"decompile should render {forth_op} rather than its long-form alias"


class TestLiterals:
    @pytest.mark.parametrize("source,literal", [
        (": five 5 ;\n", "5"),
        (": big 1000 ;\n", "1000"),
        (": neg -7 ;\n", "-7"),
    ])
    def test_literal_is_inlined_without_lit_marker(self, source, literal):
        d, _ = compile_and_dump(source)
        out = decompile(d)
        assert literal in out, f"literal {literal} should appear in decompile"
        assert "lit " not in out, \
            "raw 'lit' keyword should not appear; the value should inline it"


class TestStructuredBeginLoops:
    def test_begin_again_is_reconstructed(self):
        d, _ = compile_and_dump(": spin 0 begin 1+ again ;\n")
        out = decompile(d)
        assert "begin" in out and "again" in out, \
            "begin/again should be reconstructed as structured control flow"
        assert "branch $" not in out, \
            "raw 'branch $XXXX' should not appear once structured CF is applied"

    def test_begin_until_is_reconstructed(self):
        d, _ = compile_and_dump(": count 0 begin 1+ dup 10 = until ;\n")
        out = decompile(d)
        assert "begin" in out and "until" in out, \
            "begin/until should be reconstructed"
        assert "0branch $" not in out, \
            "raw '0branch $XXXX' should not appear once until is reconstructed"

    def test_begin_while_repeat_is_reconstructed(self):
        d, _ = compile_and_dump(": loop 0 begin dup 10 < while 1+ repeat ;\n")
        out = decompile(d)
        for keyword in ("begin", "while", "repeat"):
            assert keyword in out, \
                f"'{keyword}' should appear in reconstructed begin/while/repeat"
        assert "branch $" not in out and "0branch $" not in out, \
            "raw branches should be gone once while/repeat is reconstructed"


class TestStructuredConditionals:
    def test_if_then_is_reconstructed(self):
        d, _ = compile_and_dump(": g 1 if 2 then ;\n")
        out = decompile(d)
        assert "if" in out and "then" in out, \
            "if/then should be reconstructed"
        assert "0branch $" not in out, \
            "raw '0branch $' should not appear once if/then is reconstructed"

    def test_if_else_then_is_reconstructed(self):
        d, _ = compile_and_dump(": g 1 if 2 else 3 then ;\n")
        out = decompile(d)
        for keyword in ("if", "else", "then"):
            assert keyword in out, \
                f"'{keyword}' should appear in reconstructed if/else/then"

    def test_nested_if_is_reconstructed(self):
        d, _ = compile_and_dump(": g 1 if 2 if 3 then then ;\n")
        out = decompile(d)
        assert out.count("if") >= 2, \
            "both nested ifs should appear in decompile"
        assert out.count("then") >= 2, \
            "both matching thens should appear in decompile"


class TestStructuredDoLoop:
    def test_do_loop_is_reconstructed(self):
        d, _ = compile_and_dump(": f 10 0 do i drop loop ;\n")
        out = decompile(d)
        assert "do" in out and "loop" in out, \
            "do/loop should be reconstructed"
        assert "(do)" not in out and "(loop)" not in out, \
            "raw runtime primitive names should not appear in decompile"

    def test_leave_is_reconstructed(self):
        d, _ = compile_and_dump(": f 10 0 do i 5 = if leave then loop ;\n")
        out = decompile(d)
        assert "leave" in out, \
            "leave should be reconstructed from unloop+branch sequence"


class TestEarlyExit:
    def test_mid_body_exit_renders_as_exit_not_semicolon(self):
        d, _ = compile_and_dump(": f dup 0 < if exit then drop ;\n")
        out = decompile(d)
        assert "exit" in out, \
            "an explicit 'exit' inside an if should render as 'exit', not ';'"
        assert out.rstrip().endswith(";"), \
            "the final cell should still render as ';' to close the definition"


class TestStringLiteralWithImage:
    def test_dot_quote_reconstructed_when_image_provided(self):
        d, image = compile_and_dump(': main ." hello" ;\n')
        out = decompile(d, image=image)
        assert '." hello"' in out, \
            'with image, ." should be reconstructed with its literal text'

    def test_dot_quote_shows_raw_without_image(self):
        d, _ = compile_and_dump(': main ." hello" ;\n')
        out = decompile(d)
        assert "type" in out, \
            "without image, string literal should fall back to raw lit/lit/type"
        assert '." hello"' not in out, \
            "without image, inspect cannot reconstruct the string text"
