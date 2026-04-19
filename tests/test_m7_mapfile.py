"""Milestone-7 tests for `mapfile`: format auto-detection and Fuse / ZEsarUX rendering."""
import pytest

from zt.compile.compiler import Compiler
from zt.format.mapfile import FUSE, ZESARUX, detect_format, render, write_map


@pytest.fixture
def compiler() -> Compiler:
    c = Compiler()
    c.compile_source(": double dup + ;\n: square dup * ;\n")
    return c


class TestDetectFormat:
    @pytest.mark.parametrize("filename,expected", [
        ("out.map", FUSE),
        ("out.sym", ZESARUX),
        ("out.zesarux", ZESARUX),
        ("out.MAP", FUSE),
        ("out.unknown", FUSE),
    ])
    def test_detects_from_extension(self, tmp_path, filename, expected):
        assert detect_format(tmp_path / filename) == expected, \
            f"{filename} should detect to {expected}"


class TestFuseFormat:
    def test_line_format(self, compiler):
        out = render(compiler, FUSE)
        assert "$" in out, "fuse format should use $ prefix on addresses"
        assert " double" in out, "fuse format should list double by name"

    def test_sorted_by_address(self, compiler):
        out = render(compiler, FUSE)
        lines = [l for l in out.splitlines() if l]
        addresses = [int(l.split()[0].lstrip("$"), 16) for l in lines]
        assert addresses == sorted(addresses), \
            "fuse map lines should be sorted by address"

    def test_colon_words_present(self, compiler):
        out = render(compiler, FUSE)
        assert "double" in out, "double should appear in map"
        assert "square" in out, "square should appear in map"

    def test_immediates_excluded(self, compiler):
        out = render(compiler, FUSE)
        assert " if\n" not in out and out.endswith("\n"), \
            "immediate directives with address=0 should be excluded"


class TestZesaruxFormat:
    def test_line_format(self, compiler):
        out = render(compiler, ZESARUX)
        assert " = $" in out, "zesarux format should use 'name = $addr'"

    def test_double_present(self, compiler):
        out = render(compiler, ZESARUX)
        assert any(line.startswith("double = $") for line in out.splitlines()), \
            "double should appear in zesarux map with '= $' syntax"


class TestWriteMap:
    def test_writes_file(self, tmp_path, compiler):
        target = tmp_path / "out.map"
        write_map(compiler, target)
        assert target.exists(), "write_map should create the output file"

    @pytest.mark.parametrize("suffix,needle", [
        (".map", "$"),
        (".sym", " = $"),
    ])
    def test_format_follows_extension(self, tmp_path, compiler, suffix, needle):
        target = tmp_path / f"out{suffix}"
        write_map(compiler, target)
        assert needle in target.read_text(), \
            f"{suffix} output should contain {needle!r}"

    def test_explicit_format_overrides_extension(self, tmp_path, compiler):
        target = tmp_path / "out.map"
        write_map(compiler, target, fmt=ZESARUX)
        assert " = $" in target.read_text(), \
            "explicit fmt=ZESARUX should override .map extension"
