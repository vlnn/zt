"""Milestone-7 tests for compiler-emitted warnings when a user word is redefined."""
import pytest

from zt.compiler import Compiler


class TestRedefinitionWarning:
    def test_redefining_user_word_produces_warning(self):
        c = Compiler()
        c.compile_source(": double dup + ;\n: double dup + dup + ;\n", source="a.fs")
        assert len(c.warnings) == 1, \
            "redefining a user colon word should produce exactly one warning"

    def test_warning_names_the_word(self):
        c = Compiler()
        c.compile_source(": double dup + ;\n: double dup + dup + ;\n", source="a.fs")
        assert "'double'" in c.warnings[0], \
            "warning should quote the redefined word name"

    def test_warning_cites_both_locations(self):
        c = Compiler()
        c.compile_source("\n: double dup + ;\n\n\n: double dup + dup + ;\n",
                         source="a.fs")
        msg = c.warnings[0]
        assert "a.fs:2" in msg, \
            "warning should cite the first definition's line"
        assert "a.fs:5" in msg, \
            "warning should cite the redefinition's line"

    def test_no_warning_for_new_word(self):
        c = Compiler()
        c.compile_source(": double dup + ;\n: square dup * ;\n")
        assert c.warnings == [], \
            "defining a fresh word should not produce warnings"

    def test_no_warning_when_shadowing_a_primitive(self):
        c = Compiler()
        c.compile_source(": dup dup dup ;\n")
        assert c.warnings == [], \
            "shadowing a primitive should not warn (Forth idiom)"

    def test_warnings_accumulate_across_multiple_redefinitions(self):
        c = Compiler()
        c.compile_source(": a 1 ;\n: a 2 ;\n: a 3 ;\n", source="x.fs")
        assert len(c.warnings) == 2, \
            "two redefinitions should produce two warnings"
