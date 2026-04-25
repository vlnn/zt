"""Iterate simulator in chunks; track cumulative T-states externally."""
import time
from pathlib import Path
from zt.compile.compiler import Compiler
from zt.sim import Z80, decode_screen_text, SPECTRUM_FONT_BASE, TEST_FONT, DEFAULT_DATA_STACK_TOP_128K, DEFAULT_RETURN_STACK_TOP_128K

def measure():
    main = Path('examples/zlm-tinychat/main.fs')
    c = Compiler(data_stack_top=DEFAULT_DATA_STACK_TOP_128K, return_stack_top=DEFAULT_RETURN_STACK_TOP_128K)
    c.include_stdlib(); c.compile_source(main.read_text(), source=str(main)); c.compile_main_call()
    image = c.build()
    m = Z80(mode='128k')
    m.load(c.origin, image); m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    for b, d in c.banks().items(): m.load_bank(b, d)
    m.pc = c.words['_start'].address
    m.input_buffer = bytearray(b'HELLO\r')
    t0 = time.time()
    cum_t = 0
    cum_instr = 0
    chunk = 1_000_000
    while cum_instr < 30_000_000:
        m.run(max_ticks=chunk)
        cum_t += m._t_states
        cum_instr += m._ticks
        raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0).decode('ascii','replace')
        if 'HI' in raw and 'HELLO' in raw:
            break
    wall = time.time() - t0
    return cum_t, cum_instr, wall

t, i, w = measure()
print(f't_states={t:,}  instr={i:,}  wall={w:.1f}s')
