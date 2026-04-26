"""
`Run`: pytest-level inspection layer over `ForthResult` and the underlying
`ForthMachine`. Tests assert on Forth-vocabulary state (stack, screen,
banks, cursor) instead of bare addresses or `_last_m`.
"""
from __future__ import annotations

from dataclasses import dataclass

from zt.sim import (
    SPECTRUM_ATTR_BASE,
    ForthMachine,
    ForthResult,
    decode_screen_cell,
)


SCREEN_COLS = 32
SCREEN_ROWS = 24
ADDR_SPACE = 0x10000
BANKM_SHADOW_ADDR = 0x5B5C


@dataclass(frozen=True)
class Run:
    machine: ForthMachine
    result: ForthResult | None = None

    @classmethod
    def of(cls, machine: ForthMachine, result: ForthResult | None = None) -> "Run":
        return cls(machine=machine, result=result)

    def top(self) -> int:
        stack = self._stack_or_raise("top")
        if not stack:
            raise IndexError("data stack is empty")
        return stack[-1]

    def stack(self) -> tuple[int, ...]:
        return tuple(self._stack_or_raise("stack"))

    def depth(self) -> int:
        return len(self._stack_or_raise("depth"))

    def chars_out(self) -> bytes:
        if self.result is None:
            raise RuntimeError("chars_out() requires a captured ForthResult")
        return self.result.chars_out

    def cursor(self) -> tuple[int, int]:
        row_addr = self._label("_emit_cursor_row")
        col_addr = self._label("_emit_cursor_col")
        mem = self._mem
        return mem[row_addr], mem[col_addr]

    def screen(self, row: int, col: int) -> int:
        _check_screen_coords(row, col)
        return decode_screen_cell(self._mem, row, col)

    def attr(self, row: int, col: int) -> int:
        _check_screen_coords(row, col)
        return self._mem[SPECTRUM_ATTR_BASE + row * SCREEN_COLS + col]

    def border_writes(self) -> tuple[int, ...]:
        if self.result is not None:
            return tuple(self.result.border_writes)
        return tuple(self._derive_border_writes())

    def page_writes(self) -> tuple[int, ...]:
        if self.result is not None:
            return tuple(self.result.page_writes)
        return tuple(self._derive_page_writes())

    def bank(self, n: int) -> bytes:
        if self.machine.mode != "128k":
            raise RuntimeError("bank() requires 128k mode")
        return bytes(self._z80.mem_bank(n))

    def paged_bank(self) -> int:
        if self.machine.mode != "128k":
            raise RuntimeError("paged_bank() requires 128k mode")
        return self._z80.port_7ffd & 0x07

    def port_7ffd(self) -> int:
        if self.machine.mode != "128k":
            raise RuntimeError("port_7ffd() requires 128k mode")
        return self._z80.port_7ffd

    def bank_shadow(self) -> int:
        if self.machine.mode != "128k":
            raise RuntimeError("bank_shadow() requires 128k mode")
        return self._mem[BANKM_SHADOW_ADDR]

    def byte(self, addr: int) -> int:
        _check_addr(addr)
        return self._mem[addr]

    def word(self, addr: int) -> int:
        _check_addr(addr)
        _check_addr(addr + 1)
        return self._mem[addr] | (self._mem[addr + 1] << 8)

    @property
    def _z80(self):
        z80 = self.machine._last_m
        if z80 is None:
            raise RuntimeError("machine has not been run yet")
        return z80

    @property
    def _mem(self):
        return self._z80.mem

    def _label(self, name: str) -> int:
        return self.machine._prim_asm.labels[name]

    def _stack_or_raise(self, op: str) -> list[int]:
        if self.result is None:
            raise RuntimeError(
                f"{op}() requires a captured ForthResult; pass it to Run(machine, result)"
            )
        return self.result.data_stack

    def _derive_border_writes(self) -> list[int]:
        from zt.sim import SPECTRUM_BORDER_PORT
        return [v for port, v in self._z80._outputs if (port & 0xFF) == SPECTRUM_BORDER_PORT]

    def _derive_page_writes(self) -> list[int]:
        from zt.sim import is_7ffd_write
        return [v for port, v in self._z80._outputs if is_7ffd_write(port)]


def _check_screen_coords(row: int, col: int) -> None:
    if not 0 <= row < SCREEN_ROWS:
        raise ValueError(f"row {row} outside 0..{SCREEN_ROWS - 1}")
    if not 0 <= col < SCREEN_COLS:
        raise ValueError(f"col {col} outside 0..{SCREEN_COLS - 1}")


def _check_addr(addr: int) -> None:
    if not 0 <= addr < ADDR_SPACE:
        raise ValueError(f"address {addr} outside 0..0x{ADDR_SPACE - 1:04X}")
