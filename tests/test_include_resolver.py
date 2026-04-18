from pathlib import Path

import pytest

from zt.include_resolver import IncludeResolver, IncludeNotFound


@pytest.fixture
def tmp_fs(tmp_path: Path) -> Path:
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "math.fs").write_text("\\ math lib\n")
    (tmp_path / "lib" / "screen.fs").write_text("\\ screen lib\n")
    (tmp_path / "main.fs").write_text(": main halt ;\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "main.fs").write_text(": main halt ;\n")
    (tmp_path / "sub" / "helper.fs").write_text("\\ sibling of sub/main.fs\n")
    return tmp_path


class TestAbsolutePath:

    def test_resolves_existing_absolute_path(self, tmp_fs):
        target = tmp_fs / "lib" / "math.fs"
        resolver = IncludeResolver([])
        result = resolver.resolve(str(target), source_path=Path("anywhere.fs"))
        assert result == target.resolve(), (
            "an absolute path pointing at a real file should resolve to itself"
        )

    def test_missing_absolute_path_raises(self, tmp_fs):
        resolver = IncludeResolver([])
        with pytest.raises(IncludeNotFound, match="missing.fs"):
            resolver.resolve(
                str(tmp_fs / "missing.fs"),
                source_path=Path("anywhere.fs"),
            )


class TestRelativeToSource:

    def test_finds_file_next_to_source(self, tmp_fs):
        resolver = IncludeResolver([])
        result = resolver.resolve(
            "helper.fs",
            source_path=tmp_fs / "sub" / "main.fs",
        )
        assert result == (tmp_fs / "sub" / "helper.fs").resolve(), (
            "relative include should be resolved relative to the source file's directory"
        )

    def test_skips_source_dir_when_source_is_not_a_file(self, tmp_fs):
        resolver = IncludeResolver([tmp_fs / "lib"])
        result = resolver.resolve(
            "math.fs",
            source_path=Path("<input>"),
        )
        assert result == (tmp_fs / "lib" / "math.fs").resolve(), (
            "when source_path is not a real file, resolution should fall back to include_dirs"
        )


class TestSearchDirs:

    def test_finds_file_in_search_dir(self, tmp_fs):
        resolver = IncludeResolver([tmp_fs / "lib"])
        result = resolver.resolve(
            "math.fs",
            source_path=tmp_fs / "main.fs",
        )
        assert result == (tmp_fs / "lib" / "math.fs").resolve(), (
            "file absent next to source but present in include_dirs should resolve via the dir"
        )

    def test_source_dir_takes_priority_over_search_dirs(self, tmp_fs):
        (tmp_fs / "sub" / "math.fs").write_text("\\ sub-local math\n")
        resolver = IncludeResolver([tmp_fs / "lib"])
        result = resolver.resolve(
            "math.fs",
            source_path=tmp_fs / "sub" / "main.fs",
        )
        assert result == (tmp_fs / "sub" / "math.fs").resolve(), (
            "the source file's directory should be searched before include_dirs"
        )

    def test_first_matching_dir_wins(self, tmp_fs):
        (tmp_fs / "first").mkdir()
        (tmp_fs / "first" / "x.fs").write_text("first x\n")
        (tmp_fs / "second").mkdir()
        (tmp_fs / "second" / "x.fs").write_text("second x\n")
        resolver = IncludeResolver([tmp_fs / "first", tmp_fs / "second"])
        result = resolver.resolve("x.fs", source_path=Path("<input>"))
        assert result == (tmp_fs / "first" / "x.fs").resolve(), (
            "earlier include_dirs should shadow later ones"
        )


class TestNotFound:

    def test_missing_file_raises_include_not_found(self, tmp_fs):
        resolver = IncludeResolver([tmp_fs / "lib"])
        with pytest.raises(IncludeNotFound, match="missing.fs"):
            resolver.resolve("missing.fs", source_path=tmp_fs / "main.fs")

    def test_error_lists_all_searched_paths(self, tmp_fs):
        resolver = IncludeResolver([tmp_fs / "lib", tmp_fs / "other"])
        with pytest.raises(IncludeNotFound) as exc_info:
            resolver.resolve("missing.fs", source_path=tmp_fs / "main.fs")
        msg = str(exc_info.value)
        assert "lib" in msg and "other" in msg, (
            "not-found error should enumerate all searched directories to aid debugging"
        )


class TestDedupe:

    def test_has_seen_is_false_initially(self, tmp_fs):
        resolver = IncludeResolver([])
        assert resolver.has_seen(tmp_fs / "main.fs") is False, (
            "a fresh resolver should report no files seen yet"
        )

    def test_mark_seen_then_has_seen_is_true(self, tmp_fs):
        resolver = IncludeResolver([])
        path = tmp_fs / "main.fs"
        resolver.mark_seen(path)
        assert resolver.has_seen(path) is True, (
            "after mark_seen, has_seen should return True for that path"
        )

    def test_seen_paths_are_independent(self, tmp_fs):
        resolver = IncludeResolver([])
        resolver.mark_seen(tmp_fs / "main.fs")
        assert resolver.has_seen(tmp_fs / "other.fs") is False, (
            "marking one path should not affect seen status of unrelated paths"
        )
