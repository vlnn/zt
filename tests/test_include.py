"""
End-to-end tests for `INCLUDE` / `REQUIRE` via the compiler: relative resolution, include-dir fallback, error reporting, and dedupe semantics.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compiler import Compiler, CompileError, compile_and_run


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


class TestIncludeResolution:

    def test_include_resolves_relative_to_including_file(self, tmp_path: Path):
        _write(tmp_path / "lib.fs", ": double dup + ;")
        main = _write(tmp_path / "main.fs",
                      "include lib.fs\n: main 21 double halt ;")
        c = Compiler()
        c.compile_source(main.read_text(), source=str(main))
        assert "double" in c.words, "INCLUDE should resolve relative to the including file"

    def test_include_falls_back_to_include_dir(self, tmp_path: Path):
        libdir = tmp_path / "libs"
        libdir.mkdir()
        _write(libdir / "helpers.fs", ": triple dup dup + + ;")
        c = Compiler(include_dirs=[libdir])
        c.compile_source("include helpers.fs\n: main halt ;")
        assert "triple" in c.words, "INCLUDE should fall back to --include-dir paths"

    def test_include_accepts_absolute_path(self, tmp_path: Path):
        lib = _write(tmp_path / "abs.fs", ": quad 2* 2* ;")
        c = Compiler()
        c.compile_source(f"include {lib}\n: main halt ;")
        assert "quad" in c.words, "INCLUDE should accept absolute paths"

    def test_nested_include(self, tmp_path: Path):
        _write(tmp_path / "inner.fs", ": inner-word 100 ;")
        _write(tmp_path / "outer.fs",
               "include inner.fs\n: outer-word inner-word ;")
        c = Compiler()
        c.compile_source(
            f"include {tmp_path / 'outer.fs'}\n: main outer-word halt ;"
        )
        assert "inner-word" in c.words, "nested INCLUDE should pull through inner file"
        assert "outer-word" in c.words, "outer file's own definitions should be registered"

    def test_include_dir_order_searched_after_current_file(self, tmp_path: Path):
        libdir = tmp_path / "libs"
        libdir.mkdir()
        _write(libdir / "shadow.fs", ": shadow 111 ;")
        main_dir = tmp_path / "main"
        main_dir.mkdir()
        _write(main_dir / "shadow.fs", ": shadow 222 ;")
        main = _write(main_dir / "main.fs",
                      "include shadow.fs\n: main halt ;")
        c = Compiler(include_dirs=[libdir])
        c.compile_source(main.read_text(), source=str(main))
        assert c.words["shadow"].kind == "colon", (
            "current file's directory should be searched before --include-dir"
        )


class TestIncludeErrors:

    def test_missing_file_raises(self):
        c = Compiler()
        with pytest.raises(CompileError, match="cannot find"):
            c.compile_source("include no_such.fs")

    def test_missing_file_reports_source_location(self):
        c = Compiler()
        with pytest.raises(CompileError) as exc:
            c.compile_source("include missing.fs", source="demo.fs")
        assert "demo.fs:1:" in str(exc.value), (
            "missing-include error should report source:line:col"
        )

    def test_include_without_filename_raises(self):
        c = Compiler()
        with pytest.raises(CompileError, match="expected filename"):
            c.compile_source("include")

    def test_include_with_number_as_filename_raises(self):
        c = Compiler()
        with pytest.raises(CompileError, match="expected filename"):
            c.compile_source("include 42")


class TestIncludeBehavioral:

    def test_included_word_actually_runs(self, tmp_path: Path):
        _write(tmp_path / "lib.fs", ": double dup + ;")
        src = f"include {tmp_path / 'lib.fs'}\n: main 21 double halt ;"
        assert compile_and_run(src) == [42], (
            "a word defined via INCLUDE should execute correctly"
        )

    def test_include_preserves_error_location_in_included_file(self, tmp_path: Path):
        lib = _write(tmp_path / "bad.fs", ": broken\n  unknown-word ;")
        c = Compiler()
        with pytest.raises(CompileError) as exc:
            c.compile_source(f"include {lib}")
        msg = str(exc.value)
        assert str(lib) in msg, "error inside included file should report that file"
        assert ":2:" in msg, "error inside included file should report correct line"


class TestRequire:

    def test_require_includes_file(self, tmp_path: Path):
        lib = _write(tmp_path / "lib.fs", ": double dup + ;")
        c = Compiler()
        c.compile_source(f"require {lib}\n: main 21 double halt ;")
        assert "double" in c.words, "REQUIRE should include the file at least once"

    def test_require_deduplicates(self, tmp_path: Path):
        lib = _write(tmp_path / "lib.fs", ": double dup + ;")
        c = Compiler()
        c.compile_source(
            f"require {lib}\nrequire {lib}\n: main halt ;"
        )
        assert c.include_resolver.seen_paths() == frozenset({lib.resolve()}), (
            "REQUIRE should mark the file as included exactly once"
        )

    def test_require_same_file_twice_still_runs(self, tmp_path: Path):
        lib = _write(tmp_path / "lib.fs", ": double dup + ;")
        src = f"require {lib}\nrequire {lib}\n: main 21 double halt ;"
        assert compile_and_run(src) == [42], (
            "require'd word should still execute when required twice"
        )

    def test_require_resolves_through_include_dir(self, tmp_path: Path):
        libdir = tmp_path / "lib"
        libdir.mkdir()
        _write(libdir / "m.fs", ": quad 2* 2* ;")
        c = Compiler(include_dirs=[libdir])
        c.compile_source("require m.fs\nrequire m.fs\n: main halt ;")
        assert "quad" in c.words, "REQUIRE should resolve through --include-dir"

    def test_mixed_include_then_require_dedupes(self, tmp_path: Path):
        lib = _write(tmp_path / "lib.fs", ": double dup + ;")
        c = Compiler()
        c.compile_source(
            f"include {lib}\nrequire {lib}\n: main halt ;"
        )
        assert "double" in c.words, (
            "include followed by require should not redefine and should succeed"
        )
