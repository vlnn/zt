"""
Declarative Z80 opcode table. Each `OpcodeSpec` pairs a mnemonic with its encoding and operand kind; `asm.Asm` auto-generates a method per entry, and `decode()` provides single-instruction disassembly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

OperandKind = Optional[Literal["n", "d", "nn"]]


@dataclass(frozen=True)
class OpcodeSpec:
    mnemonic: str
    encoding: tuple[int, ...]
    operand: OperandKind = None

    @property
    def total_length(self) -> int:
        if self.operand is None:
            return len(self.encoding)
        if self.operand in ("n", "d"):
            return len(self.encoding) + 1
        if self.operand == "nn":
            return len(self.encoding) + 2
        raise ValueError(f"unknown operand kind: {self.operand!r}")


def _no(mnemonic: str, *encoding: int) -> OpcodeSpec:
    return OpcodeSpec(mnemonic=mnemonic, encoding=tuple(encoding), operand=None)


def _n(mnemonic: str, *encoding: int) -> OpcodeSpec:
    """8-bit immediate (one byte)"""
    return OpcodeSpec(mnemonic=mnemonic, encoding=tuple(encoding), operand="n")


def _d(mnemonic: str, *encoding: int) -> OpcodeSpec:
    """8-bit signed"""
    return OpcodeSpec(mnemonic=mnemonic, encoding=tuple(encoding), operand="d")


def _nn(mnemonic: str, *encoding: int) -> OpcodeSpec:
    """16-bit immediate / absolute address (two bytes, little-endian)"""
    return OpcodeSpec(mnemonic=mnemonic, encoding=tuple(encoding), operand="nn")


OPCODES: tuple[OpcodeSpec, ...] = (
    _no("push_hl",      0xE5),
    _no("pop_hl",       0xE1),
    _no("push_de",      0xD5),
    _no("pop_de",       0xD1),
    _no("push_bc",      0xC5),
    _no("pop_bc",       0xC1),
    _no("push_af",      0xF5),
    _no("pop_af",       0xF1),
    _no("push_ix",      0xDD, 0xE5),
    _no("pop_ix",       0xDD, 0xE1),

    _no("ex_de_hl",     0xEB),
    _no("ex_sp_hl",     0xE3),
    _no("ex_sp_ix",     0xDD, 0xE3),

    _no("add_hl_de",    0x19),
    _no("add_hl_hl",    0x29),
    _no("add_hl_bc",    0x09),
    _no("sbc_hl_de",    0xED, 0x52),
    _no("inc_hl",       0x23),
    _no("dec_hl",       0x2B),
    _no("inc_de",       0x13),
    _no("dec_de",       0x1B),
    _no("inc_bc",       0x03),
    _no("dec_bc",       0x0B),

    _no("or_a",         0xB7),
    _no("xor_a",        0xAF),
    _no("sub_l",        0x95),
    _no("sub_h",        0x94),
    _no("sbc_a_a",      0x9F),
    _no("add_a_e",      0x83),
    _no("adc_a_d",      0x8A),
    _no("inc_a",        0x3C),
    _no("dec_a",        0x3D),
    _no("dec_e",        0x1D),
    _no("inc_h",        0x24),
    _no("cp_d",         0xBA),
    _no("cp_e",         0xBB),
    _n ("cp_n",         0xFE),
    _no("add_a_a",      0x87),

    _no("and_d",        0xA2),
    _no("and_e",        0xA3),
    _n ("and_n",        0xE6),
    _no("or_b",         0xB0),
    _no("or_c",         0xB1),
    _no("or_d",         0xB2),
    _no("or_e",         0xB3),
    _no("or_h",         0xB4),
    _no("or_l",         0xB5),
    _n ("or_n",         0xF6),
    _no("xor_d",        0xAA),
    _no("xor_e",        0xAB),
    _no("cpl",          0x2F),
    _no("rrca",         0x0F),
    _no("rlca",         0x07),

    _no("ld_a_b",       0x78),
    _no("ld_a_c",       0x79),
    _no("ld_a_d",       0x7A),
    _no("ld_a_e",       0x7B),
    _no("ld_a_h",       0x7C),
    _no("ld_a_l",       0x7D),
    _no("ld_b_a",       0x47),
    _no("ld_b_h",       0x44),
    _no("ld_b_l",       0x45),
    _no("ld_c_l",       0x4D),
    _no("ld_d_b",       0x50),
    _no("ld_d_h",       0x54),
    _no("ld_e_c",       0x59),
    _no("ld_e_l",       0x5D),
    _no("ld_h_a",       0x67),
    _no("ld_h_b",       0x60),
    _no("ld_h_d",       0x62),
    _no("ld_l_a",       0x6F),
    _no("ld_l_c",       0x69),
    _no("ld_l_e",       0x6B),
    _n ("ld_b_n",       0x06),
    _n ("ld_h_n",       0x26),
    _n ("ld_l_n",       0x2E),
    _n ("ld_a_n",       0x3E),
    _n ("ld_e_n",       0x1E),
    _n ("ld_d_n",       0x16),

    _no("ld_e_ind_hl",  0x5E),
    _no("ld_d_ind_hl",  0x56),
    _no("ld_l_ind_hl",  0x6E),
    _no("ld_ind_hl_e",  0x73),
    _no("ld_ind_hl_d",  0x72),
    _no("ld_ind_hl_a",  0x77),
    _no("ld_a_ind_hl",  0x7E),

    _no("ld_a_ind_de",  0x1A),

    _nn("ld_a_ind_nn",  0x3A),
    _nn("ld_ind_nn_a",  0x32),

    _nn("ld_sp_nn",     0x31),
    _nn("ld_hl_nn",     0x21),
    _nn("ld_de_nn",     0x11),
    _nn("ld_bc_nn",     0x01),

    _nn("ld_ix_nn",     0xDD, 0x21),
    _no("inc_ix",       0xDD, 0x23),
    _d ("ld_e_ix",      0xDD, 0x5E),
    _d ("ld_d_ix",      0xDD, 0x56),
    _d ("ld_l_ix",      0xDD, 0x6E),
    _d ("ld_h_ix",      0xDD, 0x66),

    _nn("ld_iy_nn",     0xFD, 0x21),
    _no("push_iy",      0xFD, 0xE5),
    _no("pop_iy",       0xFD, 0xE1),
    _no("inc_iy",       0xFD, 0x23),
    _no("dec_iy",       0xFD, 0x2B),
    _d ("ld_e_iy",      0xFD, 0x5E),
    _d ("ld_d_iy",      0xFD, 0x56),
    _d ("ld_iy_e",      0xFD, 0x73),
    _d ("ld_iy_d",      0xFD, 0x72),
    _d ("ld_iy_l",      0xFD, 0x75),
    _d ("ld_iy_h",      0xFD, 0x74),
    _d ("ld_l_iy",      0xFD, 0x6E),
    _d ("ld_h_iy",      0xFD, 0x66),

    _no("sra_h",        0xCB, 0x2C),
    _no("rr_l",         0xCB, 0x1D),
    _no("srl_h",        0xCB, 0x3C),
    _no("rl_b",         0xCB, 0x10),
    _no("rl_c",         0xCB, 0x11),
    _no("rl_l",         0xCB, 0x15),
    _no("rl_h",         0xCB, 0x14),
    _no("sla_c",        0xCB, 0x21),

    _no("bit_7_h",      0xCB, 0x7C),

    _no("ldir",         0xED, 0xB0),

    _no("ret",          0xC9),
    _no("halt",         0x76),
    _no("nop",          0x00),
    _no("di",           0xF3),
    _no("ei",           0xFB),
    _no("scf",          0x37),

    _no("inc_b",        0x04),
    _no("inc_d",        0x14),
    _no("dec_b",        0x05),
    _no("add_a_b",      0x80),
    _no("add_a_d",      0x82),
    _no("sub_b",        0x90),
    _no("cp_ind_hl",    0xBE),
    _no("ld_b_c",       0x41),
    _no("ld_e_a",       0x5F),
    _no("rlc_e",        0xCB, 0x03),
    _n ("sub_n",        0xD6),

    _n ("out_n_a",      0xD3),
    _n ("in_a_n",       0xDB),
)


_BY_ENCODING_NO_OPERAND: dict[tuple[int, ...], OpcodeSpec] = {
    spec.encoding: spec for spec in OPCODES if spec.operand is None
}
_BY_ENCODING_WITH_OPERAND: dict[tuple[int, ...], OpcodeSpec] = {
    spec.encoding: spec for spec in OPCODES if spec.operand is not None
}


def decode(memory: bytes | bytearray, pc: int) -> tuple[OpcodeSpec, int]:
    """Return (spec, next_pc) for the instruction at `pc`, preferring 2-byte prefixed encodings."""
    for encoding_len in (2, 1):
        if pc + encoding_len > len(memory):
            continue
        candidate = tuple(memory[pc:pc + encoding_len])
        spec = _BY_ENCODING_NO_OPERAND.get(candidate) or _BY_ENCODING_WITH_OPERAND.get(candidate)
        if spec is not None:
            return spec, pc + spec.total_length
    raise ValueError(
        f"no opcode matches bytes {bytes(memory[pc:pc + 2]).hex()} at pc={pc:#06x}"
    )
