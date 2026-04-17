from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from zt.asm import Asm
from zt.debug import SourceEntry
from zt.peephole import (
    DEFAULT_RULES,
    PatternElement,
    PeepholeRule,
    find_match,
    max_pattern_length,
)
from zt.primitives import PRIMITIVES
from zt.tokenizer import Token, tokenize


@dataclass
class Word:
    name: str
    address: int
    kind: Literal["prim", "colon", "variable", "constant"]
    immediate: bool = False
    compile_action: Callable | None = None
    body: list[int] = field(default_factory=list)
    source_file: str | None = None
    source_line: int | None = None


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
        inline_next: bool = False,
    ):
        self.origin = origin
        self.data_stack_top = data_stack_top
        self.return_stack_top = return_stack_top
        self.include_dirs: list[Path] = [Path(d) for d in (include_dirs or [])]
        self.included_files: set[Path] = set()
        self.asm = Asm(origin, inline_next=inline_next)
        self.words: dict[str, Word] = {}
        self.state: Literal["interpret", "compile"] = "interpret"
        self.control_stack: list[tuple[str, Any]] = []
        self.current_word: str | None = None
        self._tokens: list[Token] = []
        self._token_pos: int = 0
        self._host_stack: list[int] = []
        self._pending_strings: list[tuple[str, bytes]] = []
        self._string_counter: int = 0
        self.source_map: list[SourceEntry] = []
        self._current_body: list[int | str] | None = None
        self._body_cell_refs: dict[int, tuple[list[int | str], int]] = {}
        self.warnings: list[str] = []
        self.optimize: bool = optimize
        self.inline_next: bool = inline_next
        self._peephole_rules: tuple[PeepholeRule, ...] = DEFAULT_RULES
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
            (".\"", self._immediate_dot_quote),
            ("s\"", self._immediate_s_quote),
            ("include", self._immediate_include),
            ("require", self._immediate_require),
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
        if self.optimize and self._try_peephole(tok):
            return
        if tok.kind == "word":
            word = self.words.get(tok.value)
            if word is None:
                raise CompileError(f"unknown word '{tok.value}'", tok)
            if word.immediate and word.compile_action:
                word.compile_action(self, tok)
                return
            self._emit_cell(word.address, tok)
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
        self._token_pos += len(rule.pattern) - 1
        self._emit_cell(replacement.address, tok)
        return True

    def _peephole_window(self, first_tok: Token) -> list[PatternElement | None]:
        span = max_pattern_length(self._peephole_rules)
        if span <= 0:
            return []
        tail = self._tokens[self._token_pos:self._token_pos + span - 1]
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
        self._current_body = []
        addr = self.asm.here
        self.asm.call("DOCOL")
        self.words[name] = Word(
            name=name, address=addr, kind="colon",
            source_file=tok.source, source_line=tok.line,
        )

    def _warn_if_redefining(self, name: str, tok: Token) -> None:
        previous = self.words.get(name)
        if previous is None or previous.kind != "colon":
            return
        if previous.source_file is None or previous.source_line is None:
            return
        here = f"{tok.source}:{tok.line}"
        there = f"{previous.source_file}:{previous.source_line}"
        self.warnings.append(
            f"{here}: warning: redefining '{name}' "
            f"(first defined at {there})"
        )

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
        self._emit_cell(exit_addr, tok)
        word = self.words[self.current_word]
        word.body = self._current_body or []
        self._current_body = None
        self.state = "interpret"
        self.current_word = None

    def _compile_literal(self, value: int, tok: Token) -> None:
        lit_addr = self.words["lit"].address
        self._emit_cell(lit_addr, tok)
        self._emit_cell(value & 0xFFFF, tok)

    def _emit_cell(self, value: int | str, tok: Token) -> None:
        offset = len(self.asm.code)
        self.source_map.append(
            SourceEntry(self.asm.here, tok.source, tok.line, tok.col)
        )
        if self._current_body is not None:
            self._body_cell_refs[offset] = (self._current_body, len(self._current_body))
            self._current_body.append(value)
        self.asm.word(value)

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

    def _compile_push_value(self, name: str, value: int, kind: str, tok: Token) -> None:
        addr = self.asm.here
        self.asm.push_hl()
        self.asm.ld_hl_nn(value & 0xFFFF)
        self.asm.jp("NEXT")
        self.words[name] = Word(
            name=name, address=addr, kind=kind,
            source_file=tok.source, source_line=tok.line,
        )

    # --- directives ---

    def _directive_variable(self, _compiler: Compiler, tok: Token) -> None:
        name_tok = self._next_token(tok)
        data_addr = self.asm.here + 4 + 3
        self._compile_push_value(name_tok.value, data_addr, "variable", name_tok)
        self.asm.word(0)

    def _directive_constant(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        name_tok = self._next_token(tok)
        self._compile_push_value(name_tok.value, value, "constant", name_tok)

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
            name=name_tok.value, address=data_addr_placeholder, kind="variable",
            source_file=name_tok.source, source_line=name_tok.line,
        )

    def _directive_comma(self, _compiler: Compiler, tok: Token) -> None:
        value = self._host_pop(tok)
        self._emit_cell(value & 0xFFFF, tok)

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

    def _compile_zbranch_placeholder(self, tok: Token) -> int:
        self._emit_cell(self.words["0branch"].address, tok)
        offset = len(self.asm.code)
        self._emit_cell(0, tok)
        return offset

    def _compile_branch_placeholder(self, tok: Token) -> int:
        self._emit_cell(self.words["branch"].address, tok)
        offset = len(self.asm.code)
        self._emit_cell(0, tok)
        return offset

    def _patch_placeholder(self, offset: int, target: int) -> None:
        self.asm.code[offset] = target & 0xFF
        self.asm.code[offset + 1] = (target >> 8) & 0xFF
        ref = self._body_cell_refs.get(offset)
        if ref is not None:
            body_list, body_idx = ref
            body_list[body_idx] = target

    def _compile_branch_to(self, target: int, tok: Token) -> None:
        self._emit_cell(self.words["branch"].address, tok)
        self._emit_cell(target, tok)

    # --- immediate words: BEGIN/AGAIN ---

    def _immediate_begin(self, _compiler: Compiler, tok: Token) -> None:
        self._push_control("begin", self.asm.here)

    def _immediate_again(self, _compiler: Compiler, tok: Token) -> None:
        target = self._pop_control("begin", tok)
        self._compile_branch_to(target, tok)

    # --- immediate words: IF/THEN/ELSE ---

    def _immediate_if(self, _compiler: Compiler, tok: Token) -> None:
        placeholder = self._compile_zbranch_placeholder(tok)
        self._push_control("if", placeholder)

    def _immediate_then(self, _compiler: Compiler, tok: Token) -> None:
        _tag, value = self._pop_control_any(["if", "else"], tok)
        self._patch_placeholder(value, self.asm.here)

    def _immediate_else(self, _compiler: Compiler, tok: Token) -> None:
        if_placeholder = self._pop_control("if", tok)
        else_placeholder = self._compile_branch_placeholder(tok)
        self._patch_placeholder(if_placeholder, self.asm.here)
        self._push_control("else", else_placeholder)

    # --- immediate words: UNTIL/WHILE/REPEAT ---

    def _immediate_until(self, _compiler: Compiler, tok: Token) -> None:
        target = self._pop_control("begin", tok)
        self._emit_cell(self.words["0branch"].address, tok)
        self._emit_cell(target, tok)

    def _immediate_while(self, _compiler: Compiler, tok: Token) -> None:
        if not self.control_stack:
            raise CompileError(
                "control stack underflow (while)", tok
            )
        placeholder = self._compile_zbranch_placeholder(tok)
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
        self._compile_branch_to(begin_addr, tok)
        self._patch_placeholder(while_placeholder, self.asm.here)

    # --- immediate words: DO/LOOP/+LOOP/LEAVE ---

    def _immediate_do(self, _compiler: Compiler, tok: Token) -> None:
        self._emit_cell(self.words["(do)"].address, tok)
        body_addr = self.asm.here
        self._push_control("do", {"addr": body_addr, "leaves": []})

    def _immediate_loop(self, _compiler: Compiler, tok: Token) -> None:
        do_info = self._pop_control("do", tok)
        self._emit_cell(self.words["(loop)"].address, tok)
        self._emit_cell(do_info["addr"], tok)
        for leave_offset in do_info["leaves"]:
            self._patch_placeholder(leave_offset, self.asm.here)

    def _immediate_plus_loop(self, _compiler: Compiler, tok: Token) -> None:
        do_info = self._pop_control("do", tok)
        self._emit_cell(self.words["(+loop)"].address, tok)
        self._emit_cell(do_info["addr"], tok)
        for leave_offset in do_info["leaves"]:
            self._patch_placeholder(leave_offset, self.asm.here)

    def _immediate_leave(self, _compiler: Compiler, tok: Token) -> None:
        for i in range(len(self.control_stack) - 1, -1, -1):
            if self.control_stack[i][0] == "do":
                self._emit_cell(self.words["unloop"].address, tok)
                placeholder = self._compile_branch_placeholder(tok)
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
        self._compile_literal(word.address, tok)

    def _immediate_recurse(self, _compiler: Compiler, tok: Token) -> None:
        if self.current_word is None:
            raise CompileError("RECURSE outside colon definition", tok)
        word = self.words[self.current_word]
        self._emit_cell(word.address, tok)

    # --- immediate words: string literals ---

    def _next_string_token(self, starter: Token) -> Token:
        if self._token_pos >= len(self._tokens):
            raise CompileError(
                f"{starter.value} without string body", starter,
            )
        tok = self._tokens[self._token_pos]
        if tok.kind != "string":
            raise CompileError(
                f"{starter.value} must be followed by a string, got {tok.kind} '{tok.value}'",
                starter,
            )
        self._token_pos += 1
        return tok

    def _allocate_string(self, data: bytes) -> str:
        label = f"_str_{self._string_counter}"
        self._string_counter += 1
        self._pending_strings.append((label, data))
        return label

    def _compile_string_literal(self, data: bytes, tok: Token) -> tuple[str, int]:
        label = self._allocate_string(data)
        lit_addr = self.words["lit"].address
        self._emit_cell(lit_addr, tok)
        self._emit_cell(label, tok)
        self._emit_cell(lit_addr, tok)
        self._emit_cell(len(data), tok)
        return label, len(data)

    def _immediate_dot_quote(self, _compiler: Compiler, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError('." outside colon definition', tok)
        body = self._next_string_token(tok)
        self._compile_string_literal(body.value.encode("latin-1"), tok)
        self._emit_cell(self.words["type"].address, tok)

    def _immediate_s_quote(self, _compiler: Compiler, tok: Token) -> None:
        if self.state != "compile":
            raise CompileError('s" outside colon definition', tok)
        body = self._next_string_token(tok)
        self._compile_string_literal(body.value.encode("latin-1"), tok)

    def _flush_pending_strings(self) -> None:
        for label, data in self._pending_strings:
            self.asm.label(label)
            for byte_value in data:
                self.asm.byte(byte_value)
        self._pending_strings.clear()

    # --- immediate words: INCLUDE / REQUIRE ---

    def _immediate_include(self, _compiler: Compiler, tok: Token) -> None:
        filename = self._read_filename_token(tok)
        path = self._resolve_include(filename, tok)
        self._include_file(path)

    def _immediate_require(self, _compiler: Compiler, tok: Token) -> None:
        filename = self._read_filename_token(tok)
        path = self._resolve_include(filename, tok)
        if path in self.included_files:
            return
        self._include_file(path)

    def _read_filename_token(self, context_tok: Token) -> str:
        if self._token_pos >= len(self._tokens):
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

    def _resolve_include(self, filename: str, context_tok: Token) -> Path:
        given = Path(filename)
        if given.is_absolute():
            if given.is_file():
                return given.resolve()
            raise CompileError(
                f"include: cannot find '{filename}'", context_tok,
            )
        candidates: list[Path] = []
        current = Path(context_tok.source)
        if current.is_file():
            candidates.append(current.parent / filename)
        candidates.extend(d / filename for d in self.include_dirs)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        searched = "\n  ".join(str(p) for p in candidates) or "(no search paths)"
        raise CompileError(
            f"include: cannot find '{filename}'; searched:\n  {searched}",
            context_tok,
        )

    def _include_file(self, path: Path) -> None:
        self.included_files.add(path)
        text = path.read_text()
        new_tokens = tokenize(text, source=str(path))
        self._tokens[self._token_pos:self._token_pos] = new_tokens

    # --- build ---

    def include_stdlib(self, path: object | None = None) -> None:
        if path is None:
            path = Path(__file__).resolve().parent.parent.parent / "stdlib" / "core.fs"
        else:
            path = Path(path)
        self.included_files.add(path.resolve())
        self.compile_source(path.read_text(), source=str(path))

    def compile_main_call(self) -> None:
        if "main" not in self.words:
            raise CompileError("no 'main' word defined")
        self._flush_pending_strings()
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
        self._resolve_body_cells(image)
        return image

    def _resolve_body_cells(self, image: bytes) -> None:
        for offset, (body_list, body_idx) in self._body_cell_refs.items():
            low = image[offset]
            high = image[offset + 1]
            body_list[body_idx] = low | (high << 8)


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
    inline_next: bool = False,
) -> list[int]:
    from zt.sim import Z80, _read_data_stack

    c = Compiler(origin=origin, optimize=optimize, inline_next=inline_next)
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
    max_ticks: int = 10_000_000,
    stdlib: bool = False,
    optimize: bool = True,
    inline_next: bool = False,
) -> tuple[list[int], bytes]:
    from zt.sim import (
        SPECTRUM_FONT_BASE,
        TEST_FONT,
        Z80,
        _read_data_stack,
        decode_screen_text,
    )

    c = Compiler(origin=origin, optimize=optimize, inline_next=inline_next)
    if stdlib:
        c.include_stdlib()
    c.compile_source(source)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.input_buffer = bytearray(input_buffer)
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
    inline_next: bool = False,
) -> tuple[bytes, Compiler]:
    c = Compiler(origin=origin, data_stack_top=data_stack_top,
                 return_stack_top=return_stack_top, optimize=optimize,
                 inline_next=inline_next)
    c.compile_source(source)
    c.compile_main_call()
    return c.build(), c
