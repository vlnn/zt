from __future__ import annotations

from dataclasses import dataclass, field

from zt.asm import Asm
from zt.primitives import PRIMITIVES

SPECTRUM_BORDER_PORT = 0xFE
SPECTRUM_FONT_BASE = 0x3D00
SPECTRUM_SCREEN_BASE = 0x4000
SPECTRUM_ATTR_BASE = 0x5800

DEFAULT_ORIGIN = 0x8000
DEFAULT_DATA_STACK_TOP = 0xFF00
DEFAULT_RETURN_STACK_TOP = 0xFE00
DEFAULT_MAX_TICKS = 10_000_000

FLAG_C = 0x01
FLAG_N = 0x02
FLAG_PV = 0x04
FLAG_H = 0x10
FLAG_Z = 0x40
FLAG_S = 0x80

TEST_FONT = bytes(n for n in range(32, 128) for _ in range(8))


def screen_addr(row: int, col: int, line: int = 0) -> int:
    band = row >> 3
    text_row_in_band = row & 7
    return (SPECTRUM_SCREEN_BASE
            | (band << 11)
            | (line << 8)
            | (text_row_in_band << 5)
            | col)


def decode_screen_cell(mem: bytearray, row: int, col: int) -> int:
    lines = {mem[screen_addr(row, col, line)] for line in range(8)}
    if len(lines) != 1:
        raise ValueError(
            f"inconsistent screen cell at row={row} col={col}: {sorted(lines)}"
        )
    return lines.pop()


def _decode_row(mem: bytearray, row: int, last_col: int) -> bytes:
    line = bytearray()
    for col in range(last_col):
        ch = decode_screen_cell(mem, row, col)
        if ch == 0:
            break
        line.append(ch)
    return bytes(line)


def decode_screen_text(mem: bytearray, cursor_row: int, cursor_col: int) -> bytes:
    complete_rows = [_decode_row(mem, r, 32) for r in range(cursor_row)]
    partial = _decode_row(mem, cursor_row, cursor_col)
    return b"\r".join(complete_rows + [partial])


@dataclass
class ForthResult:
    data_stack: list[int]
    border_writes: list[int] = field(default_factory=list)
    chars_out: bytes = b""


class Z80:
    __slots__ = (
        "mem", "pc", "sp", "a", "f", "b", "c", "d", "e", "h", "l",
        "ix", "iy", "halted", "iff", "_outputs", "_ticks",
    )

    def __init__(self) -> None:
        self.mem = bytearray(65536)
        self.pc = self.sp = 0
        self.a = self.f = 0
        self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.ix = self.iy = 0
        self.halted = False
        self.iff = False
        self._outputs: list[tuple[int, int]] = []
        self._ticks = 0

    @property
    def hl(self) -> int: return (self.h << 8) | self.l
    @hl.setter
    def hl(self, v: int) -> None: self.h, self.l = (v >> 8) & 0xFF, v & 0xFF

    @property
    def de(self) -> int: return (self.d << 8) | self.e
    @de.setter
    def de(self, v: int) -> None: self.d, self.e = (v >> 8) & 0xFF, v & 0xFF

    @property
    def bc(self) -> int: return (self.b << 8) | self.c
    @bc.setter
    def bc(self, v: int) -> None: self.b, self.c = (v >> 8) & 0xFF, v & 0xFF

    @property
    def af(self) -> int: return (self.a << 8) | self.f
    @af.setter
    def af(self, v: int) -> None: self.a, self.f = (v >> 8) & 0xFF, v & 0xFF

    def load(self, addr: int, data: bytes) -> None:
        self.mem[addr:addr + len(data)] = data

    def _rb(self, addr: int) -> int:
        return self.mem[addr & 0xFFFF]

    def _rw(self, addr: int) -> int:
        a = addr & 0xFFFF
        return self.mem[a] | (self.mem[(a + 1) & 0xFFFF] << 8)

    def _wb(self, addr: int, v: int) -> None:
        self.mem[addr & 0xFFFF] = v & 0xFF

    def _ww(self, addr: int, v: int) -> None:
        a = addr & 0xFFFF
        self.mem[a] = v & 0xFF
        self.mem[(a + 1) & 0xFFFF] = (v >> 8) & 0xFF

    def _fetch(self) -> int:
        v = self.mem[self.pc]
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def _fetch_word(self) -> int:
        lo = self._fetch()
        hi = self._fetch()
        return (hi << 8) | lo

    def _push(self, v: int) -> None:
        self.sp = (self.sp - 2) & 0xFFFF
        self._ww(self.sp, v)

    def _pop(self) -> int:
        v = self._rw(self.sp)
        self.sp = (self.sp + 2) & 0xFFFF
        return v

    def _flag_sz(self, v: int) -> int:
        f = 0
        if v == 0: f |= FLAG_Z
        if v & 0x80: f |= FLAG_S
        return f

    def _add8(self, a: int, b: int, carry: int = 0) -> int:
        r = a + b + carry
        half = (a & 0xF) + (b & 0xF) + carry
        self.f = 0
        if (r & 0xFF) == 0: self.f |= FLAG_Z
        if r & 0x80: self.f |= FLAG_S
        if r > 0xFF: self.f |= FLAG_C
        if half > 0xF: self.f |= FLAG_H
        if ((a ^ b) & 0x80) == 0 and ((a ^ r) & 0x80) != 0: self.f |= FLAG_PV
        return r & 0xFF

    def _sub8(self, a: int, b: int, carry: int = 0) -> int:
        r = a - b - carry
        half = (a & 0xF) - (b & 0xF) - carry
        self.f = FLAG_N
        if (r & 0xFF) == 0: self.f |= FLAG_Z
        if r & 0x80: self.f |= FLAG_S
        if r < 0: self.f |= FLAG_C
        if half < 0: self.f |= FLAG_H
        if ((a ^ b) & 0x80) != 0 and ((a ^ r) & 0x80) != 0: self.f |= FLAG_PV
        return r & 0xFF

    def _jr_cond(self, cond: bool) -> None:
        offset = self._fetch()
        if offset & 0x80: offset -= 256
        if cond:
            self.pc = (self.pc + offset) & 0xFFFF

    def _get_reg(self, idx: int) -> int:
        return (self.b, self.c, self.d, self.e, self.h, self.l, self._rb(self.hl), self.a)[idx]

    def _set_reg(self, idx: int, v: int) -> None:
        v &= 0xFF
        if   idx == 0: self.b = v
        elif idx == 1: self.c = v
        elif idx == 2: self.d = v
        elif idx == 3: self.e = v
        elif idx == 4: self.h = v
        elif idx == 5: self.l = v
        elif idx == 6: self._wb(self.hl, v)
        elif idx == 7: self.a = v

    def run(self, max_ticks: int = DEFAULT_MAX_TICKS) -> None:
        self._ticks = 0
        while not self.halted and self._ticks < max_ticks:
            self._step()
            self._ticks += 1

    def _step(self) -> None:
        op = self._fetch()
        if op == 0xCB:
            self._exec_cb()
        elif op == 0xDD:
            self._exec_dd()
        elif op == 0xFD:
            self._exec_fd()
        elif op == 0xED:
            self._exec_ed()
        else:
            self._exec_main(op)

    def _exec_main(self, op: int) -> None:
        if op == 0x00: pass
        elif op == 0x76: self.halted = True

        elif op == 0x01: self.bc = self._fetch_word()
        elif op == 0x11: self.de = self._fetch_word()
        elif op == 0x21: self.hl = self._fetch_word()
        elif op == 0x31: self.sp = self._fetch_word()

        elif op == 0x06: self.b = self._fetch()
        elif op == 0x0E: self.c = self._fetch()
        elif op == 0x16: self.d = self._fetch()
        elif op == 0x1E: self.e = self._fetch()
        elif op == 0x26: self.h = self._fetch()
        elif op == 0x2E: self.l = self._fetch()
        elif op == 0x36: self._wb(self.hl, self._fetch())
        elif op == 0x3E: self.a = self._fetch()

        elif op == 0x1A: self.a = self._rb(self.de)
        elif op == 0x3A:
            addr = self._fetch_word()
            self.a = self._rb(addr)
        elif op == 0x32:
            addr = self._fetch_word()
            self._wb(addr, self.a)

        elif 0x40 <= op <= 0x7F:
            dst, src = (op >> 3) & 7, op & 7
            self._set_reg(dst, self._get_reg(src))

        elif op == 0xC5: self._push(self.bc)
        elif op == 0xD5: self._push(self.de)
        elif op == 0xE5: self._push(self.hl)
        elif op == 0xF5: self._push(self.af)
        elif op == 0xC1: self.bc = self._pop()
        elif op == 0xD1: self.de = self._pop()
        elif op == 0xE1: self.hl = self._pop()
        elif op == 0xF1: self.af = self._pop()

        elif op == 0xEB: self.hl, self.de = self.de, self.hl
        elif op == 0xE3:
            tmp = self._rw(self.sp)
            self._ww(self.sp, self.hl)
            self.hl = tmp

        elif op == 0x09: self._add_hl(self.bc)
        elif op == 0x19: self._add_hl(self.de)
        elif op == 0x29: self._add_hl(self.hl)
        elif op == 0x03: self.bc = (self.bc + 1) & 0xFFFF
        elif op == 0x0B: self.bc = (self.bc - 1) & 0xFFFF
        elif op == 0x13: self.de = (self.de + 1) & 0xFFFF
        elif op == 0x1B: self.de = (self.de - 1) & 0xFFFF
        elif op == 0x23: self.hl = (self.hl + 1) & 0xFFFF
        elif op == 0x2B: self.hl = (self.hl - 1) & 0xFFFF

        elif op == 0x24: self.h = self._inc8(self.h)
        elif op == 0x3C: self.a = self._inc8(self.a)
        elif op == 0x3D: self.a = self._dec8(self.a)
        elif op == 0x1D: self.e = self._dec8(self.e)

        elif 0x80 <= op <= 0xBF:
            src = self._get_reg(op & 7)
            grp = (op >> 3) & 7
            if   grp == 0: self.a = self._add8(self.a, src)
            elif grp == 1: self.a = self._add8(self.a, src, self.f & FLAG_C)
            elif grp == 2: self.a = self._sub8(self.a, src)
            elif grp == 3: self.a = self._sub8(self.a, src, self.f & FLAG_C)
            elif grp == 4: self.a &= src; self.f = self._flag_sz(self.a) | FLAG_H
            elif grp == 5: self.a ^= src; self.f = self._flag_sz(self.a)
            elif grp == 6: self.a |= src; self.f = self._flag_sz(self.a)
            elif grp == 7: self._sub8(self.a, src)

        elif op == 0xE6:
            self.a &= self._fetch()
            self.f = self._flag_sz(self.a) | FLAG_H
        elif op == 0xF6:
            self.a |= self._fetch()
            self.f = self._flag_sz(self.a)
        elif op == 0xFE:
            self._sub8(self.a, self._fetch())

        elif op == 0x0F:
            c = self.a & 1
            self.a = ((self.a >> 1) | (c << 7)) & 0xFF
            self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | (FLAG_C if c else 0)

        elif op == 0x2F: self.a ^= 0xFF; self.f |= FLAG_H | FLAG_N
        elif op == 0x37: self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | FLAG_C

        elif op == 0xC3: self.pc = self._fetch_word()
        elif op == 0xCA: addr = self._fetch_word(); (self.f & FLAG_Z) and self._jp(addr)
        elif op == 0xC2: addr = self._fetch_word(); (not (self.f & FLAG_Z)) and self._jp(addr)
        elif op == 0xF2: addr = self._fetch_word(); (not (self.f & FLAG_S)) and self._jp(addr)
        elif op == 0xFA: addr = self._fetch_word(); (self.f & FLAG_S) and self._jp(addr)

        elif op == 0x18: self._jr_cond(True)
        elif op == 0x20: self._jr_cond(not (self.f & FLAG_Z))
        elif op == 0x28: self._jr_cond(bool(self.f & FLAG_Z))
        elif op == 0x30: self._jr_cond(not (self.f & FLAG_C))
        elif op == 0x38: self._jr_cond(bool(self.f & FLAG_C))
        elif op == 0x10:
            self.b = (self.b - 1) & 0xFF
            self._jr_cond(self.b != 0)

        elif op == 0xCD:
            addr = self._fetch_word()
            self._push(self.pc)
            self.pc = addr
        elif op == 0xC9: self.pc = self._pop()

        elif op == 0xD3:
            port = self._fetch()
            self._outputs.append((port | (self.a << 8), self.a))

        elif op == 0xF3: self.iff = False
        elif op == 0xFB: self.iff = True

        else:
            raise RuntimeError(f"unimplemented opcode {op:#04x} at {(self.pc - 1) & 0xFFFF:#06x}")

    def _jp(self, addr: int) -> None:
        self.pc = addr

    def _add_hl(self, v: int) -> None:
        r = self.hl + v
        self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | (FLAG_C if r > 0xFFFF else 0)
        self.hl = r & 0xFFFF

    def _inc8(self, v: int) -> int:
        r = (v + 1) & 0xFF
        self.f = (self.f & FLAG_C) | self._flag_sz(r)
        if (v & 0x0F) == 0x0F: self.f |= FLAG_H
        if v == 0x7F: self.f |= FLAG_PV
        return r

    def _dec8(self, v: int) -> int:
        r = (v - 1) & 0xFF
        self.f = (self.f & FLAG_C) | FLAG_N | self._flag_sz(r)
        if (v & 0x0F) == 0x00: self.f |= FLAG_H
        if v == 0x80: self.f |= FLAG_PV
        return r

    def _exec_cb(self) -> None:
        op = self._fetch()
        idx = op & 7
        val = self._get_reg(idx)
        grp = (op >> 3) & 7
        cat = op >> 6

        if cat == 0:
            cf = 1 if self.f & FLAG_C else 0
            if   grp == 0: c = val >> 7;  r = ((val << 1) | c) & 0xFF
            elif grp == 1: c = val & 1;   r = (val >> 1) | (c << 7)
            elif grp == 2: c = val >> 7;  r = ((val << 1) | cf) & 0xFF
            elif grp == 3: c = val & 1;   r = (val >> 1) | (cf << 7)
            elif grp == 4: c = val >> 7;  r = (val << 1) & 0xFF
            elif grp == 5: c = val & 1;   r = (val >> 1) | (val & 0x80)
            elif grp == 7: c = val & 1;   r = val >> 1
            else:          c = val >> 7;  r = ((val << 1) | 1) & 0xFF
            self.f = (FLAG_C if c else 0) | self._flag_sz(r)
            self._set_reg(idx, r)

        elif cat == 1:
            self.f = (self.f & FLAG_C) | FLAG_H
            if not (val & (1 << grp)): self.f |= FLAG_Z

        elif cat == 2:
            self._set_reg(idx, val & ~(1 << grp))

        elif cat == 3:
            self._set_reg(idx, val | (1 << grp))

    def _exec_ix_iy(self, reg_get, reg_set) -> None:
        op = self._fetch()
        r = reg_get()

        if op == 0x21: reg_set(self._fetch_word())
        elif op == 0x23: reg_set((r + 1) & 0xFFFF)
        elif op == 0x2B: reg_set((r - 1) & 0xFFFF)
        elif op == 0xE5: self._push(r)
        elif op == 0xE1: reg_set(self._pop())
        elif op == 0x5E: d = self._fetch(); self.e = self._rb(r + _signed(d))
        elif op == 0x56: d = self._fetch(); self.d = self._rb(r + _signed(d))
        elif op == 0x6E: d = self._fetch(); self.l = self._rb(r + _signed(d))
        elif op == 0x66: d = self._fetch(); self.h = self._rb(r + _signed(d))
        elif op == 0x75: d = self._fetch(); self._wb(r + _signed(d), self.l)
        elif op == 0x74: d = self._fetch(); self._wb(r + _signed(d), self.h)
        elif op == 0x73: d = self._fetch(); self._wb(r + _signed(d), self.e)
        elif op == 0x72: d = self._fetch(); self._wb(r + _signed(d), self.d)
        else:
            raise RuntimeError(
                f"unimplemented IX/IY opcode {op:#04x} at {(self.pc - 2) & 0xFFFF:#06x}"
            )

    def _exec_dd(self) -> None:
        self._exec_ix_iy(lambda: self.ix, self._set_ix)

    def _exec_fd(self) -> None:
        self._exec_ix_iy(lambda: self.iy, self._set_iy)

    def _set_ix(self, v: int) -> None: self.ix = v & 0xFFFF
    def _set_iy(self, v: int) -> None: self.iy = v & 0xFFFF

    def _exec_ed(self) -> None:
        op = self._fetch()
        if op == 0x52:
            c = 1 if (self.f & FLAG_C) else 0
            r = self.hl - self.de - c
            self.f = FLAG_N
            if (r & 0xFFFF) == 0: self.f |= FLAG_Z
            if r & 0x8000: self.f |= FLAG_S
            if r < 0: self.f |= FLAG_C
            h1, h2, hr = self.hl & 0xFFF, self.de & 0xFFF, c
            if (h1 - h2 - hr) < 0: self.f |= FLAG_H
            ov = ((self.hl ^ self.de) & 0x8000) and ((self.hl ^ r) & 0x8000)
            if ov: self.f |= FLAG_PV
            self.hl = r & 0xFFFF
        elif op == 0xB0:
            while self.bc:
                self._wb(self.de, self._rb(self.hl))
                self.hl = (self.hl + 1) & 0xFFFF
                self.de = (self.de + 1) & 0xFFFF
                self.bc = (self.bc - 1) & 0xFFFF
            self.f &= ~(FLAG_H | FLAG_PV | FLAG_N)
        else:
            raise RuntimeError(f"unimplemented ED opcode {op:#04x} at {(self.pc - 2) & 0xFFFF:#06x}")


def _signed(v: int) -> int:
    return v - 256 if v & 0x80 else v


class ForthMachine:

    def __init__(
        self,
        origin: int = DEFAULT_ORIGIN,
        data_stack_top: int = DEFAULT_DATA_STACK_TOP,
        return_stack_top: int = DEFAULT_RETURN_STACK_TOP,
    ):
        self.origin = origin
        self.data_stack_top = data_stack_top
        self.return_stack_top = return_stack_top
        self._prim_asm = Asm(origin)
        for creator in PRIMITIVES:
            creator(self._prim_asm)
        self._prim_code = self._prim_asm.resolve()
        self._body_base = self._prim_asm.here
        self._last_m: Z80 | None = None

    def label(self, name: str) -> int:
        return self._prim_asm.labels[name]

    def run(
        self,
        cells: list,
        initial_stack: list[int] | None = None,
        max_ticks: int = DEFAULT_MAX_TICKS,
    ) -> ForthResult:
        body_bytes, body_addr = self._build_body(cells)
        return self._execute(body_bytes, body_addr, initial_stack or [], max_ticks)

    def run_colon(
        self,
        body_cells: list[str | int],
        main_cells: list[str | int],
        max_ticks: int = DEFAULT_MAX_TICKS,
    ) -> ForthResult:
        cells: list = [("call_docol", "DOUBLE")]
        cells.extend(body_cells)
        cells.append(("main_start",))
        cells.extend(main_cells)
        body_bytes, body_addr = self._build_body(cells)
        return self._execute(body_bytes, body_addr, [], max_ticks)

    def _build_body(self, cells: list) -> tuple[bytes, int]:
        prim_labels = self._prim_asm.labels
        local_labels: dict[str, int] = {}
        addr = self._body_base
        body_start = self._body_base

        sized_entries: list = []
        for cell in cells:
            if isinstance(cell, tuple):
                tag = cell[0]
                if tag == "label":
                    local_labels[cell[1]] = addr
                    continue
                if tag == "call_docol":
                    local_labels[cell[1]] = addr
                    sized_entries.append(("call", "DOCOL"))
                    addr += 3
                    continue
                if tag == "main_start":
                    body_start = addr
                    continue
            sized_entries.append(cell)
            addr += 2

        sized_entries.append("HALT")

        all_labels = {**prim_labels, **local_labels}
        buf = bytearray()
        for entry in sized_entries:
            if isinstance(entry, tuple) and entry[0] == "call":
                target = all_labels[entry[1]]
                buf.extend([0xCD, target & 0xFF, (target >> 8) & 0xFF])
            elif isinstance(entry, str):
                target = all_labels[entry]
                buf.extend([target & 0xFF, (target >> 8) & 0xFF])
            else:
                buf.extend([entry & 0xFF, (entry >> 8) & 0xFF])

        return bytes(buf), body_start

    def _execute(
        self,
        body_bytes: bytes,
        body_addr: int,
        initial_stack: list[int],
        max_ticks: int,
    ) -> ForthResult:
        m = Z80()
        m.load(self.origin, self._prim_code)
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.load(self._body_base, body_bytes)

        startup_addr = self._body_base + len(body_bytes)
        startup = self._emit_startup(body_addr, initial_stack, startup_addr)
        m.load(startup_addr, startup)

        m.pc = startup_addr
        m.run(max_ticks)

        self._last_m = m

        if not m.halted:
            raise TimeoutError(f"execution exceeded {max_ticks} ticks")

        border_writes = [v for port, v in m._outputs if (port & 0xFF) == SPECTRUM_BORDER_PORT]

        return ForthResult(
            data_stack=_read_data_stack(m, self.data_stack_top, bool(initial_stack)),
            border_writes=border_writes,
            chars_out=self._extract_chars_out(m),
        )

    def _extract_chars_out(self, m: Z80) -> bytes:
        row_addr = self._prim_asm.labels.get("_emit_cursor_row")
        col_addr = self._prim_asm.labels.get("_emit_cursor_col")
        if row_addr is None or col_addr is None:
            return b""
        return decode_screen_text(m.mem, m.mem[row_addr], m.mem[col_addr])

    def _emit_startup(
        self,
        body_addr: int,
        initial_stack: list[int],
        startup_addr: int,
    ) -> bytes:
        a = Asm(startup_addr)
        a.ld_sp_nn(self.data_stack_top)
        a.ld_iy_nn(self.return_stack_top)
        if initial_stack:
            for value in initial_stack[:-1]:
                a.ld_de_nn(value)
                a.push_de()
            a.ld_hl_nn(initial_stack[-1])
        a.ld_ix_nn(body_addr)
        a.labels["NEXT"] = self.label("NEXT")
        a.jp("NEXT")
        return a.resolve()


def _read_data_stack(
    m: Z80,
    data_stack_top: int,
    had_initial_stack: bool,
) -> list[int]:
    sp = m.sp
    if sp > data_stack_top:
        return []

    hw_top_first: list[int] = []
    while sp < data_stack_top:
        hw_top_first.append(m._rw(sp))
        sp += 2

    bottom_first = list(reversed(hw_top_first))

    if not had_initial_stack:
        if not bottom_first:
            return []
        bottom_first = bottom_first[1:]

    bottom_first.append(m.hl)
    return bottom_first
