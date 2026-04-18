from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zt.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT / "src")},
    )


@pytest.fixture
def project(tmp_path):
    (tmp_path / "test_pass.fs").write_text(textwrap.dedent("""\
        include test-lib.fs
        : test-one  1 1 assert-eq ;
        : test-two  2 2 assert-eq ;
    """))
    (tmp_path / "test_fail.fs").write_text(textwrap.dedent("""\
        include test-lib.fs
        : test-broken  3 4 + 8 assert-eq ;
    """))
    return tmp_path


class TestZtTestExitCodes:

    def test_all_pass_exits_zero(self, project):
        result = _run_cli("test", str(project / "test_pass.fs"))
        assert result.returncode == 0, \
            f"all-passing run should exit 0; stderr={result.stderr}"

    def test_any_failure_exits_non_zero(self, project):
        result = _run_cli("test", str(project / "test_fail.fs"))
        assert result.returncode != 0, \
            "zt test should exit non-zero when any test fails"


class TestZtTestOutput:

    def test_summary_reports_total_count(self, project):
        result = _run_cli("test", str(project / "test_pass.fs"))
        assert "2 passed" in result.stdout, \
            f"summary should report total passes; stdout={result.stdout!r}"

    def test_summary_reports_failures(self, project):
        result = _run_cli("test", str(project / "test_fail.fs"))
        combined = result.stdout + result.stderr
        assert "1 failed" in combined, \
            f"summary should mention failure count; stdout={result.stdout!r}"

    def test_failure_shows_expected_and_actual(self, project):
        result = _run_cli("test", str(project / "test_fail.fs"))
        combined = result.stdout + result.stderr
        assert "expected: 8" in combined, "should print expected value"
        assert "actual:   7" in combined, "should print actual value"

    def test_failure_names_the_word(self, project):
        result = _run_cli("test", str(project / "test_fail.fs"))
        combined = result.stdout + result.stderr
        assert "test-broken" in combined, "failure line should name the failing word"


class TestZtTestFilters:

    def test_k_filter_runs_matching_only(self, project):
        result = _run_cli("test", str(project), "-k", "one")
        assert "1 passed" in result.stdout, \
            f"-k 'one' should match only test-one; stdout={result.stdout!r}"

    def test_x_stops_on_first_failure(self, project):
        (project / "test_extra.fs").write_text(textwrap.dedent("""\
            include test-lib.fs
            : test-alpha  1 1 assert-eq ;
        """))
        result = _run_cli("test", str(project), "-x")
        assert result.returncode != 0, "-x should still exit non-zero on failure"

    def test_file_word_spec_runs_single_test(self, project):
        spec = f"{project / 'test_pass.fs'}::test-one"
        result = _run_cli("test", spec)
        assert "1 passed" in result.stdout, \
            "file::word spec should run exactly one test"


class TestZtTestVerbose:

    def test_verbose_lists_each_test(self, project):
        result = _run_cli("test", str(project / "test_pass.fs"), "-v")
        assert "test-one" in result.stdout, "-v should list each word"
        assert "test-two" in result.stdout, "-v should list each word"
        assert "PASSED" in result.stdout, "-v should show PASSED marker"

    def test_non_verbose_uses_dots(self, project):
        result = _run_cli("test", str(project / "test_pass.fs"))
        assert ".." in result.stdout, \
            "non-verbose mode should print one dot per passing test"


class TestZtTestDefaults:

    def test_default_path_is_cwd(self, project):
        result = _run_cli("test", cwd=project)
        combined = result.stdout + result.stderr
        assert "1 failed" in combined, \
            "bare 'zt test' should discover tests under cwd"
