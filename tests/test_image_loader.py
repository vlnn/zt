from __future__ import annotations

from pathlib import Path

import pytest

from zt.image_loader import default_map_path, load_sna, read_map
from zt.sna import SNA_RAM_BASE, build_sna


class TestLoadSna:

    def test_roundtrip_bytes_at_origin(self, tmp_path: Path):
        origin = 0x8000
        payload = b"\x21\x34\x12"
        path = tmp_path / "test.sna"
        path.write_bytes(build_sna(payload, origin))
        mem = load_sna(path)
        assert bytes(mem[origin:origin + 3]) == payload, (
            "load_sna should restore bytes at their original origin"
        )

    def test_returns_full_64k_memory(self, tmp_path: Path):
        path = tmp_path / "test.sna"
        path.write_bytes(build_sna(b"\x00", 0x8000))
        mem = load_sna(path)
        assert len(mem) == 0x10000, "load_sna should return a full 64KB memory image"

    def test_below_ram_base_is_untouched(self, tmp_path: Path):
        path = tmp_path / "test.sna"
        path.write_bytes(build_sna(b"\x42", 0x8000))
        mem = load_sna(path)
        assert all(b == 0 for b in mem[:SNA_RAM_BASE]), (
            "memory below SNA_RAM_BASE should be zero (no ROM present in .sna)"
        )

    def test_rejects_wrong_size(self, tmp_path: Path):
        path = tmp_path / "short.sna"
        path.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError, match="unexpected .sna size"):
            load_sna(path)


class TestReadMap:

    @pytest.mark.parametrize("line,expected_name,expected_addr", [
        ("$8000 _start",       "_start", 0x8000),
        ("8000 _start",        "_start", 0x8000),
        ("$ABCD my_word",      "my_word", 0xABCD),
        ("_start = $8000",     "_start", 0x8000),
        ("my_word=$ABCD",      "my_word", 0xABCD),
    ])
    def test_parses_line_formats(self, tmp_path: Path, line, expected_name, expected_addr):
        path = tmp_path / "test.map"
        path.write_text(line + "\n")
        labels = read_map(path)
        assert labels == {expected_name: expected_addr}, (
            f"line {line!r} should parse to {expected_name}={expected_addr:#x}"
        )

    def test_skips_blank_and_comments(self, tmp_path: Path):
        path = tmp_path / "test.map"
        path.write_text("\n# comment\n; also a comment\n$8000 real\n\n")
        assert read_map(path) == {"real": 0x8000}, (
            "blanks and comments should be skipped"
        )

    def test_multiple_labels(self, tmp_path: Path):
        path = tmp_path / "test.map"
        path.write_text("$8000 _start\n$8010 DUP\n$8020 SWAP\n")
        labels = read_map(path)
        assert labels == {"_start": 0x8000, "DUP": 0x8010, "SWAP": 0x8020}, (
            "multiple labels should all be captured"
        )


class TestDefaultMapPath:

    def test_swaps_extension_to_map(self):
        assert default_map_path(Path("plasma.sna")) == Path("plasma.map"), (
            "default map path should replace .sna with .map"
        )

    def test_handles_nested_paths(self):
        assert default_map_path(Path("build/out.sna")) == Path("build/out.map"), (
            "default map path should preserve directory structure"
        )
