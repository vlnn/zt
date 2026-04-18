from __future__ import annotations

import inspect

import pytest

from zt.asm import Asm
from zt.opcodes import OPCODES, OpcodeSpec, decode


HAND_WRITTEN = frozenset({
    "jp", "jp_z", "jp_nz", "jp_p", "jp_m",
    "call",
    "jr_to", "jr_nz_to", "jr_z_to", "jr_nc_to", "jr_c_to", "djnz_to",
    "word", "byte", "label", "alias", "resolve",
    "dispatch", "emit_next_body",
})


def _public_asm_methods() -> list[str]:
    names = []
    for name in dir(Asm):
        if name.startswith("_"):
            continue
        attr = getattr(Asm, name)
        if not callable(attr):
            continue
        names.append(name)
    return names


class TestOpcodeSpec:

    def test_no_operand_spec_carries_single_byte(self):
        spec = OpcodeSpec(mnemonic="push_hl", encoding=(0xE5,), operand=None)
        assert spec.encoding == (0xE5,), "push_hl encoding should be the single byte 0xE5"

    def test_prefixed_no_operand_spec_carries_two_bytes(self):
        spec = OpcodeSpec(mnemonic="push_ix", encoding=(0xDD, 0xE5), operand=None)
        assert len(spec.encoding) == 2, "prefixed no-operand spec should carry 2 prefix+opcode bytes"

    def test_spec_is_frozen(self):
        spec = OpcodeSpec(mnemonic="x", encoding=(0x00,), operand=None)
        with pytest.raises((AttributeError, Exception)):
            spec.mnemonic = "y"


class TestTableCoverage:

    def test_every_table_entry_matches_a_public_asm_method(self):
        asm_methods = set(_public_asm_methods())
        missing_methods = [
            spec.mnemonic for spec in OPCODES
            if spec.mnemonic not in asm_methods
        ]
        assert missing_methods == [], (
            f"OPCODES entries must all have matching Asm methods; "
            f"missing: {missing_methods}"
        )

    def test_every_table_mnemonic_is_unique(self):
        mnemonics = [spec.mnemonic for spec in OPCODES]
        duplicates = [m for m in set(mnemonics) if mnemonics.count(m) > 1]
        assert duplicates == [], (
            f"OPCODES mnemonics must be unique; duplicates: {duplicates}"
        )

    def test_no_duplicate_encodings_for_no_operand_opcodes(self):
        seen: dict[tuple[int, ...], str] = {}
        for spec in OPCODES:
            if spec.operand is not None:
                continue
            encoding = spec.encoding
            if encoding in seen:
                pytest.fail(
                    f"duplicate encoding {encoding!r} for "
                    f"{seen[encoding]!r} and {spec.mnemonic!r}"
                )
            seen[encoding] = spec.mnemonic

    def test_table_has_reasonable_size(self):
        assert len(OPCODES) >= 100, (
            f"OPCODES should cover at least 100 encodings; got {len(OPCODES)}"
        )


class TestParityWithAsm:

    @pytest.mark.parametrize("spec", [
        s for s in OPCODES if s.operand is None
    ], ids=lambda s: s.mnemonic)
    def test_no_operand_asm_emission_matches_table(self, spec):
        asm = Asm(0x8000, inline_next=False)
        method = getattr(asm, spec.mnemonic)
        method()
        assert bytes(asm.code) == bytes(spec.encoding), (
            f"Asm.{spec.mnemonic}() should emit the bytes declared in OPCODES; "
            f"table says {list(spec.encoding)}, got {list(asm.code)}"
        )

    @pytest.mark.parametrize("spec", [
        s for s in OPCODES if s.operand == "n"
    ], ids=lambda s: s.mnemonic)
    def test_n_operand_asm_emission_matches_table(self, spec):
        asm = Asm(0x8000, inline_next=False)
        method = getattr(asm, spec.mnemonic)
        method(0x42)
        assert bytes(asm.code) == bytes([*spec.encoding, 0x42]), (
            f"Asm.{spec.mnemonic}(0x42) should emit the table prefix+opcode followed "
            f"by 0x42; got {list(asm.code)}"
        )

    @pytest.mark.parametrize("spec", [
        s for s in OPCODES if s.operand == "d"
    ], ids=lambda s: s.mnemonic)
    def test_d_operand_asm_emission_matches_table(self, spec):
        asm = Asm(0x8000, inline_next=False)
        method = getattr(asm, spec.mnemonic)
        method(0x12)
        assert bytes(asm.code) == bytes([*spec.encoding, 0x12]), (
            f"Asm.{spec.mnemonic}(0x12) should emit prefix+opcode+displacement; "
            f"got {list(asm.code)}"
        )

    @pytest.mark.parametrize("spec", [
        s for s in OPCODES if s.operand == "nn"
    ], ids=lambda s: s.mnemonic)
    def test_nn_operand_asm_emission_matches_table(self, spec):
        asm = Asm(0x8000, inline_next=False)
        method = getattr(asm, spec.mnemonic)
        method(0xBEEF)
        expected = bytes([*spec.encoding, 0xEF, 0xBE])
        assert bytes(asm.code) == expected, (
            f"Asm.{spec.mnemonic}(0xBEEF) should emit prefix+opcode+LE word; "
            f"got {list(asm.code)}"
        )


class TestDecode:

    def test_decode_no_operand_returns_spec_and_next_pc(self):
        memory = bytearray(b"\xE5")
        spec, next_pc = decode(memory, 0)
        assert spec.mnemonic == "push_hl", "0xE5 should decode to push_hl"
        assert next_pc == 1, "next_pc should advance past the opcode byte"

    def test_decode_prefixed_no_operand(self):
        memory = bytearray(b"\xDD\xE5")
        spec, next_pc = decode(memory, 0)
        assert spec.mnemonic == "push_ix", "0xDD 0xE5 should decode to push_ix"
        assert next_pc == 2, "next_pc should advance past both prefix and opcode"

    def test_decode_n_operand_advances_three_bytes_for_prefix(self):
        memory = bytearray(b"\x06\x42")
        spec, next_pc = decode(memory, 0)
        assert spec.mnemonic == "ld_b_n", "0x06 n should decode to ld_b_n"
        assert next_pc == 2, "ld_b_n should advance past opcode + immediate byte"

    def test_decode_nn_operand_advances_three_bytes(self):
        memory = bytearray(b"\x21\xEF\xBE")
        spec, next_pc = decode(memory, 0)
        assert spec.mnemonic == "ld_hl_nn", "0x21 nn nn should decode to ld_hl_nn"
        assert next_pc == 3, "ld_hl_nn should advance past opcode + 2 immediate bytes"

    def test_decode_d_operand_advances_three_bytes(self):
        memory = bytearray(b"\xDD\x5E\x00")
        spec, next_pc = decode(memory, 0)
        assert spec.mnemonic == "ld_e_ix", "DD 5E d should decode to ld_e_ix"
        assert next_pc == 3, "ld_e_ix should advance past prefix + opcode + displacement"


class TestEncodeDecodeRoundtrip:

    @pytest.mark.parametrize("spec", [
        s for s in OPCODES if s.operand is None
    ], ids=lambda s: s.mnemonic)
    def test_no_operand_roundtrip(self, spec):
        asm = Asm(0x8000, inline_next=False)
        getattr(asm, spec.mnemonic)()
        decoded, next_pc = decode(asm.code, 0)
        assert decoded.mnemonic == spec.mnemonic, (
            f"roundtrip for {spec.mnemonic} should recover the same mnemonic"
        )
        assert next_pc == len(asm.code), (
            f"roundtrip for {spec.mnemonic} should consume exactly the emitted bytes"
        )
