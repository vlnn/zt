"""
Tests for `run_profile_command`: single-run mode, image mode, word matching, JSON output, save / diff, and regression gating.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from zt.cli.profile import (
    EXIT_OK,
    EXIT_REGRESSION,
    EXIT_RUNTIME,
    ProfileArgs,
    run_profile_command,
)


SAMPLE_SOURCE = """\
: banner
    ." ==================" cr
    ."   FORTH ON Z80"     cr
    ." ==================" cr ;

: count-to-five
    6 1 do i . loop cr ;

: greet
    banner
    ." counting: " count-to-five ;

: main 7 0 cls begin greet again ;
"""

SMALL_BUDGET = 50_000


@pytest.fixture
def sample_fs(tmp_path: Path) -> Path:
    """A small, self-contained Forth program written to a tmp file.

    Runtime profile of this program reliably exercises `emit`, `cr`, and
    several stdlib words, which is what the CLI tests need to assert against.
    """
    path = tmp_path / "sample.fs"
    path.write_text(SAMPLE_SOURCE)
    return path


def _args(**overrides) -> ProfileArgs:
    defaults = dict(
        source=None, image=None, symbols=None,
        max_ticks=SMALL_BUDGET, words=[], baseline=None,
        save=None, json_output=False, fail_if_slower=None,
    )
    defaults.update(overrides)
    return ProfileArgs(**defaults)


def _run(args: ProfileArgs) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = run_profile_command(args, out, err)
    return code, out.getvalue(), err.getvalue()


class TestSingleRunMode:

    def test_source_run_exits_ok(self, sample_fs: Path):
        code, _out, _err = _run(_args(source=sample_fs))
        assert code == EXIT_OK, "a clean profile of the sample program should exit 0"

    def test_output_contains_expected_columns(self, sample_fs: Path):
        _code, out, _err = _run(_args(source=sample_fs))
        for col in ["Word", "Calls", "Self", "Self%", "Incl", "Incl%", "Avg"]:
            assert col in out, f"single-mode table should contain {col!r} column"

    def test_output_contains_total_line(self, sample_fs: Path):
        _code, out, _err = _run(_args(source=sample_fs))
        assert "Total:" in out, "single-mode output should include a totals line"

    def test_words_filter_restricts_rows(self, sample_fs: Path):
        _code, out, _err = _run(_args(source=sample_fs, words=["emit"]))
        assert "emit" in out, "selected word should appear"
        assert "docol" not in out, "unselected word should not appear"

    def test_missing_source_exits_runtime(self, tmp_path: Path):
        code, _out, err = _run(_args(source=tmp_path / "does_not_exist.fs"))
        assert code == EXIT_RUNTIME, "missing source should yield exit 3"
        assert "not found" in err, "stderr should explain why we failed"


class TestWordMatching:

    def test_all_or_nothing_typo_exits_runtime(self, sample_fs: Path):
        code, _out, err = _run(_args(source=sample_fs, words=["emit", "NOTAWORD"]))
        assert code == EXIT_RUNTIME, "any missing word should trigger all-or-nothing exit"
        assert "NOTAWORD" in err, "stderr should name the missing word"
        assert "not found in profile" in err, "stderr should explain the error"

    def test_all_valid_words_passes(self, sample_fs: Path):
        code, _out, _err = _run(_args(source=sample_fs, words=["emit", "cr"]))
        assert code == EXIT_OK, "a word list containing only valid names should succeed"


class TestJsonOutput:

    def test_json_flag_emits_valid_json(self, sample_fs: Path):
        _code, out, _err = _run(_args(source=sample_fs, json_output=True))
        data = json.loads(out)
        assert "entries" in data, "JSON output should include entries"
        assert "total_ticks" in data, "JSON output should include total_ticks"

    def test_json_preserves_selected_words(self, sample_fs: Path):
        _code, out, _err = _run(_args(source=sample_fs, words=["emit"], json_output=True))
        data = json.loads(out)
        words = {e["word"] for e in data["entries"]}
        assert words == {"emit"}, "--words filter should carry through to --json output"


class TestSave:

    def test_writes_both_prof_and_zprof(self, tmp_path: Path, sample_fs: Path):
        base = tmp_path / "snapshot"
        code, _out, _err = _run(_args(source=sample_fs, save=base))
        assert code == EXIT_OK, "save should not fail a single-run profile"
        assert (tmp_path / "snapshot.prof").exists(), "--save should write the text .prof"
        assert (tmp_path / "snapshot.zprof").exists(), "--save should write the JSON .zprof"

    def test_zprof_is_roundtrippable(self, tmp_path: Path, sample_fs: Path):
        base = tmp_path / "snapshot"
        _run(_args(source=sample_fs, save=base))
        data = json.loads((tmp_path / "snapshot.zprof").read_text())
        assert data["version"] == 1, "saved zprof should declare current version"
        assert data["entries"], "saved zprof should contain entries"


class TestDiffMode:

    @pytest.fixture
    def baseline(self, tmp_path: Path, sample_fs: Path) -> Path:
        base = tmp_path / "baseline"
        _run(_args(source=sample_fs, save=base))
        return tmp_path / "baseline.zprof"

    def test_identical_run_has_zero_delta(self, sample_fs: Path, baseline: Path):
        _code, out, _err = _run(_args(source=sample_fs, baseline=baseline, words=["emit"]))
        assert "+0.0%" in out or "+0" in out, (
            "comparing the sample against its own snapshot should show zero deltas"
        )

    def test_diff_table_has_delta_columns(self, sample_fs: Path, baseline: Path):
        _code, out, _err = _run(_args(source=sample_fs, baseline=baseline))
        for col in ["Base Incl", "Curr Incl"]:
            assert col in out, f"diff mode should include column {col!r}"

    def test_missing_baseline_exits_runtime(self, tmp_path: Path, sample_fs: Path):
        bad = tmp_path / "does_not_exist.zprof"
        code, _out, err = _run(_args(source=sample_fs, baseline=bad))
        assert code == EXIT_RUNTIME, "missing baseline should yield exit 3"
        assert "not found" in err, "stderr should explain the missing baseline"


class TestRegressionGating:

    def test_no_fail_flag_means_exit_zero_even_with_regressions(
        self, tmp_path: Path, sample_fs: Path,
    ):
        halved = self._halved_baseline(tmp_path, sample_fs)
        code, _out, _err = _run(
            _args(source=sample_fs, baseline=halved, words=["emit"])
        )
        assert code == EXIT_OK, (
            "without --fail-if-slower, a regression should not change exit code"
        )

    def test_regression_over_threshold_exits_one(
        self, tmp_path: Path, sample_fs: Path,
    ):
        halved = self._halved_baseline(tmp_path, sample_fs)
        code, _out, err = _run(
            _args(source=sample_fs, baseline=halved, words=["emit"], fail_if_slower=5.0)
        )
        assert code == EXIT_REGRESSION, (
            "100%% regression with threshold 5%% should exit 1"
        )
        assert "emit" in err, "stderr should name the regressed word"

    def test_no_regression_passes_threshold(
        self, tmp_path: Path, sample_fs: Path,
    ):
        base = tmp_path / "baseline"
        _run(_args(source=sample_fs, save=base))
        code, _out, _err = _run(
            _args(source=sample_fs, baseline=tmp_path / "baseline.zprof",
                  words=["emit"], fail_if_slower=1.0)
        )
        assert code == EXIT_OK, "identical run should exit 0 even with tight threshold"

    def _halved_baseline(self, tmp_path: Path, sample_fs: Path) -> Path:
        base = tmp_path / "baseline"
        _run(_args(source=sample_fs, save=base))
        path = tmp_path / "baseline.zprof"
        data = json.loads(path.read_text())
        for e in data["entries"]:
            e["incl_t_states"] //= 2
        path.write_text(json.dumps(data))
        return path


class TestImageMode:

    @pytest.fixture
    def built(self, tmp_path: Path, sample_fs: Path) -> tuple[Path, Path]:
        from zt.cli.main import _build_compiler as build
        import argparse as ap
        ns = ap.Namespace(
            source=sample_fs, origin=0x8000, dstack=0xFF00, rstack=0xFE00,
            include_dirs=[], optimize=True, inline_next=True,
            inline_primitives=True, stdlib=True,
        )
        compiler = build(ns)
        image = compiler.build()
        from zt.format.sna import build_sna
        sna_path = tmp_path / "sample.sna"
        map_path = tmp_path / "sample.map"
        sna_path.write_bytes(build_sna(
            image, 0x8000, entry=compiler.words["_start"].address,
        ))
        map_path.write_text(
            "\n".join(
                f"${w.address:04X} {name}"
                for name, w in compiler.words.items()
                if w.address
            ) + "\n"
        )
        return sna_path, map_path

    def test_image_with_sibling_map_works(self, built):
        sna, _map = built
        code, out, _err = _run(_args(image=sna, words=["emit"]))
        assert code == EXIT_OK, "--image should work when sibling .map exists"
        assert "emit" in out, "image-mode output should include selected word"

    def test_image_missing_symbols_exits_runtime(self, tmp_path: Path, built):
        sna, _map = built
        elsewhere = tmp_path / "has_no_map.sna"
        elsewhere.write_bytes(sna.read_bytes())
        code, _out, err = _run(_args(image=elsewhere))
        assert code == EXIT_RUNTIME, "missing map should exit 3"
        assert "not found" in err, "stderr should explain the missing symbol map"

    def test_image_explicit_symbols_override(self, tmp_path: Path, built):
        sna, map_path = built
        elsewhere = tmp_path / "relocated.sna"
        elsewhere.write_bytes(sna.read_bytes())
        code, out, _err = _run(_args(image=elsewhere, symbols=map_path, words=["emit"]))
        assert code == EXIT_OK, "explicit --symbols should override sibling search"
        assert "emit" in out, "explicit --symbols run should find the requested word"
