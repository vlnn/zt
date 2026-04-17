from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

Operand = Union[int, str]


@dataclass
class Asm:
    origin: int
    code: bytearray = field(default_factory=bytearray)
    labels: dict[str, int] = field(default_factory=dict)
    fixups: list[tuple[int, str]] = field(default_factory=list)

    @property
    def here(self) -> int:
        return self.origin + len(self.code)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = self.here

    def word(self, value: Operand) -> None:
        if isinstance(value, str):
            self.fixups.append((len(self.code), value))
            self.code.extend((0, 0))
        else:
            self.code.extend((value & 0xFF, (value >> 8) & 0xFF))

    def jp(self, target: Operand) -> None:
        self.code.append(0xC3)
        self.word(target)

    def call(self, target: Operand) -> None:
        self.code.append(0xCD)
        self.word(target)

    def resolve(self) -> bytes:
        for offset, name in self.fixups:
            if name not in self.labels:
                raise KeyError(f"undefined label: {name}")
            addr = self.labels[name]
            self.code[offset] = addr & 0xFF
            self.code[offset + 1] = (addr >> 8) & 0xFF
        return bytes(self.code)

    def push_hl(self):     self.code.append(0xE5)
    def pop_hl(self):      self.code.append(0xE1)
    def push_de(self):     self.code.append(0xD5)
    def pop_de(self):      self.code.append(0xD1)
    def push_ix(self):     self.code.extend((0xDD, 0xE5))
    def pop_ix(self):      self.code.extend((0xDD, 0xE1))
    def ret(self):         self.code.append(0xC9)
    def halt(self):        self.code.append(0x76)
    def ex_de_hl(self):    self.code.append(0xEB)
    def ex_sp_hl(self):    self.code.append(0xE3)
    def add_hl_de(self):   self.code.append(0x19)
    def or_a(self):        self.code.append(0xB7)
    def sbc_hl_de(self):   self.code.extend((0xED, 0x52))
    def inc_hl(self):      self.code.append(0x23)
    def inc_ix(self):      self.code.extend((0xDD, 0x23))
    def inc_iy(self):      self.code.extend((0xFD, 0x23))
    def dec_iy(self):      self.code.extend((0xFD, 0x2B))
    def ld_e_ind_hl(self): self.code.append(0x5E)
    def ld_d_ind_hl(self): self.code.append(0x56)
    def ld_ind_hl_e(self): self.code.append(0x73)
    def ld_ind_hl_d(self): self.code.append(0x72)

    def ld_sp_nn(self, value: Operand):
        self.code.append(0x31)
        self.word(value)

    def ld_ix_nn(self, value: Operand):
        self.code.extend((0xDD, 0x21))
        self.word(value)

    def ld_iy_nn(self, value: Operand):
        self.code.extend((0xFD, 0x21))
        self.word(value)

    def ld_e_ix(self, d): self.code.extend((0xDD, 0x5E, d & 0xFF))
    def ld_d_ix(self, d): self.code.extend((0xDD, 0x56, d & 0xFF))
    def ld_l_ix(self, d): self.code.extend((0xDD, 0x6E, d & 0xFF))
    def ld_h_ix(self, d): self.code.extend((0xDD, 0x66, d & 0xFF))
    def ld_e_iy(self, d): self.code.extend((0xFD, 0x5E, d & 0xFF))
    def ld_d_iy(self, d): self.code.extend((0xFD, 0x56, d & 0xFF))
    def ld_iy_e(self, d): self.code.extend((0xFD, 0x73, d & 0xFF))
    def ld_iy_d(self, d): self.code.extend((0xFD, 0x72, d & 0xFF))

    def ld_a_l(self):     self.code.append(0x7D)
    def out_n_a(self, port): self.code.extend((0xD3, port & 0xFF))
