"""
Forth test runner behind `zt test`. Discovers `test-*` words in `.fs` files, compiles and runs each under the simulator, and aggregates `TestSummary` results.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from zt.compiler import Compiler


STDLIB_DIR = Path(__file__).resolve().parent.parent.parent / "stdlib"
TEST_WORD_RE = re.compile(r"^\s*:\s+(test-\S+)", re.MULTILINE)


@dataclass(frozen=True)
class ForthTestResult:
    failed: bool
    expected: int | None = None
    actual: int | None = None


@dataclass(frozen=True)
class TestEvent:
    path: Path
    word: str
    result: ForthTestResult


@dataclass(frozen=True)
class TestSummary:
    passed: int
    failures: list[TestEvent]

    @property
    def success(self) -> bool:
        return not self.failures

    @property
    def total(self) -> int:
        return self.passed + len(self.failures)


class TestDiscoveryError(Exception):
    pass


def run_tests(
    specs: Iterable[str | Path],
    *,
    keyword: str | None = None,
    stop_on_first_failure: bool = False,
    on_result: Callable[[TestEvent], None] | None = None,
    max_ticks: int = 1_000_000,
) -> TestSummary:
    passed = 0
    failures: list[TestEvent] = []
    for path, word in discover_tests(specs):
        if keyword is not None and keyword not in word:
            continue
        result = _run_one(path, word, max_ticks)
        event = TestEvent(path=path, word=word, result=result)
        if on_result is not None:
            on_result(event)
        if result.failed:
            failures.append(event)
            if stop_on_first_failure:
                break
        else:
            passed += 1
    return TestSummary(passed=passed, failures=failures)


def _run_one(path: Path, word: str, max_ticks: int) -> ForthTestResult:
    source = path.read_text()
    return compile_and_run_word(
        source, word,
        extra_include_dirs=[path.parent],
        max_ticks=max_ticks,
    )


def discover_tests(specs: Iterable[str | Path]) -> Iterator[tuple[Path, str]]:
    for spec in specs:
        yield from _expand_spec(spec)


def _expand_spec(spec: str | Path) -> Iterator[tuple[Path, str]]:
    file_path, word = _split_word_spec(spec)
    if word is not None:
        yield from _one_word(file_path, word)
        return
    if file_path.is_dir():
        yield from _walk_directory(file_path)
        return
    if file_path.is_file():
        yield from _words_in_file(file_path)
        return
    raise TestDiscoveryError(f"no such path: {file_path}")


def _split_word_spec(spec: str | Path) -> tuple[Path, str | None]:
    text = str(spec)
    if "::" in text:
        file_part, word = text.split("::", 1)
        return Path(file_part), word
    return Path(text), None


def _one_word(file_path: Path, word: str) -> Iterator[tuple[Path, str]]:
    available = list(_words_in_file(file_path))
    for _, candidate in available:
        if candidate == word:
            yield file_path, word
            return
    raise TestDiscoveryError(
        f"word {word!r} not found in {file_path}"
    )


def _walk_directory(root: Path) -> Iterator[tuple[Path, str]]:
    for path in sorted(root.rglob("test_*.fs")):
        yield from _words_in_file(path)


def _words_in_file(path: Path) -> Iterator[tuple[Path, str]]:
    source = path.read_text()
    for match in TEST_WORD_RE.finditer(source):
        yield path, match.group(1)


def compile_and_run_word(
    source: str,
    test_word: str,
    *,
    max_ticks: int = 1_000_000,
    extra_include_dirs: Iterable[Path] = (),
) -> ForthTestResult:
    compiler, image = _compile(source, test_word, extra_include_dirs)
    machine = _run(compiler, image, max_ticks, test_word)
    if _read_var(machine, compiler, "_result") == 0:
        return ForthTestResult(failed=False)
    return ForthTestResult(
        failed=True,
        expected=_read_var(machine, compiler, "_expected"),
        actual=_read_var(machine, compiler, "_actual"),
    )


def _compile(
    source: str, test_word: str, extra_include_dirs: Iterable[Path],
) -> tuple[Compiler, bytes]:
    full_source = f"{source}\n: main {test_word} halt ;\n"
    compiler = Compiler(include_dirs=[STDLIB_DIR, *extra_include_dirs])
    compiler.compile_source(full_source)
    compiler.compile_main_call()
    return compiler, compiler.build()


def _run(compiler: Compiler, image: bytes, max_ticks: int, test_word: str):
    from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80

    m = Z80()
    m.load(compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = compiler.words["_start"].address
    m.run(max_ticks=max_ticks)
    if not m.halted:
        raise TimeoutError(
            f"forth test {test_word!r} did not halt within {max_ticks} ticks"
        )
    return m


def _read_var(machine, compiler: Compiler, name: str) -> int:
    word = compiler.words.get(name)
    if word is None or word.data_address is None:
        raise RuntimeError(
            f"{name!r} is not a variable (did you `include test-lib.fs`?)"
        )
    addr = word.data_address
    return machine.mem[addr] | (machine.mem[addr + 1] << 8)
