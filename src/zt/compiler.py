from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from zt.asm import Asm
from zt.primitives import PRIMITIVES
from zt.tokenizer import Token, tokenize


@dataclass
class Word:
    name: str
    address: int
    kind: Literal["prim", "colon", "variable", "constant"]
    immediate: bool = False
    compile_action: Callable | None = None


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
    ):
        self.origin = origin
        self.data_stack_top = data_stack_top
        self.return_stack_top = return_stack_top
        self.asm = Asm(origin)
        self.words: dict[str, Word] = {}
        self.state: Literal["interpret", "compile"] = "interpret"
        self.control_stack: list[tuple[str, Any]] = []
        self.current_word: str | None = None
        self._tokens: list[Token] = []
        self._token_pos: int = 0
        self._host_stack: list[int] = []
        self._register_primitives()
        self._register_directives()
        self._register_immediates()

    def _register_primitives(self) -> None:
        for creator in PRIMITIVES:
            creator(self.asm)
        for name, addr in self.asm.labels.items():
            if name.startswith("_"):
                continue
            lower = name.lower()
            if lower not in self.words:
                self.words[lower] = Word(name=lower, address=addr, kind="prim")

    def _register_directives(self) -> None:
        for name, action in [
            ("variable", self._directive_variable),
            ("constant", self._directive_constant),
            ("create", self._directive_create),
            (",", self._directive_comma),
            ("c,", self._directive_c_comma),
            ("allot", self._directive_allot),
        ]:
            self.words[name] = Word(
                name=name, address=0, kind="prim",
                immediate=True, compile_action=action,
            )

    def _register_immediates(self) -> None:
        for name, action in [
            ("begin", self._immediate_begin),
            ("again", self._immediate_again),
            ("if", self._immediate_if),
            ("then", self._immediate_then),
            ("else", self._immediate_else),
            ("until", self._immediate_until),
            ("while", self._immediate_while),
            ("repeat", self._immediate_repeat),
            ("do", self._immediate_do),
            ("loop", self._immediate_loop),
            ("+loop", self._immediate_plus_loop),
            ("leave", self._immediate_leave),
            ("[", self._immediate_lbracket),
            ("]", self._immediate_rbracket),
            ("[']", self._immediate_bracket_tick),
            ("recurse", self._immediate_recurse),
        ]:
            self.words[name] = Word(
                name=name, address=0, kind="prim",
                immediate=True, compile_action=action,
            )

    def compile_source(self, text: str, source: str = "<input>") -> None:
        self._tokens = tokenize(text, source)
        self._token_pos = 0
        while self._token_pos < len(self._tokens):
            tok = self._tokens[self._token_pos]
            self._token_pos += 1
            self._compile_token(tok)
        if self.state == "compile":
            raise CompileError(
                f"unclosed colon definition '{self.current_word}'",
                self._tokens[-1] if self._tokens else None,
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
        if tok.kind == "word":
            word = self.words.get(tok.value)
            if word is None:
                raise CompileError(f"unknown word '{tok.value}'", tok)
            if word.immediate and word.compile_action:
                word.compile_action(self, tok)
                return
            self.asm.word(word.address)
            return
        if tok.kind == "number":
            value = parse_number(tok.value)
            self._compile_literal(value)
            return
        raise CompileError(f"unexpected token '{tok.value}'", tok)

    def _start_colon(self, tok: Token) -> None:
        if self.state == "compile":
            raise CompileError("nested colon definition", tok)
        name_tok = self._next_token(tok)
        name = name_tok.value
        self.state = "compile"
        self.current_word = name
        addr = self.asm.here
        self.asm.call("DOCOL")
        self.words[name] = Word(name=name, address=addr, kind="colon")

    def _end_colon(self, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError("; outside colon definition", tok)
        if self.control_stack:
            tag, _ = self.control_stack[-1]
            self.control_stack.clear()
            raise CompileError(
                f"unclosed {tag} in '{self.current_word}'", tok
            )
        exit_addr = self.words["exit"].address
        self.asm.word(exit_addr)
        self.state = "interpret"
        self.current_word = None

    def _compile_literal(self, value: int) -> None:
        lit_addr = self.words["lit"].address
        self.asm.word(lit_addr)
        self.asm.word(value & 0xFFFF)

    def _next_token(self, context_tok: Token) -> Token:
        if self._token_pos >= len(self._tokens):
            raise CompileError("unexpected end of input", context_tok)
        tok = self._tokens[self._token_pos]
        self._token_pos += 1
        return tok

    def _host_pop(self, tok: Token) -> int:
        if not self._host_stack:
            raise CompileError("host stack underflow", tok)
        return self._host_stack.pop()

    def _compile_push_value(self, name: str, value: int, kind: str) -> None:
        addr = self.asm.here
        self.asm.push_hl()
        self.asm.ld_hl_nn(value & 0xFFFF)
        self.asm.jp("NEXT")
        self.words[name] = Word(name=name, address=addr, kind=kind)

    # --- directives ---

    def _directive_variable(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        data_addr = self.asm.here + 4 + 3
        self._compile_push_value(name_tok.value, data_addr, "variable")
        self.asm.word(0)

    def _directive_constant(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        name_tok = self._next_token(tok)
        self._compile_push_value(name_tok.value, value, "constant")

    def _directive_create(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        data_addr_placeholder = self.asm.here
        self.asm.push_hl()
        self.asm.ld_hl_nn(0)
        fixup_offset = len(self.asm.code) - 2
        self.asm.jp("NEXT")
        data_start = self.asm.here
        self.asm.code[fixup_offset] = data_start & 0xFF
        self.asm.code[fixup_offset + 1] = (data_start >> 8) & 0xFF
        self.words[name_tok.value] = Word(
            name=name_tok.value, address=data_addr_placeholder, kind="variable"
        )

    def _directive_comma(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        self.asm.word(value & 0xFFFF)

    def _directive_c_comma(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        self.asm.byte(value & 0xFF)

    def _directive_allot(self, _compiler: Compiler, tok: Token) -> None:
        count = self._host_pop(tok)
        for _ in range(count):
            self.asm.byte(0)

    # --- control stack helpers ---

    def _push_control(self, tag: str, value: Any) -> None:
        self.control_stack.append((tag, value))

    def _pop_control(self, expected_tag: str, tok: Token) -> Any:
        if not self.control_stack:
            raise CompileError(
                f"control stack underflow ({expected_tag})", tok
            )
        tag, value = self.control_stack.pop()
        if tag != expected_tag:
            raise CompileError(
                f"control flow mismatch: expected {expected_tag}, got {tag}", tok
            )
        return value

    def _pop_control_any(self, expected_tags: list[str], tok: Token) -> tuple[str, Any]:
        if not self.control_stack:
            raise CompileError(
                f"control stack underflow ({'/'.join(expected_tags)})", tok
            )
        tag, value = self.control_stack.pop()
        if tag not in expected_tags:
            raise CompileError(
                f"control flow mismatch: expected {'/'.join(expected_tags)}, got {tag}",
                tok,
            )
        return tag, value

    def _compile_zbranch_placeholder(self) -> int:
        self.asm.word(self.words["0branch"].address)
        offset = len(self.asm.code)
        self.asm.word(0)
        return offset

    def _compile_branch_placeholder(self) -> int:
        self.asm.word(self.words["branch"].address)
        offset = len(self.asm.code)
        self.asm.word(0)
        return offset

    def _patch_placeholder(self, offset: int, target: int) -> None:
        self.asm.code[offset] = target & 0xFF
        self.asm.code[offset + 1] = (target >> 8) & 0xFF

    def _compile_branch_to(self, target: int) -> None:
        self.asm.word(self.words["branch"].address)
        self.asm.word(target)

    # --- immediate words: BEGIN/AGAIN ---

    def _immediate_begin(self, _compiler: Compiler, tok: Token) -> None:
        self._push_control("begin", self.asm.here)

    def _immediate_again(self, _compiler: Compiler, tok: Token) -> None:
        target = self._pop_control("begin", tok)
        self._compile_branch_to(target)

    # --- immediate words: IF/THEN/ELSE ---

    def _immediate_if(self, _compiler: Compiler, tok: Token) -> None:
        placeholder = self._compile_zbranch_placeholder()
        self._push_control("if", placeholder)

    def _immediate_then(self, _compiler: Compiler, tok: Token) -> None:
        _tag, value = self._pop_control_any(["if", "else"], tok)
        self._patch_placeholder(value, self.asm.here)

    def _immediate_else(self, _compiler: Compiler, tok: Token) -> None:
        if_placeholder = self._pop_control("if", tok)
        else_placeholder = self._compile_branch_placeholder()
        self._patch_placeholder(if_placeholder, self.asm.here)
        self._push_control("else", else_placeholder)

    # --- immediate words: UNTIL/WHILE/REPEAT ---

    def _immediate_until(self, _compiler: Compiler, tok: Token) -> None:
        target = self._pop_control("begin", tok)
        self.asm.word(self.words["0branch"].address)
        self.asm.word(target)

    def _immediate_while(self, _compiler: Compiler, tok: Token) -> None:
        if not self.control_stack:
            raise CompileError(
                "control stack underflow (while)", tok
            )
        placeholder = self._compile_zbranch_placeholder()
        begin_entry = self.control_stack.pop()
        if begin_entry[0] != "begin":
            raise CompileError(
                f"control flow mismatch: expected begin, got {begin_entry[0]}",
                tok,
            )
        self._push_control("while", placeholder)
        self.control_stack.append(begin_entry)

    def _immediate_repeat(self, _compiler: Compiler, tok: Token) -> None:
        begin_addr = self._pop_control("begin", tok)
        while_placeholder = self._pop_control("while", tok)
        self._compile_branch_to(begin_addr)
        self._patch_placeholder(while_placeholder, self.asm.here)

    # --- immediate words: DO/LOOP/+LOOP/LEAVE ---

    def _immediate_do(self, _compiler: Compiler, tok: Token) -> None:
        self.asm.word(self.words["(do)"].address)
        body_addr = self.asm.here
        self._push_control("do", {"addr": body_addr, "leaves": []})

    def _immediate_loop(self, _compiler: Compiler, tok: Token) -> None:
        do_info = self._pop_control("do", tok)
        self.asm.word(self.words["(loop)"].address)
        self.asm.word(do_info["addr"])
        for leave_offset in do_info["leaves"]:
            self._patch_placeholder(leave_offset, self.asm.here)

    def _immediate_plus_loop(self, _compiler: Compiler, tok: Token) -> None:
        do_info = self._pop_control("do", tok)
        self.asm.word(self.words["(+loop)"].address)
        self.asm.word(do_info["addr"])
        for leave_offset in do_info["leaves"]:
            self._patch_placeholder(leave_offset, self.asm.here)

    def _immediate_leave(self, _compiler: Compiler, tok: Token) -> None:
        for i in range(len(self.control_stack) - 1, -1, -1):
            if self.control_stack[i][0] == "do":
                self.asm.word(self.words["unloop"].address)
                placeholder = self._compile_branch_placeholder()
                self.control_stack[i][1]["leaves"].append(placeholder)
                return
        raise CompileError("LEAVE outside DO/LOOP", tok)

    # --- immediate words: brackets, tick, recurse ---

    def _immediate_lbracket(self, _compiler: Compiler, tok: Token) -> None:
        self.state = "interpret"

    def _immediate_rbracket(self, _compiler: Compiler, tok: Token) -> None:
        self.state = "compile"

    def _immediate_bracket_tick(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        word = self.words.get(name_tok.value)
        if word is None:
            raise CompileError(f"unknown word '{name_tok.value}'", name_tok)
        self._compile_literal(word.address)

    def _immediate_recurse(self, _compiler: Compiler, tok: Token) -> None:
        if self.current_word is None:
            raise CompileError("RECURSE outside colon definition", tok)
        word = self.words[self.current_word]
        self.asm.word(word.address)

    # --- build ---

    def compile_main_call(self) -> None:
        if "main" not in self.words:
            raise CompileError("no 'main' word defined")
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
        return self.asm.resolve()


def parse_number(text: str) -> int:
    if text.startswith("$"):
        return int(text[1:], 16)
    if text.startswith("%"):
        return int(text[1:], 2)
    return int(text)


def compile_and_run(source: str, origin: int = DEFAULT_ORIGIN) -> list[int]:
    from zt.sim import Z80, _read_data_stack

    c = Compiler(origin=origin)
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


def build_from_source(
    source: str,
    origin: int = DEFAULT_ORIGIN,
    data_stack_top: int = DEFAULT_DATA_STACK_TOP,
    return_stack_top: int = DEFAULT_RETURN_STACK_TOP,
) -> tuple[bytes, Compiler]:
    c = Compiler(origin=origin, data_stack_top=data_stack_top,
                 return_stack_top=return_stack_top)
    c.compile_source(source)
    c.compile_main_call()
    return c.build(), c
