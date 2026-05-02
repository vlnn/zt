"""
Compiler pipeline: tokenise → parse immediates/directives → emit IR → resolve to a Z80 image. Also defines the `Word` record and top-level `compile_*` helpers used by tests and the CLI.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal as TypingLiteral

from zt.assemble.asm import Asm
from zt.compile.code_emitter import CodeEmitter
from zt.compile.control_stack import ControlStack, ControlStackError
from zt.compile.source import SourceEntry
from zt.compile.dictionary import Dictionary
from zt.compile.include_resolver import IncludeNotFound, IncludeResolver
from zt.assemble.inline_bodies import (
    InlineContext,
    emit_inline_plan,
    emit_native_primitive_body,
    plan_colon_inlining,
)
from zt.compile.ir import (
    Branch,
    Cell,
    ColonRef,
    Label,
    Literal,
    PrimRef,
    StringRef,
    WordLiteral,
    cell_size,
    resolve,
)
from zt.compile.peephole import (
    DEFAULT_RULES,
    PatternElement,
    PeepholeRule,
    find_match,
    max_pattern_length,
)
from zt.assemble.primitives import PRIMITIVES
from zt.compile.string_pool import StringPool
from zt.compile.token_stream import TokenStream
from zt.compile.tokenizer import Token, tokenize
from zt.compile.word_registry import (
    collected_directives,
    collected_immediates,
    collected_macros,
    directive,
    immediate,
    macro,
)


@dataclass
class Word:
    name: str
    address: int
    kind: TypingLiteral["prim", "colon", "variable", "constant"]
    immediate: bool = False
    compile_action: Callable | None = None
    body: list[Cell] = field(default_factory=list)
    inlined: bool = False
    source_file: str | None = None
    source_line: int | None = None
    data_address: int | None = None
    force_inline: bool = False
    bank: int | None = None


@dataclass(frozen=True)
class WordAddressRef:
    asm_addr: int
    target: str
    owner: str


class CompileError(Exception):
    def __init__(self, message: str, token: Token | None = None) -> None:
        self.token = token
        loc = ""
        if token:
            loc = f"{token.source}:{token.line}:{token.col}: "
        super().__init__(f"{loc}{message}")


DEFAULT_ORIGIN = 0x8000
DEFAULT_DATA_STACK_TOP = 0xFF00
DEFAULT_RETURN_STACK_TOP = 0xFE00


def _bundled_stdlib_dir() -> Path:
    import zt.stdlib
    return Path(zt.stdlib.__path__[0])


class Compiler:

    def __init__(
        self,
        origin: int = DEFAULT_ORIGIN,
        data_stack_top: int = DEFAULT_DATA_STACK_TOP,
        return_stack_top: int = DEFAULT_RETURN_STACK_TOP,
        include_dirs: list[Path] | None = None,
        optimize: bool = True,
        inline_next: bool = True,
        inline_primitives: bool = True,
        native_control_flow: bool = False,
    ):
        self.origin = origin
        self.data_stack_top = data_stack_top
        self.return_stack_top = return_stack_top
        self.include_resolver: IncludeResolver = IncludeResolver(
            include_dirs or [], bundled_stdlib_dir=_bundled_stdlib_dir(),
        )
        outer_asm = Asm(origin, inline_next=inline_next)
        self.words: Dictionary = Dictionary()
        self.state: TypingLiteral["interpret", "compile"] = "interpret"
        self.control_stack: ControlStack = ControlStack()
        self.current_word: str | None = None
        self._tokens: TokenStream = TokenStream([])
        self._host_stack: list[int] = []
        self._uses_word_address_data: bool = False
        self._pending_tick: tuple[str, int] | None = None
        self._tick_unsafe: bool = False
        self._word_address_refs: list[WordAddressRef] = []
        self._inside_asm_body: bool = False
        self._asm_word_blobs: list = []
        self.string_pool: StringPool = StringPool()
        self.emitter: CodeEmitter = CodeEmitter(
            asm=outer_asm, words=self.words, origin=origin,
        )
        self.warnings: list[str] = []
        self.optimize: bool = optimize
        self.inline_next: bool = inline_next
        self.inline_primitives: bool = inline_primitives
        self.native_control_flow: bool = native_control_flow
        self._primitives: list = list(PRIMITIVES)
        self._inline_context: InlineContext | None = None
        self._peephole_rules: tuple[PeepholeRule, ...] = DEFAULT_RULES
        self._main_asm: Asm = outer_asm
        self._bank_asms: dict[int, Asm] = {}
        self._active_bank: int | None = None
        self._register_primitives()
        self._register_directives()
        self._register_immediates()
        self._register_macros()

    @property
    def source_map(self) -> list[SourceEntry]:
        return self.emitter.source_map

    @property
    def asm(self) -> Asm:
        return self.emitter.asm

    @asm.setter
    def asm(self, value: Asm) -> None:
        self.emitter.asm = value

    def _register_primitives(self) -> None:
        from zt.assemble.primitive_blob import BlobRegistry, emit_blob
        self._blob_registry = BlobRegistry.from_creators(
            self._primitives, inline_next=self.inline_next,
        )
        for blob in self._blob_registry.blobs:
            emit_blob(self.asm, blob)
        self.words.register_primitives(self.asm)
        if self.inline_primitives:
            self._inline_context = InlineContext.build(self._primitives)
        self._creators_by_name: dict[str, Callable] = (
            self._blob_registry.forth_visible_creators()
        )

    def _register_directives(self) -> None:
        for name, action in collected_directives(type(self)):
            self.words.register(Word(
                name=name, address=0, kind="prim",
                immediate=True, compile_action=action.__get__(self, type(self)),
            ))

    def _register_immediates(self) -> None:
        for name, action in collected_immediates(type(self)):
            self.words.register(Word(
                name=name, address=0, kind="prim",
                immediate=True, compile_action=action.__get__(self, type(self)),
            ))

    def _register_macros(self) -> None:
        self._macros: set[str] = set()
        for name, action in collected_macros(type(self)):
            self.words.register(Word(
                name=name, address=0, kind="prim",
                immediate=True, compile_action=action.__get__(self, type(self)),
            ))
            self._macros.add(name)

    def _is_macro(self, name: str) -> bool:
        return name in self._macros

    def compile_source(self, text: str, source: str = "<input>") -> None:
        self._tokens = TokenStream(tokenize(text, source))
        while self._tokens.has_more():
            tok = self._tokens.next()
            self._compile_token(tok)
        if self.state == "compile":
            raise CompileError(
                f"unclosed colon definition '{self.current_word}'",
                self._tokens.last_token(),
            )

    def _compile_token(self, tok: Token) -> None:
        if self.state == "interpret":
            self._invalidate_pending_tick_unless_paired(tok)
            self._interpret_token(tok)
        else:
            self._compile_state_token(tok)

    def _invalidate_pending_tick_unless_paired(self, tok: Token) -> None:
        if self._pending_tick is None:
            return
        if tok.kind == "word" and tok.value in {",", "'"}:
            return
        self._tick_unsafe = True
        self._pending_tick = None

    def _interpret_token(self, tok: Token) -> None:
        if tok.kind == "word" and tok.value == ":":
            self._start_colon(tok, force_inline=False)
            return
        if tok.kind == "word" and tok.value == "::":
            self._start_colon(tok, force_inline=True)
            return
        if tok.kind == "word":
            word = self.words.get(tok.value)
            if word and word.immediate and word.compile_action:
                word.compile_action(self, tok)
                return
            raise CompileError(
                f"unexpected word '{tok.value}' in interpret state", tok
            )
        if tok.kind == "number":
            self._host_stack.append(parse_number(tok.value))
            return
        raise CompileError(f"unexpected token '{tok.value}'", tok)

    def _compile_state_token(self, tok: Token) -> None:
        if tok.kind == "word" and tok.value == ";":
            self._end_colon(tok)
            return
        if tok.kind == "word" and tok.value == ":":
            raise CompileError("nested colon definition", tok)
        if tok.kind == "word" and tok.value == "::":
            raise CompileError("nested colon definition", tok)
        if self.optimize and self._try_peephole(tok):
            return
        if tok.kind == "word":
            word = self.words.get(tok.value)
            if word is None:
                raise CompileError(f"unknown word '{tok.value}'", tok)
            if word.immediate and word.compile_action:
                word.compile_action(self, tok)
                return
            self._emit_word_ref(word, tok)
            return
        if tok.kind == "number":
            value = parse_number(tok.value)
            self._compile_literal(value, tok)
            return
        raise CompileError(f"unexpected token '{tok.value}'", tok)

    def _try_peephole(self, tok: Token) -> bool:
        elements = self._peephole_window(tok)
        rule = find_match(elements, self._peephole_rules)
        if rule is None:
            return False
        replacement = self.words.get(rule.replacement)
        if replacement is None:
            return False
        self._tokens.advance_by(len(rule.pattern) - 1)
        self._emit_word_ref(replacement, tok)
        return True

    def _peephole_window(self, first_tok: Token) -> list[PatternElement | None]:
        span = max_pattern_length(self._peephole_rules)
        if span <= 0:
            return []
        tail = self._tokens.lookahead(span - 1)
        return [self._token_element(t) for t in (first_tok, *tail)]

    def _token_element(self, tok: Token) -> PatternElement | None:
        if self._is_structural_token(tok) or self._is_immediate_token(tok):
            return None
        if tok.kind == "number":
            return parse_number(tok.value)
        if tok.kind == "word":
            return tok.value.lower()
        return None

    def _is_structural_token(self, tok: Token) -> bool:
        return tok.kind == "word" and tok.value in (";", ":", "::")

    def _is_immediate_token(self, tok: Token) -> bool:
        if tok.kind != "word":
            return False
        word = self.words.get(tok.value)
        return word is not None and word.immediate

    def _start_colon(self, tok: Token, force_inline: bool = False) -> None:
        if self.state == "compile":
            raise CompileError("nested colon definition", tok)
        if force_inline and self.native_control_flow:
            raise CompileError(
                ":: force-inline is not yet supported with native_control_flow",
                tok,
            )
        name_tok = self._next_token(tok)
        name = name_tok.value
        self._warn_if_redefining(name, tok, force_inline=force_inline)
        self.state = "compile"
        self.current_word = name
        self.emitter.begin_body()
        self.emitter.begin_buffered()
        addr = self.asm.here
        if not self.native_control_flow:
            self.asm.call("DOCOL")
        self.words[name] = Word(
            name=name, address=addr, kind="colon",
            force_inline=force_inline,
            source_file=tok.source, source_line=tok.line,
            bank=self._active_bank,
        )

    def _warn_if_redefining(
        self, name: str, tok: Token, *, force_inline: bool = False,
    ) -> None:
        warning = self.words.redefinition_warning(
            name, source_file=tok.source, source_line=tok.line,
            force_inline=force_inline,
        )
        if warning is not None:
            self.warnings.append(warning)

    def _reject_native_unsupported(self, construct: str, tok: Token) -> None:
        if self.native_control_flow:
            raise CompileError(
                f"{construct} is not yet supported in native_control_flow mode",
                tok,
            )

    def _end_colon(self, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError("; outside colon definition", tok)
        if self.control_stack:
            tag, _ = self.control_stack.peek()
            self.control_stack.clear()
            raise CompileError(
                f"unclosed {tag} in '{self.current_word}'", tok
            )
        if self.native_control_flow:
            # Native colons are emitted as straight-line code; no EXIT cell, no
            # RET. The native startup `JP`s to main, so main must end with HALT
            # (or any instruction sequence that doesn't need to return).
            self._append_ir(PrimRef("exit"))
        else:
            self._emit_word_ref(self.words["exit"], tok)
        word = self.words[self.current_word]
        word.body = self.emitter.end_body()
        self.state = "interpret"
        self.current_word = None
        if word.force_inline:
            self._force_inline_colon(word, tok)
        elif self.native_control_flow:
            self.emitter.commit_buffered()
        else:
            self._try_inline_colon(word)

    def _force_inline_colon(self, word: Word, tok: Token) -> None:
        self._reject_self_recursion(word, tok)
        reason = self._first_non_inlinable_cell(word.body)
        if reason is not None:
            raise CompileError(
                f":: word '{word.name}' cannot be inlined: {reason}", tok,
            )
        self.emitter.discard_buffered()
        self._emit_force_inline_body(word, tok)
        word.inlined = True

    def _emit_force_inline_body(self, word: Word, tok: Token) -> None:
        """Walk the word's IR cells and emit native bytes at the current asm
        position. Forward branches are placed via the emitter's placeholder
        helpers and patched once their target labels are reached. The body
        ends with a threaded NEXT dispatch so the spliced fragment returns
        control to the caller's threaded interpreter."""
        label_addrs: dict[int, int] = {}
        forward_fixups: list[tuple[int, int]] = []
        body = word.body
        if body and isinstance(body[-1], PrimRef) and body[-1].name == "exit":
            body = body[:-1]
        for cell in body:
            if isinstance(cell, Literal):
                self._emit_force_inline_literal(cell, tok)
            elif isinstance(cell, WordLiteral):
                self._emit_force_inline_word_literal(cell, tok)
            elif isinstance(cell, PrimRef):
                self._emit_force_inline_primitive(cell, tok)
            elif isinstance(cell, Label):
                label_addrs[cell.id] = self.asm.here
            elif isinstance(cell, Branch):
                self._emit_force_inline_branch(
                    cell, tok, label_addrs, forward_fixups,
                )
            else:
                raise CompileError(
                    f":: word '{word.name}' cannot be inlined: "
                    f"unsupported cell {type(cell).__name__}",
                    tok,
                )
        for offset, target_id in forward_fixups:
            target_addr = label_addrs.get(target_id)
            if target_addr is None:
                raise CompileError(
                    f":: word '{word.name}' has unresolved forward branch "
                    f"to label {target_id}",
                    tok,
                )
            self._patch_placeholder(offset, target_addr)
        self.asm.dispatch()

    def _emit_force_inline_literal(self, cell: Literal, tok: Token) -> None:
        self.emitter.source_map.append(
            SourceEntry(self.asm.here, tok.source, tok.line, tok.col)
        )
        self.asm.push_hl()
        self.asm.ld_hl_nn(cell.value & 0xFFFF)

    def _emit_force_inline_word_literal(self, cell: WordLiteral, tok: Token) -> None:
        target = self.words[cell.name]
        self.emitter.source_map.append(
            SourceEntry(self.asm.here, tok.source, tok.line, tok.col)
        )
        self.asm.push_hl()
        self.asm.ld_hl_nn(target.address & 0xFFFF)

    def _emit_force_inline_primitive(self, cell: PrimRef, tok: Token) -> None:
        self.emitter.source_map.append(
            SourceEntry(self.asm.here, tok.source, tok.line, tok.col)
        )
        name = cell.name.lower()
        if name == "halt":
            self.asm.halt()
            return
        creator = self._creators_by_name.get(name)
        if creator is None or not emit_native_primitive_body(creator, self.asm):
            raise CompileError(
                f":: cannot re-emit primitive '{cell.name}' at splice address",
                tok,
            )

    def _emit_force_inline_branch(
        self, cell: Branch, tok: Token,
        label_addrs: dict[int, int],
        forward_fixups: list[tuple[int, int]],
    ) -> None:
        if not isinstance(cell.target, Label):
            raise CompileError(
                f":: branch with non-label target is not supported", tok,
            )
        target_id = cell.target.id
        kind = cell.kind
        if target_id in label_addrs:
            self.emitter.compile_native_branch_to_label(
                kind, label_addrs[target_id], target_id, tok,
            )
            return
        if kind == "branch":
            offset = self.emitter.compile_native_branch_placeholder(tok)
        elif kind == "0branch":
            offset = self.emitter.compile_native_zbranch_placeholder(tok)
        else:
            raise CompileError(
                f":: forward branch kind '{kind}' is not supported", tok,
            )
        forward_fixups.append((offset, target_id))

    def _reject_self_recursion(self, word: Word, tok: Token) -> None:
        for cell in word.body:
            if isinstance(cell, ColonRef) and cell.name == word.name:
                raise CompileError(
                    f"recursive :: expansion in '{cell.name}'", tok,
                )

    def _first_non_inlinable_cell(self, body: list[Cell]) -> str | None:
        if not body:
            return "empty body (missing EXIT terminator)"
        if not (isinstance(body[-1], PrimRef) and body[-1].name == "exit"):
            return "missing EXIT terminator"
        for i, cell in enumerate(body[:-1]):
            if isinstance(cell, (Literal, WordLiteral, Label)):
                continue
            if isinstance(cell, PrimRef):
                name = cell.name.lower()
                if name == "halt":
                    continue
                if name not in self._creators_by_name:
                    return f"unknown primitive '{cell.name}' at position {i}"
                continue
            if isinstance(cell, Branch):
                continue
            if isinstance(cell, ColonRef):
                return (
                    f"calls colon word '{cell.name}' at position {i}; "
                    f"nested calls are not yet inlinable"
                )
            if isinstance(cell, StringRef):
                return f"string reference at position {i} is not inlinable"
            return f"unsupported cell {type(cell).__name__} at position {i}"
        return None

    def _try_inline_colon(self, word: Word) -> None:
        plan = self._inline_plan_for(word)
        if plan is None:
            self.emitter.commit_buffered()
            return
        self.emitter.discard_buffered()
        emit_inline_plan(self.asm, plan, self._inline_context)
        word.inlined = True

    def _inline_plan_for(self, word: Word):
        if self._inline_context is None:
            return None
        return plan_colon_inlining(word, self.words, self._inline_context)

    def _compile_literal(self, value: int, tok: Token) -> None:
        if self.native_control_flow:
            self._compile_literal_native(value, tok)
        else:
            self.emitter.compile_literal(value, tok)

    def _compile_literal_native(self, value: int, tok: Token) -> None:
        masked = value & 0xFFFF
        self.emitter.source_map.append(
            SourceEntry(self.asm.here, tok.source, tok.line, tok.col)
        )
        # TOS-in-HL convention: push old TOS first, then load new TOS into HL.
        self.asm.push_hl()
        self.asm.ld_hl_nn(masked)
        self._append_ir(Literal(masked))

    def _emit_cell(self, value: int | str, tok: Token) -> None:
        self.emitter.emit_cell(value, tok)

    def _append_ir(self, cell: Cell) -> None:
        self.emitter.append_ir(cell)

    def _allocate_label(self) -> int:
        return self.emitter.allocate_label()

    def _emit_word_ref(self, word: Word, tok: Token) -> None:
        if self.native_control_flow:
            self._emit_word_ref_native(word, tok)
        else:
            self.emitter.emit_word_ref(word, tok)

    def _emit_word_ref_native(self, word: Word, tok: Token) -> None:
        """Splice the primitive's body bytes at the current address. Re-emits
        each primitive against a temp Asm whose origin equals the splice
        address, so internal absolute jumps (e.g. the `jp_p` in `<` and `>`)
        resolve correctly."""
        if word.kind != "prim":
            raise CompileError(
                f"{word.kind} '{word.name}' is not yet supported in "
                f"native_control_flow mode (only primitives are emitted "
                f"natively in this phase)",
                tok,
            )
        name = word.name.lower()
        self.emitter.source_map.append(
            SourceEntry(self.asm.here, tok.source, tok.line, tok.col)
        )
        self._append_ir(PrimRef(word.name))
        if name == "halt":
            self.asm.halt()
            return
        creator = self._creators_by_name.get(name)
        if creator is None:
            raise CompileError(
                f"primitive '{word.name}' has no native re-emitter "
                f"(unknown to native_control_flow mode)",
                tok,
            )
        if not emit_native_primitive_body(creator, self.asm):
            raise CompileError(
                f"primitive '{word.name}' cannot be safely re-emitted "
                f"in native_control_flow mode",
                tok,
            )

    def _next_token(self, context_tok: Token) -> Token:
        if not self._tokens.has_more():
            raise CompileError("unexpected end of input", context_tok)
        return self._tokens.next()

    def _host_pop(self, tok: Token) -> int:
        if not self._host_stack:
            raise CompileError("host stack underflow", tok)
        return self._host_stack.pop()

    def _emit_pusher(self, value: int) -> int:
        code_addr = self.asm.here
        self.asm.push_hl()
        self.asm.ld_hl_nn(value & 0xFFFF)
        self.asm.jp("NEXT")
        return code_addr

    def _emit_variable_shim(self) -> tuple[int, int]:
        code_addr = self._main_asm.here
        self._main_asm.push_hl()
        self._main_asm.ld_hl_nn(0)
        fixup = len(self._main_asm.code) - 2
        self._main_asm.jp("NEXT")
        data_addr = self.asm.here
        self._main_asm.code[fixup] = data_addr & 0xFF
        self._main_asm.code[fixup + 1] = (data_addr >> 8) & 0xFF
        return code_addr, data_addr

    # --- directives ---

    @directive("variable")
    def _directive_variable(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        code_addr, data_addr = self._emit_variable_shim()
        self.asm.word(0)
        self.words[name_tok.value] = Word(
            name=name_tok.value, address=code_addr, kind="variable",
            data_address=data_addr,
            source_file=name_tok.source, source_line=name_tok.line,
            bank=self._active_bank,
        )

    @directive("constant")
    def _directive_constant(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        name_tok = self._next_token(tok)
        code_addr = self._emit_pusher(value)
        self.words[name_tok.value] = Word(
            name=name_tok.value, address=code_addr, kind="constant",
            source_file=name_tok.source, source_line=name_tok.line,
            bank=self._active_bank,
        )

    @directive("create")
    def _directive_create(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        code_addr, data_addr = self._emit_variable_shim()
        self.words[name_tok.value] = Word(
            name=name_tok.value, address=code_addr, kind="variable",
            data_address=data_addr,
            source_file=name_tok.source, source_line=name_tok.line,
            bank=self._active_bank,
        )

    @directive(":::")
    def _directive_asm_word(self, _compiler: Compiler, tok: Token) -> None:
        if self.state == "compile":
            raise CompileError("::: not allowed inside a colon definition", tok)
        name_tok = self._next_token(tok)
        code_addr = self.asm.here
        body_start = len(self.asm.code)
        fixup_count = len(self.asm.fixups)
        rel_fixup_count = len(self.asm.rel_fixups)
        self._asm_word_name = name_tok.value
        self._asm_fixup_snapshot = (fixup_count, rel_fixup_count)
        self._inside_asm_body = True
        try:
            self._assemble_asm_body(tok)
            self._verify_asm_labels_resolved(tok)
        finally:
            self._asm_word_name = None
            self._inside_asm_body = False
            self._pending_tick = None
        self.words[name_tok.value] = Word(
            name=name_tok.value, address=code_addr, kind="prim",
            source_file=name_tok.source, source_line=name_tok.line,
            bank=self._active_bank,
        )
        self._asm_word_blobs.append(self._snapshot_asm_blob(
            name_tok.value, code_addr, body_start,
            fixup_count, rel_fixup_count,
        ))

    def _snapshot_asm_blob(
        self, name: str, code_addr: int, body_start: int,
        fixup_start: int, rel_fixup_start: int,
    ):
        from types import MappingProxyType
        from zt.assemble.primitive_blob import PrimitiveBlob
        body_bytes = bytes(self.asm.code[body_start:])
        prefix = f"__asm__{name}__"
        labels = {
            label: addr - code_addr
            for label, addr in self.asm.labels.items()
            if label == name or label.startswith(prefix)
        }
        labels[name] = 0
        body_fixups = tuple(
            (off - body_start, ref)
            for off, ref in self.asm.fixups[fixup_start:]
        )
        body_rel_fixups = tuple(
            (off - body_start, ref)
            for off, ref in self.asm.rel_fixups[rel_fixup_start:]
        )
        deps = frozenset(
            ref for _, ref in body_fixups + body_rel_fixups
            if ref not in labels
        )
        return PrimitiveBlob(
            label_offsets=MappingProxyType(labels),
            code=body_bytes,
            fixups=body_fixups,
            rel_fixups=body_rel_fixups,
            external_deps=deps,
        )

    def _scoped_label(self, local: str) -> str:
        return f"__asm__{self._asm_word_name}__{local}"

    def _verify_asm_labels_resolved(self, tok: Token) -> None:
        abs_start, rel_start = self._asm_fixup_snapshot
        prefix = f"__asm__{self._asm_word_name}__"
        for _, name in (
            list(self.asm.fixups[abs_start:]) + list(self.asm.rel_fixups[rel_start:])
        ):
            if name.startswith(prefix) and name not in self.asm.labels:
                local = name[len(prefix):]
                raise CompileError(f"undefined label '{local}'", tok)

    @macro("[times]")
    def _macro_times(self, _compiler: Compiler, tok: Token) -> None:
        count_tok = self._next_token(tok)
        body_tok = self._next_token(tok)
        count = self._parse_macro_count(count_tok)
        self._tokens.splice_in([body_tok] * count)

    @macro("[defined]")
    def _macro_defined(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        flag = 1 if name_tok.value in self.words else 0
        self._host_stack.append(flag)

    @macro("[if]")
    def _macro_if(self, _compiler: Compiler, tok: Token) -> None:
        flag = self._host_pop(tok)
        if not flag:
            self._skip_to_branch_terminator(tok, accept_else=True)

    @macro("[else]")
    def _macro_else(self, _compiler: Compiler, tok: Token) -> None:
        self._skip_to_branch_terminator(tok, accept_else=False)

    @macro("[then]")
    def _macro_then(self, _compiler: Compiler, tok: Token) -> None:
        pass

    @macro("[string]")
    def _macro_string(self, _compiler: Compiler, tok: Token) -> None:
        starter = self._next_token(tok)
        if starter.kind != "word" or starter.value not in ('s"', '."'):
            raise CompileError(
                f"[string] expects an s\" or .\" string, got {starter.value!r}",
                starter,
            )
        body = self._next_string_token(starter)
        spliced: list[Token] = []
        for byte in body.value.encode("latin-1"):
            spliced.append(self._synthetic_token(str(byte), "number", body))
            spliced.append(self._synthetic_token("c,", "word", body))
        self._tokens.splice_in(spliced)

    def _synthetic_token(self, value: str, kind, near: Token) -> Token:
        return Token(
            value=value, kind=kind,
            line=near.line, col=near.col, source=near.source,
        )

    def _skip_to_branch_terminator(
        self, opener: Token, *, accept_else: bool,
    ) -> None:
        depth = 1
        while True:
            tok = self._next_token(opener)
            if tok.kind != "word":
                continue
            if tok.value == "[if]":
                depth += 1
            elif tok.value == "[then]":
                depth -= 1
                if depth == 0:
                    return
            elif tok.value == "[else]" and accept_else and depth == 1:
                return

    def _parse_macro_count(self, tok: Token) -> int:
        if tok.kind != "number":
            raise CompileError(
                f"[TIMES] count must be a number, got {tok.value!r}", tok,
            )
        count = parse_number(tok.value)
        if count < 0:
            raise CompileError(
                f"[TIMES] count must be non-negative, got {count}", tok,
            )
        return count

    def _assemble_asm_body(self, opener: Token) -> None:
        from zt.assemble.asm_vocab import lookup, UnknownMnemonic
        while True:
            tok = self._next_token(opener)
            if tok.kind == "word" and tok.value == ";":
                self.asm.dispatch()
                return
            if tok.kind == "word" and tok.value == ":::":
                raise CompileError("nested ::: definition", tok)
            if tok.kind == "word" and tok.value == "'":
                self._asm_body_tick(tok)
                continue
            if tok.kind == "number":
                self._host_stack.append(parse_number(tok.value))
                continue
            if tok.kind == "word" and self._is_macro(tok.value):
                self.words[tok.value].compile_action(self, tok)
                continue
            if tok.kind == "word":
                try:
                    spec = lookup(tok.value)
                except UnknownMnemonic:
                    raise CompileError(
                        f"unknown asm mnemonic '{tok.value}'", tok,
                    )
                self._emit_asm_op(spec, tok)
                continue
            raise CompileError(f"unexpected token '{tok.value}'", tok)

    def _asm_body_tick(self, tok: Token) -> None:
        name_tok = self._next_token(tok)
        word = self.words.get(name_tok.value)
        if word is None:
            raise CompileError(f"unknown word '{name_tok.value}' after '", name_tok)
        label = self._asm_body_tick_label(name_tok.value, word)
        self._host_stack.append(label)

    def _asm_body_tick_label(self, name: str, word: Word) -> str:
        if word.data_address is not None:
            label = f"__word_data__{name}"
            if label not in self.asm.labels:
                self.asm.labels[label] = word.data_address
            return label
        return self._resolve_asm_target(name)

    def _emit_asm_op(self, spec, tok: Token) -> None:
        method = getattr(self.asm, spec.mnemonic)
        if spec.operand is None:
            method()
            return
        if spec.operand == "label":
            self._emit_label_op(method, tok)
            return
        method(self._host_pop(tok))

    def _emit_label_op(self, method, tok: Token) -> None:
        name_tok = self._next_token(tok)
        if name_tok.kind != "word":
            raise CompileError(
                f"label name must be a word, got {name_tok.kind} '{name_tok.value}'",
                name_tok,
            )
        is_declaration = method.__name__ == "label"
        if is_declaration:
            target = self._scoped_label(name_tok.value)
        else:
            target = self._resolve_asm_target(name_tok.value)
        try:
            method(target)
        except ValueError as e:
            if "duplicate label" in str(e):
                raise CompileError(
                    f"duplicate label '{name_tok.value}'", name_tok,
                )
            raise

    def _resolve_asm_target(self, name: str) -> str:
        scoped = self._scoped_label(name)
        if scoped in self.asm.labels:
            return scoped
        if name in self.words:
            synth = f"__word__{name}"
            if synth not in self.asm.labels:
                self.asm.labels[synth] = self.words[name].address
            return synth
        return scoped

    @directive(",")
    def _directive_comma(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        asm_addr = self.asm.here
        self._emit_cell(value & 0xFFFF, tok)
        self._capture_pending_tick_at(asm_addr, value)

    def _capture_pending_tick_at(self, asm_addr: int, value: int) -> None:
        if self._pending_tick is None:
            return
        target, expected = self._pending_tick
        self._pending_tick = None
        if value != expected:
            self._tick_unsafe = True
            return
        owner = self._latest_data_word_at(asm_addr)
        if owner is None:
            self._tick_unsafe = True
            return
        self._word_address_refs.append(
            WordAddressRef(asm_addr=asm_addr, target=target, owner=owner)
        )

    def _latest_data_word_at(self, asm_addr: int) -> str | None:
        best_addr = -1
        best_name: str | None = None
        for word in self.words.values():
            if word.data_address is None:
                continue
            if word.data_address <= asm_addr and word.data_address > best_addr:
                best_addr = word.data_address
                best_name = word.name
        return best_name

    @macro("'")
    def _directive_tick(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        word = self.words.get(name_tok.value)
        if word is None:
            raise CompileError(f"unknown word '{name_tok.value}' after '", name_tok)
        addr = word.data_address if word.data_address is not None else word.address
        self._host_stack.append(addr)
        self._uses_word_address_data = True
        if self._inside_asm_body:
            self._tick_unsafe = True
            return
        if self._pending_tick is not None:
            self._tick_unsafe = True
        self._pending_tick = (name_tok.value, addr)

    @directive("c,")
    def _directive_c_comma(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        self.asm.byte(value & 0xFF)

    @directive("allot")
    def _directive_allot(self, _compiler: Compiler, tok: Token) -> None:
        count = self._host_pop(tok)
        for _ in range(count):
            self.asm.byte(0)

    @directive("in-bank")
    def _directive_in_bank(self, _compiler: Compiler, tok: Token) -> None:
        bank = self._host_pop(tok)
        if bank not in range(8):
            raise CompileError(
                f"in-bank: bank {bank} must be in range 0..7", tok,
            )
        self._activate_bank(bank)

    @directive("end-bank")
    def _directive_end_bank(self, _compiler: Compiler, tok: Token) -> None:
        if self._active_bank is None:
            raise CompileError(
                "end-bank without a matching in-bank", tok,
            )
        self._deactivate_bank()

    def _activate_bank(self, bank: int) -> None:
        if bank not in self._bank_asms:
            self._bank_asms[bank] = Asm(0xC000, inline_next=self.inline_next)
        self._active_bank = bank
        self.emitter.asm = self._bank_asms[bank]

    def _deactivate_bank(self) -> None:
        self._active_bank = None
        self.emitter.asm = self._main_asm

    def bank_image(self, bank: int) -> bytes:
        if bank not in self._bank_asms:
            return b""
        return bytes(self._bank_asms[bank].code)

    def banks(self) -> dict[int, bytes]:
        return {b: bytes(a.code) for b, a in self._bank_asms.items() if a.code}

    # --- control stack helpers ---

    def _push_control(self, tag: str, value: Any) -> None:
        self.control_stack.push(tag, value)

    def _pop_control(self, expected_tag: str, tok: Token) -> Any:
        try:
            return self.control_stack.pop(expected_tag)
        except ControlStackError as e:
            raise CompileError(str(e), tok) from e

    def _pop_control_any(self, expected_tags: list[str], tok: Token) -> tuple[str, Any]:
        try:
            return self.control_stack.pop_any(expected_tags)
        except ControlStackError as e:
            raise CompileError(str(e), tok) from e

    def _compile_zbranch_placeholder(self, tok: Token) -> int:
        if self.native_control_flow:
            return self.emitter.compile_native_zbranch_placeholder(tok)
        return self.emitter.compile_zbranch_placeholder(tok)

    def _compile_branch_placeholder(self, tok: Token) -> int:
        if self.native_control_flow:
            return self.emitter.compile_native_branch_placeholder(tok)
        return self.emitter.compile_branch_placeholder(tok)

    def _patch_placeholder(self, offset: int, target: int) -> None:
        self.emitter.patch_placeholder(offset, target)

    def _compile_branch_to_label(self, kind: str, target_addr: int,
                                 target_label_id: int, tok: Token) -> None:
        if self.native_control_flow:
            self.emitter.compile_native_branch_to_label(
                kind, target_addr, target_label_id, tok,
            )
        else:
            self.emitter.compile_branch_to_label(
                kind, target_addr, target_label_id, tok,
            )

    # --- immediate words: BEGIN/AGAIN ---

    @immediate("begin")
    def _immediate_begin(self, _compiler: Compiler, tok: Token) -> None:
        label_id = self._allocate_label()
        self._append_ir(Label(id=label_id))
        self._push_control("begin", (self.asm.here, label_id))

    @immediate("again")
    def _immediate_again(self, _compiler: Compiler, tok: Token) -> None:
        target_addr, label_id = self._pop_control("begin", tok)
        self._compile_branch_to_label("branch", target_addr, label_id, tok)

    # --- immediate words: IF/THEN/ELSE ---

    @immediate("if")
    def _immediate_if(self, _compiler: Compiler, tok: Token) -> None:
        placeholder = self._compile_zbranch_placeholder(tok)
        self._push_control("if", placeholder)

    @immediate("then")
    def _immediate_then(self, _compiler: Compiler, tok: Token) -> None:
        _tag, value = self._pop_control_any(["if", "else"], tok)
        self._patch_placeholder(value, self.asm.here)

    @immediate("else")
    def _immediate_else(self, _compiler: Compiler, tok: Token) -> None:
        if_placeholder = self._pop_control("if", tok)
        else_placeholder = self._compile_branch_placeholder(tok)
        self._patch_placeholder(if_placeholder, self.asm.here)
        self._push_control("else", else_placeholder)

    # --- immediate words: UNTIL/WHILE/REPEAT ---

    @immediate("until")
    def _immediate_until(self, _compiler: Compiler, tok: Token) -> None:
        target_addr, label_id = self._pop_control("begin", tok)
        self._compile_branch_to_label("0branch", target_addr, label_id, tok)

    @immediate("while")
    def _immediate_while(self, _compiler: Compiler, tok: Token) -> None:
        placeholder = self._compile_zbranch_placeholder(tok)
        begin_value = self._pop_control("begin", tok)
        self._push_control("while", placeholder)
        self._push_control("begin", begin_value)

    @immediate("repeat")
    def _immediate_repeat(self, _compiler: Compiler, tok: Token) -> None:
        begin_addr, begin_label_id = self._pop_control("begin", tok)
        while_placeholder = self._pop_control("while", tok)
        self._compile_branch_to_label("branch", begin_addr, begin_label_id, tok)
        self._patch_placeholder(while_placeholder, self.asm.here)

    # --- immediate words: DO/LOOP/+LOOP/LEAVE ---

    @immediate("do")
    def _immediate_do(self, _compiler: Compiler, tok: Token) -> None:
        self._emit_word_ref(self.words["(do)"], tok)
        body_addr = self.asm.here
        body_label_id = self._allocate_label()
        self._append_ir(Label(id=body_label_id))
        self._push_control("do", {
            "addr": body_addr,
            "label_id": body_label_id,
            "leaves": [],
        })

    @immediate("loop")
    def _immediate_loop(self, _compiler: Compiler, tok: Token) -> None:
        do_info = self._pop_control("do", tok)
        self._compile_branch_to_label(
            "(loop)", do_info["addr"], do_info["label_id"], tok,
        )
        for leave_offset in do_info["leaves"]:
            self._patch_placeholder(leave_offset, self.asm.here)

    @immediate("+loop")
    def _immediate_plus_loop(self, _compiler: Compiler, tok: Token) -> None:
        do_info = self._pop_control("do", tok)
        self._compile_branch_to_label(
            "(+loop)", do_info["addr"], do_info["label_id"], tok,
        )
        for leave_offset in do_info["leaves"]:
            self._patch_placeholder(leave_offset, self.asm.here)

    @immediate("leave")
    def _immediate_leave(self, _compiler: Compiler, tok: Token) -> None:
        self._reject_native_unsupported("LEAVE", tok)
        if (self.current_word
                and self.current_word in self.words
                and self.words[self.current_word].force_inline):
            raise CompileError(
                f"LEAVE is not supported inside :: definitions "
                f"(in '{self.current_word}')", tok,
            )
        frame = self.control_stack.find_innermost("do")
        if frame is None:
            raise CompileError("LEAVE outside DO/LOOP", tok)
        _tag, do_info = frame
        self._emit_word_ref(self.words["unloop"], tok)
        placeholder = self._compile_branch_placeholder(tok)
        do_info["leaves"].append(placeholder)

    # --- immediate words: brackets, tick, recurse ---

    @immediate("[")
    def _immediate_lbracket(self, _compiler: Compiler, tok: Token) -> None:
        self.state = "interpret"

    @immediate("]")
    def _immediate_rbracket(self, _compiler: Compiler, tok: Token) -> None:
        self.state = "compile"

    @immediate("[']")
    def _immediate_bracket_tick(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        word = self.words.get(name_tok.value)
        if word is None:
            raise CompileError(f"unknown word '{name_tok.value}'", name_tok)
        self.emitter.compile_word_literal(word, tok)

    @immediate("recurse")
    def _immediate_recurse(self, _compiler: Compiler, tok: Token) -> None:
        if self.current_word is None:
            raise CompileError("RECURSE outside colon definition", tok)
        word = self.words[self.current_word]
        self._emit_word_ref(word, tok)

    # --- immediate words: string literals ---

    def _next_string_token(self, starter: Token) -> Token:
        peeked = self._tokens.peek()
        if peeked is None:
            raise CompileError(
                f"{starter.value} without string body", starter,
            )
        if peeked.kind != "string":
            raise CompileError(
                f"{starter.value} must be followed by a string, got {peeked.kind} '{peeked.value}'",
                starter,
            )
        return self._tokens.next()

    def _allocate_string(self, data: bytes) -> str:
        return self.string_pool.allocate(data)

    def _compile_string_literal(self, data: bytes, tok: Token) -> tuple[str, int]:
        label = self._allocate_string(data)
        lit_addr = self.words["lit"].address
        self._emit_cell(lit_addr, tok)
        self._append_ir(PrimRef("lit"))
        self._emit_cell(label, tok)
        self._append_ir(StringRef(label))
        self._emit_cell(lit_addr, tok)
        self._emit_cell(len(data), tok)
        self._append_ir(Literal(len(data)))
        return label, len(data)

    @immediate(".\"")
    def _immediate_dot_quote(self, _compiler: Compiler, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError('." outside colon definition', tok)
        body = self._next_string_token(tok)
        self._compile_string_literal(body.value.encode("latin-1"), tok)
        self._emit_word_ref(self.words["type"], tok)

    @immediate("s\"")
    def _immediate_s_quote(self, _compiler: Compiler, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError('s" outside colon definition', tok)
        body = self._next_string_token(tok)
        self._compile_string_literal(body.value.encode("latin-1"), tok)

    # --- immediate words: INCLUDE / REQUIRE ---

    @immediate("include")
    def _immediate_include(self, _compiler: Compiler, tok: Token) -> None:
        filename = self._read_filename_token(tok)
        path = self._resolve_include_path(filename, tok)
        self._include_file(path)

    @immediate("require")
    def _immediate_require(self, _compiler: Compiler, tok: Token) -> None:
        filename = self._read_filename_token(tok)
        path = self._resolve_include_path(filename, tok)
        if self.include_resolver.has_seen(path):
            return
        self._include_file(path)

    def _read_filename_token(self, context_tok: Token) -> str:
        if not self._tokens.has_more():
            raise CompileError(
                f"expected filename after '{context_tok.value}'",
                context_tok,
            )
        name_tok = self._next_token(context_tok)
        if name_tok.kind != "word":
            raise CompileError(
                f"expected filename after '{context_tok.value}', "
                f"got {name_tok.kind} '{name_tok.value}'",
                name_tok,
            )
        return name_tok.raw or name_tok.value

    def _resolve_include_path(self, filename: str, context_tok: Token) -> Path:
        try:
            return self.include_resolver.resolve(filename, Path(context_tok.source))
        except IncludeNotFound as e:
            raise CompileError(str(e), context_tok) from e

    def _include_file(self, path: Path) -> None:
        self.include_resolver.mark_seen(path)
        text = path.read_text()
        new_tokens = tokenize(text, source=str(path))
        self._tokens.splice_in(new_tokens)

    # --- build ---

    def include_stdlib(self, path: object | None = None) -> None:
        source = Path(path) if path is not None else _bundled_stdlib_dir() / "core.fs"
        self.include_resolver.mark_seen(source.resolve())
        self.compile_source(source.read_text(), source=str(source))

    def compile_main_call(self) -> None:
        if "main" not in self.words:
            raise CompileError("no 'main' word defined")
        self.string_pool.flush(self.asm)
        if self.native_control_flow:
            self._emit_native_start()
        else:
            self._emit_threaded_start()
        self.words["_start"] = Word(
            name="_start", address=self.asm.labels["_start"], kind="prim"
        )

    def _emit_threaded_start(self) -> None:
        main_body_addr = self.asm.here
        self.asm.word(self.words["main"].address)
        halt_addr = self.words["halt"].address
        self.asm.word(halt_addr)
        self.asm.label("_start")
        self.asm.di()
        self.asm.ld_sp_nn(self.data_stack_top)
        self.asm.ld_iy_nn(self.return_stack_top)
        self.asm.ld_ix_nn(main_body_addr)
        next_addr = self.words["next"].address
        self.asm.jp(next_addr)

    def _emit_native_start(self) -> None:
        self.asm.label("_start")
        self.asm.di()
        self.asm.ld_sp_nn(self.data_stack_top)
        self.asm.ld_iy_nn(self.return_stack_top)
        self.asm.jp(self.words["main"].address)

    def build(self) -> bytes:
        image = self.asm.resolve()
        if os.getenv("ZT_VERIFY_IR") == "1" and not self.native_control_flow:
            self._verify_ir(image)
        return image

    def build_tree_shaken(self) -> tuple[bytes, int]:
        from zt.compile.tree_shake import build_tree_shaken_image
        return build_tree_shaken_image(self)

    def compute_liveness(self):
        from zt.compile.liveness import compute_liveness
        return compute_liveness(
            roots=self._liveness_roots(),
            bodies=self._liveness_bodies(),
            prim_deps=self._all_prim_deps(),
            data_refs=self._liveness_data_refs(),
        )

    def _liveness_data_refs(self) -> dict[str, list[str]]:
        refs: dict[str, list[str]] = {}
        for ref in self._word_address_refs:
            refs.setdefault(ref.owner, []).append(ref.target)
        return refs

    def word_address_refs_by_owner(self) -> dict[str, list[WordAddressRef]]:
        refs: dict[str, list[WordAddressRef]] = {}
        for ref in self._word_address_refs:
            refs.setdefault(ref.owner, []).append(ref)
        return refs

    def _all_prim_deps(self) -> dict[str, frozenset[str]]:
        deps = dict(self._blob_registry.dependency_graph())
        for blob in self._asm_word_blobs:
            translated = frozenset(
                self._translate_synthetic_dep(name) for name in blob.external_deps
            )
            for label in blob.label_offsets:
                deps[label] = translated
        return deps

    def _translate_synthetic_dep(self, name: str) -> str:
        for prefix in ("__word_data__", "__word__"):
            if name.startswith(prefix):
                return name[len(prefix):]
        return name

    def _liveness_roots(self) -> list[str]:
        return ["main", "halt", "next", "docol"]

    def _liveness_bodies(self) -> dict[str, list]:
        return {
            word.name: word.body
            for word in self.words.values()
            if word.kind == "colon" and word.body is not None
        }

    def _verify_ir(self, image: bytes) -> None:
        word_addrs = self._build_verify_addr_table()
        for word in self.words.values():
            if word.kind != "colon" or word.inlined:
                continue
            body_start = word.address + 3
            expected = resolve(word.body, word_addrs, base_address=body_start)
            start = body_start - self.origin
            actual = bytes(image[start:start + len(expected)])
            if expected != actual:
                raise AssertionError(
                    f"ZT_VERIFY_IR: IR/bytes mismatch for colon word '{word.name}' "
                    f"at {body_start:#06x}: "
                    f"expected {expected.hex()}, got {actual.hex()}"
                )

    def _build_verify_addr_table(self) -> dict[str, int]:
        addrs: dict[str, int] = dict(self.asm.labels)
        for name, word in self.words.items():
            addrs[name] = word.address
        return addrs


def parse_number(text: str) -> int:
    if text.startswith("$"):
        return int(text[1:], 16)
    if text.startswith("%"):
        return int(text[1:], 2)
    return int(text)


def compile_and_run(
    source: str,
    origin: int = DEFAULT_ORIGIN,
    optimize: bool = True,
    inline_next: bool = True,
    inline_primitives: bool = True,
    native_control_flow: bool = False,
) -> list[int]:
    from zt.sim import Z80, _read_data_stack

    c = Compiler(
        origin=origin, optimize=optimize,
        inline_next=inline_next, inline_primitives=inline_primitives,
        native_control_flow=native_control_flow,
    )
    c.compile_source(source)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(origin, image)
    m.pc = c.words["_start"].address
    m.run()
    if not m.halted:
        raise TimeoutError("execution timed out")
    return _read_data_stack(m, c.data_stack_top, False)


def compile_and_run_with_output(
    source: str,
    origin: int = DEFAULT_ORIGIN,
    input_buffer: bytes = b"",
    pressed_keys: set[int] | None = None,
    max_ticks: int = 10_000_000,
    stdlib: bool = False,
    optimize: bool = True,
    inline_next: bool = True,
    inline_primitives: bool = True,
    native_control_flow: bool = False,
) -> tuple[list[int], bytes]:
    from zt.sim import (
        SPECTRUM_FONT_BASE,
        TEST_FONT,
        Z80,
        _read_data_stack,
        decode_screen_text,
    )

    c = Compiler(
        origin=origin, optimize=optimize,
        inline_next=inline_next, inline_primitives=inline_primitives,
        native_control_flow=native_control_flow,
    )
    if stdlib:
        c.include_stdlib()
    c.compile_source(source)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.input_buffer = bytearray(input_buffer)
    if pressed_keys is not None:
        m.pressed_keys = set(pressed_keys)
    m.pc = c.words["_start"].address
    m.run(max_ticks=max_ticks)
    if not m.halted:
        raise TimeoutError("execution timed out")

    stack = _read_data_stack(m, c.data_stack_top, False)
    row_addr = c.asm.labels.get("_emit_cursor_row")
    col_addr = c.asm.labels.get("_emit_cursor_col")
    if row_addr is None or col_addr is None:
        return stack, b""
    chars = decode_screen_text(m.mem, m.mem[row_addr], m.mem[col_addr])
    return stack, chars


def build_from_source(
    source: str,
    origin: int = DEFAULT_ORIGIN,
    data_stack_top: int = DEFAULT_DATA_STACK_TOP,
    return_stack_top: int = DEFAULT_RETURN_STACK_TOP,
    optimize: bool = True,
    inline_next: bool = True,
    inline_primitives: bool = True,
    native_control_flow: bool = False,
) -> tuple[bytes, Compiler]:
    c = Compiler(
        origin=origin, data_stack_top=data_stack_top,
        return_stack_top=return_stack_top, optimize=optimize,
        inline_next=inline_next, inline_primitives=inline_primitives,
        native_control_flow=native_control_flow,
    )
    c.compile_source(source)
    c.compile_main_call()
    return c.build(), c
