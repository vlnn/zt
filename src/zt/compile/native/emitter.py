"""
Emits one colon word as native Z80. Each IR cell becomes inline code, a `CALL` to another
colon, or a linked jump to an out-of-line primitive; the word's entry and return follow
the calling convention chosen for it.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import count

from zt.assemble.asm import Asm
from zt.compile.ir import (
    Branch, Cell, ColonRef, Label, Literal, NativeFetch, NativeOffsetFetch,
    NativeOffsetStore, NativeStore, PrimRef, StringRef, WordLiteral,
)
from zt.compile.native.analysis import Convention
from zt.compile.native.labels import (
    EXECUTE_LABEL,
    branch_label,
    colon_label,
    data_label,
    return_operand_label,
    return_slot_label,
    xt_wrapper_name,
)
from zt.compile.native.primitives import NativePrimitive, splice_inline
from zt.compile.native.resolve import PrimKind, Resolver

JP_OPCODE = 0xC3
LOOP_FRAME_BYTES = 4


@dataclass
class Requirements:
    out_of_line: dict[str, NativePrimitive] = field(default_factory=dict)
    data_refs: set[tuple[str, int]] = field(default_factory=set)
    execute: bool = False


class ColonEmitter:

    def __init__(self, asm: Asm, resolver: Resolver, requirements: Requirements) -> None:
        self.asm = asm
        self.resolver = resolver
        self.requirements = requirements
        self._return_sites = count()
        self._name = ""
        self._convention = Convention.FRAME
        self._exits_left = 0

    def emit(self, name: str, cells: Sequence[Cell], convention: Convention) -> None:
        self._name = name
        self._convention = convention
        self._exits_left = sum(self._is_exit(cell) for cell in cells)
        self.asm.label(colon_label(name))
        self._enter()
        for cell in cells:
            self._emit_cell(cell)

    def _is_exit(self, cell: Cell) -> bool:
        return isinstance(cell, PrimRef) and self.resolver.kind(cell.name) is PrimKind.EXIT

    # --- entry and return ---

    def _enter(self) -> None:
        a = self.asm
        if self._convention is Convention.LEAF:
            a.pop_ix()
        elif self._convention is Convention.STATIC:
            a.pop_bc()
            a.ld_ind_nn_bc(return_operand_label(self._name))
        else:
            a.pop_de()
            a.dec_iy()
            a.dec_iy()
            a.ld_iy_e(0)
            a.ld_iy_d(1)

    def _return(self) -> None:
        self._exits_left -= 1
        if self._convention is Convention.LEAF:
            self.asm.jp_ix()
        elif self._convention is Convention.STATIC:
            self._return_through_slot()
        else:
            self._return_through_frame()

    def _return_through_slot(self) -> None:
        a = self.asm
        if self._exits_left > 0:
            a.jp(return_slot_label(self._name))
            return
        a.label(return_slot_label(self._name))
        a.byte(JP_OPCODE)
        a.label(return_operand_label(self._name))
        a.word(0)

    def _return_through_frame(self) -> None:
        a = self.asm
        a.ld_e_iy(0)
        a.ld_d_iy(1)
        a.inc_iy()
        a.inc_iy()
        a.push_de()
        a.ret()

    # --- cells ---

    def _emit_cell(self, cell: Cell) -> None:
        match cell:
            case Label(id=label_id):
                self.asm.label(branch_label(label_id))
            case Literal(value=value):
                self._push_literal(value)
            case WordLiteral(name=name):
                self._push_literal(self._xt_label(name))
            case StringRef(label=label):
                self.asm.ld_hl_nn(label)
            case ColonRef(name=name):
                self.asm.call(colon_label(name))
            case Branch(kind=kind, target=target):
                self._emit_branch(kind, branch_label(target.id))
            case NativeFetch():
                self._emit_absolute_fetch(cell)
            case NativeStore():
                self._emit_absolute_store(cell)
            case NativeOffsetFetch():
                self._emit_offset_fetch(cell)
            case NativeOffsetStore():
                self._emit_offset_store(cell)
            case PrimRef(name=name):
                self._emit_prim(name)
            case _:
                raise TypeError(f"unknown cell type: {type(cell).__name__}")

    def _push_literal(self, value: int | str) -> None:
        self.asm.push_hl()
        self.asm.ld_hl_nn(value)

    def _xt_label(self, name: str) -> str:
        word = self.resolver.word(name)
        if word is not None and word.kind == "colon":
            return colon_label(name)
        return colon_label(xt_wrapper_name(name))

    # --- primitives and data words ---

    def _emit_prim(self, name: str) -> None:
        kind = self.resolver.kind(name)
        handler = {
            PrimKind.VARIABLE: self._push_variable,
            PrimKind.CONSTANT: self._push_constant,
            PrimKind.STRING_PUSH: self._push_for_string,
            PrimKind.EXIT: self._return_from,
            PrimKind.HALT: self._halt,
            PrimKind.EXECUTE: self._execute,
            PrimKind.INLINE: self._inline,
            PrimKind.OUT_OF_LINE: self._call_out_of_line,
        }[kind]
        handler(name)

    def _push_variable(self, name: str) -> None:
        word = self.resolver.word(name)
        if word.bank is not None:
            self._push_literal(word.data_address)
            return
        self.requirements.data_refs.add((word.name, 0))
        self._push_literal(data_label(word.name))

    def _push_constant(self, name: str) -> None:
        self._push_literal(self.resolver.word(name).value & 0xFFFF)

    def _push_for_string(self, name: str) -> None:
        self.asm.push_hl()

    def _return_from(self, name: str) -> None:
        self._return()

    def _halt(self, name: str) -> None:
        self.asm.halt()

    def _execute(self, name: str) -> None:
        self.requirements.execute = True
        self.asm.ex_de_hl()
        self.asm.pop_hl()
        self.asm.call(EXECUTE_LABEL)

    def _inline(self, name: str) -> None:
        splice_inline(self.resolver.primitive(name), self.asm)

    def _call_out_of_line(self, name: str) -> None:
        prim = self.resolver.primitive(name)
        self.requirements.out_of_line[prim.label] = prim
        return_site = f"__link__{next(self._return_sites)}"
        self.asm.ld_ix_nn(return_site)
        self.asm.jp(prim.label)
        self.asm.label(return_site)

    # --- control flow ---

    def _emit_branch(self, kind: str, target: str) -> None:
        handler = {
            "branch": self.asm.jp,
            "0branch": self._branch_if_zero,
            "(loop)": self._loop,
            "(+loop)": self._plus_loop,
        }.get(kind)
        if handler is None:
            raise NotImplementedError(f"branch kind {kind!r} has no native code generator")
        handler(target)

    def _branch_if_zero(self, target: str) -> None:
        a = self.asm
        a.ld_a_h()
        a.or_l()
        a.pop_hl()
        a.jp_z(target)

    def _loop(self, target: str) -> None:
        a = self.asm
        a.push_hl()
        a.ld_e_iy(0)
        a.ld_d_iy(1)
        a.inc_de()
        a.ld_iy_e(0)
        a.ld_iy_d(1)
        a.ld_l_iy(2)
        a.ld_h_iy(3)
        a.or_a()
        a.sbc_hl_de()
        a.pop_hl()
        a.jp_nz(target)
        self._drop_loop_frame()

    def _plus_loop(self, target: str) -> None:
        a = self.asm
        a.ld_e_iy(0)
        a.ld_d_iy(1)
        a.add_hl_de()
        a.ld_iy_l(0)
        a.ld_iy_h(1)
        a.push_hl()
        a.ld_l_iy(2)
        a.ld_h_iy(3)
        a.ex_de_hl()
        a.or_a()
        a.sbc_hl_de()
        a.ex_sp_hl()
        a.or_a()
        a.sbc_hl_de()
        a.pop_de()
        a.ld_a_h()
        a.xor_d()
        a.pop_hl()
        a.jp_p(target)
        self._drop_loop_frame()

    def _drop_loop_frame(self) -> None:
        for _ in range(LOOP_FRAME_BYTES):
            self.asm.inc_iy()

    # --- fused memory access ---

    def _absolute_label(self, cell: NativeFetch | NativeStore) -> str:
        self.requirements.data_refs.add((cell.target, cell.offset))
        return data_label(cell.target, cell.offset)

    def _emit_absolute_fetch(self, cell: NativeFetch) -> None:
        a = self.asm
        a.push_hl()
        if cell.width == "cell":
            a.ld_hl_ind_nn(self._absolute_label(cell))
            return
        a.ld_a_ind_nn(self._absolute_label(cell))
        a.ld_l_a()
        a.ld_h_n(0)

    def _emit_absolute_store(self, cell: NativeStore) -> None:
        a = self.asm
        if cell.width == "cell":
            a.ld_ind_nn_hl(self._absolute_label(cell))
        else:
            a.ld_a_l()
            a.ld_ind_nn_a(self._absolute_label(cell))
        a.pop_hl()

    def _add_offset(self, offset: int) -> None:
        self.asm.ld_de_nn(offset)
        self.asm.add_hl_de()

    def _emit_offset_fetch(self, cell: NativeOffsetFetch) -> None:
        a = self.asm
        self._add_offset(cell.offset)
        if cell.width == "cell":
            a.ld_e_ind_hl()
            a.inc_hl()
            a.ld_d_ind_hl()
            a.ex_de_hl()
            return
        a.ld_l_ind_hl()
        a.ld_h_n(0)

    def _emit_offset_store(self, cell: NativeOffsetStore) -> None:
        a = self.asm
        self._add_offset(cell.offset)
        a.pop_de()
        a.ld_ind_hl_e()
        if cell.width == "cell":
            a.inc_hl()
            a.ld_ind_hl_d()
        a.pop_hl()
