from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

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
        self.control_stack: list[int] = []
        self.current_word: str | None = None
        self._tokens: list[Token] = []
        self._token_pos: int = 0
        self._register_primitives()

    def _register_primitives(self) -> None:
        for creator in PRIMITIVES:
            creator(self.asm)
        for name, addr in self.asm.labels.items():
            if name.startswith("_"):
                continue
            lower = name.lower()
            if lower not in self.words:
                self.words[lower] = Word(name=lower, address=addr, kind="prim")

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
            raise CompileError(
                f"bare number '{tok.value}' in interpret state", tok
            )
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
        if name in self.words:
            pass  # allow redefinition (standard Forth behavior)
        self.state = "compile"
        self.current_word = name
        addr = self.asm.here
        self.asm.call("DOCOL")
        self.words[name] = Word(name=name, address=addr, kind="colon")

    def _end_colon(self, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError("; outside colon definition", tok)
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
