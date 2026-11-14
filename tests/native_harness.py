"""
Shared helper for native-backend tests: builds one Forth program with either backend,
runs it in the simulator and captures everything an observer could tell apart.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from zt.compile.compiler import Compiler
from zt.sim import (
    DEFAULT_DATA_STACK_TOP_128K,
    DEFAULT_RETURN_STACK_TOP_128K,
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    _read_data_stack,
)

SCREEN = slice(0x4000, 0x5B00)
STACKS_128K = {
    "data_stack_top": DEFAULT_DATA_STACK_TOP_128K,
    "return_stack_top": DEFAULT_RETURN_STACK_TOP_128K,
}


@dataclass(frozen=True)
class Outcome:
    halted: bool
    stack: tuple[int, ...]
    screen: bytes
    port_writes: tuple[tuple[int, int], ...]
    t_states: int
    image_size: int

    @property
    def observable(self) -> tuple:
        return (self.halted, self.stack, self.screen, self.port_writes)


def compile_program(
    source: str,
    *,
    source_name: str = "<input>",
    include_dirs: Iterable[Path] = (),
    mode: str = "48k",
) -> Compiler:
    stacks = STACKS_128K if mode == "128k" else {}
    compiler = Compiler(include_dirs=list(include_dirs), **stacks)
    compiler.include_stdlib()
    compiler.compile_source(source, source=source_name)
    compiler.compile_main_call()
    return compiler


def build_image(compiler: Compiler, *, native: bool) -> tuple[bytes, int]:
    if native:
        return compiler.build_native()
    return compiler.build(), compiler.words["_start"].address


def run_program(
    source: str,
    *,
    native: bool,
    source_name: str = "<input>",
    include_dirs: Iterable[Path] = (),
    mode: str = "48k",
    max_ticks: int = 20_000_000,
    input_buffer: bytes = b"",
) -> Outcome:
    compiler = compile_program(
        source, source_name=source_name, include_dirs=include_dirs, mode=mode,
    )
    image, start = build_image(compiler, native=native)
    machine = _load(compiler, image, start, mode, input_buffer)
    machine.run(max_ticks=max_ticks)
    return Outcome(
        halted=machine.halted,
        stack=tuple(_read_data_stack(machine, compiler.data_stack_top, False)),
        screen=bytes(machine.mem[SCREEN]),
        port_writes=tuple(machine._outputs),
        t_states=machine._t_states,
        image_size=len(image),
    )


def run_file(path: Path, *, native: bool, **options) -> Outcome:
    return run_program(
        path.read_text(), native=native, source_name=str(path), **options,
    )


def run_both(source: str, **options) -> tuple[Outcome, Outcome]:
    return (
        run_program(source, native=False, **options),
        run_program(source, native=True, **options),
    )


def _load(
    compiler: Compiler, image: bytes, start: int, mode: str, input_buffer: bytes,
) -> Z80:
    machine = Z80(mode=mode)
    machine.load(compiler.origin, image)
    machine.load(SPECTRUM_FONT_BASE, TEST_FONT)
    for bank, data in compiler.banks().items():
        machine.load_bank(bank, data)
    machine.input_buffer = bytearray(input_buffer)
    machine.pc = start
    return machine
