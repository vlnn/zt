"""
Tests for the 128K banking primitives: byte-level layout of `BANK!`, `BANK@`,
`RAW-BANK!`, `128K?`, the `$5B5C` shadow, and end-to-end behaviour through
`ForthMachine(mode="128k")`.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitives import (
    BANKM_ADDR,
    PORT_7FFD,
    create_128k_query,
    create_bank_fetch,
    create_bank_store,
    create_raw_bank_store,
)
from zt.sim import ForthMachine


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _compile_primitive(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


class TestBankmAddress:

    def test_bankm_is_canonical_0x5B5C(self):
        assert BANKM_ADDR == 0x5B5C, (
            "BANKM shadow address should match the ZX 128 ROM's canonical slot"
        )

    def test_port_7ffd_constant(self):
        assert PORT_7FFD == 0x7FFD, (
            "PORT_7FFD constant should equal the 128K paging port address"
        )


class TestBankStoreBytes:

    def test_bank_store_begins_with_mask_of_tos_low(self):
        out = _compile_primitive(create_bank_store)
        assert out[0] == 0x7D, "BANK! should start with LD A,L (pull low byte of TOS)"
        assert out[1:3] == bytes([0xE6, 0x07]), "then AND $07 to mask the bank bits"

    def test_bank_store_reads_shadow_and_merges(self):
        out = _compile_primitive(create_bank_store)
        assert out[3] == 0x47, "then LD B,A to stash masked bank bits"
        assert out[4:7] == bytes([0x3A, 0x5C, 0x5B]), (
            f"then LD A,({BANKM_ADDR:#06x}) to read the shadow"
        )
        assert out[7:9] == bytes([0xE6, 0xF8]), (
            "then AND $F8 to clear the bank bits of the shadow, preserving screen/ROM/lock"
        )
        assert out[9] == 0xB0, "then OR B to merge bank bits back in"

    def test_bank_store_writes_shadow_then_port(self):
        out = _compile_primitive(create_bank_store)
        assert out[10:13] == bytes([0x32, 0x5C, 0x5B]), (
            "then LD (BANKM),A to update the shadow"
        )
        assert out[13:16] == bytes([0x01, 0xFD, 0x7F]), (
            "then LD BC,$7FFD to address the paging port"
        )
        assert out[16:18] == bytes([0xED, 0x79]), "then OUT (C),A to page"

    def test_bank_store_ends_with_pop_then_next(self):
        out = _compile_primitive(create_bank_store)
        assert out[18] == 0xE1, "BANK! should POP HL for the next TOS"
        assert out[19] == 0xC3, "BANK! should end with JP NEXT"


class TestBankFetchBytes:

    def test_bank_fetch_preserves_tos(self):
        out = _compile_primitive(create_bank_fetch)
        assert out[0] == 0xE5, "BANK@ should start with PUSH HL to save old TOS"

    def test_bank_fetch_reads_shadow_masked_to_low_three_bits(self):
        out = _compile_primitive(create_bank_fetch)
        assert out[1:4] == bytes([0x3A, 0x5C, 0x5B]), "then LD A,(BANKM)"
        assert out[4:6] == bytes([0xE6, 0x07]), "then AND $07 to keep only bank bits"

    def test_bank_fetch_builds_new_tos_in_hl(self):
        out = _compile_primitive(create_bank_fetch)
        assert out[6] == 0x6F, "then LD L,A to put bank bits in low byte of HL"
        assert out[7:9] == bytes([0x26, 0x00]), "then LD H,$00 for a zero high byte"
        assert out[9] == 0xC3, "BANK@ should end with JP NEXT"


class TestRawBankStoreBytes:

    def test_raw_bank_store_skips_masking(self):
        out = _compile_primitive(create_raw_bank_store)
        assert out[0] == 0x7D, "RAW-BANK! should start with LD A,L"
        assert out[1:4] == bytes([0x32, 0x5C, 0x5B]), (
            "then LD (BANKM),A directly — no AND mask"
        )
        assert out[4:7] == bytes([0x01, 0xFD, 0x7F]), "then LD BC,$7FFD"
        assert out[7:9] == bytes([0xED, 0x79]), "then OUT (C),A"
        assert out[9] == 0xE1, "then POP HL"
        assert out[10] == 0xC3, "and JP NEXT"


class TestBankStoreEndToEnd:

    @pytest.mark.parametrize("bank", list(range(8)))
    def test_bank_store_writes_bank_bits_to_port(self, bank):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("LIT"), bank,
                         fm.label("BANK!"),
                         fm.label("HALT")])
        assert len(result.page_writes) == 1, (
            f"BANK! {bank} should cause exactly one $7FFD write"
        )
        assert result.page_writes[0] & 0x07 == bank, (
            f"BANK! {bank} should land bank bits {bank} in the port value"
        )

    @pytest.mark.parametrize("bank", [0, 1, 3, 4, 6, 7])
    def test_bank_store_actually_pages(self, bank):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), bank, fm.label("BANK!"), fm.label("HALT")])
        m = fm._last_m
        assert m.port_7ffd & 0x07 == bank, (
            f"BANK! {bank} should leave the simulator's port_7ffd at {bank}"
        )

    def test_bank_store_preserves_upper_bits(self):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), 0x18, fm.label("RAW-BANK!"),
                fm.label("LIT"), 3, fm.label("BANK!"),
                fm.label("HALT")])
        m = fm._last_m
        assert m.port_7ffd & 0xF8 == 0x18, (
            "BANK! should preserve upper bits of the shadow (screen/ROM)"
        )
        assert m.port_7ffd & 0x07 == 3, (
            "BANK! should still place the requested bank bits in the low 3 bits"
        )

    def test_bank_store_masks_tos_to_low_three_bits(self):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), 0xFF, fm.label("BANK!"), fm.label("HALT")])
        m = fm._last_m
        assert m.port_7ffd & 0x07 == 0x07, (
            "BANK! with TOS=$FF should only use the low 3 bits"
        )

    def test_bank_store_consumes_one_stack_item(self):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("LIT"), 7, fm.label("LIT"), 3,
                         fm.label("BANK!"), fm.label("HALT")])
        assert result.data_stack == [7], (
            "BANK! should consume one stack item and leave the rest intact"
        )

    def test_bank_store_updates_shadow_at_5b5c(self):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), 5, fm.label("BANK!"), fm.label("HALT")])
        m = fm._last_m
        assert m.mem[BANKM_ADDR] == m.port_7ffd, (
            "BANK! should keep the shadow at $5B5C in sync with port_7ffd"
        )


class TestBankFetchEndToEnd:

    @pytest.mark.parametrize("bank", list(range(8)))
    def test_bank_fetch_returns_current_bank(self, bank):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("LIT"), bank, fm.label("BANK!"),
                         fm.label("BANK@"),
                         fm.label("HALT")])
        assert result.data_stack == [bank], (
            f"BANK@ after BANK! {bank} should return {bank}"
        )

    def test_bank_fetch_returns_zero_at_startup(self):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("BANK@"), fm.label("HALT")])
        assert result.data_stack == [0], (
            "BANK@ at startup should return 0 (no paging yet)"
        )

    def test_bank_fetch_does_not_write_the_port(self):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("BANK@"), fm.label("HALT")])
        assert result.page_writes == [], (
            "BANK@ should not emit any $7FFD writes — it reads the shadow only"
        )


class TestRawBankStoreEndToEnd:

    def test_raw_bank_store_writes_full_byte(self):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), 0x17, fm.label("RAW-BANK!"), fm.label("HALT")])
        m = fm._last_m
        assert m.port_7ffd == 0x17, (
            "RAW-BANK! should write the full byte (bits 0-7) without masking"
        )

    def test_raw_bank_store_can_set_lock_bit(self):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), 0x20, fm.label("RAW-BANK!"), fm.label("HALT")])
        m = fm._last_m
        assert m.port_7ffd & 0x20 != 0, (
            "RAW-BANK! with $20 should set the paging lock bit"
        )

    def test_raw_bank_store_updates_shadow(self):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), 0x14, fm.label("RAW-BANK!"), fm.label("HALT")])
        m = fm._last_m
        assert m.mem[BANKM_ADDR] == 0x14, (
            "RAW-BANK! should store the exact byte in the $5B5C shadow"
        )


class TestBankRoundtripBankedStorage:

    def test_each_bank_retains_its_own_bytes(self):
        fm = ForthMachine(mode="128k")
        program = []
        for bank in (0, 1, 3, 4, 6, 7):
            program += [fm.label("LIT"), bank, fm.label("BANK!"),
                        fm.label("LIT"), 0xA0 + bank,
                        fm.label("LIT"), 0xC000, fm.label("C_STORE")]
        for bank in (0, 1, 3, 4, 6, 7):
            program += [fm.label("LIT"), bank, fm.label("BANK!"),
                        fm.label("LIT"), 0xC000, fm.label("C_FETCH")]
        program.append(fm.label("HALT"))
        result = fm.run(program)
        assert result.data_stack == [0xA0 + b for b in (0, 1, 3, 4, 6, 7)], (
            "each bank should retain its own byte at $C000 across paging"
        )


class TestOneTwentyEightKQuery:

    def test_returns_true_in_128k_mode(self):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("128K?"), fm.label("HALT")])
        assert result.data_stack == [0xFFFF], (
            "128K? should return -1 (TRUE) when running on a 128K simulator"
        )

    def test_returns_false_in_48k_mode(self):
        fm = ForthMachine(mode="48k")
        result = fm.run([fm.label("128K?"), fm.label("HALT")])
        assert result.data_stack == [0x0000], (
            "128K? should return 0 (FALSE) when running on a 48K simulator"
        )

    def test_preserves_other_stack_items(self):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("LIT"), 0x1234,
                         fm.label("128K?"),
                         fm.label("HALT")])
        assert result.data_stack == [0x1234, 0xFFFF], (
            "128K? should push its result above any existing stack items"
        )

    def test_restores_original_bank_after_probe(self):
        fm = ForthMachine(mode="128k")
        fm.run([fm.label("LIT"), 4, fm.label("BANK!"),
                fm.label("128K?"), fm.label("DROP"),
                fm.label("HALT")])
        m = fm._last_m
        assert m.port_7ffd & 0x07 == 4, (
            "128K? should restore the original paged bank after its probing"
        )

    def test_probe_in_48k_mode_does_not_corrupt_memory(self):
        fm = ForthMachine(mode="48k")
        m_entry = 0xC000
        fm.run([fm.label("LIT"), 0x42,
                fm.label("LIT"), m_entry, fm.label("C_STORE"),
                fm.label("128K?"), fm.label("DROP"),
                fm.label("LIT"), m_entry, fm.label("C_FETCH"),
                fm.label("HALT")])
        result_stack = fm._last_m.mem[m_entry]
        assert result_stack == 0x5A, (
            "128K? on 48K leaves the $5A sentinel at $C000 (no real paging); "
            "document that the probe is destructive. Restoring is impossible "
            "without paging, so callers should run 128K? before seeding RAM"
        )
