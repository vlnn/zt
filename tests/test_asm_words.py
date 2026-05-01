"""
Tests for the `:::` assembler-word directive: defines a primitive whose body
is straight-line Z80 written using `OPCODES` mnemonics, terminated by `;`.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, CompileError


def make_compiler() -> Compiler:
    return Compiler(inline_primitives=False, inline_next=False)


def _body_bytes(c: Compiler, name: str) -> bytes:
    word = c.words[name]
    end = next(
        (w.address for w in c.words.values() if w.address > word.address),
        c.asm.here,
    )
    start = word.address - c.origin
    stop = end - c.origin
    return bytes(c.asm.code[start:stop])


class TestEmptyBody:

    def test_defines_a_primitive_word(self):
        c = make_compiler()
        c.compile_source("::: nop-word ( -- ) ;")
        assert "nop-word" in c.words, "::: should register the named word"
        assert c.words["nop-word"].kind == "prim", (
            "::: should define a primitive (no DOCOL prologue)"
        )

    def test_body_is_just_dispatch(self):
        c = make_compiler()
        c.compile_source("::: nop-word ( -- ) ;")
        body = _body_bytes(c, "nop-word")
        assert body == b"\xc3" + b"\x00\x00", (
            "empty ::: body should be exactly `JP NEXT` (dispatch with inline_next=False)"
        )

    def test_address_points_at_emitted_code(self):
        c = make_compiler()
        before = c.asm.here
        c.compile_source("::: nop-word ( -- ) ;")
        assert c.words["nop-word"].address == before, (
            "::: should record the address of the first emitted byte"
        )


class TestMnemonicEmission:

    def test_single_no_operand_op_emits_its_byte(self):
        c = make_compiler()
        c.compile_source("::: just-a ( -- ) ld_a_l ;")
        body = _body_bytes(c, "just-a")
        assert body == b"\x7d" + b"\xc3\x00\x00", (
            "ld_a_l should emit 0x7D, then dispatch as JP NEXT"
        )

    def test_nn_operand_consumes_host_stack(self):
        c = make_compiler()
        c.compile_source("::: load-3000 ( -- ) 3000 ld_hl_nn ;")
        body = _body_bytes(c, "load-3000")
        assert body == b"\x21\xb8\x0b" + b"\xc3\x00\x00", (
            "3000 ld_hl_nn should emit 0x21 followed by little-endian 3000"
        )

    @pytest.mark.parametrize("source,expected", [
        ("::: w ( -- ) ld_a_l ;",                 b"\x7d"),
        ("::: w ( -- ) 65 ld_a_n ;",              b"\x3e\x41"),
        ("::: w ( -- ) 3000 ld_hl_nn ;",          b"\x21\xb8\x0b"),
        ("::: w ( -- ) ex_de_hl ;",               b"\xeb"),
        ("::: w ( -- ) pop_hl ;",                 b"\xe1"),
        ("::: w ( -- ) ld_a_l ld_ind_hl_a ;",     b"\x7d\x77"),
    ], ids=["no-operand", "n", "nn", "ex_de_hl", "pop_hl", "two-ops"])
    def test_emission_table(self, source, expected):
        c = make_compiler()
        c.compile_source(source)
        body = _body_bytes(c, "w")
        assert body == expected + b"\xc3\x00\x00", (
            f"body of {source!r} should emit {expected!r} then dispatch"
        )

    def test_full_x_to_3000_example(self):
        c = make_compiler()
        c.compile_source(
            "::: x-to-3000 ( x -- ) ld_a_l 3000 ld_hl_nn ld_ind_hl_a pop_hl ;"
        )
        body = _body_bytes(c, "x-to-3000")
        assert body == b"\x7d\x21\xb8\x0b\x77\xe1" + b"\xc3\x00\x00", (
            "x-to-3000 should compile to LD A,L; LD HL,3000; LD (HL),A; POP HL; JP NEXT"
        )


class TestErrors:

    def test_unknown_mnemonic_inside_body(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unknown asm mnemonic 'lda'"):
            c.compile_source("::: bad ( -- ) lda ;")

    def test_unclosed_definition(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected end of input"):
            c.compile_source("::: bad ( -- ) ld_a_l")

    def test_nested_triple_colon(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="nested :::"):
            c.compile_source("::: outer ( -- ) ::: inner ( -- ) ; ;")

    def test_inside_colon_definition(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="::: not allowed inside"):
            c.compile_source(": outer ::: inner ( -- ) ; ;")

    def test_missing_immediate_operand(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="host stack underflow"):
            c.compile_source("::: bad ( -- ) ld_hl_nn ;")


class TestEndToEnd:

    def test_x_to_3000_actually_writes_to_memory(self):
        from zt.compile.compiler import compile_and_run_with_output  # noqa: F401
        from zt.sim import Z80
        c = make_compiler()
        c.compile_source(
            "::: x-to-3000 ( x -- ) ld_a_l 3000 ld_hl_nn ld_ind_hl_a pop_hl ;\n"
            ": main 42 x-to-3000 halt ;"
        )
        c.compile_main_call()
        image = c.build()
        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "program with halt should reach the halted state"
        assert m.mem[3000] == 42, (
            "x-to-3000 with TOS=42 should leave 42 at address 3000"
        )

    def test_asm_word_callable_from_colon_word(self):
        from zt.sim import Z80
        c = make_compiler()
        c.compile_source(
            "::: store-low ( x -- ) ld_a_l 3000 ld_hl_nn ld_ind_hl_a pop_hl ;\n"
            ": store-twice 7 store-low 11 store-low ;\n"
            ": main store-twice halt ;"
        )
        c.compile_main_call()
        image = c.build()
        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run()
        assert m.mem[3000] == 11, (
            "second store-low should overwrite first, leaving 11 at 3000"
        )


class TestTimesInsideAsmWord:

    def test_repeats_a_no_operand_mnemonic(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) [TIMES] 3 inc_a ;")
        body = _body_bytes(c, "w")
        assert body == b"\x3c\x3c\x3c" + b"\xc3\x00\x00", (
            "[TIMES] 3 inc_a inside ::: should emit three 0x3C bytes then dispatch"
        )

    def test_matches_explicit_repetition_byte_for_byte(self):
        c1 = make_compiler()
        c1.compile_source("::: a ( -- ) [TIMES] 4 inc_a ;")
        c2 = make_compiler()
        c2.compile_source("::: a ( -- ) inc_a inc_a inc_a inc_a ;")
        assert bytes(c1.asm.code) == bytes(c2.asm.code), (
            "::: bodies built via [TIMES] should match hand-expanded ones byte-for-byte"
        )

    def test_zero_count_inside_asm(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) [TIMES] 0 inc_a ;")
        body = _body_bytes(c, "w")
        assert body == b"\xc3\x00\x00", (
            "[TIMES] 0 inside ::: should consume the body and emit only dispatch"
        )


class TestRawBytesAndWords:

    def test_byte_emits_single_byte(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) 42 byte ;")
        body = _body_bytes(c, "w")
        assert body == b"\x2a" + b"\xc3\x00\x00", (
            "42 byte inside ::: should emit a single 0x2A byte then dispatch"
        )

    def test_word_emits_little_endian_pair(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) 12345 word ;")
        body = _body_bytes(c, "w")
        assert body == b"\x39\x30" + b"\xc3\x00\x00", (
            "12345 word inside ::: should emit 0x39 0x30 (LE) then dispatch"
        )

    @pytest.mark.parametrize("source,expected", [
        ("::: w ( -- ) 0 byte ;",      b"\x00"),
        ("::: w ( -- ) 255 byte ;",    b"\xff"),
        ("::: w ( -- ) 0 word ;",      b"\x00\x00"),
        ("::: w ( -- ) 65535 word ;",  b"\xff\xff"),
    ], ids=["byte-zero", "byte-max", "word-zero", "word-max"])
    def test_byte_and_word_boundary_values(self, source, expected):
        c = make_compiler()
        c.compile_source(source)
        body = _body_bytes(c, "w")
        assert body == expected + b"\xc3\x00\x00", (
            f"{source!r} should emit {expected!r} then dispatch"
        )

    def test_byte_missing_operand(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="host stack underflow"):
            c.compile_source("::: w ( -- ) byte ;")

    def test_byte_inside_colon_definition_is_unknown(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unknown word 'byte'"):
            c.compile_source(": w byte ;")
