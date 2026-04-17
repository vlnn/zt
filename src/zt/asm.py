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
    rel_fixups: list[tuple[int, str]] = field(default_factory=list)
    inline_next: bool = False

    @property
    def here(self) -> int:
        return self.origin + len(self.code)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = self.here

    def alias(self, name: str, target: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        if target not in self.labels:
            raise KeyError(f"alias target not found: {target}")
        self.labels[name] = self.labels[target]

    def word(self, value: Operand) -> None:
        if isinstance(value, str):
            self.fixups.append((len(self.code), value))
            self.code.extend((0, 0))
        else:
            self.code.extend((value & 0xFF, (value >> 8) & 0xFF))

    def byte(self, value: int) -> None:
        self.code.append(value & 0xFF)

    def jp(self, target: Operand) -> None:
        self.code.append(0xC3)
        self.word(target)

    def jp_z(self, target: Operand) -> None:
        self.code.append(0xCA)
        self.word(target)

    def jp_nz(self, target: Operand) -> None:
        self.code.append(0xC2)
        self.word(target)

    def jp_p(self, target: Operand) -> None:
        self.code.append(0xF2)
        self.word(target)

    def jp_m(self, target: Operand) -> None:
        self.code.append(0xFA)
        self.word(target)

    def call(self, target: Operand) -> None:
        self.code.append(0xCD)
        self.word(target)

    def _emit_jr(self, opcode: int, target: str) -> None:
        self.code.append(opcode)
        self.rel_fixups.append((len(self.code), target))
        self.code.append(0x00)

    def jr_to(self, target: str) -> None:       self._emit_jr(0x18, target)
    def jr_nz_to(self, target: str) -> None:    self._emit_jr(0x20, target)
    def jr_z_to(self, target: str) -> None:     self._emit_jr(0x28, target)
    def jr_nc_to(self, target: str) -> None:    self._emit_jr(0x30, target)
    def jr_c_to(self, target: str) -> None:     self._emit_jr(0x38, target)
    def djnz_to(self, target: str) -> None:     self._emit_jr(0x10, target)

    def resolve(self) -> bytes:
        for offset, name in self.fixups:
            if name not in self.labels:
                raise KeyError(f"undefined label: {name}")
            addr = self.labels[name]
            self.code[offset] = addr & 0xFF
            self.code[offset + 1] = (addr >> 8) & 0xFF
        for offset, name in self.rel_fixups:
            if name not in self.labels:
                raise KeyError(f"undefined label: {name}")
            target_addr = self.labels[name]
            pc_after = self.origin + offset + 1
            displacement = target_addr - pc_after
            if displacement < -128 or displacement > 127:
                raise ValueError(
                    f"relative jump to {name} out of range: {displacement}"
                )
            self.code[offset] = displacement & 0xFF
        return bytes(self.code)

    def emit_next_body(self) -> None:
        self.ld_e_ix(0)
        self.ld_d_ix(1)
        self.inc_ix()
        self.inc_ix()
        self.push_de()
        self.ret()

    def dispatch(self) -> None:
        if self.inline_next:
            self.emit_next_body()
        else:
            self.jp("NEXT")

    # -- stack --
    def push_hl(self):     self.code.append(0xE5)
    def pop_hl(self):      self.code.append(0xE1)
    def push_de(self):     self.code.append(0xD5)
    def pop_de(self):      self.code.append(0xD1)
    def push_bc(self):     self.code.append(0xC5)
    def pop_bc(self):      self.code.append(0xC1)
    def push_af(self):     self.code.append(0xF5)
    def pop_af(self):      self.code.append(0xF1)
    def push_ix(self):     self.code.extend((0xDD, 0xE5))
    def pop_ix(self):      self.code.extend((0xDD, 0xE1))

    # -- exchange --
    def ex_de_hl(self):    self.code.append(0xEB)
    def ex_sp_hl(self):    self.code.append(0xE3)

    # -- 16-bit arithmetic --
    def add_hl_de(self):   self.code.append(0x19)
    def add_hl_hl(self):   self.code.append(0x29)
    def add_hl_bc(self):   self.code.append(0x09)
    def sbc_hl_de(self):   self.code.extend((0xED, 0x52))
    def inc_hl(self):      self.code.append(0x23)
    def dec_hl(self):      self.code.append(0x2B)
    def inc_de(self):      self.code.append(0x13)
    def dec_de(self):      self.code.append(0x1B)
    def inc_bc(self):      self.code.append(0x03)
    def dec_bc(self):      self.code.append(0x0B)

    # -- 8-bit arithmetic --
    def or_a(self):        self.code.append(0xB7)
    def xor_a(self):       self.code.append(0xAF)
    def sub_l(self):       self.code.append(0x95)
    def sub_h(self):       self.code.append(0x94)
    def sbc_a_a(self):     self.code.append(0x9F)
    def add_a_e(self):     self.code.append(0x83)
    def adc_a_d(self):     self.code.append(0x8A)
    def inc_a(self):       self.code.append(0x3C)
    def dec_a(self):       self.code.append(0x3D)
    def dec_e(self):       self.code.append(0x1D)
    def inc_h(self):       self.code.append(0x24)
    def cp_d(self):        self.code.append(0xBA)
    def cp_e(self):        self.code.append(0xBB)
    def cp_n(self, n):     self.code.extend((0xFE, n & 0xFF))
    def add_a_a(self):     self.code.append(0x87)

    # -- 8-bit logic --
    def and_d(self):       self.code.append(0xA2)
    def and_e(self):       self.code.append(0xA3)
    def and_n(self, n):    self.code.extend((0xE6, n & 0xFF))
    def or_b(self):        self.code.append(0xB0)
    def or_c(self):        self.code.append(0xB1)
    def or_d(self):        self.code.append(0xB2)
    def or_e(self):        self.code.append(0xB3)
    def or_h(self):        self.code.append(0xB4)
    def or_l(self):        self.code.append(0xB5)
    def or_n(self, n):     self.code.extend((0xF6, n & 0xFF))
    def xor_d(self):       self.code.append(0xAA)
    def xor_e(self):       self.code.append(0xAB)
    def cpl(self):         self.code.append(0x2F)
    def rrca(self):        self.code.append(0x0F)

    # -- 8-bit loads --
    def ld_a_b(self):      self.code.append(0x78)
    def ld_a_c(self):      self.code.append(0x79)
    def ld_a_d(self):      self.code.append(0x7A)
    def ld_a_e(self):      self.code.append(0x7B)
    def ld_a_h(self):      self.code.append(0x7C)
    def ld_a_l(self):      self.code.append(0x7D)
    def ld_b_a(self):      self.code.append(0x47)
    def ld_b_h(self):      self.code.append(0x44)
    def ld_b_l(self):      self.code.append(0x45)
    def ld_c_l(self):      self.code.append(0x4D)
    def ld_d_b(self):      self.code.append(0x50)
    def ld_d_h(self):      self.code.append(0x54)
    def ld_e_c(self):      self.code.append(0x59)
    def ld_e_l(self):      self.code.append(0x5D)
    def ld_h_a(self):      self.code.append(0x67)
    def ld_h_b(self):      self.code.append(0x60)
    def ld_h_d(self):      self.code.append(0x62)
    def ld_l_a(self):      self.code.append(0x6F)
    def ld_l_c(self):      self.code.append(0x69)
    def ld_l_e(self):      self.code.append(0x6B)
    def ld_b_n(self, n):   self.code.extend((0x06, n & 0xFF))
    def ld_h_n(self, n):   self.code.extend((0x26, n & 0xFF))
    def ld_l_n(self, n):   self.code.extend((0x2E, n & 0xFF))
    def ld_a_n(self, n):   self.code.extend((0x3E, n & 0xFF))
    def ld_e_n(self, n):   self.code.extend((0x1E, n & 0xFF))
    def ld_d_n(self, n):   self.code.extend((0x16, n & 0xFF))

    # -- indirect HL --
    def ld_e_ind_hl(self): self.code.append(0x5E)
    def ld_d_ind_hl(self): self.code.append(0x56)
    def ld_l_ind_hl(self): self.code.append(0x6E)
    def ld_ind_hl_e(self): self.code.append(0x73)
    def ld_ind_hl_d(self): self.code.append(0x72)
    def ld_ind_hl_a(self): self.code.append(0x77)
    def ld_a_ind_hl(self): self.code.append(0x7E)

    # -- indirect DE --
    def ld_a_ind_de(self): self.code.append(0x1A)

    # -- absolute addressing --
    def ld_a_ind_nn(self, addr: Operand):
        self.code.append(0x3A)
        self.word(addr)

    def ld_ind_nn_a(self, addr: Operand):
        self.code.append(0x32)
        self.word(addr)

    # -- 16-bit loads --
    def ld_sp_nn(self, value: Operand):
        self.code.append(0x31)
        self.word(value)

    def ld_hl_nn(self, value: Operand):
        self.code.append(0x21)
        self.word(value)

    def ld_de_nn(self, value: Operand):
        self.code.append(0x11)
        self.word(value)

    def ld_bc_nn(self, value: Operand):
        self.code.append(0x01)
        self.word(value)

    # -- IX indexed --
    def ld_ix_nn(self, value: Operand):
        self.code.extend((0xDD, 0x21))
        self.word(value)

    def inc_ix(self):      self.code.extend((0xDD, 0x23))

    def ld_e_ix(self, d):  self.code.extend((0xDD, 0x5E, d & 0xFF))
    def ld_d_ix(self, d):  self.code.extend((0xDD, 0x56, d & 0xFF))
    def ld_l_ix(self, d):  self.code.extend((0xDD, 0x6E, d & 0xFF))
    def ld_h_ix(self, d):  self.code.extend((0xDD, 0x66, d & 0xFF))

    # -- IY indexed --
    def ld_iy_nn(self, value: Operand):
        self.code.extend((0xFD, 0x21))
        self.word(value)

    def inc_iy(self):      self.code.extend((0xFD, 0x23))
    def dec_iy(self):      self.code.extend((0xFD, 0x2B))

    def ld_e_iy(self, d):  self.code.extend((0xFD, 0x5E, d & 0xFF))
    def ld_d_iy(self, d):  self.code.extend((0xFD, 0x56, d & 0xFF))
    def ld_iy_e(self, d):  self.code.extend((0xFD, 0x73, d & 0xFF))
    def ld_iy_d(self, d):  self.code.extend((0xFD, 0x72, d & 0xFF))
    def ld_iy_l(self, d):  self.code.extend((0xFD, 0x75, d & 0xFF))
    def ld_iy_h(self, d):  self.code.extend((0xFD, 0x74, d & 0xFF))
    def ld_l_iy(self, d):  self.code.extend((0xFD, 0x6E, d & 0xFF))
    def ld_h_iy(self, d):  self.code.extend((0xFD, 0x66, d & 0xFF))

    # -- shifts and rotates --
    def sra_h(self):       self.code.extend((0xCB, 0x2C))
    def rr_l(self):        self.code.extend((0xCB, 0x1D))
    def srl_h(self):       self.code.extend((0xCB, 0x3C))
    def rl_b(self):        self.code.extend((0xCB, 0x10))
    def rl_c(self):        self.code.extend((0xCB, 0x11))
    def rl_l(self):        self.code.extend((0xCB, 0x15))
    def rl_h(self):        self.code.extend((0xCB, 0x14))
    def sla_c(self):       self.code.extend((0xCB, 0x21))

    # -- bit test --
    def bit_7_h(self):     self.code.extend((0xCB, 0x7C))

    # -- block --
    def ldir(self):        self.code.extend((0xED, 0xB0))

    # -- misc --
    def ret(self):         self.code.append(0xC9)
    def halt(self):        self.code.append(0x76)
    def nop(self):         self.code.append(0x00)
    def di(self):          self.code.append(0xF3)
    def ei(self):          self.code.append(0xFB)
    def scf(self):         self.code.append(0x37)

    # -- I/O --
    def out_n_a(self, port): self.code.extend((0xD3, port & 0xFF))
