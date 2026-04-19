"""
`TokenStream`: cursor over the token list exposing `peek` / `next` / `lookahead` and in-place `splice_in`, used by the compiler to expand `INCLUDE` inline.
"""
from __future__ import annotations

from zt.compile.tokenizer import Token


class TokenStreamExhausted(Exception):
    pass


class TokenStream:

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens: list[Token] = list(tokens)
        self._pos: int = 0

    def has_more(self) -> bool:
        return self._pos < len(self._tokens)

    def peek(self) -> Token | None:
        if self._pos >= len(self._tokens):
            return None
        return self._tokens[self._pos]

    def next(self) -> Token:
        if self._pos >= len(self._tokens):
            raise TokenStreamExhausted("no more tokens to read")
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def lookahead(self, count: int) -> list[Token]:
        return self._tokens[self._pos:self._pos + count]

    def advance_by(self, count: int) -> None:
        self._pos += count

    def splice_in(self, tokens: list[Token]) -> None:
        self._tokens[self._pos:self._pos] = tokens

    def last_token(self) -> Token | None:
        if not self._tokens:
            return None
        return self._tokens[-1]
