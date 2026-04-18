import pytest

from zt.asm import Asm
from zt.code_emitter import CodeEmitter
from zt.compiler import Word
from zt.ir import Branch, ColonRef, Label, Literal, PrimRef
from zt.tokenizer import Token


def _tok(line: int = 1, col: int = 1) -> Token:
    return Token(value="x", kind="word", line=line, col=col, source="<test>")


def _asm() -> Asm:
    return Asm(0x8000, inline_next=False)


def _words_with(entries: dict[str, int]) -> dict[str, Word]:
    return {
        name: Word(name=name, address=addr, kind="prim")
        for name, addr in entries.items()
    }


@pytest.fixture
def asm() -> Asm:
    return _asm()


@pytest.fixture
def words() -> dict[str, Word]:
    return _words_with({
        "lit": 0x1000,
        "branch": 0x1010,
        "0branch": 0x1020,
        "dup": 0x1030,
    })


@pytest.fixture
def emitter(asm: Asm, words: dict[str, Word]) -> CodeEmitter:
    return CodeEmitter(asm=asm, words=words, origin=0x8000)


class TestCellEmission:

    def test_emit_cell_writes_two_bytes_to_asm(self, emitter, asm):
        emitter.emit_cell(0x1234, _tok())
        assert bytes(asm.code) == bytes([0x34, 0x12]), (
            "emit_cell should write the 16-bit value as two little-endian bytes"
        )

    def test_emit_cell_records_source_entry(self, emitter):
        emitter.emit_cell(0x1234, _tok(line=5, col=7))
        assert len(emitter.source_map) == 1, (
            "emit_cell should append one SourceEntry per cell emitted"
        )
        assert emitter.source_map[0].line == 5, (
            "source entry should carry the token's line"
        )


class TestBodyCapture:

    def test_emit_word_ref_appends_prim(self, emitter, words):
        emitter.begin_body()
        emitter.emit_word_ref(words["dup"], _tok())
        body = emitter.end_body()
        assert body == [PrimRef("dup")], (
            "emit_word_ref for a primitive should append a PrimRef"
        )

    def test_emit_word_ref_appends_colon(self, emitter):
        user = Word(name="my-word", address=0x9000, kind="colon")
        emitter.begin_body()
        emitter.emit_word_ref(user, _tok())
        body = emitter.end_body()
        assert body == [ColonRef("my-word")], (
            "emit_word_ref for a colon word should append a ColonRef"
        )

    def test_compile_literal_appends_literal_cell(self, emitter):
        emitter.begin_body()
        emitter.compile_literal(42, _tok())
        body = emitter.end_body()
        assert body == [Literal(42)], "compile_literal should append one Literal cell"

    def test_literal_masks_to_16_bits(self, emitter):
        emitter.begin_body()
        emitter.compile_literal(-1, _tok())
        body = emitter.end_body()
        assert body == [Literal(0xFFFF)], (
            "compile_literal should mask values to 16 bits (−1 → 0xFFFF)"
        )

    def test_no_ir_appended_outside_body(self, emitter, words):
        emitter.emit_word_ref(words["dup"], _tok())
        assert emitter.current_body() is None, (
            "outside begin_body/end_body, there should be no active body to append to"
        )


class TestLabelAllocation:

    def test_first_label_is_zero(self, emitter):
        assert emitter.allocate_label() == 0, "first allocated label id should be 0"

    def test_subsequent_labels_are_sequential(self, emitter):
        ids = [emitter.allocate_label() for _ in range(4)]
        assert ids == [0, 1, 2, 3], "label ids should be sequential"


class TestBranchPlaceholder:

    def test_zbranch_placeholder_emits_0branch_plus_zero(self, emitter, asm):
        offset = emitter.compile_zbranch_placeholder(_tok())
        assert offset == 2, (
            "placeholder offset should point at the target cell (just after 0branch)"
        )
        assert bytes(asm.code[:2]) == bytes([0x20, 0x10]), (
            "first two bytes should be the 0branch primitive address"
        )
        assert bytes(asm.code[2:4]) == bytes([0x00, 0x00]), (
            "next two bytes should be a zero placeholder target"
        )

    def test_branch_placeholder_emits_branch_plus_zero(self, emitter, asm):
        emitter.compile_branch_placeholder(_tok())
        assert bytes(asm.code[:2]) == bytes([0x10, 0x10]), (
            "first two bytes should be the branch primitive address"
        )

    def test_placeholder_appends_branch_cell(self, emitter):
        emitter.begin_body()
        emitter.compile_branch_placeholder(_tok())
        body = emitter.end_body()
        branches = [c for c in body if isinstance(c, Branch)]
        assert len(branches) == 1 and branches[0].kind == "branch", (
            "compile_branch_placeholder should append one Branch cell with kind 'branch'"
        )


class TestPatchPlaceholder:

    def test_patch_writes_target_bytes(self, emitter, asm):
        offset = emitter.compile_branch_placeholder(_tok())
        emitter.patch_placeholder(offset, 0x8500)
        assert bytes(asm.code[offset:offset + 2]) == bytes([0x00, 0x85]), (
            "patch should write the target as two little-endian bytes at the placeholder offset"
        )

    def test_patch_appends_label_at_current_position(self, emitter):
        emitter.begin_body()
        offset = emitter.compile_branch_placeholder(_tok())
        emitter.patch_placeholder(offset, 0x8500)
        body = emitter.end_body()
        labels = [c for c in body if isinstance(c, Label)]
        assert len(labels) == 1, (
            "patch should append exactly one Label cell (the branch target)"
        )
        branches = [c for c in body if isinstance(c, Branch)]
        assert branches[0].target == labels[0], (
            "the Branch's target should match the appended Label"
        )


class TestBufferedEmission:

    def test_begin_buffered_does_not_write_to_outer(self, emitter, asm):
        asm.word(0xABCD)
        emitter.begin_buffered()
        emitter.emit_cell(0x1234, _tok())
        emitter.emit_cell(0x5678, _tok())
        assert bytes(asm.code) == bytes([0xCD, 0xAB]), (
            "begin_buffered should redirect writes away from the outer asm"
        )

    def test_commit_appends_buffered_bytes_to_outer(self, emitter, asm):
        asm.word(0xABCD)
        emitter.begin_buffered()
        emitter.emit_cell(0x1234, _tok())
        emitter.commit_buffered()
        assert bytes(asm.code) == bytes([0xCD, 0xAB, 0x34, 0x12]), (
            "commit_buffered should append buffered bytes to the outer asm"
        )

    def test_discard_drops_buffered_bytes(self, emitter, asm):
        asm.word(0xABCD)
        emitter.begin_buffered()
        emitter.emit_cell(0x1234, _tok())
        emitter.discard_buffered()
        assert bytes(asm.code) == bytes([0xCD, 0xAB]), (
            "discard_buffered should leave the outer asm unchanged"
        )

    def test_commit_translates_fixups_to_outer_offsets(self, emitter, asm):
        asm.word(0xABCD)
        emitter.begin_buffered()
        emitter.emit_cell("some_label", _tok())
        emitter.commit_buffered()
        fixup_offsets = [off for off, _ in asm.fixups]
        assert 2 in fixup_offsets, (
            "commit_buffered should translate buffered fixup offsets into outer-asm offsets"
        )
