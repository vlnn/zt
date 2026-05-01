"""
Tests for `assemble.asm_vocab`: the mnemonic-name → opcode-spec lookup that
backs the `:::` assembler-word directive.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm_vocab import VOCAB, lookup, UnknownMnemonic


class TestLookup:

    def test_known_mnemonic_returns_spec(self):
        spec = lookup("ld_a_l")
        assert spec.mnemonic == "ld_a_l", "lookup should return the matching OpcodeSpec"

    @pytest.mark.parametrize("mnemonic,operand_kind", [
        ("ld_a_l",       None),
        ("ld_hl_nn",     "nn"),
        ("ld_a_n",       "n"),
        ("ld_e_ix",      "d"),
        ("ld_ind_hl_a",  None),
        ("ex_de_hl",     None),
        ("pop_hl",       None),
    ], ids=["no-operand", "nn", "n", "d", "store", "ex_de_hl", "pop_hl"])
    def test_operand_kind_round_trip(self, mnemonic, operand_kind):
        assert lookup(mnemonic).operand == operand_kind, (
            f"{mnemonic} should report operand kind {operand_kind!r}"
        )

    def test_unknown_mnemonic_raises(self):
        with pytest.raises(UnknownMnemonic, match="lda"):
            lookup("lda")


class TestVocabCoverage:

    def test_vocab_contains_every_opcode(self):
        from zt.assemble.opcodes import OPCODES
        missing = {spec.mnemonic for spec in OPCODES} - set(VOCAB)
        assert not missing, (
            f"VOCAB should expose every OPCODES entry; missing: {sorted(missing)}"
        )

    def test_vocab_keys_match_their_specs(self):
        for name, spec in VOCAB.items():
            assert name == spec.mnemonic, (
                f"VOCAB key {name!r} should equal spec.mnemonic {spec.mnemonic!r}"
            )
