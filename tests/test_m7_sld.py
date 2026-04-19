"""
Milestone-7 tests for SLD output: header, `|T` trace lines, `|L` label lines, and `write_sld`.
"""
import pytest

from zt.compiler import Compiler
from zt.sld import HEADER, render, write_sld


@pytest.fixture
def compiler() -> Compiler:
    c = Compiler()
    c.compile_source(": double dup + ;\n", source="mod.fs")
    return c


class TestHeader:
    def test_version_declaration_first(self, compiler):
        out = render(compiler)
        assert out.startswith("|SLD.data.version|1\n"), \
            "SLD output should start with the version declaration"

    def test_device_declaration_second(self, compiler):
        out = render(compiler)
        assert "device:ZXSPECTRUM48" in out.splitlines()[1], \
            "second SLD line should declare the device"

    def test_header_present_for_empty_compiler(self):
        empty = Compiler()
        out = render(empty)
        assert out == HEADER, "empty compiler should emit only the header"


class TestTraceLines:
    def test_every_source_map_entry_has_trace_line(self, compiler):
        out = render(compiler)
        trace_count = sum(1 for line in out.splitlines() if line.endswith("|T|"))
        assert trace_count == len(compiler.source_map), \
            "each source_map entry should produce one T line"

    def test_trace_uses_nine_pipe_fields(self, compiler):
        out = render(compiler)
        trace_lines = [l for l in out.splitlines() if l.endswith("|T|")]
        for line in trace_lines:
            assert line.count("|") == 8, \
                f"SLD T line should have 8 pipe separators (9 fields): {line}"

    def test_trace_carries_address(self, compiler):
        out = render(compiler)
        addresses = {e.address for e in compiler.source_map}
        for addr in addresses:
            assert f"|{addr}|T|" in out, \
                f"address {addr} should appear as a T-line value"


class TestLabelLines:
    def test_colon_word_gets_label_line(self, compiler):
        out = render(compiler)
        assert "|L|double" in out, \
            "colon word 'double' should produce an L line"

    def test_primitives_have_no_label_lines(self, compiler):
        out = render(compiler)
        assert "|L|dup" not in out, \
            "primitives without source location should not produce L lines"


class TestWriteSld:
    def test_writes_file(self, tmp_path, compiler):
        target = tmp_path / "out.sld"
        write_sld(compiler, target)
        assert target.read_text().startswith("|SLD.data.version|"), \
            "written sld file should begin with the version marker"
