"""Test that `zt build --target 48k` (or default sna output) refuses to silently
drop `in-bank ... end-bank` data. Without this, copy-pasting a 128K example
into the 48K target produces a snapshot whose CFAs point at empty memory."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zt.cli", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


@pytest.fixture
def source_with_bank_data(tmp_path: Path) -> Path:
    src = tmp_path / "needs_bank.fs"
    src.write_text(
        "0 in-bank\n"
        "create blob 16 allot\n"
        "end-bank\n"
        ": main blob drop ;\n"
    )
    return src


def test_sna_build_errors_on_bank_data(tmp_path: Path, source_with_bank_data) -> None:
    out = tmp_path / "broken.sna"
    result = _run_cli("build", str(source_with_bank_data), "-o", str(out))
    assert result.returncode != 0, (
        "48K SNA build with `in-bank` data should fail loudly, not silently "
        "drop the bank bytes"
    )


def test_sna_build_error_mentions_bank(tmp_path: Path, source_with_bank_data) -> None:
    out = tmp_path / "broken.sna"
    result = _run_cli("build", str(source_with_bank_data), "-o", str(out))
    combined = (result.stderr + result.stdout).lower()
    assert "bank" in combined, (
        f"error message should mention 'bank' so the user knows why; "
        f"got stderr={result.stderr!r} stdout={result.stdout!r}"
    )


def test_sna_build_error_suggests_target_128k(tmp_path: Path, source_with_bank_data) -> None:
    out = tmp_path / "broken.sna"
    result = _run_cli("build", str(source_with_bank_data), "-o", str(out))
    combined = (result.stderr + result.stdout).lower()
    assert "128k" in combined or "--target 128k" in combined, (
        f"error message should point the user at the 128K target; "
        f"got stderr={result.stderr!r}"
    )


def test_sna_build_succeeds_when_no_bank_data(tmp_path: Path) -> None:
    src = tmp_path / "plain.fs"
    src.write_text(": main 42 drop ;\n")
    out = tmp_path / "plain.sna"
    result = _run_cli("build", str(src), "-o", str(out))
    assert result.returncode == 0, (
        f"plain 48K source without bank data should still build cleanly; "
        f"stderr={result.stderr}"
    )
    assert out.exists(), "build should produce a snapshot file"
