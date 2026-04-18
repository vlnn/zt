import hashlib

import pytest

from zt.compiler import Compiler
from zt.debug import SourceEntry


def make_compiler() -> Compiler:
    return Compiler(inline_primitives=False, inline_next=False)


@pytest.fixture
def compiler() -> Compiler:
    return make_compiler()


class TestWordSourceLocation:
    def test_colon_records_line(self, compiler):
        compiler.compile_source("\n\n: double dup + ;\n", source="mod.fs")
        w = compiler.words["double"]
        assert w.source_line == 3, "double should record its definition line 3"
        assert w.source_file == "mod.fs", "double should record its source file"

    def test_variable_records_source(self, compiler):
        compiler.compile_source("\nvariable counter\n", source="a.fs")
        w = compiler.words["counter"]
        assert w.source_line == 2, "counter should be marked at line 2"
        assert w.source_file == "a.fs", "counter should record source_file a.fs"

    def test_constant_records_source(self, compiler):
        compiler.compile_source("42 constant answer\n", source="a.fs")
        w = compiler.words["answer"]
        assert w.source_line == 1, "answer should be marked at line 1"
        assert w.source_file == "a.fs", "answer should record source_file a.fs"

    def test_primitives_have_no_source_location(self, compiler):
        w = compiler.words["dup"]
        assert w.source_file is None, "primitives should not claim a Forth source file"
        assert w.source_line is None, "primitives should not claim a Forth source line"

    @pytest.mark.parametrize("prefix,expected_line", [
        ("", 1),
        ("\n", 2),
        ("\n\n\n", 4),
    ])
    def test_line_offset(self, compiler, prefix, expected_line):
        compiler.compile_source(f"{prefix}: a 1 ;\n", source="f.fs")
        assert compiler.words["a"].source_line == expected_line, \
            f"word a after {len(prefix)} leading newlines should be at line {expected_line}"


class TestColonBody:
    def test_body_populated(self, compiler):
        compiler.compile_source(": double dup + ;\n")
        assert len(compiler.words["double"].body) > 0, \
            "double.body should be populated after compilation"

    def test_body_contains_primitive_refs(self, compiler):
        from zt.ir import PrimRef
        compiler.compile_source(": double dup + ;\n")
        w = compiler.words["double"]
        assert PrimRef("dup") in w.body, \
            "double.body should contain a PrimRef for dup"
        assert PrimRef("+") in w.body, \
            "double.body should contain a PrimRef for +"

    def test_body_contains_literal_cell(self, compiler):
        from zt.ir import Literal
        compiler.compile_source(": five 5 ;\n")
        w = compiler.words["five"]
        assert Literal(5) in w.body, \
            "five.body should contain a Literal(5) cell"

    def test_body_ends_with_exit(self, compiler):
        from zt.ir import PrimRef
        compiler.compile_source(": x 1 ;\n")
        assert compiler.words["x"].body[-1] == PrimRef("exit"), \
            "body of a colon word should end with a PrimRef(exit) cell"

    def test_primitive_has_empty_body(self, compiler):
        assert compiler.words["dup"].body == [], \
            "primitive words should have an empty body"

    def test_variable_has_empty_body(self, compiler):
        compiler.compile_source("variable x\n")
        assert compiler.words["x"].body == [], \
            "variables should have an empty body"

    def test_nested_definitions_keep_separate_bodies(self, compiler):
        from zt.ir import Literal
        compiler.compile_source(": a 5 ;\n: b 7 ;\n")
        a_body = compiler.words["a"].body
        b_body = compiler.words["b"].body
        assert Literal(5) in a_body and Literal(7) not in a_body, \
            "a.body should contain only cells from a"
        assert Literal(7) in b_body and Literal(5) not in b_body, \
            "b.body should contain only cells from b"

class TestSourceMap:
    def test_populated(self, compiler):
        compiler.compile_source(": f 1 + ;\n", source="x.fs")
        assert len(compiler.source_map) > 0, \
            "source_map should have entries after compiling code"

    def test_all_entries_are_source_entry(self, compiler):
        compiler.compile_source(": f 1 ;\n", source="x.fs")
        assert all(isinstance(e, SourceEntry) for e in compiler.source_map), \
            "every source_map entry should be a SourceEntry instance"

    def test_addresses_are_monotonic(self, compiler):
        compiler.compile_source(": f 1 2 3 + + ;\n")
        addrs = [e.address for e in compiler.source_map]
        assert addrs == sorted(addrs), \
            "source_map addresses should be non-decreasing"

    def test_entries_cover_used_lines(self, compiler):
        compiler.compile_source(": f\n  1\n  + ;\n", source="m.fs")
        lines = {e.line for e in compiler.source_map}
        assert {2, 3} <= lines, \
            "source_map should record lines 2 and 3 from the multi-line definition"

    def test_source_file_preserved(self, compiler):
        compiler.compile_source(": f 1 ;\n", source="abc.fs")
        files = {e.source_file for e in compiler.source_map}
        assert files == {"abc.fs"}, \
            "every source_map entry should carry source_file 'abc.fs'"


class TestImageUnchanged:
    @pytest.mark.parametrize("src", [
        ": double dup + ;\n",
        ": f 1 2 + ;\n",
        "variable x\n: main 5 x ! ;\n",
        ": loop1 0 begin 1+ dup 10 = until ;\n",
        ": choose 5 > if 1 else 0 then ;\n",
    ])
    def test_build_still_produces_image(self, src):
        c = make_compiler()
        c.compile_source(src)
        image = c.build()
        assert len(image) > 0, f"build should produce a non-empty image for {src!r}"

    @pytest.mark.parametrize("src", [
        ": f 1 + ;\n",
        ": double dup + ;\n",
        "variable x\n: main 5 x ! ;\n",
    ])
    def test_build_is_deterministic(self, src):
        c1 = make_compiler(); c1.compile_source(src)
        c2 = make_compiler(); c2.compile_source(src)
        h1 = hashlib.sha256(c1.build()).hexdigest()
        h2 = hashlib.sha256(c2.build()).hexdigest()
        assert h1 == h2, \
            f"two identical compilations should produce byte-identical images for {src!r}"
