"""
Guards against the `make examples` target silently skipping example projects.
Parses `make -n examples` output and asserts that every example directory /
single-file under examples/ has a build rule planned.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
SNA_TARGET_RE = re.compile(r"-o\s+build/([A-Za-z0-9_-]+)\.sna")


def _planned_targets() -> set[str]:
    result = subprocess.run(
        ["make", "-Bn", "examples"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    return set(SNA_TARGET_RE.findall(result.stdout))


def _expected_targets() -> set[str]:
    single = {p.stem for p in EXAMPLES_DIR.glob("*.fs")}
    multi = {p.parent.name for p in EXAMPLES_DIR.glob("*/main.fs")}
    return single | multi


@pytest.fixture(scope="module")
def planned() -> set[str]:
    return _planned_targets()


class TestMakeExamplesCoverage:

    def test_every_example_is_planned_for_build(self, planned):
        expected = _expected_targets()
        missing = expected - planned
        assert not missing, (
            f"make examples should build every example under examples/; "
            f"missing: {sorted(missing)}"
        )

    @pytest.mark.parametrize("name", sorted(_expected_targets()))
    def test_example_has_build_rule(self, planned, name):
        assert name in planned, (
            f"{name} should have a build/{name}.sna rule wired into `make examples`"
        )


class TestBuildFlagsPer128kExample:

    @pytest.mark.parametrize("name", ["plasma-128k"])
    def test_128k_example_uses_128k_target(self, name):
        result = subprocess.run(
            ["make", "-Bn", f"build/{name}.sna"],
            capture_output=True, text=True, cwd=REPO_ROOT, check=True,
        )
        assert "--target 128k" in result.stdout, (
            f"{name} should be built with --target 128k; "
            f"planned command: {result.stdout!r}"
        )
