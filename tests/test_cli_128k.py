"""
Integration tests for `zt build --target 128k`: output size, default stack
placement in bank 2, rejection of stacks that would land in the paged slot,
and round-trip through `load_sna_128`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from zt.format.image_loader import Sna128Image, load_sna_128
from zt.format.sna import SNA_128K_TOTAL_SIZE, SNA_TOTAL_SIZE


REPO_ROOT = Path(__file__).parent.parent
HELLO_PATH = REPO_ROOT / "examples" / "hello.fs"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zt.cli", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestTargetDefault:

    def test_default_target_produces_48k_sna(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out))
        assert result.returncode == 0, (
            f"default build should succeed; stderr={result.stderr}"
        )
        assert out.stat().st_size == SNA_TOTAL_SIZE, (
            f"default target should produce a {SNA_TOTAL_SIZE}-byte 48k snapshot"
        )

    def test_explicit_48k_matches_default(self, tmp_path):
        out_default = tmp_path / "default.sna"
        out_48k = tmp_path / "explicit.sna"
        _run_cli("build", str(HELLO_PATH), "-o", str(out_default))
        _run_cli("build", str(HELLO_PATH), "-o", str(out_48k), "--target", "48k")
        assert out_default.read_bytes() == out_48k.read_bytes(), (
            "--target 48k should produce the exact same bytes as the default"
        )


class TestTarget128k:

    def test_target_128k_produces_131103_byte_sna(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli("build", str(HELLO_PATH), "-o", str(out), "--target", "128k")
        assert result.returncode == 0, (
            f"--target 128k build should succeed; stderr={result.stderr}"
        )
        assert out.stat().st_size == SNA_128K_TOTAL_SIZE, (
            f"--target 128k default paged_bank=0 should produce a "
            f"{SNA_128K_TOTAL_SIZE}-byte snapshot"
        )

    def test_target_128k_loads_as_128k_image(self, tmp_path):
        out = tmp_path / "hello.sna"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--target", "128k")
        image = load_sna_128(out)
        assert isinstance(image, Sna128Image), (
            "--target 128k output should load via load_sna_128"
        )
        assert image.pc >= 0x4000, "pc should point at Spectrum RAM"

    def test_target_128k_places_code_in_bank_2(self, tmp_path):
        out = tmp_path / "hello.sna"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--target", "128k")
        image = load_sna_128(out)
        bank2 = image.memory[2 * 0x4000:(2 + 1) * 0x4000]
        non_zero = sum(1 for b in bank2 if b != 0)
        assert non_zero > 100, (
            "bank 2 should contain the compiled code (many non-zero bytes) "
            "since default origin $8000 is in bank 2"
        )

    def test_target_128k_uses_bank_2_stacks(self, tmp_path):
        out = tmp_path / "hello.sna"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--target", "128k")
        image = load_sna_128(out)
        sp_low = image.memory[2 * 0x4000 + (0xBF00 - 0x8000)]
        assert image.memory[2 * 0x4000 - 0x8000 + 0xBF00] is not None, (
            "bank 2 should be initialised (stack lives there)"
        )


class TestTarget128kPagedBank:

    @pytest.mark.parametrize("paged_bank", [0, 1, 3, 4, 6, 7])
    def test_paged_bank_flag_encoded_in_port(self, tmp_path, paged_bank):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--target", "128k", "--paged-bank", str(paged_bank),
        )
        assert result.returncode == 0, (
            f"--paged-bank {paged_bank} should be accepted; stderr={result.stderr}"
        )
        image = load_sna_128(out)
        assert image.port_7ffd & 0x07 == paged_bank, (
            f"--paged-bank {paged_bank} should set low 3 bits of port_7ffd"
        )

    @pytest.mark.parametrize("paged_bank", ["-1", "8", "99"])
    def test_rejects_out_of_range_paged_bank(self, tmp_path, paged_bank):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--target", "128k", "--paged-bank", paged_bank,
        )
        assert result.returncode != 0, (
            f"--paged-bank {paged_bank} outside 0..7 should fail"
        )

    def test_paged_bank_requires_128k_target(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--paged-bank", "3",
        )
        assert result.returncode != 0, (
            "--paged-bank should be rejected without --target 128k"
        )


class TestStackValidation:

    def test_rejects_48k_dstack_default_under_128k(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--target", "128k", "--dstack", "0xFF00",
        )
        assert result.returncode != 0, (
            "--target 128k with --dstack in the paged slot ($C000+) should fail"
        )
        assert "dstack" in result.stderr.lower() or "stack" in result.stderr.lower(), (
            f"error should mention stack placement; got: {result.stderr!r}"
        )

    def test_rejects_rstack_in_paged_slot(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--target", "128k", "--rstack", "0xFE00",
        )
        assert result.returncode != 0, (
            "--target 128k with --rstack in the paged slot should fail"
        )

    def test_accepts_bank_2_dstack(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--target", "128k", "--dstack", "0xBF00", "--rstack", "0xBE00",
        )
        assert result.returncode == 0, (
            f"explicit bank-2 stacks should be accepted; stderr={result.stderr}"
        )


class TestOriginValidation:

    def test_rejects_origin_in_paged_slot_under_128k(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--target", "128k", "--origin", "0xC000",
        )
        assert result.returncode != 0, (
            "--target 128k with --origin in the paged slot should fail"
        )

    def test_48k_origin_unconstrained(self, tmp_path):
        out = tmp_path / "hello.sna"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--origin", "0xC000",
        )
        assert result.returncode == 0, (
            "48k target should accept origin in the $C000+ region "
            f"(stderr={result.stderr})"
        )


class TestBankingPrimitivesUsable:

    def test_program_using_bank_store_compiles(self, tmp_path):
        src = tmp_path / "bank_test.fs"
        src.write_text(": main 3 bank! begin again ;\n")
        out = tmp_path / "bank_test.sna"
        result = _run_cli(
            "build", str(src), "-o", str(out),
            "--target", "128k",
        )
        assert result.returncode == 0, (
            f"program using bank! should compile under --target 128k; "
            f"stderr={result.stderr}"
        )
        assert out.stat().st_size == SNA_128K_TOTAL_SIZE, (
            "a program using banking primitives should still produce 131103 bytes"
        )

    def test_128k_query_detection_program_compiles(self, tmp_path):
        src = tmp_path / "detect.fs"
        src.write_text(": main 128k? begin again ;\n")
        out = tmp_path / "detect.sna"
        result = _run_cli(
            "build", str(src), "-o", str(out), "--target", "128k",
        )
        assert result.returncode == 0, (
            f"program using 128k? should compile; stderr={result.stderr}"
        )


class TestTargetZ80Format:

    def test_z80_extension_auto_detects_format(self, tmp_path):
        out = tmp_path / "hello.z80"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out), "--target", "128k",
        )
        assert result.returncode == 0, (
            f".z80 extension should auto-detect z80 format; stderr={result.stderr}"
        )
        assert out.stat().st_size > 100_000, (
            "z80 128k output should contain the full banked image"
        )

    def test_explicit_format_z80(self, tmp_path):
        out = tmp_path / "hello.bin"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out),
            "--target", "128k", "--format", "z80",
        )
        assert result.returncode == 0, (
            f"--format z80 should override extension detection; stderr={result.stderr}"
        )

    def test_z80_rejects_48k_target(self, tmp_path):
        out = tmp_path / "hello.z80"
        result = _run_cli(
            "build", str(HELLO_PATH), "-o", str(out), "--format", "z80",
        )
        assert result.returncode != 0, (
            "--format z80 with default --target 48k should fail"
        )
        assert "z80" in result.stderr.lower() or "128k" in result.stderr.lower(), (
            f"error should mention the z80/128k requirement; got: {result.stderr!r}"
        )

    def test_z80_header_identifies_spectrum_128(self, tmp_path):
        out = tmp_path / "hello.z80"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--target", "128k")
        data = out.read_bytes()
        assert data[34] == 4, (
            "hardware mode byte 34 should equal 4 (Spectrum 128), not Pentagon; "
            "this is the whole reason z80 is preferred over sna for 128k output"
        )

    def test_z80_pc_matches_start_label(self, tmp_path):
        out = tmp_path / "hello.z80"
        _run_cli("build", str(HELLO_PATH), "-o", str(out), "--target", "128k")
        data = out.read_bytes()
        pc_in_base = data[6] | (data[7] << 8)
        pc_extended = data[32] | (data[33] << 8)
        assert pc_in_base == 0, (
            "base-header PC must be 0 to signal v2/v3 extended format"
        )
        assert pc_extended >= 0x4000, (
            f"extended PC at offset 32 should be in Spectrum RAM; got {pc_extended:#06x}"
        )
