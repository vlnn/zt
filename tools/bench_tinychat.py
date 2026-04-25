"""Benchmark how many T-states it takes to generate `HELLO -> HI`.

Loads the simulator, feeds HELLO\\r, runs until both 'HI' chars are on screen
or max_ticks expires. Prints tick count and wall time. The model's behaviour
is invariant: 'HELLO' always produces 'HI', so an arbitrary speed change must
not change which characters appear.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from zt.compile.compiler import Compiler
from zt.sim import (
    DEFAULT_DATA_STACK_TOP_128K,
    DEFAULT_RETURN_STACK_TOP_128K,
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    decode_screen_text,
)


def build_image() -> tuple[Compiler, bytes]:
    main = Path("examples/zlm-tinychat/main.fs")
    c = Compiler(
        data_stack_top=DEFAULT_DATA_STACK_TOP_128K,
        return_stack_top=DEFAULT_RETURN_STACK_TOP_128K,
    )
    c.include_stdlib()
    c.compile_source(main.read_text(), source=str(main))
    c.compile_main_call()
    return c, c.build()


def run_until_response(max_ticks: int = 60_000_000) -> tuple[int, float, str]:
    c, image = build_image()
    m = Z80(mode="128k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    for bank, data in c.banks().items():
        m.load_bank(bank, data)
    m.pc = c.words["_start"].address
    m.input_buffer = bytearray(b"HELLO\r")
    t0 = time.time()
    m.run(max_ticks=max_ticks)
    wall = time.time() - t0
    raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0).decode("ascii", errors="replace")
    return m._t_states, wall, raw


if __name__ == "__main__":
    ticks, wall, screen = run_until_response()
    print(f"ticks: {ticks:>12,}  wall: {wall:5.1f}s  bytes: {len(screen)}")
    print(f"screen[:60]: {screen[:60]!r}")
    assert "HELLO" in screen, "HELLO should be echoed"
    assert "HI" in screen, "model should output HI"
    print("OK: HELLO and HI both on screen")
