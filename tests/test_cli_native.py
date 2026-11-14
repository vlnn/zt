"""
Integration tests for the native backend's CLI surface: `zt build --native` and
`zt test --native`, driven via subprocess.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from zt.format.image_loader import load_sna
from zt.sim import FRAME_T_STATES_48K, Z80

REPO_ROOT = Path(__file__).parent.parent
RAINBOW = REPO_ROOT / "examples" / "im2-rainbow" / "main.fs"

HALTING_SOURCE = """\
: square  dup * ;
: main    7 0 cls  6 square .  halt ;
"""

UNSUPPORTED_SOURCE = """\
: target 1 ;
' target constant target-xt
: main target-xt execute halt ;
"""

PASSING_TESTS = """\
include test-lib.fs
: test-adds   3 4 +  7 assert-eq ;
: test-loops  0 5 0 do i + loop  10 assert-eq ;
"""

FAILING_TESTS = """\
include test-lib.fs
: test-wrong  3 4 +  8 assert-eq ;
"""


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zt.cli", *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def _boot_snapshot(sna_path: Path) -> Z80:
    raw = sna_path.read_bytes()
    machine = Z80()
    for addr, byte in enumerate(load_sna(sna_path)):
        machine._wb(addr, byte)
    machine.sp = raw[0x17] | (raw[0x18] << 8)
    machine.pc = machine._rw(machine.sp)
    machine.sp = (machine.sp + 2) & 0xFFFF
    return machine


def _border_writes(machine: Z80) -> list[int]:
    return [value & 0x07 for port, value in machine._outputs if (port & 0xFF) == 0xFE]


class TestBuildNative:

    def test_native_build_succeeds(self, tmp_path):
        source = _write(tmp_path, "prog.fs", HALTING_SOURCE)
        result = _run_cli("build", str(source), "-o", str(tmp_path / "out.sna"), "--native")
        assert result.returncode == 0, \
            f"zt build --native should succeed; stderr={result.stderr}"

    def test_native_snapshot_has_standard_size(self, tmp_path):
        source = _write(tmp_path, "prog.fs", HALTING_SOURCE)
        out = tmp_path / "out.sna"
        _run_cli("build", str(source), "-o", str(out), "--native")
        assert out.stat().st_size == 49179, "a native .sna should still be 49179 bytes"

    def test_native_bin_differs_from_threaded_bin(self, tmp_path):
        source = _write(tmp_path, "prog.fs", HALTING_SOURCE)
        threaded, native = tmp_path / "t.bin", tmp_path / "n.bin"
        _run_cli("build", str(source), "-o", str(threaded))
        _run_cli("build", str(source), "-o", str(native), "--native")
        assert native.read_bytes() != threaded.read_bytes(), \
            "--native should produce different code from the threaded build"

    def test_native_snapshot_runs_to_halt(self, tmp_path):
        source = _write(tmp_path, "prog.fs", HALTING_SOURCE)
        out = tmp_path / "out.sna"
        _run_cli("build", str(source), "-o", str(out), "--native")
        machine = _boot_snapshot(out)
        machine.run(max_ticks=2_000_000)
        assert machine.halted, "the native snapshot should boot and run to HALT"

    def test_native_map_lists_emitted_colons(self, tmp_path):
        source = _write(tmp_path, "prog.fs", HALTING_SOURCE)
        map_path = tmp_path / "out.map"
        _run_cli("build", str(source), "-o", str(tmp_path / "out.sna"),
                 "--native", "--map", str(map_path))
        assert " main" in map_path.read_text(), \
            "the map of a native build should list main at its native address"

    @pytest.mark.parametrize("flag", ["--no-tree-shake", "--tree-shake"])
    def test_native_rejects_tree_shake_flags(self, tmp_path, flag):
        source = _write(tmp_path, "prog.fs", HALTING_SOURCE)
        result = _run_cli("build", str(source), "-o", str(tmp_path / "out.sna"),
                          "--native", flag)
        assert result.returncode != 0, \
            f"--native always rebuilds from live IR, so combining it with {flag} should fail"

    def test_native_rejects_fsym(self, tmp_path):
        source = _write(tmp_path, "prog.fs", HALTING_SOURCE)
        result = _run_cli("build", str(source), "-o", str(tmp_path / "out.sna"),
                          "--native", "--fsym", str(tmp_path / "out.fsym"))
        assert result.returncode != 0 and "--fsym" in result.stderr, \
            "--fsym describes threaded cells and should be refused with --native"

    def test_unsupported_program_reports_native_in_error(self, tmp_path):
        source = _write(tmp_path, "prog.fs", UNSUPPORTED_SOURCE)
        result = _run_cli("build", str(source), "-o", str(tmp_path / "out.sna"), "--native")
        assert result.returncode != 0 and "--native" in result.stderr, \
            "a program the native backend cannot build yet should fail naming --native"


class TestNativeInterrupts:

    @pytest.fixture(scope="class")
    def rainbow(self, tmp_path_factory) -> Path:
        out = tmp_path_factory.mktemp("rainbow") / "rainbow.sna"
        result = _run_cli("build", str(RAINBOW), "-o", str(out), "--native")
        assert result.returncode == 0, f"native rainbow build failed: {result.stderr}"
        return out

    def test_native_handler_fires_once_per_frame(self, rainbow):
        machine = _boot_snapshot(rainbow)
        machine.run_until(FRAME_T_STATES_48K * 3 + 5000)
        assert machine.interrupt_count == 3, \
            "three frames should deliver three interrupts to the native handler"

    def test_native_handler_cycles_the_border(self, rainbow):
        machine = _boot_snapshot(rainbow)
        machine.run_until(FRAME_T_STATES_48K * 8 + 5000)
        assert _border_writes(machine) == [1, 2, 3, 4, 5, 6, 7, 0], \
            "the native colon handler should advance the border once per frame"


class TestTestNative:

    def test_passing_forth_tests_pass_natively(self, tmp_path):
        spec = _write(tmp_path, "test_ok.fs", PASSING_TESTS)
        result = _run_cli("test", str(spec), "--native")
        assert result.returncode == 0, \
            f"zt test --native should pass passing tests; out={result.stdout}{result.stderr}"

    def test_failing_forth_test_fails_natively(self, tmp_path):
        spec = _write(tmp_path, "test_bad.fs", FAILING_TESTS)
        result = _run_cli("test", str(spec), "--native")
        assert result.returncode == 1, \
            "zt test --native should report a failing assertion with exit code 1"


class TestNativeDebugArtifacts:

    SOURCE = """\
42 constant answer
: tiny    1+ ;
: main    answer tiny dup * . halt ;
"""

    @pytest.fixture
    def sld_text(self, tmp_path) -> str:
        source = _write(tmp_path, "prog.fs", self.SOURCE)
        sld = tmp_path / "out.sld"
        result = _run_cli("build", str(source), "-o", str(tmp_path / "out.sna"),
                          "--native", "--sld", str(sld))
        assert result.returncode == 0, f"native build with --sld failed: {result.stderr}"
        return sld.read_text()

    def test_sld_labels_emitted_colons(self, sld_text):
        assert "|L|main" in sld_text, "the SLD of a native build should label main"

    @pytest.mark.parametrize("name", ["answer", "tiny"])
    def test_sld_omits_words_without_an_address(self, sld_text, name):
        assert f"|L|{name}" not in sld_text, \
            f"{name!r} has no address in a native image and should not get an SLD label"
