"""End-to-end test: install a Forth colon word as IM 2 handler.

The shim inserted by `IM2-HANDLER!` saves and restores AF/HL/BC/DE/IX/IY
around the handler call, so a user can write the ISR body in plain Forth
with no `:::` Z80 boilerplate. This file pins down that behaviour.
"""
from __future__ import annotations

import pytest

from zt.assemble.im2_table import (
    IM2_HANDLER_SLOT_ADDR,
    IM2_TABLE_ADDR,
    IM2_TABLE_LEN,
    IM2_VECTOR_BYTE,
)
from zt.compile.compiler import Compiler
from zt.sim import (
    DEFAULT_DATA_STACK_TOP_128K,
    DEFAULT_RETURN_STACK_TOP_128K,
    FRAME_T_STATES_128K,
    Z80,
)


SOURCE_BUMPS_A_COUNTER = """
variable hits

: bump  ( -- )  1 hits +! ;

: main
    ['] bump im2-handler!  ei
    begin again ;
"""


def _build(source: str) -> tuple[Compiler, Z80]:
    c = Compiler(
        data_stack_top=DEFAULT_DATA_STACK_TOP_128K,
        return_stack_top=DEFAULT_RETURN_STACK_TOP_128K,
    )
    c.include_stdlib()
    c.compile_source(source)
    c.compile_main_call()
    image = c.build()
    m = Z80(mode="128k")
    m.load(c.origin, image)
    for bank, data in c.banks().items():
        m.load_bank(bank, data)
    for i in range(IM2_TABLE_LEN):
        m._wb(IM2_TABLE_ADDR + i, IM2_VECTOR_BYTE)
    m._wb(IM2_HANDLER_SLOT_ADDR, 0xC3)
    m._wb(IM2_HANDLER_SLOT_ADDR + 1, 0x00)
    m._wb(IM2_HANDLER_SLOT_ADDR + 2, 0x00)
    m.pc = c.words["_start"].address
    return c, m


def _hits(c: Compiler, m: Z80) -> int:
    return m._rw(c.words["hits"].data_address)


@pytest.mark.parametrize("frames", [1, 3, 7, 12])
def test_colon_word_runs_once_per_frame(frames):
    c, m = _build(SOURCE_BUMPS_A_COUNTER)
    m.run_until(FRAME_T_STATES_128K * frames + 5_000)
    assert _hits(c, m) == frames, (
        f"colon-word ISR should fire once per ULA frame; "
        f"after {frames} frames hits should equal {frames}, got {_hits(c, m)}"
    )


def test_interrupt_count_matches_hits():
    c, m = _build(SOURCE_BUMPS_A_COUNTER)
    m.run_until(FRAME_T_STATES_128K * 7 + 5_000)
    assert m.interrupt_count == _hits(c, m), (
        f"every IM 2 dispatch should run the colon body exactly once; "
        f"got {m.interrupt_count} fires vs {_hits(c, m)} hits"
    )


def test_foreground_keeps_running_across_many_frames():
    c, m = _build(SOURCE_BUMPS_A_COUNTER)
    m.run_until(FRAME_T_STATES_128K * 30 + 5_000)
    assert m.interrupt_count >= 30, (
        f"a steady stream of fires across 30 frames proves the foreground "
        f"is being resumed correctly via RETI; got {m.interrupt_count}"
    )


SOURCE_TWO_LEVEL_NESTED = """
variable hits

: inner  ( -- )  1 hits +! ;
: outer  ( -- )  inner inner ;

: main
    ['] outer im2-handler!  ei
    begin again ;
"""


def test_nested_colon_calls_inside_isr():
    c, m = _build(SOURCE_TWO_LEVEL_NESTED)
    m.run_until(FRAME_T_STATES_128K * 4 + 5_000)
    assert _hits(c, m) == 8, (
        f"nested colon calls inside the handler should work normally; "
        f"`outer` calls `inner` twice, 4 frames * 2 = 8 hits, got {_hits(c, m)}"
    )


SOURCE_FOREGROUND_DOES_WORK = """
variable hits
variable foreground-counter

: bump  ( -- )  1 hits +! ;

: main
    ['] bump im2-handler!  ei
    begin
        1 foreground-counter +!
    again ;
"""


def test_foreground_keeps_advancing_between_fires():
    c, m = _build(SOURCE_FOREGROUND_DOES_WORK)
    m.run_until(FRAME_T_STATES_128K * 5 + 5_000)
    fg_addr = c.words["foreground-counter"].data_address
    fg_count = m._rw(fg_addr)
    assert fg_count > 100, (
        f"foreground should advance freely between IM 2 fires; "
        f"after 5 frames foreground-counter should be well above 100, "
        f"got {fg_count}"
    )
    assert _hits(c, m) == 5, (
        f"ISR should still fire 5 times despite a busy foreground; got {_hits(c, m)}"
    )
