"""
Tests for the native primitive table: which primitive bodies get inlined at their call
sites, which are called out of line through the IX link, and how `:::` words are relinked.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitives import PRIMITIVES
from zt.compile.compiler import Compiler
from zt.compile.native.primitives import (
    INLINE_BYTE_LIMIT,
    JP_IX,
    native_primitive_table,
    splice_inline,
)


@pytest.fixture(scope="module")
def table():
    return native_primitive_table(PRIMITIVES, [])


def _asm_word_table(source: str, **compiler_flags):
    c = Compiler(**compiler_flags)
    c.compile_source(source)
    return c, native_primitive_table(PRIMITIVES, c._asm_word_blobs)


class TestInlineDecision:

    @pytest.mark.parametrize("name", [
        "dup", "drop", "swap", "+", "-", "@", "!", "c@", "c!", "1+", "2*",
        "and", "invert", "=", "0=", "<", ">", "abs", "min", "max", "i", "j",
        ">r", "r>", "r@", "+!",
    ])
    def test_small_primitive_is_inlined(self, table, name):
        assert table[name].inlines, \
            f"{name!r} fits in {INLINE_BYTE_LIMIT} bytes and should be inlined"

    @pytest.mark.parametrize("name", ["*", "u/mod", "emit", "type", "key", "beep"])
    def test_large_primitive_is_called_out_of_line(self, table, name):
        assert not table[name].inlines, \
            f"{name!r} is too large to inline and should be called through IX"

    def test_do_runtime_is_inlined_despite_its_size(self, table):
        assert table["(do)"].inlines, \
            "(do) should always be inlined so loops do not break leaf words"

    @pytest.mark.parametrize("name", ["key-state", "emit"])
    def test_primitive_with_external_labels_is_not_inlined(self, table, name):
        assert not table[name].inlines, \
            f"{name!r} refers to code outside its own body and cannot be relocated"

    @pytest.mark.parametrize("name", [
        "lit", "branch", "0branch", "(loop)", "(+loop)", "exit", "(@abs)", "(!off)",
    ])
    def test_threading_primitive_is_flagged_as_using_ix(self, table, name):
        assert table[name].uses_ix, \
            f"{name!r} walks the threaded IP and should be flagged as using IX"

    @pytest.mark.parametrize("name", ["dup", "*", "emit", "(do)", "i"])
    def test_ordinary_primitive_does_not_use_ix(self, table, name):
        assert not table[name].uses_ix, \
            f"{name!r} should leave IX free for the link register"


class TestOutOfLineBlob:

    @pytest.mark.parametrize("name", ["*", "u/mod", "emit"])
    def test_out_of_line_blob_returns_through_ix(self, table, name):
        assert JP_IX in table[name].blob.code, \
            f"{name!r} should end its out-of-line body with JP (IX)"

    def test_aliases_share_one_blob(self, table):
        assert table["dup"].blob is table["DUP".lower()].blob, \
            "upper- and lower-case labels should resolve to the same blob"

    def test_internal_labels_are_addressable(self, table):
        assert "_emit_cursor_row" in table, \
            "internal labels should be reachable so dependencies can be resolved"


class TestSpliceInline:

    @pytest.mark.parametrize("name,expected", [
        ("dup", bytes([0xE5])),
        ("drop", bytes([0xE1])),
        ("+", bytes([0xD1, 0x19])),
    ])
    def test_splice_emits_body_without_dispatch(self, table, name, expected):
        a = Asm(0x8000)
        splice_inline(table[name], a)
        assert bytes(a.code) == expected, \
            f"inlined {name!r} should be its bare body with no dispatch tail"

    def test_splice_resolves_internal_jump_at_splice_address(self, table):
        a = Asm(0x9000)
        a.nop()
        splice_inline(table["abs"], a)
        jp_z_operand = a.code[4] | (a.code[5] << 8)
        assert jp_z_operand == 0x9000 + len(a.code), \
            "ABS's internal forward jump should land right after the spliced body"

    def test_splice_twice_does_not_clash_on_labels(self, table):
        a = Asm(0x8000)
        splice_inline(table["abs"], a)
        splice_inline(table["abs"], a)
        assert len(a.code) == 2 * table["abs"].inline_size, \
            "inlining the same primitive twice should emit two independent copies"

    def test_splice_refuses_non_inlinable_primitive(self, table):
        with pytest.raises(ValueError, match="cannot be inlined"):
            splice_inline(table["emit"], Asm(0x8000))


class TestAsmWords:

    SOURCE = "::: double  add_hl_hl ;"

    @pytest.mark.parametrize("flags,tail", [
        ({"inline_next": True}, 12),
        ({"inline_next": False}, 3),
    ], ids=["inline-next", "jp-next"])
    def test_asm_word_blob_records_its_dispatch_tail(self, flags, tail):
        c, _ = _asm_word_table(self.SOURCE, **flags)
        assert c._asm_word_blobs[0].dispatch_tail == tail, \
            f"::: blob should record a {tail}-byte dispatch tail"

    @pytest.mark.parametrize("flags", [
        {"inline_next": True}, {"inline_next": False},
    ], ids=["inline-next", "jp-next"])
    def test_asm_word_is_relinked_through_ix(self, flags):
        _, table = _asm_word_table(self.SOURCE, **flags)
        assert table["double"].blob.code == bytes([0x29]) + JP_IX, \
            "::: word should keep its body and swap the NEXT tail for JP (IX)"

    def test_relinked_asm_word_drops_next_dependency(self):
        _, table = _asm_word_table(self.SOURCE, inline_next=False)
        assert "NEXT" not in table["double"].blob.external_deps, \
            "relinked ::: word should no longer depend on NEXT"

    def test_asm_word_is_called_out_of_line(self):
        _, table = _asm_word_table(self.SOURCE)
        assert not table["double"].inlines, \
            "::: words should be called out of line"

    def test_asm_word_using_ix_is_flagged(self):
        _, table = _asm_word_table("::: clobber  push_ix pop_ix ;")
        assert table["clobber"].uses_ix, \
            "a ::: word touching IX should be flagged so the backend can reject it"
