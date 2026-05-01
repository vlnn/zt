"""
Tests for compile-time macros — words that rewrite the token stream
during parsing rather than emitting code. `[TIMES]` is the first one:
`[TIMES] N TOK` splices N copies of TOK back into the stream.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, CompileError


def make_compiler() -> Compiler:
    return Compiler(inline_primitives=False, inline_next=False)


def _compile(source: str) -> Compiler:
    c = make_compiler()
    c.compile_source(source)
    return c


def _word_body(c: Compiler, name: str) -> list:
    return c.words[name].body


class TestTimesInColonBody:

    @pytest.mark.parametrize("count", [0, 1, 2, 3, 7])
    def test_splices_n_copies_of_body_token(self, count):
        c = _compile(f": w [TIMES] {count} dup ;")
        prim_refs = [
            cell for cell in _word_body(c, "w")
            if type(cell).__name__ == "PrimRef" and cell.name == "dup"
        ]
        assert len(prim_refs) == count, (
            f"[TIMES] {count} dup should emit exactly {count} dup refs"
        )

    def test_zero_count_consumes_body_token(self):
        c = _compile(": w [TIMES] 0 dup ;")
        names = [
            cell.name for cell in _word_body(c, "w")
            if type(cell).__name__ == "PrimRef"
        ]
        assert "dup" not in names, (
            "[TIMES] 0 dup should consume the body token without emitting it"
        )

    def test_body_can_be_a_number(self):
        from zt.compile.compiler import compile_and_run
        result = compile_and_run(": main [TIMES] 3 5 + + halt ;")
        assert result == [15], (
            "[TIMES] 3 5 should splice three 5s, summed via two + into 15"
        )

    def test_macro_does_not_appear_as_a_runtime_call(self):
        c = _compile(": w [TIMES] 3 dup ;")
        names = [
            cell.name for cell in _word_body(c, "w")
            if hasattr(cell, "name")
        ]
        assert "[TIMES]" not in names, (
            "[TIMES] is a parse-time macro; it should leave no runtime trace"
        )


class TestTimesInlinerTransparency:

    def test_force_inline_with_times_matches_explicit_repetition(self):
        c1 = _compile(":: w [TIMES] 3 dup ;")
        c2 = _compile(":: w dup dup dup ;")
        assert bytes(c1.asm.code) == bytes(c2.asm.code), (
            "force-inline word built via [TIMES] should compile to identical bytes "
            "as the hand-expanded version"
        )

    def test_plain_colon_with_times_matches_explicit_repetition(self):
        c1 = _compile(": w [TIMES] 3 dup ;")
        c2 = _compile(": w dup dup dup ;")
        assert bytes(c1.asm.code) == bytes(c2.asm.code), (
            "regular colon word built via [TIMES] should compile to identical bytes "
            "as the hand-expanded version"
        )


class TestTimesErrors:

    def test_missing_count_token(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected end of input"):
            c.compile_source(": w [TIMES]")

    def test_missing_body_token(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected end of input"):
            c.compile_source(": w [TIMES] 3")

    def test_non_numeric_count(self):
        c = make_compiler()
        with pytest.raises(CompileError, match=r"\[TIMES\] count must be a number"):
            c.compile_source(": w [TIMES] dup dup ;")

    def test_negative_count(self):
        c = make_compiler()
        with pytest.raises(CompileError, match=r"\[TIMES\] count must be non-negative"):
            c.compile_source(": w [TIMES] -2 dup ;")


class TestDefined:

    def test_defined_word_pushes_one(self):
        from zt.compile.compiler import compile_and_run
        result = compile_and_run("[DEFINED] dup : main halt ;")
        c = make_compiler()
        c.compile_source("[DEFINED] dup")
        assert c._host_stack == [1], (
            "[DEFINED] dup should push 1 because dup is a built-in primitive"
        )
        assert result == [], "trailing test that the compile actually succeeds"

    def test_undefined_word_pushes_zero(self):
        c = make_compiler()
        c.compile_source("[DEFINED] no-such-word")
        assert c._host_stack == [0], (
            "[DEFINED] should push 0 for a name that's not in the dictionary"
        )

    def test_after_user_definition(self):
        c = make_compiler()
        c.compile_source(": my-word ; [DEFINED] my-word")
        assert c._host_stack == [1], (
            "[DEFINED] should see words defined earlier in the same source"
        )

    def test_missing_name_token(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected end of input"):
            c.compile_source("[DEFINED]")


class TestIfElseThen:

    def test_truthy_keeps_branch(self):
        c = _compile("1 [IF] : kept ; [THEN]")
        assert "kept" in c.words, (
            "1 [IF] ... [THEN] should keep the body and define `kept`"
        )

    def test_falsy_skips_branch(self):
        c = _compile("0 [IF] : skipped ; [THEN]")
        assert "skipped" not in c.words, (
            "0 [IF] ... [THEN] should drop the body, leaving `skipped` undefined"
        )

    def test_truthy_with_else_keeps_first_branch(self):
        c = _compile("1 [IF] : aaa ; [ELSE] : bbb ; [THEN]")
        assert "aaa" in c.words, "truthy [IF] should keep the [IF]/[ELSE] branch"
        assert "bbb" not in c.words, "truthy [IF] should skip the [ELSE]/[THEN] branch"

    def test_falsy_with_else_keeps_second_branch(self):
        c = _compile("0 [IF] : aaa ; [ELSE] : bbb ; [THEN]")
        assert "aaa" not in c.words, "falsy [IF] should skip the [IF]/[ELSE] branch"
        assert "bbb" in c.words, "falsy [IF] should keep the [ELSE]/[THEN] branch"

    @pytest.mark.parametrize("outer,inner,expected_kept", [
        (1, 1, ["a", "c"]),
        (1, 0, ["b", "c"]),
        (0, 1, ["d"]),
        (0, 0, ["d"]),
    ], ids=["TT", "TF", "FT", "FF"])
    def test_nested_branches(self, outer, inner, expected_kept):
        source = (
            f"{outer} [IF] "
            f"  {inner} [IF] : a ; [ELSE] : b ; [THEN] : c ; "
            f"[ELSE] : d ; [THEN]"
        )
        c = _compile(source)
        for name in ["a", "b", "c", "d"]:
            present = name in c.words
            should_be_present = name in expected_kept
            assert present == should_be_present, (
                f"with outer={outer} inner={inner}, "
                f"`{name}` should be {'defined' if should_be_present else 'absent'}"
            )

    def test_defined_plus_if_pattern(self):
        c = _compile(
            ": already-here ; "
            "[DEFINED] already-here [IF] : alpha ; [ELSE] : beta ; [THEN] "
            "[DEFINED] never-defined [IF] : gamma ; [ELSE] : delta ; [THEN]"
        )
        assert "alpha" in c.words, (
            "[DEFINED] of an existing word should select the [IF] branch"
        )
        assert "beta" not in c.words, (
            "[DEFINED] of an existing word should skip the [ELSE] branch"
        )
        assert "gamma" not in c.words, (
            "[DEFINED] of an unknown word should skip the [IF] branch"
        )
        assert "delta" in c.words, (
            "[DEFINED] of an unknown word should select the [ELSE] branch"
        )

    def test_if_inside_asm_word(self):
        c = make_compiler()
        c.compile_source(
            "::: w ( -- ) 1 [IF] inc_a [ELSE] dec_a [THEN] ;"
        )
        end = c.asm.here
        body = bytes(c.asm.code[c.words["w"].address - c.origin:end - c.origin])
        assert body == b"\x3c" + b"\xc3\x00\x00", (
            "1 [IF] inc_a [ELSE] dec_a [THEN] inside ::: should emit 0x3C only"
        )

    def test_if_missing_flag_on_host_stack(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="host stack underflow"):
            c.compile_source("[IF] : foo ; [THEN]")


class TestStringMacro:

    def test_emits_one_byte_per_character(self):
        from zt.compile.compiler import compile_and_run
        result = compile_and_run(
            "create banner [string] s\" Hi\" "
            ": main banner c@ banner 1 + c@ halt ;"
        )
        assert result == [ord("H"), ord("i")], (
            "[string] s\" Hi\" should lay down 'H' then 'i' inline at banner's data area"
        )

    def test_accepts_dot_quote_starter(self):
        from zt.compile.compiler import compile_and_run
        result = compile_and_run(
            "create banner [string] .\" Yo\" "
            ": main banner c@ banner 1 + c@ halt ;"
        )
        assert result == [ord("Y"), ord("o")], (
            "[string] .\" Yo\" should behave identically to the s\" form"
        )

    def test_empty_string_emits_nothing(self):
        c = make_compiler()
        before = c.asm.here
        c.compile_source("[string] s\" \"")
        assert c.asm.here == before, (
            "[string] with an empty body should not advance the emission cursor"
        )

    def test_does_not_consult_runtime_string_pool(self):
        c = make_compiler()
        c.compile_source("create t [string] s\" abc\"")
        labels_with_str_prefix = [
            label for label in c.asm.labels if label.startswith("_str_")
        ]
        assert labels_with_str_prefix == [], (
            "[string] should emit bytes inline, not allocate runtime string-pool entries"
        )

    def test_full_byte_range_round_trip(self):
        from zt.compile.compiler import compile_and_run
        result = compile_and_run(
            "create t [string] s\" \xff\" "
            ": main t c@ halt ;"
        )
        assert result == [0xFF], (
            "[string] should preserve high-bit bytes via latin-1 encoding"
        )

    def test_missing_string_starter(self):
        c = make_compiler()
        with pytest.raises(CompileError, match=r"\[string\] expects"):
            c.compile_source("[string] dup")

    def test_eof_after_macro(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected end of input"):
            c.compile_source("[string]")
