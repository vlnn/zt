"""Smoke-run the tinychat .sna in the 128K simulator and print the screen."""
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


MAIN = Path(__file__).parent.parent / "examples" / "zlm-tinychat" / "main.fs"


def main():
    max_ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 5_000_000
    print(f"compiling {MAIN}...")
    c = Compiler(
        data_stack_top=DEFAULT_DATA_STACK_TOP_128K,
        return_stack_top=DEFAULT_RETURN_STACK_TOP_128K,
    )
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    image = c.build()
    print(f"  code: {len(image)} bytes; banks: {sorted(c.banks().keys())}")

    m = Z80(mode="128k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    for bank, data in c.banks().items():
        m.load_bank(bank, data)
    m.pc = c.words["_start"].address
    print(f"running with max_ticks={max_ticks:,}...")
    t0 = time.time()
    m.run(max_ticks=max_ticks)
    dt = time.time() - t0
    print(f"  finished in {dt:.1f}s; pc=${m.pc:04X}; halted={m.halted}")
    print(f"  T-states: {m._t_states:,}; instructions: {m._ticks:,}")

    raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0)
    text = raw.decode("ascii", errors="replace")
    print()
    print("=== screen ===")
    for i, line in enumerate(text.split("\r")[:6]):
        print(f"  {i:>2}: {line!r}")


if __name__ == "__main__":
    main()
