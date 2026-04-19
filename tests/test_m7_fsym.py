"""Milestone-7 tests for `to_dict` / `write_fsym` / `load_fsym` round-trip."""
import json

import pytest

from zt.compile.compiler import Compiler
from zt.inspect.fsym import load_fsym, to_dict, write_fsym


@pytest.fixture
def compiler() -> Compiler:
    c = Compiler()
    c.compile_source(": double dup + ;\nvariable counter\n", source="mod.fs")
    c.build()
    return c


class TestToDict:
    def test_has_origin(self, compiler):
        d = to_dict(compiler)
        assert d["origin"] == compiler.origin, \
            "fsym dict should record compiler.origin"

    def test_has_words(self, compiler):
        d = to_dict(compiler)
        assert "double" in d["words"], "double should appear in fsym words"
        assert "counter" in d["words"], "counter should appear in fsym words"
        assert "dup" in d["words"], "primitive dup should also appear in fsym words"

    def test_colon_carries_body(self, compiler):
        d = to_dict(compiler)
        double = d["words"]["double"]
        assert double["kind"] == "colon", "double should be kind 'colon'"
        assert isinstance(double["cells"], list) and double["cells"], \
            "double.cells should be a non-empty list"

    def test_primitive_has_no_body_key(self, compiler):
        d = to_dict(compiler)
        assert "cells" not in d["words"]["dup"], \
            "primitive without body should omit the cells key"

    def test_source_location_on_user_word(self, compiler):
        d = to_dict(compiler)
        assert d["words"]["double"]["source_file"] == "mod.fs", \
            "double should serialize source_file=mod.fs"
        assert d["words"]["double"]["source_line"] == 1, \
            "double should serialize source_line=1"


class TestRoundtrip:
    def test_write_then_load_is_identical(self, tmp_path, compiler):
        target = tmp_path / "out.fsym"
        write_fsym(compiler, target)
        loaded = load_fsym(target)
        assert loaded == to_dict(compiler), \
            "writing then loading fsym should yield an identical dict"

    def test_output_is_valid_json(self, tmp_path, compiler):
        target = tmp_path / "out.fsym"
        write_fsym(compiler, target)
        json.loads(target.read_text())

    def test_output_is_sorted(self, tmp_path, compiler):
        target = tmp_path / "out.fsym"
        write_fsym(compiler, target)
        text = target.read_text()
        assert '"origin"' in text, "fsym JSON should contain origin"
        assert '"words"' in text, "fsym JSON should contain words"
