"""
Tests for the pieces the native backend needs from the assembler and the simulator:
linked dispatch (`JP (IX)` instead of NEXT), dispatch counting, and the indirect jumps.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitives import create_dup, create_zbranch
from zt.sim import Z80

JP_IX = bytes([0xDD, 0xE9])
JP_HL = bytes([0xE9])


@pytest.fixture
def m():
    return Z80()


def _at(m, addr, *opcode_bytes):
    m.load(addr, bytes(opcode_bytes))
    m.pc = addr


class TestLinkedDispatch:

    def test_linked_dispatch_emits_jp_ix(self):
        a = Asm(0x8000, linked=True)
        a.dispatch()
        assert bytes(a.code) == JP_IX, \
            "linked dispatch should return through the IX link register"

    @pytest.mark.parametrize("flags", [
        {"inline_next": True},
        {"inline_next": False},
        {"native": True},
    ], ids=["inline-next", "jp-next", "native-ret"])
    def test_linked_dispatch_wins_over_other_modes(self, flags):
        a = Asm(0x8000, linked=True, **flags)
        a.dispatch()
        assert bytes(a.code) == JP_IX, \
            f"linked should take priority over {flags}"

    def test_unlinked_dispatch_is_unchanged(self):
        a = Asm(0x8000, inline_next=False)
        a.dispatch()
        assert a.code[0] == 0xC3, \
            "default non-inline dispatch should still be JP NEXT"

    def test_linked_primitive_ends_with_jp_ix(self):
        a = Asm(0x8000, linked=True)
        create_dup(a)
        assert bytes(a.code) == bytes([0xE5]) + JP_IX, \
            "linked DUP should be PUSH HL followed by JP (IX)"


class TestDispatchCount:

    def test_fresh_asm_has_no_dispatches(self):
        assert Asm(0x8000).dispatch_count == 0, \
            "a fresh Asm should report zero dispatches"

    @pytest.mark.parametrize("creator,expected", [
        (create_dup, 1),
        (create_zbranch, 2),
    ], ids=["dup", "0branch"])
    def test_dispatch_count_tracks_exit_points(self, creator, expected):
        a = Asm(0x8000, linked=True)
        creator(a)
        assert a.dispatch_count == expected, \
            f"{creator.__name__} should dispatch from {expected} exit point(s)"


class TestIndirectJumpEncoding:

    @pytest.mark.parametrize("mnemonic,encoding", [
        ("jp_hl", JP_HL),
        ("jp_ix", JP_IX),
    ])
    def test_indirect_jump_encodes(self, mnemonic, encoding):
        a = Asm(0x8000)
        getattr(a, mnemonic)()
        assert bytes(a.code) == encoding, \
            f"{mnemonic} should assemble to {encoding.hex()}"


class TestIndirectJumpExecution:

    def test_jp_hl_jumps_to_hl(self, m):
        _at(m, 0x8000, 0xE9)
        m.hl = 0x9000
        m._step()
        assert m.pc == 0x9000, "JP (HL) should load PC from HL"

    def test_jp_hl_costs_4_t_states(self, m):
        _at(m, 0x8000, 0xE9)
        m._step()
        assert m._t_states == 4, "JP (HL) should cost 4 T-states"

    def test_jp_ix_jumps_to_ix(self, m):
        _at(m, 0x8000, 0xDD, 0xE9)
        m.ix = 0x9000
        m._step()
        assert m.pc == 0x9000, "JP (IX) should load PC from IX"

    def test_jp_ix_costs_8_t_states(self, m):
        _at(m, 0x8000, 0xDD, 0xE9)
        m._step()
        assert m._t_states == 8, "JP (IX) should cost 8 T-states"

    def test_jp_ix_leaves_ix_untouched(self, m):
        _at(m, 0x8000, 0xDD, 0xE9)
        m.ix = 0x9000
        m._step()
        assert m.ix == 0x9000, "JP (IX) should not modify IX"
