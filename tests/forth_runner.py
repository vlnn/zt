"""
Standalone helper for compiling and running a single Forth `test-*` word under the simulator, used by tests that exercise the test-runner plumbing itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from zt.compile.compiler import Compiler


STDLIB_DIR = Path(__file__).resolve().parent.parent / "src" / "zt" / "stdlib"


@dataclass(frozen=True)
class ForthTestResult:
    failed: bool
    expected: int | None = None
    actual: int | None = None


def compile_and_run_word(
    source: str,
    test_word: str,
    *,
    max_ticks: int = 1_000_000,
) -> ForthTestResult:
    compiler, image = _compile(source, test_word)
    machine = _run(compiler, image, max_ticks, test_word)
    if _read_var(machine, compiler, "_result") == 0:
        return ForthTestResult(failed=False)
    return ForthTestResult(
        failed=True,
        expected=_read_var(machine, compiler, "_expected"),
        actual=_read_var(machine, compiler, "_actual"),
    )


def _compile(source: str, test_word: str) -> tuple[Compiler, bytes]:
    full_source = f"{source}\n: main {test_word} halt ;\n"
    compiler = Compiler(include_dirs=[STDLIB_DIR])
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
