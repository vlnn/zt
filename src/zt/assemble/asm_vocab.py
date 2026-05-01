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
}

VOCAB.update(PSEUDO_OPS)


def lookup(name: str) -> OpcodeSpec:
    spec = VOCAB.get(name)
    if spec is None:
        raise UnknownMnemonic(name)
    return spec
