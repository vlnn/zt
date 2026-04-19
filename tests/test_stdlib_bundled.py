from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


class TestIncludeStdlibBundled:

    def test_include_stdlib_loads_core_fs_regardless_of_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        c = Compiler()
        c.include_stdlib()
        assert "cr" in c.words, (
            "include_stdlib() should load bundled core.fs regardless of CWD"
        )

    def test_include_stdlib_records_bundled_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        c = Compiler()
        c.include_stdlib()
        assert any(p.name == "core.fs" for p in c.include_resolver.seen_paths()), (
            "bundled core.fs should be recorded in include_resolver.seen_paths()"
        )

    def test_include_stdlib_explicit_path_overrides_bundled(self, tmp_path):
        override = _write(tmp_path / "mystdlib.fs", ": my-marker 42 ;")
        c = Compiler()
        c.include_stdlib(override)
        assert "my-marker" in c.words, (
            "explicit path argument should override the bundled stdlib"
        )


class TestBundledStdlibResolvesViaInclude:

    @pytest.mark.parametrize("bundled_name", ["core.fs", "test-lib.fs"])
    def test_bundled_file_resolves_by_bare_name(self, tmp_path, bundled_name, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main = _write(
            tmp_path / "main.fs",
            f"include {bundled_name}\n: main halt ;",
        )
        c = Compiler()
        c.compile_source(main.read_text(), source=str(main))
        assert any(p.name == bundled_name for p in c.include_resolver.seen_paths()), (
            f"`include {bundled_name}` should resolve via the bundled stdlib"
        )

    def test_user_include_dir_shadows_bundled_stdlib(self, tmp_path):
        shadow_dir = tmp_path / "shadows"
        shadow_dir.mkdir()
        _write(shadow_dir / "core.fs", ": shadow-marker 999 ;")
        main = _write(
            tmp_path / "main.fs",
            "include core.fs\n: main halt ;",
        )
        c = Compiler(include_dirs=[shadow_dir])
        c.compile_source(main.read_text(), source=str(main))
        assert "shadow-marker" in c.words, (
            "user --include-dir should take precedence over bundled stdlib"
        )

    def test_missing_file_error_mentions_bundled_stdlib_path(self, tmp_path):
        from zt.compile.compiler import CompileError

        c = Compiler()
        with pytest.raises(CompileError) as exc:
            c.compile_source("include definitely-not-there.fs")
        assert "stdlib" in str(exc.value), (
            "error message should list the bundled stdlib dir as a searched path"
        )
