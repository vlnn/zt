from __future__ import annotations

from typing import Any

from zt.asm import Asm
from zt.debug import SourceEntry
from zt.ir import Branch, Cell, ColonRef, Label, Literal, PrimRef
from zt.tokenizer import Token


class CodeEmitter:

    def __init__(self, asm: Asm, words: dict[str, Any], origin: int) -> None:
        self.asm: Asm = asm
        self.words: dict[str, Any] = words
        self.origin: int = origin
        self.source_map: list[SourceEntry] = []
        self._current_body: list[Cell] | None = None
        self._label_counter: int = 0
        self._placeholder_labels: dict[int, int] = {}

    # --- body lifecycle ---

    def begin_body(self) -> None:
        self._current_body = []

    def end_body(self) -> list[Cell]:
        body = self._current_body or []
        self._current_body = None
        return body

    def current_body(self) -> list[Cell] | None:
        return self._current_body

    # --- low-level emission ---

    def emit_cell(self, value: int | str, tok: Token) -> None:
        self.source_map.append(
            SourceEntry(self.asm.here, tok.source, tok.line, tok.col)
        )
        self.asm.word(value)

    def append_ir(self, cell: Cell) -> None:
        if self._current_body is not None:
            self._current_body.append(cell)

    # --- label allocation ---

    def allocate_label(self) -> int:
        label_id = self._label_counter
        self._label_counter += 1
        return label_id

    # --- structured emission ---

    def compile_literal(self, value: int, tok: Token) -> None:
        masked = value & 0xFFFF
        lit_addr = self.words["lit"].address
        self.emit_cell(lit_addr, tok)
        self.emit_cell(masked, tok)
        self.append_ir(Literal(masked))

    def emit_word_ref(self, word: Any, tok: Token) -> None:
        self.emit_cell(word.address, tok)
        if word.kind == "colon":
            self.append_ir(ColonRef(word.name))
        else:
            self.append_ir(PrimRef(word.name))

    def emit_label_here(self, label_id: int) -> None:
        self.append_ir(Label(id=label_id))

    # --- branches ---

    def compile_zbranch_placeholder(self, tok: Token) -> int:
        return self._compile_branch_with_placeholder("0branch", tok)

    def compile_branch_placeholder(self, tok: Token) -> int:
        return self._compile_branch_with_placeholder("branch", tok)

    def compile_branch_to_label(self, kind: str, target_addr: int,
                                target_label_id: int, tok: Token) -> None:
        self._emit_branch_cell(kind, target_label_id, tok)
        self.emit_cell(target_addr, tok)

    def patch_placeholder(self, offset: int, target: int) -> None:
        self.asm.code[offset] = target & 0xFF
        self.asm.code[offset + 1] = (target >> 8) & 0xFF
        label_id = self._placeholder_labels.pop(offset, None)
        if label_id is not None:
            self.append_ir(Label(id=label_id))

    # --- rewind (for inlining) ---

    def rewind_to(self, address: int) -> None:
        code_offset = address - self.origin
        del self.asm.code[code_offset:]
        self._drop_fixups_after(code_offset)
        self._drop_source_entries_after(address)

    # --- internals ---

    def _compile_branch_with_placeholder(self, kind: str, tok: Token) -> int:
        label_id = self.allocate_label()
        self._emit_branch_cell(kind, label_id, tok)
        offset = len(self.asm.code)
        self._placeholder_labels[offset] = label_id
        self.emit_cell(0, tok)
        return offset

    def _emit_branch_cell(self, kind: str, target_label_id: int, tok: Token) -> None:
        self.emit_cell(self.words[kind].address, tok)
        self.append_ir(Branch(kind=kind, target=Label(id=target_label_id)))

    def _drop_fixups_after(self, code_offset: int) -> None:
        self.asm.fixups = [
            f for f in self.asm.fixups if _fixup_offset(f) < code_offset
        ]
        rel = getattr(self.asm, "rel_fixups", None)
        if rel is not None:
            self.asm.rel_fixups = [
                f for f in rel if _fixup_offset(f) < code_offset
            ]

    def _drop_source_entries_after(self, address: int) -> None:
        self.source_map = [
            e for e in self.source_map if _source_entry_addr(e) < address
        ]


def _fixup_offset(fixup: Any) -> int:
    if hasattr(fixup, "offset"):
        return fixup.offset
    return fixup[0]


def _source_entry_addr(entry: Any) -> int:
    if hasattr(entry, "address"):
        return entry.address
    return entry[0]
