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
    directive,
    immediate,
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
    ):
        self.origin = origin
        self.data_stack_top = data_stack_top
        self.return_stack_top = return_stack_top
        self.include_resolver: IncludeResolver = IncludeResolver(include_dirs or [])
        outer_asm = Asm(origin, inline_next=inline_next)
        self.words: Dictionary = Dictionary()
        self.state: TypingLiteral["interpret", "compile"] = "interpret"
        self.control_stack: ControlStack = ControlStack()
        self.current_word: str | None = None
        self._tokens: TokenStream = TokenStream([])
        self._host_stack: list[int] = []
        self.string_pool: StringPool = StringPool()
        self.emitter: CodeEmitter = CodeEmitter(
            asm=outer_asm, words=self.words, origin=origin,
        )
        self.warnings: list[str] = []
        self.optimize: bool = optimize
        self.inline_next: bool = inline_next
        self.inline_primitives: bool = inline_primitives
        self._inline_context: InlineContext | None = None
        self._peephole_rules: tuple[PeepholeRule, ...] = DEFAULT_RULES
        self._register_primitives()
        self._register_directives()
        self._register_immediates()

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
        for creator in PRIMITIVES:
            creator(self.asm)
        self.words.register_primitives(self.asm)
        if self.inline_primitives:
            self._inline_context = InlineContext.build(PRIMITIVES)

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
            self._interpret_token(tok)
        else:
            self._compile_state_token(tok)

    def _interpret_token(self, tok: Token) -> None:
        if tok.kind == "word" and tok.value == ":":
            self._start_colon(tok)
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
        return tok.kind == "word" and tok.value in (";", ":")

    def _is_immediate_token(self, tok: Token) -> bool:
        if tok.kind != "word":
            return False
        word = self.words.get(tok.value)
        return word is not None and word.immediate

    def _start_colon(self, tok: Token) -> None:
        if self.state == "compile":
            raise CompileError("nested colon definition", tok)
        name_tok = self._next_token(tok)
        name = name_tok.value
        self._warn_if_redefining(name, tok)
        self.state = "compile"
        self.current_word = name
        self.emitter.begin_body()
        self.emitter.begin_buffered()
        addr = self.asm.here
        self.asm.call("DOCOL")
        self.words[name] = Word(
            name=name, address=addr, kind="colon",
            source_file=tok.source, source_line=tok.line,
        )

    def _warn_if_redefining(self, name: str, tok: Token) -> None:
        warning = self.words.redefinition_warning(
            name, source_file=tok.source, source_line=tok.line,
        )
        if warning is not None:
            self.warnings.append(warning)

    def _end_colon(self, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError("; outside colon definition", tok)
        if self.control_stack:
            tag, _ = self.control_stack.peek()
            self.control_stack.clear()
            raise CompileError(
                f"unclosed {tag} in '{self.current_word}'", tok
            )
        self._emit_word_ref(self.words["exit"], tok)
        word = self.words[self.current_word]
        word.body = self.emitter.end_body()
        self.state = "interpret"
        self.current_word = None
        self._try_inline_colon(word)

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
        self.emitter.compile_literal(value, tok)

    def _emit_cell(self, value: int | str, tok: Token) -> None:
        self.emitter.emit_cell(value, tok)

    def _append_ir(self, cell: Cell) -> None:
        self.emitter.append_ir(cell)

    def _allocate_label(self) -> int:
        return self.emitter.allocate_label()

    def _emit_word_ref(self, word: Word, tok: Token) -> None:
        self.emitter.emit_word_ref(word, tok)

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
        code_addr = self.asm.here
        self.asm.push_hl()
        self.asm.ld_hl_nn(0)
        fixup = len(self.asm.code) - 2
        self.asm.jp("NEXT")
        data_addr = self.asm.here
        self.asm.code[fixup] = data_addr & 0xFF
        self.asm.code[fixup + 1] = (data_addr >> 8) & 0xFF
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
        )

    @directive("constant")
    def _directive_constant(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        name_tok = self._next_token(tok)
        code_addr = self._emit_pusher(value)
        self.words[name_tok.value] = Word(
            name=name_tok.value, address=code_addr, kind="constant",
            source_file=name_tok.source, source_line=name_tok.line,
        )

    @directive("create")
    def _directive_create(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        code_addr, data_addr = self._emit_variable_shim()
        self.words[name_tok.value] = Word(
            name=name_tok.value, address=code_addr, kind="variable",
            data_address=data_addr,
            source_file=name_tok.source, source_line=name_tok.line,
        )

    @directive(",")
    def _directive_comma(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        self._emit_cell(value & 0xFFFF, tok)

    @directive("c,")
    def _directive_c_comma(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        self.asm.byte(value & 0xFF)

    @directive("allot")
    def _directive_allot(self, _compiler: Compiler, tok: Token) -> None:
        count = self._host_pop(tok)
        for _ in range(count):
            self.asm.byte(0)

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
        return self.emitter.compile_zbranch_placeholder(tok)

    def _compile_branch_placeholder(self, tok: Token) -> int:
        return self.emitter.compile_branch_placeholder(tok)

    def _patch_placeholder(self, offset: int, target: int) -> None:
        self.emitter.patch_placeholder(offset, target)

    def _compile_branch_to_label(self, kind: str, target_addr: int,
                                 target_label_id: int, tok: Token) -> None:
        self.emitter.compile_branch_to_label(kind, target_addr, target_label_id, tok)

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
        self._compile_literal(word.address, tok)

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
        if path is None:
            path = Path(__file__).resolve().parent.parent.parent.parent / "stdlib" / "core.fs"
        else:
            path = Path(path)
        self.include_resolver.mark_seen(path.resolve())
        self.compile_source(path.read_text(), source=str(path))

    def compile_main_call(self) -> None:
        if "main" not in self.words:
            raise CompileError("no 'main' word defined")
        self.string_pool.flush(self.asm)
        main_body_addr = self.asm.here
        self.asm.word(self.words["main"].address)
        halt_addr = self.words["halt"].address
        self.asm.word(halt_addr)
        self.asm.label("_start")
        self.asm.ld_sp_nn(self.data_stack_top)
        self.asm.ld_iy_nn(self.return_stack_top)
        self.asm.ld_ix_nn(main_body_addr)
        next_addr = self.words["next"].address
        self.asm.jp(next_addr)
        self.words["_start"] = Word(
            name="_start", address=self.asm.labels["_start"], kind="prim"
        )

    def build(self) -> bytes:
        image = self.asm.resolve()
        if os.getenv("ZT_VERIFY_IR") == "1":
            self._verify_ir(image)
        return image

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
) -> list[int]:
    from zt.sim import Z80, _read_data_stack

    c = Compiler(
        origin=origin, optimize=optimize,
        inline_next=inline_next, inline_primitives=inline_primitives,
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
) -> tuple[bytes, Compiler]:
    c = Compiler(
        origin=origin, data_stack_top=data_stack_top,
        return_stack_top=return_stack_top, optimize=optimize,
        inline_next=inline_next, inline_primitives=inline_primitives,
    )
    c.compile_source(source)
    c.compile_main_call()
    return c.build(), c
