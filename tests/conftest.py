"""
Pytest plugin that collects Forth `test-*` words from `test_*.fs` files and runs each one as an individual pytest item via `zt.test_runner.compile_and_run_word`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.test_runner import (
    ForthTestResult,
    TEST_WORD_RE,
    compile_and_run_word,
)


def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".fs" and file_path.name.startswith("test_"):
        return ForthFile.from_parent(parent, path=file_path)


class ForthFile(pytest.File):

    def collect(self):
        source = self.path.read_text()
        for match in TEST_WORD_RE.finditer(source):
            yield ForthItem.from_parent(self, name=match.group(1), source=source)


class ForthItem(pytest.Item):

    def __init__(self, *, name, parent, source):
        super().__init__(name, parent)
        self._source = source

    def runtest(self):
        result = compile_and_run_word(
            self._source, self.name,
            extra_include_dirs=[self.path.parent],
        )
        if result.failed:
            raise ForthAssertionError(self.name, result)

    def repr_failure(self, excinfo, style=None):
        err = excinfo.value
        if not isinstance(err, ForthAssertionError):
            return super().repr_failure(excinfo, style)
        return _format_failure(err)

    def reportinfo(self):
        return self.path, None, f"forth: {self.name}"


class ForthAssertionError(Exception):

    def __init__(self, test_word: str, result: ForthTestResult):
        self.test_word = test_word
        self.result = result
        super().__init__(f"forth assertion failed in {test_word!r}")


def _format_failure(err: ForthAssertionError) -> str:
    lines = [f"Forth assertion failed in `{err.test_word}`"]
    if err.result.expected is not None:
        lines.append(f"  expected: {err.result.expected}")
        lines.append(f"  actual:   {err.result.actual}")
    return "\n".join(lines)
