"""
Mnemonic-name lookup for the `:::` assembler-word directive. Maps every
`OpcodeSpec.mnemonic` to its spec so the directive can recover both the
emitter method and the operand kind in one step.
"""
from __future__ import annotations

from zt.assemble.opcodes import OPCODES, OpcodeSpec


class UnknownMnemonic(KeyError):
    pass


VOCAB: dict[str, OpcodeSpec] = {spec.mnemonic: spec for spec in OPCODES}

PSEUDO_OPS: dict[str, OpcodeSpec] = {
    "byte": OpcodeSpec(mnemonic="byte", encoding=(), operand="n"),
    "word": OpcodeSpec(mnemonic="word", encoding=(), operand="nn"),
    "label": OpcodeSpec(mnemonic="label", encoding=(), operand="label"),
    "jp":    OpcodeSpec(mnemonic="jp",    encoding=(), operand="label"),
    "jp_z":  OpcodeSpec(mnemonic="jp_z",  encoding=(), operand="label"),
    "jp_nz": OpcodeSpec(mnemonic="jp_nz", encoding=(), operand="label"),
    "jp_p":  OpcodeSpec(mnemonic="jp_p",  encoding=(), operand="label"),
    "jp_m":  OpcodeSpec(mnemonic="jp_m",  encoding=(), operand="label"),
    "call":  OpcodeSpec(mnemonic="call",  encoding=(), operand="label"),
    "jr":    OpcodeSpec(mnemonic="jr",    encoding=(), operand="label"),
    "jr_z":  OpcodeSpec(mnemonic="jr_z",  encoding=(), operand="label"),
    "jr_nz": OpcodeSpec(mnemonic="jr_nz", encoding=(), operand="label"),
    "jr_c":  OpcodeSpec(mnemonic="jr_c",  encoding=(), operand="label"),
    "jr_nc": OpcodeSpec(mnemonic="jr_nc", encoding=(), operand="label"),
    "djnz":  OpcodeSpec(mnemonic="djnz",  encoding=(), operand="label"),
}

VOCAB.update(PSEUDO_OPS)


def lookup(name: str) -> OpcodeSpec:
    spec = VOCAB.get(name)
    if spec is None:
        raise UnknownMnemonic(name)
    return spec
