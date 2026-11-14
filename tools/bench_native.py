"""Compare the threaded and native builds of Forth programs that run to HALT.

    uv run python tools/bench_native.py tests/benchmarks/*.fs examples/reaction/bench.fs

Prints T-states and image size for both builds and fails if their data stack,
screen memory or port writes differ.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from zt.compile.compiler import Compiler
from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80, _read_data_stack

SCREEN = slice(0x4000, 0x5B00)
INCLUDE_DIRS = [Path("examples")]
MAX_TICKS = 100_000_000


@dataclass(frozen=True)
class Run:
    observable: tuple
    t_states: int
    size: int


def compiled(path: Path) -> Compiler:
    compiler = Compiler(include_dirs=INCLUDE_DIRS)
    compiler.include_stdlib()
    compiler.compile_source(path.read_text(), source=str(path))
    compiler.compile_main_call()
    return compiler


def run(path: Path, *, native: bool) -> Run:
    compiler = compiled(path)
    image, start = compiler.build_native() if native else compiler.build_tree_shaken()
    machine = Z80()
    machine.load(compiler.origin, image)
    machine.load(SPECTRUM_FONT_BASE, TEST_FONT)
    machine.pc = start
    machine.run(max_ticks=MAX_TICKS)
    stack = tuple(_read_data_stack(machine, compiler.data_stack_top, False))
    observable = (machine.halted, stack, bytes(machine.mem[SCREEN]), tuple(machine._outputs))
    return Run(observable, machine._t_states, len(image))


def report(path: Path) -> bool:
    threaded, native = run(path, native=False), run(path, native=True)
    same = threaded.observable == native.observable and threaded.observable[0]
    print(
        f"{str(path):36} {'ok      ' if same else 'MISMATCH'} "
        f"T {threaded.t_states:>12,} -> {native.t_states:>12,}  "
        f"x{threaded.t_states / native.t_states:4.2f}   "
        f"bytes {threaded.size:>6} -> {native.size:>6} "
        f"({100 * native.size / threaded.size:.0f}%)"
    )
    return same


if __name__ == "__main__":
    results = [report(Path(arg)) for arg in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
