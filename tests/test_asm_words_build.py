"""
End-to-end test that ::: words survive the CLI build pipeline. The
build pipeline runs the dictionary tree-shaker after compilation, which
historically only knew about Python-defined primitives. ::: words are
also kind="prim" but live outside the blob registry; they need to be
preserved by the shaker too.

This test reproduces the user-facing scenario: a file that defines ::: 
words and a `main` that uses them, built via `zt.cli build`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _build(source_path: Path, out_dir: Path) -> tuple[int, str, str]:
    out_sna = out_dir / "out.sna"
    out_map = out_dir / "out.map"
    proc = subprocess.run(
        [sys.executable, "-m", "zt.cli", "build", str(source_path),
         "-o", str(out_sna), "--map", str(out_map)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestAsmWordsSurviveCliBuild:

    def test_examples_demo_builds(self, tmp_path):
        rc, stdout, stderr = _build(
            PROJECT_ROOT / "examples" / "asm-primitives-demo.fs", tmp_path,
        )
        assert rc == 0, (
            f"examples/asm-primitives-demo.fs should build via the CLI, "
            f"got returncode {rc}\nstdout: {stdout}\nstderr: {stderr}"
        )
        sna = tmp_path / "out.sna"
        assert sna.exists() and sna.stat().st_size > 0, (
            "build should produce a non-empty .sna file"
        )

    def test_library_file_without_main_errors_clearly(self, tmp_path):
        """asm-primitives.fs is a library — no `main`. Building it should
        fail with a clear error, not crash inside the tree-shaker."""
        rc, stdout, stderr = _build(
            PROJECT_ROOT / "examples" / "asm-primitives.fs", tmp_path,
        )
        combined = stdout + stderr
        assert rc != 0, "library file without main should fail to build"
        assert "main" in combined.lower(), (
            f"error message should mention `main`; got:\n{combined}"
        )

    def test_minimal_asm_word_with_main_builds(self, tmp_path):
        src = tmp_path / "tiny.fs"
        src.write_text(
            "::: cell+ ( addr -- addr+2 ) inc_hl inc_hl ;\n"
            ": main 1000 cell+ drop ;\n"
        )
        rc, stdout, stderr = _build(src, tmp_path)
        assert rc == 0, (
            f"a minimal program with one ::: word should build, "
            f"got returncode {rc}\nstdout: {stdout}\nstderr: {stderr}"
        )

    def test_asm_word_referenced_only_from_main(self, tmp_path):
        """The ::: word here is reachable only through main, not through any
        Python primitive's deps. Tree-shaking must not drop it."""
        src = tmp_path / "reach.fs"
        src.write_text(
            "::: just-mine ( n -- n+1 ) inc_hl ;\n"
            ": main 41 just-mine drop ;\n"
        )
        rc, stdout, stderr = _build(src, tmp_path)
        assert rc == 0, (
            f"a ::: word reachable only through main should survive "
            f"tree-shaking, got rc={rc}\nstderr: {stderr}"
        )
