"""
Pytest plugin that collects Forth `test-*` words from `test_*.fs` files and runs each one as an individual pytest item via `zt.test_runner.compile_and_run_word`.

Every word is collected twice: once against the threaded build and once, as
`<word>[native]`, against the native backend.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.test_runner import (
    ForthTestResult,
    TEST_WORD_RE,
    compile_and_run_word,
)


NATIVE_SUFFIX = "[native]"
LAYOUT_SENSITIVE = {
    "test-plot-each-row-independent":
        "plot-buf skips the carry when indexing mask-table, so it only works while "
        "the table does not straddle a page; the native layout places it across one",
}


def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".fs" and file_path.name.startswith("test_"):
        return ForthFile.from_parent(parent, path=file_path)


class ForthFile(pytest.File):

    def collect(self):
        source = self.path.read_text()
        for match in TEST_WORD_RE.finditer(source):
            word = match.group(1)
            yield ForthItem.from_parent(self, name=word, source=source, word=word)
            yield _native_item(self, word, source)


def _native_item(parent, word: str, source: str) -> "ForthItem":
    item = ForthItem.from_parent(
        parent, name=f"{word}{NATIVE_SUFFIX}", source=source, word=word, native=True,
    )
    if word in LAYOUT_SENSITIVE:
        item.add_marker(pytest.mark.xfail(reason=LAYOUT_SENSITIVE[word]))
    return item


class ForthItem(pytest.Item):

    def __init__(self, *, name, parent, source, word, native=False):
        super().__init__(name, parent)
        self._source = source
        self._word = word
        self._native = native

    def runtest(self):
        result = self._run()
        if result.failed:
            raise ForthAssertionError(self.name, result)

    def _run(self) -> ForthTestResult:
        try:
            return compile_and_run_word(
                self._source, self._word,
                extra_include_dirs=[self.path.parent],
                native=self._native,
            )
        except NotImplementedError as unsupported:
            if not self._native:
                raise
            pytest.skip(f"not yet supported by the native backend: {unsupported}")

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
