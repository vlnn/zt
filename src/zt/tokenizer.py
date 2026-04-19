r"""
Forth source tokenizer. Produces `Token(value, kind, line, col, source)` and recognises words, numbers (`$hex` / `%bin` / decimal), strings (`."`, `s"`) and both `\` line and `( )` block comments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Token:
    value: str
    kind: Literal["word", "number", "string"]
    line: int
    col: int
    source: str
    raw: str | None = None

    def __post_init__(self) -> None:
        if self.raw is None:
            object.__setattr__(self, "raw", self.value)


class TokenizeError(Exception):
    def __init__(self, message: str, line: int, col: int, source: str) -> None:
        self.line = line
        self.col = col
        self.source = source
        super().__init__(f"{source}:{line}:{col}: {message}")


_NUMBER_RE = re.compile(r"^-?[0-9]+$|^\$[0-9a-f]+$|^%[01]+$")

_STRING_STARTERS = {'."', 's"'}


def _is_number(text: str) -> bool:
    return bool(_NUMBER_RE.match(text))


def _is_whitespace(ch: str) -> bool:
    return ch in " \t\n"


def _preceded_by_whitespace_or_start(text: str, pos: int) -> bool:
    return pos == 0 or text[pos - 1] in " \t\n"


def tokenize(text: str, source: str = "<input>") -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    line = 1
    col = 1
    n = len(text)

    while pos < n:
        ch = text[pos]

        if ch in " \t":
            pos += 1
            col += 1
            continue

        if ch == "\n":
            pos += 1
            line += 1
            col = 1
            continue

        if ch == "\\" and _preceded_by_whitespace_or_start(text, pos):
            while pos < n and text[pos] != "\n":
                pos += 1
            continue

        if ch == "(" and _preceded_by_whitespace_or_start(text, pos):
            next_pos = pos + 1
            if next_pos >= n or text[next_pos] in " \t\n)":
                start_line, start_col = line, col
                pos += 1
                col += 1
                while pos < n and text[pos] != ")":
                    if text[pos] == "\n":
                        line += 1
                        col = 1
                    else:
                        col += 1
                    pos += 1
                if pos >= n:
                    raise TokenizeError("unclosed block comment", start_line, start_col, source)
                pos += 1
                col += 1
                continue

        start_line, start_col = line, col
        word_start = pos
        while pos < n and not _is_whitespace(text[pos]):
            pos += 1
            col += 1
        raw = text[word_start:pos]
        lower = raw.lower()

        if lower in _STRING_STARTERS:
            tokens.append(Token(lower, "word", start_line, start_col, source, raw=raw))
            if pos >= n or text[pos] not in " \t":
                raise TokenizeError("unclosed string", start_line, start_col, source)
            pos += 1
            col += 1
            str_line, str_col = line, col
            str_start = pos
            while pos < n and text[pos] != '"':
                if text[pos] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                pos += 1
            if pos >= n:
                raise TokenizeError("unclosed string", str_line, str_col, source)
            body = text[str_start:pos]
            tokens.append(Token(body, "string", str_line, str_col, source, raw=body))
            pos += 1
            col += 1
        elif _is_number(lower):
            tokens.append(Token(lower, "number", start_line, start_col, source, raw=raw))
        else:
            tokens.append(Token(lower, "word", start_line, start_col, source, raw=raw))

    return tokens
