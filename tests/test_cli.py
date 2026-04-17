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
