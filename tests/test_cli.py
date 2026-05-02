"""
Integration tests for `zt build` driven via subprocess: stdlib wiring, includes, map formats, profile output, and the inline-primitives flag.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent

SAMPLE_SOURCE = """\
: count-to-five  6 1 do i . loop cr ;
: greet          ." hi" cr count-to-five ;
: main           7 0 cls begin greet again ;
"""


@pytest.fixture
def sample_fs(tmp_path: Path) -> Path:
    """A self-contained Forth program with these properties:

    - Uses stdlib words (`cr`, `.`, `cls`) so `--no-stdlib` correctly fails.
    - Defines multiple colon words so map-file and tree-shake tests have
      something to inspect.
    - Halts on an infinite loop so `--profile-ticks` capping is testable.
    - Avoids `'`/`[']`/banking so auto-tree-shake applies cleanly.
    """
    path = tmp_path / "sample.fs"
    path.write_text(SAMPLE_SOURCE)
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zt.cli", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestCliStdlibDefault:

    def test_builds_without_stdlib_flag(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        result = _run_cli("build", str(sample_fs), "-o", str(out))
        assert result.returncode == 0, (
            f"build without --stdlib should succeed (stdlib is default); "
            f"stderr={result.stderr}"
        )
        assert out.exists(), "build should produce an output .sna file"
        assert out.stat().st_size == 49179, ".sna snapshots should be 49179 bytes"

    def test_fails_with_no_stdlib(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        result = _run_cli(
            "build", str(sample_fs), "-o", str(out), "--no-stdlib",
        )
        assert result.returncode != 0, (
            "--no-stdlib on a sample using cr/./cls should fail"
        )
        assert "unknown word" in result.stderr, (
            f"error should mention 'unknown word'; got: {result.stderr!r}"
        )

    def test_explicit_stdlib_flag_still_works(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        result = _run_cli(
            "build", str(sample_fs), "-o", str(out), "--stdlib",
        )
        assert result.returncode == 0, (
            "explicit --stdlib should still succeed for backwards compatibility"
        )


class TestCliNoStdlib:

    def test_primitives_only_program_builds_with_no_stdlib(self, tmp_path):
        src = tmp_path / "primitives_only.fs"
        src.write_text(": main 0 begin dup border 1+ again ;\n")
        out = tmp_path / "out.sna"
        result = _run_cli(
            "build", str(src), "-o", str(out), "--no-stdlib",
        )
        assert result.returncode == 0, (
            f"a program using only primitives should build with --no-stdlib; "
            f"stderr={result.stderr}"
        )


class TestCliInclude:

    def test_build_with_include(self, tmp_path):
        (tmp_path / "lib.fs").write_text(": double dup + ;")
        main = tmp_path / "main.fs"
        main.write_text("include lib.fs\n: main 21 double cr halt ;")
        out = tmp_path / "main.sna"
        result = _run_cli("build", str(main), "-o", str(out))
        assert result.returncode == 0, (
            f"build with INCLUDE should succeed; stderr={result.stderr}"
        )
        assert out.exists(), "CLI should produce .sna when INCLUDE resolves"

    def test_include_dir_flag(self, tmp_path):
        libdir = tmp_path / "libs"
        libdir.mkdir()
        (libdir / "helpers.fs").write_text(": triple dup dup + + ;")
        main = tmp_path / "main.fs"
        main.write_text("include helpers.fs\n: main 5 triple cr halt ;")
        out = tmp_path / "main.sna"
        result = _run_cli("build", str(main), "-o", str(out),
                          "--include-dir", str(libdir))
        assert result.returncode == 0, (
            f"--include-dir should let CLI resolve includes; stderr={result.stderr}"
        )

    def test_multiple_include_dirs(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        (a / "alpha.fs").write_text(": alpha 1 ;")
        (b / "beta.fs").write_text(": beta 2 ;")
        main = tmp_path / "main.fs"
        main.write_text(
            "include alpha.fs\ninclude beta.fs\n: main alpha beta + cr halt ;"
        )
        out = tmp_path / "main.sna"
        result = _run_cli("build", str(main), "-o", str(out),
                          "--include-dir", str(a),
                          "--include-dir", str(b))
        assert result.returncode == 0, (
            f"repeated --include-dir should accumulate paths; stderr={result.stderr}"
        )

    def test_missing_include_fails_with_location(self, tmp_path):
        main = tmp_path / "main.fs"
        main.write_text("include nonexistent.fs\n: main halt ;")
        out = tmp_path / "main.sna"
        result = _run_cli("build", str(main), "-o", str(out))
        assert result.returncode != 0, "missing include should fail the build"
        assert "cannot find" in result.stderr, (
            f"missing-include error should mention 'cannot find'; got: {result.stderr!r}"
        )


class TestCliMap:

    def test_map_file_written(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        map_path = tmp_path / "out.map"
        result = _run_cli("build", str(sample_fs), "-o", str(out),
                          "--map", str(map_path))
        assert result.returncode == 0, (
            f"build with --map should succeed; stderr={result.stderr}"
        )
        assert map_path.exists(), "--map should produce a map file"

    def test_map_contains_main_word(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        map_path = tmp_path / "out.map"
        _run_cli("build", str(sample_fs), "-o", str(out), "--map", str(map_path))
        contents = map_path.read_text()
        assert " main" in contents, "map file should contain the 'main' symbol"

    def test_map_contains_hex_addresses(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        map_path = tmp_path / "out.map"
        _run_cli("build", str(sample_fs), "-o", str(out), "--map", str(map_path))
        lines = [line for line in map_path.read_text().splitlines() if line]
        assert all(line.startswith("$") for line in lines), (
            "every map line should start with a $ hex address"
        )

    def test_map_addresses_sorted(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        map_path = tmp_path / "out.map"
        _run_cli("build", str(sample_fs), "-o", str(out), "--map", str(map_path))
        addrs = [
            int(line.split()[0].lstrip("$"), 16)
            for line in map_path.read_text().splitlines() if line
        ]
        assert addrs == sorted(addrs), "map entries should be sorted by address"

    def test_no_map_flag_no_map_file(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        map_path = tmp_path / "out.map"
        _run_cli("build", str(sample_fs), "-o", str(out))
        assert not map_path.exists(), "without --map, no map file should be written"


class TestCliFormat:

    @pytest.mark.parametrize("ext, fmt", [
        (".sna", "sna"),
        (".bin", "bin"),
    ], ids=["sna-ext", "bin-ext"])
    def test_format_auto_detected(self, tmp_path, sample_fs, ext, fmt):
        out = tmp_path / f"out{ext}"
        result = _run_cli("build", str(sample_fs), "-o", str(out))
        assert result.returncode == 0, (
            f"extension {ext} should be auto-detected as {fmt}; stderr={result.stderr}"
        )
        assert out.exists(), f"{fmt} output file should be written"

    def test_bin_output_is_image_only(self, tmp_path, sample_fs):
        out = tmp_path / "out.bin"
        _run_cli("build", str(sample_fs), "-o", str(out))
        assert out.stat().st_size < 49179, (
            ".bin output should be raw image (smaller than 49179-byte SNA)"
        )

    def test_explicit_format_overrides_extension(self, tmp_path, sample_fs):
        out = tmp_path / "out.out"
        result = _run_cli("build", str(sample_fs), "-o", str(out),
                          "--format", "bin")
        assert result.returncode == 0, (
            "explicit --format should override unknown extension"
        )

    def test_unknown_extension_without_format_fails(self, tmp_path, sample_fs):
        out = tmp_path / "out.xyz"
        result = _run_cli("build", str(sample_fs), "-o", str(out))
        assert result.returncode != 0, (
            "unknown extension without --format should fail fast"
        )
        assert "format" in result.stderr.lower(), (
            "unknown-extension error should mention format"
        )

    def test_tap_is_not_yet_implemented(self, tmp_path, sample_fs):
        out = tmp_path / "out.tap"
        result = _run_cli("build", str(sample_fs), "-o", str(out))
        assert result.returncode != 0, ".tap should fail until M8"
        assert "tap" in result.stderr.lower() or "M8" in result.stderr, (
            "tap error should indicate it's not implemented yet"
        )


class TestBuildProfileFlag:

    def test_profile_flag_writes_prof_file(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        result = _run_cli("build", str(sample_fs), "-o", str(out),
                          "--profile", "--profile-ticks", "20000")
        assert result.returncode == 0, (
            f"build --profile should succeed; stderr={result.stderr}"
        )
        assert out.with_suffix(".prof").exists(), \
            "--profile should write a .prof file next to the snapshot"

    def test_profile_file_contains_report_header(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        _run_cli("build", str(sample_fs), "-o", str(out),
                 "--profile", "--profile-ticks", "20000")
        text = out.with_suffix(".prof").read_text()
        assert "Word" in text, ".prof should contain the report header"
        assert "Ticks" in text, ".prof should contain a Ticks column"

    def test_profile_file_lists_some_primitives(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        _run_cli("build", str(sample_fs), "-o", str(out),
                 "--profile", "--profile-ticks", "50000")
        text = out.with_suffix(".prof").read_text()
        assert "NEXT" in text or "next" in text, \
            "NEXT should appear in any non-trivial profile run"

    def test_no_profile_flag_writes_no_prof_file(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        _run_cli("build", str(sample_fs), "-o", str(out))
        assert not out.with_suffix(".prof").exists(), \
            "without --profile, no .prof file should be created"

    def test_profile_output_overrides_default_path(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        custom = tmp_path / "custom-location.prof"
        _run_cli("build", str(sample_fs), "-o", str(out),
                 "--profile", "--profile-output", str(custom),
                 "--profile-ticks", "20000")
        assert custom.exists(), \
            "--profile-output should redirect the report file"
        assert not out.with_suffix(".prof").exists(), \
            "when --profile-output is set, no default .prof should be written"

    def test_profile_ticks_bounds_execution(self, tmp_path, sample_fs):
        out = tmp_path / "out.sna"
        _run_cli("build", str(sample_fs), "-o", str(out),
                 "--profile", "--profile-ticks", "500")
        text = out.with_suffix(".prof").read_text()
        total = _sum_ticks_from_report(text)
        assert total <= 500, \
            f"--profile-ticks 500 should cap samples at 500, got {total}"


class TestCliInlinePrimitivesFlag:

    _SOURCE = ": double dup + ; : main 5 double halt ;"

    def _write_source(self, tmp_path: Path) -> Path:
        src = tmp_path / "bench.fs"
        src.write_text(self._SOURCE)
        return src

    def test_flag_builds_successfully(self, tmp_path):
        src = self._write_source(tmp_path)
        out = tmp_path / "bench.bin"
        result = _run_cli("build", str(src), "-o", str(out),
                          "--no-stdlib", "--inline-primitives")
        assert result.returncode == 0, (
            f"--inline-primitives should produce a successful build; "
            f"stderr={result.stderr}"
        )
        assert out.exists(), (
            "CLI should produce an output file when --inline-primitives is used"
        )

    def test_flag_changes_output_bytes(self, tmp_path):
        """`--inline-primitives` is an eager-build optimization that splices
        primitive bodies into colon definitions; it has no effect under
        tree-shaking (which rebuilds colon bodies fresh against new primitive
        addresses). Pin against `--no-tree-shake` so the flag's effect is
        observable."""
        src = self._write_source(tmp_path)
        plain = tmp_path / "plain.bin"
        inlined = tmp_path / "inlined.bin"
        _run_cli("build", str(src), "-o", str(plain),
                 "--no-stdlib", "--no-tree-shake", "--no-inline-primitives")
        _run_cli("build", str(src), "-o", str(inlined),
                 "--no-stdlib", "--no-tree-shake", "--inline-primitives")
        assert plain.read_bytes() != inlined.read_bytes(), (
            "--inline-primitives should alter the output bytes for eager builds; "
            "otherwise the flag is wired but has no effect"
        )

    def test_composes_with_inline_next(self, tmp_path):
        src = self._write_source(tmp_path)
        out = tmp_path / "bench.bin"
        result = _run_cli("build", str(src), "-o", str(out),
                          "--no-stdlib", "--inline-primitives", "--inline-next")
        assert result.returncode == 0, (
            "--inline-primitives should compose with --inline-next; "
            f"stderr={result.stderr}"
        )
        assert out.exists(), (
            "combining --inline-primitives and --inline-next should still produce output"
        )

    def test_composes_with_no_optimize(self, tmp_path):
        src = self._write_source(tmp_path)
        out = tmp_path / "bench.bin"
        result = _run_cli("build", str(src), "-o", str(out),
                          "--no-stdlib", "--inline-primitives", "--no-optimize")
        assert result.returncode == 0, (
            "--inline-primitives should work with peephole optimizer disabled; "
            f"stderr={result.stderr}"
        )

    def test_flag_absent_by_default_in_help(self, tmp_path):
        result = _run_cli("build", "--help")
        assert "--inline-primitives" in result.stdout, (
            "--inline-primitives should be listed in 'zt build --help' output"
        )


def _sum_ticks_from_report(text: str) -> int:
    total = 0
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or not parts[-2].isdigit():
            continue
        total += int(parts[2])
    return total


class TestCliTreeShake:
    """Default behavior: auto-tree-shake when supported, fall back to eager
    with a warning when not. `--tree-shake` makes tree-shaking strict (fails on
    unsupported features). `--no-tree-shake` forces the eager build."""

    def test_default_auto_tree_shakes_when_supported(self, tmp_path, sample_fs):
        """Default build should pick the tree_shaken image for programs that
        support tree-shaking — same image bytes as `--tree-shake`."""
        default_out = tmp_path / "default.bin"
        tree_shaken_out = tmp_path / "tree_shaken.bin"
        default_result = _run_cli(
            "build", str(sample_fs), "-o", str(default_out),
        )
        tree_shaken_result = _run_cli(
            "build", str(sample_fs), "-o", str(tree_shaken_out), "--tree-shake",
        )
        assert default_result.returncode == 0
        assert tree_shaken_result.returncode == 0
        assert default_out.read_bytes() == tree_shaken_out.read_bytes(), (
            "default build should tree-shake automatically; image should match --tree-shake output"
        )

    def test_default_smaller_than_no_tree_shake(self, tmp_path, sample_fs):
        """Default (auto-tree-shake) should produce a smaller image than
        `--no-tree-shake` for any program where tree-shaking is supported."""
        default_out = tmp_path / "default.bin"
        eager_out = tmp_path / "eager.bin"
        _run_cli("build", str(sample_fs), "-o", str(default_out))
        _run_cli("build", str(sample_fs), "-o", str(eager_out), "--no-tree-shake")
        assert default_out.stat().st_size < eager_out.stat().st_size, (
            f"default should auto-tree-shake and be smaller than --no-tree-shake; "
            f"got default={default_out.stat().st_size}, "
            f"eager={eager_out.stat().st_size}"
        )

    def test_no_tree_shake_flag_forces_eager(self, tmp_path, sample_fs):
        """`--no-tree-shake` forces the eager build; result is byte-identical
        to the pre-auto-tree-shake default behavior."""
        out = tmp_path / "eager.bin"
        result = _run_cli("build", str(sample_fs), "-o", str(out), "--no-tree-shake")
        assert result.returncode == 0
        assert out.exists()

    def test_default_falls_back_silently_for_unsupported(self, tmp_path):
        """For programs using `'`/banking, default should silently
        fall back to the eager build with a single-line warning."""
        unsupported_src = tmp_path / "tick.fs"
        unsupported_src.write_text(
            ": helper 1 ;\n"
            "' helper constant helper-addr\n"
            ": main helper-addr drop ;\n"
        )
        out = tmp_path / "out.bin"
        result = _run_cli(
            "build", str(unsupported_src), "-o", str(out), "--no-stdlib",
        )
        assert result.returncode == 0, (
            "default build should fall back rather than fail; "
            f"stderr={result.stderr!r}"
        )
        assert out.exists(), "fallback should still produce output"
        assert "auto-tree-shake" in result.stderr.lower() or "fall" in result.stderr.lower(), (
            f"fallback should emit a clear warning; got stderr={result.stderr!r}"
        )

    def test_explicit_tree_shake_strict_on_unsupported(self, tmp_path):
        """`--tree-shake` (explicit opt-in) should still fail loudly on
        unsupported programs — users who ask for tree-shake want exactly tree-shake."""
        unsupported_src = tmp_path / "tick.fs"
        unsupported_src.write_text(
            ": helper 1 ;\n"
            "' helper constant helper-addr\n"
            ": main helper-addr drop ;\n"
        )
        out = tmp_path / "out.bin"
        result = _run_cli(
            "build", str(unsupported_src), "-o", str(out),
            "--tree-shake", "--no-stdlib",
        )
        assert result.returncode != 0, (
            "--tree-shake on a program using ' should fail strictly, not fall back"
        )
        assert "tick" in result.stderr or "address-as-data" in result.stderr, (
            f"error should mention the unsupported feature; got: {result.stderr!r}"
        )

    def test_default_produces_runnable_sna(self, tmp_path, sample_fs):
        """Default-build .sna should still be 49179 bytes regardless of mode."""
        out = tmp_path / "out.sna"
        result = _run_cli("build", str(sample_fs), "-o", str(out))
        assert result.returncode == 0
        assert out.stat().st_size == 49179

    def test_explicit_tree_shake_and_no_tree_shake_are_mutually_exclusive(
        self, tmp_path, sample_fs,
    ):
        """Passing both --tree-shake and --no-tree-shake should be rejected; user
        intent is ambiguous."""
        out = tmp_path / "out.bin"
        result = _run_cli(
            "build", str(sample_fs), "-o", str(out),
            "--tree-shake", "--no-tree-shake",
        )
        assert result.returncode != 0, (
            "passing both --tree-shake and --no-tree-shake should fail"
        )
        assert "not allowed" in result.stderr or "mutually exclusive" in result.stderr, (
            f"error should explain the conflict; got: {result.stderr!r}"
        )
