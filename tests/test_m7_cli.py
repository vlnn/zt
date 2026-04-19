"""
Milestone-7 tests for `zt build` / `zt inspect`: produced artifacts, map formats, error reporting, and image-stability under debug flags.
"""
import json
import sys
from pathlib import Path

import pytest

from zt import cli


@pytest.fixture
def program(tmp_path: Path) -> Path:
    src = tmp_path / "prog.fs"
    src.write_text(": double dup + ;\n: main 21 double begin again ;\n")
    return src


def run_cli(monkeypatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", ["zt", *argv])
    cli.main()


class TestBuildArtifacts:
    def test_build_produces_sna(self, monkeypatch, tmp_path, program):
        out = tmp_path / "out.sna"
        run_cli(monkeypatch, "build", str(program), "-o", str(out), "--no-stdlib")
        assert out.exists(), "zt build should produce the .sna output file"

    def test_map_flag_writes_map_file(self, monkeypatch, tmp_path, program):
        out = tmp_path / "out.sna"
        mp = tmp_path / "out.map"
        run_cli(monkeypatch, "build", str(program), "-o", str(out),
                "--no-stdlib", "--map", str(mp))
        assert mp.exists(), "--map should produce a map file at the given path"
        assert "double" in mp.read_text(), "map file should list the word 'double'"

    def test_sld_flag_writes_sld_file(self, monkeypatch, tmp_path, program):
        out = tmp_path / "out.sna"
        sld = tmp_path / "out.sld"
        run_cli(monkeypatch, "build", str(program), "-o", str(out),
                "--no-stdlib", "--sld", str(sld))
        assert sld.exists(), "--sld should produce an SLD file at the given path"
        assert sld.read_text().startswith("|SLD.data.version|"), \
            "SLD output should begin with the version marker"

    def test_fsym_flag_writes_valid_json(self, monkeypatch, tmp_path, program):
        out = tmp_path / "out.sna"
        fs = tmp_path / "out.fsym"
        run_cli(monkeypatch, "build", str(program), "-o", str(out),
                "--no-stdlib", "--fsym", str(fs))
        data = json.loads(fs.read_text())
        assert "words" in data, "fsym JSON should contain a 'words' key"
        assert "double" in data["words"], "fsym should list the word 'double'"

    def test_all_three_artifacts_together(self, monkeypatch, tmp_path, program):
        out = tmp_path / "out.sna"
        mp = tmp_path / "out.map"
        sld = tmp_path / "out.sld"
        fs = tmp_path / "out.fsym"
        run_cli(monkeypatch, "build", str(program), "-o", str(out), "--no-stdlib",
                "--map", str(mp), "--sld", str(sld), "--fsym", str(fs))
        for path in (out, mp, sld, fs):
            assert path.exists(), f"{path.name} should be written when all flags are set"


class TestMapFormat:
    @pytest.mark.parametrize("path_suffix,needle", [
        ("out.map", "$"),
        ("out.sym", " = $"),
    ])
    def test_format_from_extension(self, monkeypatch, tmp_path, program,
                                    path_suffix, needle):
        out = tmp_path / "out.sna"
        mp = tmp_path / path_suffix
        run_cli(monkeypatch, "build", str(program), "-o", str(out),
                "--no-stdlib", "--map", str(mp))
        assert needle in mp.read_text(), \
            f"{path_suffix} should produce a map containing {needle!r}"

    def test_explicit_override(self, monkeypatch, tmp_path, program):
        out = tmp_path / "out.sna"
        mp = tmp_path / "out.map"
        run_cli(monkeypatch, "build", str(program), "-o", str(out),
                "--no-stdlib", "--map", str(mp), "--map-format", "zesarux")
        assert " = $" in mp.read_text(), \
            "--map-format zesarux should override the .map extension"


class TestInspect:
    def test_inspect_prints_decompiled_word(self, monkeypatch, tmp_path, program, capsys):
        out = tmp_path / "out.sna"
        fs = tmp_path / "out.fsym"
        run_cli(monkeypatch, "build", str(program), "-o", str(out),
                "--no-stdlib", "--fsym", str(fs))
        capsys.readouterr()
        run_cli(monkeypatch, "inspect", "--symbols", str(fs))
        out_text = capsys.readouterr().out
        assert ": double" in out_text, \
            "inspect output should contain the colon definition of 'double'"
        assert "dup" in out_text and "+" in out_text, \
            "inspect body should name the primitives dup and +"

    def test_inspect_missing_file_exits_nonzero(self, monkeypatch, tmp_path, capsys):
        missing = tmp_path / "nope.fsym"
        with pytest.raises(SystemExit) as exc:
            run_cli(monkeypatch, "inspect", "--symbols", str(missing))
        assert exc.value.code == 1, \
            "inspect should exit 1 when symbols file is missing"


class TestBuildErrors:
    def test_missing_source_exits_nonzero(self, monkeypatch, tmp_path, capsys):
        out = tmp_path / "out.sna"
        missing = tmp_path / "nope.fs"
        with pytest.raises(SystemExit) as exc:
            run_cli(monkeypatch, "build", str(missing), "-o", str(out), "--no-stdlib")
        assert exc.value.code == 1, \
            "zt build should exit 1 when the source file is missing"


class TestImageUnchangedByDebugFlags:
    def test_map_flag_does_not_change_sna(self, monkeypatch, tmp_path, program):
        out1 = tmp_path / "a.sna"
        out2 = tmp_path / "b.sna"
        run_cli(monkeypatch, "build", str(program), "-o", str(out1), "--no-stdlib")
        run_cli(monkeypatch, "build", str(program), "-o", str(out2), "--no-stdlib",
                "--map", str(tmp_path / "out.map"),
                "--sld", str(tmp_path / "out.sld"),
                "--fsym", str(tmp_path / "out.fsym"))
        assert out1.read_bytes() == out2.read_bytes(), \
            "emitting debug artifacts must not change the .sna bytes"
