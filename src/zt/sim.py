"""
Z80 simulator and `ForthMachine` wrapper. Interprets compiled images cycle-by-cycle with enough fidelity for pytest, and models the Spectrum screen / keyboard / border IO surface the primitives rely on.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from zt.assemble.asm import Asm
from zt.assemble.primitives import PRIMITIVES
from zt.profile.core import ProfileReport, Profiler, build_word_ranges

SPECTRUM_BORDER_PORT = 0xFE
SPECTRUM_FONT_BASE = 0x3D00
SPECTRUM_SCREEN_BASE = 0x4000
SPECTRUM_ATTR_BASE = 0x5800
SPECTRUM_KEYBOARD_PORT_LOW = 0xFE

BANK_SIZE = 0x4000
PAGED_SLOT_START = 0xC000
PAGED_SLOT_END = 0x10000
BANK_FIVE_SLOT = slice(0x4000, 0x8000)
BANK_TWO_SLOT = slice(0x8000, 0xC000)
PAGED_SLOT = slice(PAGED_SLOT_START, PAGED_SLOT_END)
FIXED_SLOT_OF_BANK = {5: BANK_FIVE_SLOT, 2: BANK_TWO_SLOT}
PORT_7FFD_DECODE_MASK = 0x8002
PORT_7FFD_PAGE_MASK = 0x07
PORT_7FFD_SCREEN_BIT = 0x08
PORT_7FFD_LOCK_BIT = 0x20
NORMAL_SCREEN_BANK = 5
SHADOW_SCREEN_BANK = 7
SCREEN_BITMAP_SIZE = 6144
SCREEN_ATTRS_SIZE = 768


def is_7ffd_write(port: int) -> bool:
    return (port & PORT_7FFD_DECODE_MASK) == 0

SPECTRUM_KEY_LAYOUT: dict[int, tuple[int, int]] = {
    0x01: (0, 0), ord("Z"): (0, 1), ord("X"): (0, 2), ord("C"): (0, 3), ord("V"): (0, 4),
    ord("A"): (1, 0), ord("S"): (1, 1), ord("D"): (1, 2), ord("F"): (1, 3), ord("G"): (1, 4),
    ord("Q"): (2, 0), ord("W"): (2, 1), ord("E"): (2, 2), ord("R"): (2, 3), ord("T"): (2, 4),
    ord("1"): (3, 0), ord("2"): (3, 1), ord("3"): (3, 2), ord("4"): (3, 3), ord("5"): (3, 4),
    ord("0"): (4, 0), ord("9"): (4, 1), ord("8"): (4, 2), ord("7"): (4, 3), ord("6"): (4, 4),
    ord("P"): (5, 0), ord("O"): (5, 1), ord("I"): (5, 2), ord("U"): (5, 3), ord("Y"): (5, 4),
    0x0D:      (6, 0), ord("L"): (6, 1), ord("K"): (6, 2), ord("J"): (6, 3), ord("H"): (6, 4),
    ord(" "): (7, 0), 0x02:      (7, 1), ord("M"): (7, 2), ord("N"): (7, 3), ord("B"): (7, 4),
}

INPUT_BUFFER_PRESSED_READS = 12
INPUT_BUFFER_RELEASED_READS = 4


def _normalize_ascii(byte: int) -> int:
    if ord("a") <= byte <= ord("z"):
        return byte - 32
    return byte


def _keyboard_port_byte(pressed_keys: set[int], high_byte: int) -> int:
    bits = 0x1F
    for ascii_code in pressed_keys:
        location = SPECTRUM_KEY_LAYOUT.get(_normalize_ascii(ascii_code))
        if location is None:
            continue
        row, col = location
        if (high_byte & (1 << row)) == 0:
            bits &= ~(1 << col)
    return (bits & 0x1F) | 0xE0

DEFAULT_ORIGIN = 0x8000
DEFAULT_DATA_STACK_TOP = 0xFF00
DEFAULT_RETURN_STACK_TOP = 0xFE00
DEFAULT_DATA_STACK_TOP_128K = 0xBF00
DEFAULT_RETURN_STACK_TOP_128K = 0xBE00
DEFAULT_MAX_TICKS = 10_000_000

FRAME_T_STATES_48K = 69_888
FRAME_T_STATES_128K = 70_908

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
    page_writes: list[int] = field(default_factory=list)
    chars_out: bytes = b""
    profile: ProfileReport | None = None
    interrupt_count: int = 0


class Z80:
    __slots__ = (
        "mem", "pc", "sp", "a", "f", "b", "c", "d", "e", "h", "l",
        "ix", "iy", "halted", "iff", "iff2", "i", "im_mode",
        "bus_byte", "t_states_per_frame",
        "_next_int_at", "_ei_pending", "_halt_waiting", "interrupt_count",
        "_outputs", "_ticks", "_t_states",
        "input_buffer", "_input_pos", "_ops", "_op_costs",
        "pressed_keys", "_port_reads_at_pos",
        "mode", "_banks", "port_7ffd",
    )

    def __init__(self, mode: str = "48k") -> None:
        if mode not in ("48k", "128k"):
            raise ValueError(f"mode must be '48k' or '128k', got {mode!r}")
        self.mode = mode
        self.mem = bytearray(65536)
        self.pc = self.sp = 0
        self.a = self.f = 0
        self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.ix = self.iy = 0
        self.halted = False
        self.iff = False
        self.iff2 = False
        self.i = 0
        self.im_mode = 0
        self.bus_byte = 0xFF
        self.t_states_per_frame = FRAME_T_STATES_128K if mode == "128k" else FRAME_T_STATES_48K
        self._next_int_at = self.t_states_per_frame
        self._ei_pending = False
        self._halt_waiting = False
        self.interrupt_count = 0
        self._outputs: list[tuple[int, int]] = []
        self._ticks = 0
        self._t_states = 0
        self.input_buffer: bytearray = bytearray()
        self._input_pos: int = 0
        self.pressed_keys: set[int] = set()
        self._port_reads_at_pos: int = 0
        self._banks: list[bytearray] | None = None
        self.port_7ffd: int = 0
        if mode == "128k":
            self._banks = [bytearray(BANK_SIZE) for _ in range(8)]
        self._ops, self._op_costs = self._build_ops_table()

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

    def mem_bank(self, bank: int) -> bytearray:
        self._require_128k("mem_bank")
        if bank not in range(8):
            raise ValueError(f"bank {bank} must be in range 0..7")
        if bank in FIXED_SLOT_OF_BANK:
            return bytearray(self.mem[FIXED_SLOT_OF_BANK[bank]])
        if bank == self.port_7ffd & PORT_7FFD_PAGE_MASK:
            return bytearray(self.mem[PAGED_SLOT])
        return bytearray(self._banks[bank])

    def load_bank(self, bank: int, data: bytes) -> None:
        self._require_128k("load_bank")
        if bank not in range(8):
            raise ValueError(f"bank {bank} must be in range 0..7")
        padded = bytes(data) + bytes(BANK_SIZE - len(data))
        if bank in FIXED_SLOT_OF_BANK:
            self.mem[FIXED_SLOT_OF_BANK[bank]] = padded
            return
        if bank == self.port_7ffd & PORT_7FFD_PAGE_MASK:
            self.mem[PAGED_SLOT] = padded
            return
        self._banks[bank][:] = padded

    def page_bank(self, bank: int) -> None:
        self._require_128k("page_bank")
        if bank not in range(8):
            raise ValueError(f"bank {bank} must be in range 0..7")
        self._write_port_7ffd((self.port_7ffd & ~PORT_7FFD_PAGE_MASK) | bank)

    def displayed_screen_bank(self) -> int:
        self._require_128k("displayed_screen_bank")
        return SHADOW_SCREEN_BANK if self.port_7ffd & PORT_7FFD_SCREEN_BIT else NORMAL_SCREEN_BANK

    def displayed_screen(self) -> tuple[bytes, bytes]:
        self._require_128k("displayed_screen")
        bank = self.mem_bank(self.displayed_screen_bank())
        return bytes(bank[:SCREEN_BITMAP_SIZE]), bytes(bank[SCREEN_BITMAP_SIZE:SCREEN_BITMAP_SIZE + SCREEN_ATTRS_SIZE])

    def _require_128k(self, method_name: str) -> None:
        if self.mode != "128k":
            raise RuntimeError(
                f"{method_name} is only available in 128k mode; got mode={self.mode!r}"
            )

    def _maybe_handle_7ffd(self, port: int, value: int) -> None:
        if self.mode != "128k":
            return
        if not is_7ffd_write(port):
            return
        self._write_port_7ffd(value)

    def _write_port_7ffd(self, value: int) -> None:
        value &= 0xFF
        if self.port_7ffd & PORT_7FFD_LOCK_BIT:
            return
        old_paged = self.port_7ffd & PORT_7FFD_PAGE_MASK
        new_paged = value & PORT_7FFD_PAGE_MASK
        self.port_7ffd = value
        if new_paged == old_paged:
            return
        self._save_paged_slot(old_paged)
        self._load_paged_slot(new_paged)

    def _save_paged_slot(self, old_paged: int) -> None:
        paged_contents = bytes(self.mem[PAGED_SLOT])
        fixed_slot = FIXED_SLOT_OF_BANK.get(old_paged)
        if fixed_slot is not None:
            self.mem[fixed_slot] = paged_contents
        else:
            self._banks[old_paged][:] = paged_contents

    def _load_paged_slot(self, new_paged: int) -> None:
        fixed_slot = FIXED_SLOT_OF_BANK.get(new_paged)
        if fixed_slot is not None:
            self.mem[PAGED_SLOT] = bytes(self.mem[fixed_slot])
        else:
            self.mem[PAGED_SLOT] = self._banks[new_paged]

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
            self._t_states += 5

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

    def run(self, max_ticks: int = DEFAULT_MAX_TICKS, profiler=None) -> None:
        self._ticks = 0
        self._t_states = 0
        while not self.halted and self._ticks < max_ticks:
            pc = self.pc
            prev_t_states = self._t_states
            self._step()
            self._ticks += 1
            if profiler is not None:
                profiler.sample(pc, self._t_states - prev_t_states)

    def fire_interrupt(self) -> None:
        if not self.iff:
            return
        self.halted = False
        self._halt_waiting = False
        self._push(self.pc)
        self.iff = False
        self.iff2 = False
        if self.im_mode == 2:
            vector_addr = ((self.i << 8) | self.bus_byte) & 0xFFFF
            self.pc = self._rw(vector_addr)
            self._t_states += 19
        else:
            self.pc = 0x0038
            self._t_states += 13
        self.interrupt_count += 1

    def run_until(self, t_state_target: int) -> None:
        while True:
            if self._should_auto_fire():
                self.fire_interrupt()
                self._next_int_at += self.t_states_per_frame
                continue
            if self._t_states >= t_state_target:
                return
            if self.halted:
                return
            if self._halt_waiting:
                if not self.iff:
                    self._halt_waiting = False
                    return
                self._tick_halt_wait()
                continue
            if self.iff and self._rb(self.pc) == 0x76:
                self.pc = (self.pc + 1) & 0xFFFF
                self._halt_waiting = True
                self._tick_halt_wait()
                continue
            self._ei_pending = False
            self._step()

    def _should_auto_fire(self) -> bool:
        return (
            self.iff
            and not self._ei_pending
            and self._t_states >= self._next_int_at
        )

    def _tick_halt_wait(self) -> None:
        self._t_states += 4
        self._ei_pending = False

    def _step(self) -> None:
        op = self._fetch()
        self._t_states += self._op_costs[op]
        self._ops[op](op)

    def _build_ops_table(self) -> tuple[list, list]:
        t = [self._op_unimplemented] * 256
        c = [0] * 256

        def reg(op: int, handler, cost: int) -> None:
            t[op] = handler
            c[op] = cost

        reg(0x00, self._op_nop, 4)
        reg(0x76, self._op_halt, 4)

        reg(0x01, self._op_ld_bc_nn, 10)
        reg(0x11, self._op_ld_de_nn, 10)
        reg(0x21, self._op_ld_hl_nn, 10)
        reg(0x31, self._op_ld_sp_nn, 10)

        for op in (0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x3E):
            reg(op, self._op_ld_r_n, 7)
        reg(0x36, self._op_ld_r_n, 10)

        reg(0x1A, self._op_ld_a_ind_de, 7)
        reg(0x0A, self._op_ld_a_ind_bc, 7)
        reg(0x12, self._op_ld_ind_de_a, 7)
        reg(0x02, self._op_ld_ind_bc_a, 7)
        reg(0x34, self._op_inc_ind_hl, 11)
        reg(0x35, self._op_dec_ind_hl, 11)
        reg(0x3A, self._op_ld_a_ind_nn, 13)
        reg(0x32, self._op_ld_ind_nn_a, 13)
        reg(0x22, self._op_ld_ind_nn_hl, 16)
        reg(0x2A, self._op_ld_hl_ind_nn, 16)

        reg(0x3F, self._op_ccf, 4)
        reg(0x17, self._op_rla, 4)
        reg(0x1F, self._op_rra, 4)
        reg(0xCE, self._op_adc_a_n, 7)
        reg(0xDE, self._op_sbc_a_n, 7)
        reg(0xEE, self._op_xor_n, 7)

        for op in range(0x40, 0x80):
            if op != 0x76:
                reg(op, self._op_ld_r_r, 4)

        reg(0xC5, self._op_push_bc, 11)
        reg(0xD5, self._op_push_de, 11)
        reg(0xE5, self._op_push_hl, 11)
        reg(0xF5, self._op_push_af, 11)
        reg(0xC1, self._op_pop_bc, 10)
        reg(0xD1, self._op_pop_de, 10)
        reg(0xE1, self._op_pop_hl, 10)
        reg(0xF1, self._op_pop_af, 10)

        reg(0xEB, self._op_ex_de_hl, 4)
        reg(0xE3, self._op_ex_sp_hl, 19)

        reg(0x09, self._op_add_hl_bc, 11)
        reg(0x19, self._op_add_hl_de, 11)
        reg(0x29, self._op_add_hl_hl, 11)

        reg(0x03, self._op_inc_bc, 6)
        reg(0x0B, self._op_dec_bc, 6)
        reg(0x13, self._op_inc_de, 6)
        reg(0x1B, self._op_dec_de, 6)
        reg(0x23, self._op_inc_hl, 6)
        reg(0x2B, self._op_dec_hl, 6)

        reg(0x24, self._op_inc_h, 4)
        reg(0x3C, self._op_inc_a, 4)
        reg(0x04, self._op_inc_b, 4)
        reg(0x14, self._op_inc_d, 4)
        reg(0x05, self._op_dec_b, 4)
        reg(0xD6, self._op_sub_n, 7)
        reg(0x3D, self._op_dec_a, 4)
        reg(0x1D, self._op_dec_e, 4)

        for op in range(0x80, 0xC0):
            reg(op, self._op_alu_a_r, 4)

        reg(0xE6, self._op_and_n, 7)
        reg(0xF6, self._op_or_n, 7)
        reg(0xFE, self._op_cp_n, 7)

        reg(0x0F, self._op_rrca, 4)
        reg(0x07, self._op_rlca, 4)
        reg(0x2F, self._op_cpl, 4)
        reg(0x37, self._op_scf, 4)

        reg(0xC3, self._op_jp_nn, 10)
        reg(0xCA, self._op_jp_z, 10)
        reg(0xC2, self._op_jp_nz, 10)
        reg(0xF2, self._op_jp_p, 10)
        reg(0xFA, self._op_jp_m, 10)

        reg(0x18, self._op_jr, 7)
        reg(0x20, self._op_jr_nz, 7)
        reg(0x28, self._op_jr_z, 7)
        reg(0x30, self._op_jr_nc, 7)
        reg(0x38, self._op_jr_c, 7)
        reg(0x10, self._op_djnz, 8)

        reg(0xCD, self._op_call_nn, 17)
        reg(0xC9, self._op_ret, 10)

        reg(0xD3, self._op_out_n_a, 11)
        reg(0xDB, self._op_in_a_n, 11)
        reg(0xF3, self._op_di, 4)
        reg(0xFB, self._op_ei, 4)

        reg(0xF9, self._op_ld_sp_hl, 6)
        reg(0x2C, self._op_inc_l, 4)
        reg(0x2D, self._op_dec_l, 4)
        reg(0xC6, self._op_add_a_n, 7)

        reg(0xCB, self._op_cb_prefix, 0)
        reg(0xDD, self._op_dd_prefix, 0)
        reg(0xED, self._op_ed_prefix, 0)
        reg(0xFD, self._op_fd_prefix, 0)

        return t, c

    def _op_unimplemented(self, op: int) -> None:
        raise RuntimeError(
            f"unimplemented opcode {op:#04x} at {(self.pc - 1) & 0xFFFF:#06x}"
        )

    def _op_nop(self, op: int) -> None:
        pass

    def _op_halt(self, op: int) -> None:
        if self.iff:
            return
        self.halted = True

    def _op_ld_bc_nn(self, op: int) -> None:
        self.bc = self._fetch_word()

    def _op_ld_de_nn(self, op: int) -> None:
        self.de = self._fetch_word()

    def _op_ld_hl_nn(self, op: int) -> None:
        self.hl = self._fetch_word()

    def _op_ld_sp_nn(self, op: int) -> None:
        self.sp = self._fetch_word()

    def _op_ld_sp_hl(self, op: int) -> None:
        self.sp = self.hl

    def _op_inc_l(self, op: int) -> None:
        self.l = self._inc8(self.l)

    def _op_dec_l(self, op: int) -> None:
        self.l = self._dec8(self.l)

    def _op_add_a_n(self, op: int) -> None:
        self.a = self._add8(self.a, self._fetch())

    def _op_ld_r_n(self, op: int) -> None:
        self._set_reg((op >> 3) & 7, self._fetch())

    def _op_ld_a_ind_de(self, op: int) -> None:
        self.a = self._rb(self.de)

    def _op_ld_a_ind_bc(self, op: int) -> None:
        self.a = self._rb(self.bc)

    def _op_ld_ind_de_a(self, op: int) -> None:
        self._wb(self.de, self.a)

    def _op_ld_ind_bc_a(self, op: int) -> None:
        self._wb(self.bc, self.a)

    def _op_inc_ind_hl(self, op: int) -> None:
        self._wb(self.hl, self._inc8(self._rb(self.hl)))

    def _op_dec_ind_hl(self, op: int) -> None:
        self._wb(self.hl, self._dec8(self._rb(self.hl)))

    def _op_ld_a_ind_nn(self, op: int) -> None:
        self.a = self._rb(self._fetch_word())

    def _op_ld_ind_nn_a(self, op: int) -> None:
        self._wb(self._fetch_word(), self.a)

    def _op_ld_ind_nn_hl(self, op: int) -> None:
        self._ww(self._fetch_word(), self.hl)

    def _op_ld_hl_ind_nn(self, op: int) -> None:
        self.hl = self._rw(self._fetch_word())

    def _op_ld_r_r(self, op: int) -> None:
        dst, src = (op >> 3) & 7, op & 7
        self._set_reg(dst, self._get_reg(src))
        if dst == 6 or src == 6:
            self._t_states += 3

    def _op_push_bc(self, op: int) -> None:
        self._push(self.bc)

    def _op_push_de(self, op: int) -> None:
        self._push(self.de)

    def _op_push_hl(self, op: int) -> None:
        self._push(self.hl)

    def _op_push_af(self, op: int) -> None:
        self._push(self.af)

    def _op_pop_bc(self, op: int) -> None:
        self.bc = self._pop()

    def _op_pop_de(self, op: int) -> None:
        self.de = self._pop()

    def _op_pop_hl(self, op: int) -> None:
        self.hl = self._pop()

    def _op_pop_af(self, op: int) -> None:
        self.af = self._pop()

    def _op_ex_de_hl(self, op: int) -> None:
        self.hl, self.de = self.de, self.hl

    def _op_ex_sp_hl(self, op: int) -> None:
        tmp = self._rw(self.sp)
        self._ww(self.sp, self.hl)
        self.hl = tmp

    def _op_add_hl_bc(self, op: int) -> None:
        self._add_hl(self.bc)

    def _op_add_hl_de(self, op: int) -> None:
        self._add_hl(self.de)

    def _op_add_hl_hl(self, op: int) -> None:
        self._add_hl(self.hl)

    def _op_inc_bc(self, op: int) -> None:
        self.bc = (self.bc + 1) & 0xFFFF

    def _op_dec_bc(self, op: int) -> None:
        self.bc = (self.bc - 1) & 0xFFFF

    def _op_inc_de(self, op: int) -> None:
        self.de = (self.de + 1) & 0xFFFF

    def _op_dec_de(self, op: int) -> None:
        self.de = (self.de - 1) & 0xFFFF

    def _op_inc_hl(self, op: int) -> None:
        self.hl = (self.hl + 1) & 0xFFFF

    def _op_dec_hl(self, op: int) -> None:
        self.hl = (self.hl - 1) & 0xFFFF

    def _op_inc_h(self, op: int) -> None:
        self.h = self._inc8(self.h)

    def _op_inc_a(self, op: int) -> None:
        self.a = self._inc8(self.a)

    def _op_inc_b(self, op: int) -> None:
        self.b = self._inc8(self.b)

    def _op_inc_d(self, op: int) -> None:
        self.d = self._inc8(self.d)

    def _op_dec_b(self, op: int) -> None:
        self.b = self._dec8(self.b)

    def _op_sub_n(self, op: int) -> None:
        n = self._fetch()
        self.a = self._sub8(self.a, n)

    def _op_dec_a(self, op: int) -> None:
        self.a = self._dec8(self.a)

    def _op_dec_e(self, op: int) -> None:
        self.e = self._dec8(self.e)

    def _op_alu_a_r(self, op: int) -> None:
        src_idx = op & 7
        src = self._get_reg(src_idx)
        grp = (op >> 3) & 7
        if   grp == 0: self.a = self._add8(self.a, src)
        elif grp == 1: self.a = self._add8(self.a, src, self.f & FLAG_C)
        elif grp == 2: self.a = self._sub8(self.a, src)
        elif grp == 3: self.a = self._sub8(self.a, src, self.f & FLAG_C)
        elif grp == 4: self.a &= src; self.f = self._flag_sz(self.a) | FLAG_H
        elif grp == 5: self.a ^= src; self.f = self._flag_sz(self.a)
        elif grp == 6: self.a |= src; self.f = self._flag_sz(self.a)
        elif grp == 7: self._sub8(self.a, src)
        if src_idx == 6:
            self._t_states += 3

    def _op_and_n(self, op: int) -> None:
        self.a &= self._fetch()
        self.f = self._flag_sz(self.a) | FLAG_H

    def _op_or_n(self, op: int) -> None:
        self.a |= self._fetch()
        self.f = self._flag_sz(self.a)

    def _op_cp_n(self, op: int) -> None:
        self._sub8(self.a, self._fetch())

    def _op_rrca(self, op: int) -> None:
        c = self.a & 1
        self.a = ((self.a >> 1) | (c << 7)) & 0xFF
        self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | (FLAG_C if c else 0)

    def _op_rlca(self, op: int) -> None:
        c = (self.a >> 7) & 1
        self.a = ((self.a << 1) | c) & 0xFF
        self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | (FLAG_C if c else 0)

    def _op_rla(self, op: int) -> None:
        old_c = 1 if (self.f & FLAG_C) else 0
        new_c = (self.a >> 7) & 1
        self.a = ((self.a << 1) | old_c) & 0xFF
        self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | (FLAG_C if new_c else 0)

    def _op_rra(self, op: int) -> None:
        old_c = 1 if (self.f & FLAG_C) else 0
        new_c = self.a & 1
        self.a = ((self.a >> 1) | (old_c << 7)) & 0xFF
        self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | (FLAG_C if new_c else 0)

    def _op_ccf(self, op: int) -> None:
        new_c = 0 if (self.f & FLAG_C) else FLAG_C
        self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | new_c

    def _op_adc_a_n(self, op: int) -> None:
        self.a = self._add8(self.a, self._fetch(), self.f & FLAG_C)

    def _op_sbc_a_n(self, op: int) -> None:
        self.a = self._sub8(self.a, self._fetch(), self.f & FLAG_C)

    def _op_xor_n(self, op: int) -> None:
        self.a ^= self._fetch()
        self.f = self._flag_sz(self.a)

    def _op_cpl(self, op: int) -> None:
        self.a ^= 0xFF
        self.f |= FLAG_H | FLAG_N

    def _op_scf(self, op: int) -> None:
        self.f = (self.f & (FLAG_Z | FLAG_S | FLAG_PV)) | FLAG_C

    def _op_jp_nn(self, op: int) -> None:
        self.pc = self._fetch_word()

    def _op_jp_z(self, op: int) -> None:
        addr = self._fetch_word()
        if self.f & FLAG_Z:
            self.pc = addr

    def _op_jp_nz(self, op: int) -> None:
        addr = self._fetch_word()
        if not (self.f & FLAG_Z):
            self.pc = addr

    def _op_jp_p(self, op: int) -> None:
        addr = self._fetch_word()
        if not (self.f & FLAG_S):
            self.pc = addr

    def _op_jp_m(self, op: int) -> None:
        addr = self._fetch_word()
        if self.f & FLAG_S:
            self.pc = addr

    def _op_jr(self, op: int) -> None:
        self._jr_cond(True)

    def _op_jr_nz(self, op: int) -> None:
        self._jr_cond(not (self.f & FLAG_Z))

    def _op_jr_z(self, op: int) -> None:
        self._jr_cond(bool(self.f & FLAG_Z))

    def _op_jr_nc(self, op: int) -> None:
        self._jr_cond(not (self.f & FLAG_C))

    def _op_jr_c(self, op: int) -> None:
        self._jr_cond(bool(self.f & FLAG_C))

    def _op_djnz(self, op: int) -> None:
        self.b = (self.b - 1) & 0xFF
        self._jr_cond(self.b != 0)

    def _op_call_nn(self, op: int) -> None:
        addr = self._fetch_word()
        self._push(self.pc)
        self.pc = addr

    def _op_ret(self, op: int) -> None:
        self.pc = self._pop()

    def _op_out_n_a(self, op: int) -> None:
        port = self._fetch()
        full_port = port | (self.a << 8)
        self._outputs.append((full_port, self.a))
        self._maybe_handle_7ffd(full_port, self.a)

    def _op_in_a_n(self, op: int) -> None:
        n = self._fetch()
        self.a = self._read_port((self.a << 8) | n)

    def _op_di(self, op: int) -> None:
        self.iff = False
        self.iff2 = False

    def _op_ei(self, op: int) -> None:
        self.iff = True
        self.iff2 = True
        self._ei_pending = True

    def _op_cb_prefix(self, op: int) -> None:
        self._exec_cb()

    def _op_dd_prefix(self, op: int) -> None:
        self._exec_ix_iy(lambda: self.ix, self._set_ix)

    def _op_ed_prefix(self, op: int) -> None:
        self._exec_ed()

    def _op_fd_prefix(self, op: int) -> None:
        self._exec_ix_iy(lambda: self.iy, self._set_iy)

    def _read_port(self, port: int) -> int:
        if (port & 0xFF) != SPECTRUM_KEYBOARD_PORT_LOW:
            return 0xFF
        keys = self._current_pressed_keys()
        return _keyboard_port_byte(keys, (port >> 8) & 0xFF)

    def _current_pressed_keys(self) -> set[int]:
        if self.pressed_keys:
            return self.pressed_keys
        if self._input_pos >= len(self.input_buffer):
            return set()
        cycle = INPUT_BUFFER_PRESSED_READS + INPUT_BUFFER_RELEASED_READS
        phase = self._port_reads_at_pos
        self._port_reads_at_pos += 1
        if self._port_reads_at_pos >= cycle:
            self._port_reads_at_pos = 0
            self._input_pos += 1
        if phase < INPUT_BUFFER_PRESSED_READS:
            ch = self.input_buffer[self._input_pos if phase < cycle else 0]
            return {_normalize_ascii(ch)}
        return set()

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

        if idx == 6:
            self._t_states += 12 if cat == 1 else 15
        else:
            self._t_states += 8

    _IX_IY_COSTS = {
        0x21: 14, 0x23: 10, 0x2B: 10, 0xE5: 15, 0xE1: 14,
        0x5E: 19, 0x56: 19, 0x6E: 19, 0x66: 19,
        0x75: 19, 0x74: 19, 0x73: 19, 0x72: 19,
        0xE3: 23,
    }

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
        elif op == 0xE3:
            lo = self._rb(self.sp)
            hi = self._rb((self.sp + 1) & 0xFFFF)
            self._wb(self.sp, r & 0xFF)
            self._wb((self.sp + 1) & 0xFFFF, (r >> 8) & 0xFF)
            reg_set(lo | (hi << 8))
        else:
            raise RuntimeError(
                f"unimplemented IX/IY opcode {op:#04x} at {(self.pc - 2) & 0xFFFF:#06x}"
            )

        self._t_states += self._IX_IY_COSTS[op]

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
            self._t_states += 15
        elif op == 0xB0:
            while True:
                self._wb(self.de, self._rb(self.hl))
                self.hl = (self.hl + 1) & 0xFFFF
                self.de = (self.de + 1) & 0xFFFF
                self.bc = (self.bc - 1) & 0xFFFF
                if self.bc == 0:
                    self._t_states += 16
                    break
                self._t_states += 21
            self.f &= ~(FLAG_H | FLAG_PV | FLAG_N)
        elif op == 0x79:
            self._outputs.append((self.bc, self.a))
            self._maybe_handle_7ffd(self.bc, self.a)
            self._t_states += 12
        elif op == 0x4B:
            self.bc = self._rw(self._fetch_word())
            self._t_states += 20
        elif op == 0x43:
            self._ww(self._fetch_word(), self.bc)
            self._t_states += 20
        elif op == 0x73:
            self._ww(self._fetch_word(), self.sp)
            self._t_states += 20
        elif op == 0x7B:
            self.sp = self._rw(self._fetch_word())
            self._t_states += 20
        elif op == 0x46:
            self.im_mode = 0
            self._t_states += 8
        elif op == 0x56:
            self.im_mode = 1
            self._t_states += 8
        elif op == 0x5E:
            self.im_mode = 2
            self._t_states += 8
        elif op == 0x47:
            self.i = self.a
            self._t_states += 9
        elif op == 0x57:
            self.a = self.i
            self.f = (self.f & FLAG_C) | self._flag_sz(self.i) | (FLAG_PV if self.iff2 else 0)
            self._t_states += 9
        elif op == 0x45:
            self.pc = self._pop()
            self.iff = self.iff2
            self._t_states += 14
        elif op == 0x4D:
            self.pc = self._pop()
            self._t_states += 14
        else:
            raise RuntimeError(f"unimplemented ED opcode {op:#04x} at {(self.pc - 2) & 0xFFFF:#06x}")


def _signed(v: int) -> int:
    return v - 256 if v & 0x80 else v


def _default_data_stack_top(mode: str) -> int:
    if mode == "128k":
        return DEFAULT_DATA_STACK_TOP_128K
    return DEFAULT_DATA_STACK_TOP


def _default_return_stack_top(mode: str) -> int:
    if mode == "128k":
        return DEFAULT_RETURN_STACK_TOP_128K
    return DEFAULT_RETURN_STACK_TOP


class ForthMachine:

    def __init__(
        self,
        origin: int = DEFAULT_ORIGIN,
        data_stack_top: int | None = None,
        return_stack_top: int | None = None,
        mode: str = "48k",
    ):
        self.origin = origin
        self.mode = mode
        self.data_stack_top = data_stack_top if data_stack_top is not None else _default_data_stack_top(mode)
        self.return_stack_top = return_stack_top if return_stack_top is not None else _default_return_stack_top(mode)
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
        input_buffer: bytes = b"",
        pressed_keys: set[int] | None = None,
        profile: bool = False,
    ) -> ForthResult:
        body_bytes, body_addr, local_labels = self._build_body(cells)
        return self._execute(
            body_bytes, body_addr, initial_stack or [], max_ticks, input_buffer,
            local_labels=local_labels, profile=profile, pressed_keys=pressed_keys,
        )

    def run_colon(
        self,
        body_cells: list[str | int],
        main_cells: list[str | int],
        max_ticks: int = DEFAULT_MAX_TICKS,
        input_buffer: bytes = b"",
        profile: bool = False,
    ) -> ForthResult:
        cells: list = [("call_docol", "DOUBLE")]
        cells.extend(body_cells)
        cells.append(("main_start",))
        cells.extend(main_cells)
        body_bytes, body_addr, local_labels = self._build_body(cells)
        return self._execute(
            body_bytes, body_addr, [], max_ticks, input_buffer,
            local_labels=local_labels, profile=profile,
        )

    def _build_body(self, cells: list) -> tuple[bytes, int, dict[str, int]]:
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

        return bytes(buf), body_start, local_labels

    def _execute(
        self,
        body_bytes: bytes,
        body_addr: int,
        initial_stack: list[int],
        max_ticks: int,
        input_buffer: bytes = b"",
        local_labels: dict[str, int] | None = None,
        profile: bool = False,
        pressed_keys: set[int] | None = None,
    ) -> ForthResult:
        m = Z80(mode=self.mode)
        m.load(self.origin, self._prim_code)
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.load(self._body_base, body_bytes)
        m.input_buffer = bytearray(input_buffer)
        if pressed_keys is not None:
            m.pressed_keys = set(pressed_keys)

        startup_addr = self._body_base + len(body_bytes)
        startup = self._emit_startup(body_addr, initial_stack, startup_addr)
        m.load(startup_addr, startup)

        profiler = self._make_profiler(body_bytes, local_labels) if profile else None

        m.pc = startup_addr
        m.run(max_ticks, profiler=profiler)

        self._last_m = m

        if not m.halted:
            raise TimeoutError(f"execution exceeded {max_ticks} ticks")

        border_writes = [v for port, v in m._outputs if (port & 0xFF) == SPECTRUM_BORDER_PORT]
        page_writes = [v for port, v in m._outputs if is_7ffd_write(port)]

        return ForthResult(
            data_stack=_read_data_stack(m, self.data_stack_top, bool(initial_stack)),
            border_writes=border_writes,
            page_writes=page_writes,
            chars_out=self._extract_chars_out(m),
            profile=profiler.report() if profiler is not None else None,
            interrupt_count=m.interrupt_count,
        )

    def _make_profiler(
        self,
        body_bytes: bytes,
        local_labels: dict[str, int] | None,
    ) -> Profiler:
        labels = {**self._prim_asm.labels, **(local_labels or {})}
        code_end = self._body_base + len(body_bytes)
        ranges = build_word_ranges(labels, code_end=code_end)
        return Profiler(ranges)

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
