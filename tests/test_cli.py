from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
HELLO_PATH = REPO_ROOT / "examples" / "hello.fs"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zt.cli", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestCliStdlibDefault:

    def test_hello_builds_without_flag(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out))
        assert result.returncode == 0, (
            f"build without --stdlib should succeed (stdlib is default); "
            f"stderr={result.stderr}"
        )
        assert out.exists(), "build should produce an output .sna file"
        assert out.stat().st_size == 49179, ".sna snapshots should be 49179 bytes"

    def test_hello_fails_with_no_stdlib(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out), "--no-stdlib",
        )
        assert result.returncode != 0, (
            "--no-stdlib on hello.fs should fail since hello uses cr/./etc."
        )
        assert "unknown word" in result.stderr, (
            f"error should mention 'unknown word'; got: {result.stderr!r}"
        )

    def test_explicit_stdlib_flag_still_works(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out), "--stdlib",
        )
        assert result.returncode == 0, (
            "explicit --stdlib should still succeed for backwards compatibility"
        )


class TestCliCounterStillWorks:

    def test_counter_builds_with_no_stdlib(self, tmp_path):
        counter_path = REPO_ROOT / "examples" / "counter.fs"
        if not counter_path.exists():
            pytest.skip("counter.fs not present")
        out = tmp_path / "counter.sna"
        result = _run_cli(
            "build", str(counter_path), "-o", str(out), "--no-stdlib",
        )
        assert result.returncode == 0, (
            f"counter.fs should build with --no-stdlib (uses only primitives); "
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

    def test_map_file_written(self, tmp_path):
        out = tmp_path / "hello.sna"
        map_path = tmp_path / "hello.map"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out),
                          "--map", str(map_path))
        assert result.returncode == 0, (
            f"build with --map should succeed; stderr={result.stderr}"
        )
        assert map_path.exists(), "--map should produce a map file"

    def test_map_contains_main_word(self, tmp_path):
        out = tmp_path / "hello.sna"
        map_path = tmp_path / "hello.map"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--map", str(map_path))
        contents = map_path.read_text()
        assert " main" in contents, "map file should contain the 'main' symbol"

    def test_map_contains_hex_addresses(self, tmp_path):
        out = tmp_path / "hello.sna"
        map_path = tmp_path / "hello.map"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--map", str(map_path))
        lines = [line for line in map_path.read_text().splitlines() if line]
        assert all(line.startswith("$") for line in lines), (
            "every map line should start with a $ hex address"
        )

    def test_map_addresses_sorted(self, tmp_path):
        out = tmp_path / "hello.sna"
        map_path = tmp_path / "hello.map"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--map", str(map_path))
        addrs = [
            int(line.split()[0].lstrip("$"), 16)
            for line in map_path.read_text().splitlines() if line
        ]
        assert addrs == sorted(addrs), "map entries should be sorted by address"

    def test_no_map_flag_no_map_file(self, tmp_path):
        out = tmp_path / "hello.sna"
        map_path = tmp_path / "hello.map"
        _run_cli("build", str(HELLO_PATH), "-o", str(out))
        assert not map_path.exists(), "without --map, no map file should be written"


class TestCliFormat:

    @pytest.mark.parametrize("ext, fmt", [
        (".sna", "sna"),
        (".bin", "bin"),
    ], ids=["sna-ext", "bin-ext"])
    def test_format_auto_detected(self, tmp_path, ext, fmt):
        out = tmp_path / f"hello{ext}"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out))
        assert result.returncode == 0, (
            f"extension {ext} should be auto-detected as {fmt}; stderr={result.stderr}"
        )
        assert out.exists(), f"{fmt} output file should be written"

    def test_bin_output_is_image_only(self, tmp_path):
        out = tmp_path / "hello.bin"
        _run_cli("build", str(HELLO_PATH), "-o", str(out))
        assert out.stat().st_size < 49179, (
            ".bin output should be raw image (smaller than 49179-byte SNA)"
        )

    def test_explicit_format_overrides_extension(self, tmp_path):
        out = tmp_path / "hello.out"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out),
                          "--format", "bin")
        assert result.returncode == 0, (
            "explicit --format should override unknown extension"
        )

    def test_unknown_extension_without_format_fails(self, tmp_path):
        out = tmp_path / "hello.xyz"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out))
        assert result.returncode != 0, (
            "unknown extension without --format should fail fast"
        )
        assert "format" in result.stderr.lower(), (
            "unknown-extension error should mention format"
        )

    def test_tap_is_not_yet_implemented(self, tmp_path):
        out = tmp_path / "hello.tap"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out))
        assert result.returncode != 0, ".tap should fail until M8"
        assert "tap" in result.stderr.lower() or "M8" in result.stderr, (
            "tap error should indicate it's not implemented yet"
        )
