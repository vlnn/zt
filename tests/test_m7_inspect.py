import pytest

from zt.compiler import Compiler
from zt.fsym import to_dict
from zt.inspect import decompile


def compile_and_dump(source: str) -> dict:
    c = Compiler()
    c.compile_source(source)
    c.build()
    return to_dict(c)


class TestDecompileBasics:
    def test_empty_program_produces_empty_output(self):
        d = {"origin": 0x8000, "words": {}}
        assert decompile(d) == "", "empty fsym should produce empty decompile"

    def test_colon_word_renders_as_colon_definition(self):
        d = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        assert out.startswith(": double"), \
            "decompile should start with ': <name>' for the colon word"

    def test_header_includes_address(self):
        d = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        addr = d["words"]["double"]["address"]
        assert f"${addr:04X}" in out, \
            "decompile header should include the word's hex address"

    def test_body_contains_primitive_names(self):
        d = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        assert "dup" in out and "+" in out, \
            "decompile body should name the primitives dup and +"

    def test_exit_renders_as_semicolon(self):
        d = compile_and_dump(": x 1 ;\n")
        out = decompile(d)
        assert out.rstrip().endswith(";"), \
            "decompiled word should end with ;"

    def test_primitives_are_not_decompiled(self):
        d = compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        assert ": dup" not in out, \
            "primitive dup should not be decompiled as a colon definition"


class TestLiterals:
    @pytest.mark.parametrize("source,literal", [
        (": five 5 ;\n", "5"),
        (": big 1000 ;\n", "1000"),
        (": neg -7 ;\n", "-7"),
    ])
    def test_literal_is_inlined_without_lit_marker(self, source, literal):
        d = compile_and_dump(source)
        out = decompile(d)
        assert literal in out, f"literal {literal} should appear in decompile"
        assert "lit " not in out, \
            "raw 'lit' keyword should not appear; the value should inline it"


class TestControlFlow:
    def test_branch_shows_target_address(self):
        d = compile_and_dump(": loop 0 begin 1+ again ;\n")
        out = decompile(d)
        assert "branch $" in out, \
            "begin/again should decompile with 'branch $XXXX' in raw mode"

    def test_zbranch_shows_target_address(self):
        d = compile_and_dump(": g 1 if 2 then ;\n")
        out = decompile(d)
        assert "0branch $" in out, \
            "if/then should decompile with '0branch $XXXX' in raw mode"
