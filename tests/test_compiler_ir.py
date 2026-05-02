"""
Tests that the compiler populates word body cells correctly and that IR resolution produces bytes matching the final image (including the `VERIFY_IR` env-var path).
"""
import os

import pytest

from zt.compile.compiler import Compiler
from zt.compile.ir import (
    Branch,
    ColonRef,
    Label,
    Literal,
    PrimRef,
    StringRef,
    WordLiteral,
    cell_size,
    resolve,
)


def _compile(source: str, stdlib: bool = False) -> Compiler:
    c = Compiler()
    if stdlib:
        c.include_stdlib()
    c.compile_source(source)
    return c


def _compile_built(source: str, stdlib: bool = False) -> tuple[Compiler, bytes]:
    c = Compiler()
    if stdlib:
        c.include_stdlib()
    c.compile_source(source)
    c.compile_main_call()
    image = c.build()
    return c, image


class TestBodyCellsPopulation:

    def test_simple_prim_refs(self):
        c = _compile(": double dup + ; : main halt ;")
        body = c.words["double"].body
        assert body == [PrimRef("dup"), PrimRef("+"), PrimRef("exit")], (
            "simple prim-only colon body should contain PrimRef cells and trailing exit"
        )

    def test_literal_becomes_literal_cell(self):
        c = _compile(": five 5 ; : main halt ;")
        body = c.words["five"].body
        assert body == [Literal(5), PrimRef("exit")], (
            "a numeric literal should become a Literal cell, not LIT+value pair"
        )

    def test_colon_ref_emitted_for_user_word(self):
        c = _compile(": inner dup + ; : outer inner inner ; : main halt ;")
        body = c.words["outer"].body
        assert body == [ColonRef("inner"), ColonRef("inner"), PrimRef("exit")], (
            "calls to user-defined colon words should become ColonRef cells"
        )

    def test_recurse_emits_colon_ref_to_current_word(self):
        c = _compile(": loop-self recurse ; : main halt ;")
        body = c.words["loop-self"].body
        assert ColonRef("loop-self") in body, (
            "RECURSE should emit a ColonRef pointing to the word being defined"
        )


class TestBracketTickEmitsWordLiteral:

    def test_bracket_tick_to_colon_emits_word_literal(self):
        c = _compile(": helper 1 + ; : caller ['] helper drop ; : main halt ;")
        body = c.words["caller"].body
        assert WordLiteral("helper") in body, (
            "['] helper should compile to a WordLiteral cell carrying the target name"
        )

    def test_bracket_tick_does_not_emit_bare_literal_with_address(self):
        c = _compile(": helper 1 + ; : caller ['] helper drop ; : main halt ;")
        body = c.words["caller"].body
        helper_addr = c.words["helper"].address
        bare_literals = [cell for cell in body if isinstance(cell, Literal)]
        assert all(lit.value != helper_addr for lit in bare_literals), (
            "['] helper should not produce a raw Literal(addr); the address is "
            "carried by WordLiteral instead so liveness can follow it"
        )

    def test_bracket_tick_to_primitive_emits_word_literal(self):
        c = _compile(": pusher ['] dup drop ; : main halt ;")
        body = c.words["pusher"].body
        assert WordLiteral("dup") in body, (
            "['] dup should compile to a WordLiteral, even for primitive targets"
        )

    def test_bracket_tick_resolved_bytes_match_eager_address(self):
        c = _compile_built(": helper 1 + ; : caller ['] helper drop ; : main caller halt ;")
        compiler, image = c
        body = compiler.words["caller"].body
        word_addrs = _build_word_addr_table(compiler)
        body_start = compiler.words["caller"].address + 3
        expected = resolve(body, word_addrs, base_address=body_start)
        offset = body_start - compiler.origin
        actual = bytes(image[offset:offset + len(expected)])
        assert expected == actual, (
            "WordLiteral should lower to bytes identical to a bare lit+addr pair"
        )


class TestBodyCellsControlFlow:

    def test_if_then_emits_zbranch_and_label(self):
        c = _compile(": conditional dup if drop then ; : main halt ;")
        body = c.words["conditional"].body
        branches = [cell for cell in body if isinstance(cell, Branch)]
        labels = [cell for cell in body if isinstance(cell, Label)]
        assert len(branches) == 1, "IF/THEN should produce exactly one Branch"
        assert branches[0].kind == "0branch", "IF should emit a 0branch"
        assert len(labels) == 1, "IF/THEN should produce exactly one Label"
        assert branches[0].target == labels[0], (
            "the 0branch target should be the Label emitted at THEN"
        )

    def test_if_else_then_emits_zbranch_then_branch(self):
        c = _compile(": branched dup if drop else dup then ; : main halt ;")
        body = c.words["branched"].body
        branches = [cell for cell in body if isinstance(cell, Branch)]
        kinds = [b.kind for b in branches]
        assert kinds == ["0branch", "branch"], (
            "IF/ELSE/THEN should emit a 0branch (skip-then) then a branch (skip-else)"
        )

    def test_begin_until_emits_zbranch_to_begin_label(self):
        c = _compile(": repeater begin 1- dup 0= until drop ; : main halt ;")
        body = c.words["repeater"].body
        branches = [cell for cell in body if isinstance(cell, Branch)]
        labels = [cell for cell in body if isinstance(cell, Label)]
        assert len(branches) == 1 and branches[0].kind == "0branch", (
            "BEGIN/UNTIL should emit a single 0branch jumping back to BEGIN"
        )
        assert len(labels) == 1, "BEGIN/UNTIL should define one Label at BEGIN"
        assert branches[0].target == labels[0], (
            "UNTIL's 0branch should target the Label at BEGIN"
        )

    def test_begin_again(self):
        c = _compile(": forever begin dup again ; : main halt ;")
        body = c.words["forever"].body
        branches = [cell for cell in body if isinstance(cell, Branch)]
        labels = [cell for cell in body if isinstance(cell, Label)]
        assert len(branches) == 1 and branches[0].kind == "branch", (
            "BEGIN/AGAIN should emit a single unconditional branch back to BEGIN"
        )
        assert branches[0].target == labels[0], (
            "AGAIN's branch should target the Label at BEGIN"
        )

    def test_begin_while_repeat(self):
        c = _compile(
            ": scan begin dup while 1- repeat drop ; : main halt ;"
        )
        body = c.words["scan"].body
        branches = [cell for cell in body if isinstance(cell, Branch)]
        kinds = [b.kind for b in branches]
        assert kinds == ["0branch", "branch"], (
            "BEGIN/WHILE/REPEAT should emit a 0branch (exit) then a branch (loop-back)"
        )

    def test_do_loop_emits_loop_branch(self):
        c = _compile(": count 10 0 do i drop loop ; : main halt ;")
        body = c.words["count"].body
        assert PrimRef("(do)") in body, "DO should emit the (do) primitive"
        loop_branches = [b for b in body if isinstance(b, Branch) and b.kind == "(loop)"]
        assert len(loop_branches) == 1, (
            "DO/LOOP should emit exactly one (loop) branch back to the start of the body"
        )


class TestBodyCellsStrings:

    def test_s_quote_emits_string_ref_and_length(self):
        c = _compile(': greet s" hi" drop drop ; : main halt ;')
        body = c.words["greet"].body
        string_refs = [cell for cell in body if isinstance(cell, StringRef)]
        assert len(string_refs) == 1, 's" should emit exactly one StringRef'
        assert string_refs[0].label.startswith("_str_"), (
            "StringRef label should be a compiler-allocated string label"
        )
        literals = [cell for cell in body if isinstance(cell, Literal)]
        assert any(lit.value == 2 for lit in literals), (
            's" "hi" should emit a Literal(2) for the length'
        )


class TestResolveAgreesWithImage:

    @pytest.mark.parametrize("source", [
        ": double dup + ; : main double halt ;",
        ": five 5 ; : main five halt ;",
        ": conditional dup if drop then ; : main 1 conditional halt ;",
        ": branched dup if drop else dup then ; : main 1 branched halt ;",
        ": count 3 0 do i drop loop ; : main count halt ;",
        ": repeater begin 1- dup 0= until drop ; : main 5 repeater halt ;",
    ])
    def test_body_resolves_to_the_actual_image_bytes(self, source):
        c, image = _compile_built(source)
        word_addrs = _build_word_addr_table(c)
        for name, word in c.words.items():
            if word.kind != "colon" or word.inlined:
                continue
            body_start = word.address + 3
            expected = resolve(word.body, word_addrs, base_address=body_start)
            actual_slice = bytes(image[body_start - c.origin : body_start - c.origin + len(expected)])
            assert expected == actual_slice, (
                f"resolve(body) for '{name}' should equal the image bytes at the body's location"
            )


class TestVerifyIrEnvVar:

    def test_verify_ir_env_var_runs_without_raising(self, monkeypatch):
        monkeypatch.setenv("ZT_VERIFY_IR", "1")
        c = Compiler()
        c.compile_source(
            ": double dup + ; "
            ": branched dup if drop else 0 then ; "
            ": main 1 branched double halt ;"
        )
        c.compile_main_call()
        image = c.build()
        assert len(image) > 0, (
            "build() with ZT_VERIFY_IR=1 should return the same image when IR matches bytes"
        )


def _build_word_addr_table(c: Compiler) -> dict[str, int]:
    addrs: dict[str, int] = {
        name: word.address for name, word in c.words.items()
    }
    addrs.update(c.asm.labels)
    return addrs
