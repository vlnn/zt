"""
`CodeEmitter`: turns tokens and IR cells into Z80 bytes during compilation, and tracks the in-flight colon body, source map entries and branch-label placeholders.
"""
from __future__ import annotations

from typing import Any

from zt.assemble.asm import Asm
from zt.compile.source import SourceEntry
from zt.compile.ir import Branch, Cell, ColonRef, Label, Literal, PrimRef, WordLiteral
from zt.compile.tokenizer import Token


class CodeEmitter:

    def __init__(self, asm: Asm, words: dict[str, Any], origin: int) -> None:
        self.asm: Asm = asm
        self.words: dict[str, Any] = words
        self.origin: int = origin
        self.source_map: list[SourceEntry] = []
        self._current_body: list[Cell] | None = None
        self._label_counter: int = 0
        self._placeholder_labels: dict[int, int] = {}
        self._outer_asm: Asm | None = None

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

    def compile_word_literal(self, word: Any, tok: Token) -> None:
        lit_addr = self.words["lit"].address
        self.emit_cell(lit_addr, tok)
        self.emit_cell(word.address, tok)
        self.append_ir(WordLiteral(word.name))

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

    # --- buffered emission for colon bodies ---

    def begin_buffered(self) -> None:
        outer = self.asm
        buffered = Asm(origin=outer.here, inline_next=outer.inline_next)
        self._outer_asm = outer
        self.asm = buffered

    def commit_buffered(self) -> None:
        buffered = self.asm
        outer = self._outer_asm
        base_offset = len(outer.code)
        outer.code.extend(buffered.code)
        for offset, name in buffered.fixups:
            outer.fixups.append((base_offset + offset, name))
        for offset, name in buffered.rel_fixups:
            outer.rel_fixups.append((base_offset + offset, name))
        self.asm = outer
        self._outer_asm = None

    def discard_buffered(self) -> None:
        self.asm = self._outer_asm
        self._outer_asm = None

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

    # --- native control-flow emission ---

    def compile_native_zbranch_placeholder(self, tok: Token) -> int:
        """Emit native forward conditional branch matching the threaded ZBRANCH
        primitive's flow: test the flag in HL (current TOS), pop the new TOS
        from the data stack, then jump to a forward placeholder when the flag
        was zero. Returns the operand offset of the JP Z instruction so it can
        be resolved later by `patch_placeholder`."""
        label_id = self.allocate_label()
        asm = self.asm
        self.source_map.append(
            SourceEntry(asm.here, tok.source, tok.line, tok.col)
        )
        asm.ld_a_h()
        asm.or_l()
        asm.pop_hl()
        asm.code.append(0xCA)
        offset = len(asm.code)
        asm.code.extend([0x00, 0x00])
        self._placeholder_labels[offset] = label_id
        self.append_ir(Branch(kind="0branch", target=Label(id=label_id)))
        return offset

    def compile_native_branch_placeholder(self, tok: Token) -> int:
        """Emit `jp 0` as a native forward unconditional branch. Returns the
        operand offset for later patching."""
        label_id = self.allocate_label()
        asm = self.asm
        self.source_map.append(
            SourceEntry(asm.here, tok.source, tok.line, tok.col)
        )
        asm.code.append(0xC3)
        offset = len(asm.code)
        asm.code.extend([0x00, 0x00])
        self._placeholder_labels[offset] = label_id
        self.append_ir(Branch(kind="branch", target=Label(id=label_id)))
        return offset

    def compile_native_branch_to_label(
        self, kind: str, target_addr: int, target_label_id: int, tok: Token,
    ) -> None:
        """Emit a native backward branch to a known address."""
        asm = self.asm
        self.source_map.append(
            SourceEntry(asm.here, tok.source, tok.line, tok.col)
        )
        self.append_ir(Branch(kind=kind, target=Label(id=target_label_id)))
        if kind == "branch":
            asm.jp(target_addr)
        elif kind == "0branch":
            asm.ld_a_h()
            asm.or_l()
            asm.pop_hl()
            asm.jp_z(target_addr)
        elif kind == "(loop)":
            self._emit_native_loop_body(target_addr)
        elif kind == "(+loop)":
            self._emit_native_plus_loop_body(target_addr)
        else:
            raise ValueError(
                f"native branch kind '{kind}' not supported; expected "
                f"'branch', '0branch', '(loop)', or '(+loop)'"
            )

    def _emit_native_loop_body(self, body_addr: int) -> None:
        """Emit native LOOP: increment index, compare against limit, JP back
        to body if not equal, fall through with frame drop if equal.
        Mirrors the threaded `(loop)` runtime minus the IX-cell-reading dance."""
        asm = self.asm
        asm.push_hl()
        asm.ld_e_iy(0)
        asm.ld_d_iy(1)
        asm.inc_de()
        asm.ld_iy_e(0)
        asm.ld_iy_d(1)
        asm.ld_l_iy(2)
        asm.ld_h_iy(3)
        asm.or_a()
        asm.sbc_hl_de()
        asm.pop_hl()
        asm.code.append(0x28)
        asm.code.append(0x03)
        asm.jp(body_addr)
        asm.inc_iy()
        asm.inc_iy()
        asm.inc_iy()
        asm.inc_iy()

    def _emit_native_plus_loop_body(self, body_addr: int) -> None:
        """Emit native +LOOP: step + index, sign-XOR check for crossing the
        limit, JP back to body if not crossed, fall through with frame drop
        otherwise. Mirrors the threaded `(+loop)` runtime minus the IX dance."""
        asm = self.asm
        asm.ld_e_iy(0)
        asm.ld_d_iy(1)
        asm.add_hl_de()
        asm.ld_iy_l(0)
        asm.ld_iy_h(1)
        asm.push_hl()
        asm.ld_l_iy(2)
        asm.ld_h_iy(3)
        asm.ex_de_hl()
        asm.or_a()
        asm.sbc_hl_de()
        asm.ex_sp_hl()
        asm.or_a()
        asm.sbc_hl_de()
        asm.pop_de()
        asm.ld_a_h()
        asm.xor_d()
        asm.pop_hl()
        # Target of JP M lands right after the JP body_addr below — i.e. at
        # the inc_iy frame-drop sequence. JP M is 3 bytes, JP body_addr is
        # 3 bytes, so the target is current pos + 6.
        done_addr = asm.origin + len(asm.code) + 6
        asm.jp_m(done_addr)
        asm.jp(body_addr)
        asm.inc_iy()
        asm.inc_iy()
        asm.inc_iy()
        asm.inc_iy()
