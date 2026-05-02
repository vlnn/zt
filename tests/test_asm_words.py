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
    """Bytes the user wrote between ::: name and ; — dispatch tail stripped."""
    word = c.words[name]
    end = next(
        (w.address for w in c.words.values() if w.address > word.address),
        c.asm.here,
    )
    start = word.address - c.origin
    stop = end - c.origin - 3  # strip trailing JP NEXT (3 bytes)
    resolved = c.asm.resolve()
    return bytes(resolved[start:stop])


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
        assert body == b"", (
            "empty ::: body should emit no user bytes (dispatch tail handled separately)"
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
        assert body == b"\x7d", (
            "ld_a_l should emit 0x7D, then dispatch as JP NEXT"
        )

    def test_nn_operand_consumes_host_stack(self):
        c = make_compiler()
        c.compile_source("::: load-3000 ( -- ) 3000 ld_hl_nn ;")
        body = _body_bytes(c, "load-3000")
        assert body == b"\x21\xb8\x0b", (
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
        assert body == expected, (
            f"body of {source!r} should emit {expected!r} then dispatch"
        )

    def test_full_x_to_3000_example(self):
        c = make_compiler()
        c.compile_source(
            "::: x-to-3000 ( x -- ) ld_a_l 3000 ld_hl_nn ld_ind_hl_a pop_hl ;"
        )
        body = _body_bytes(c, "x-to-3000")
        assert body == b"\x7d\x21\xb8\x0b\x77\xe1", (
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
        assert body == b"\x3c\x3c\x3c", (
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
        assert body == b"", (
            "[TIMES] 0 inside ::: should consume the body without emitting any user bytes"
        )


class TestRawBytesAndWords:

    def test_byte_emits_single_byte(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) 42 byte ;")
        body = _body_bytes(c, "w")
        assert body == b"\x2a", (
            "42 byte inside ::: should emit a single 0x2A byte then dispatch"
        )

    def test_word_emits_little_endian_pair(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) 12345 word ;")
        body = _body_bytes(c, "w")
        assert body == b"\x39\x30", (
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
        assert body == expected, (
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


class TestLabels:

    def test_label_declares_target_for_backward_jump(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) label loop nop jp loop ;")
        body = _body_bytes(c, "w")
        loop_addr = c.words["w"].address
        lo, hi = loop_addr & 0xFF, (loop_addr >> 8) & 0xFF
        assert body == bytes([0x00, 0xC3, lo, hi]), (
            "label loop / nop / jp loop should emit nop then a 3-byte jump back to loop"
        )

    def test_forward_jump_resolves_at_definition_end(self):
        c = make_compiler()
        c.compile_source("::: w ( -- ) jp ahead nop label ahead ;")
        body = _body_bytes(c, "w")
        ahead_addr = c.words["w"].address + 4
        lo, hi = ahead_addr & 0xFF, (ahead_addr >> 8) & 0xFF
        assert body == bytes([0xC3, lo, hi, 0x00]), (
            "forward jp to ahead should patch the address to point past the nop"
        )

    @pytest.mark.parametrize("mnemonic,opcode", [
        ("jp",    0xC3),
        ("jp_z",  0xCA),
        ("jp_nz", 0xC2),
        ("jp_p",  0xF2),
        ("jp_m",  0xFA),
        ("call",  0xCD),
    ], ids=["jp", "jp_z", "jp_nz", "jp_p", "jp_m", "call"])
    def test_absolute_jump_family(self, mnemonic, opcode):
        c = make_compiler()
        c.compile_source(f"::: w ( -- ) label here {mnemonic} here ;")
        body = _body_bytes(c, "w")
        here_addr = c.words["w"].address
        lo, hi = here_addr & 0xFF, (here_addr >> 8) & 0xFF
        assert body == bytes([opcode, lo, hi]), (
            f"{mnemonic} here should emit {opcode:#x} followed by little-endian here address"
        )

    @pytest.mark.parametrize("mnemonic,opcode", [
        ("jr",    0x18),
        ("jr_z",  0x28),
        ("jr_nz", 0x20),
        ("jr_c",  0x38),
        ("jr_nc", 0x30),
        ("djnz",  0x10),
    ], ids=["jr", "jr_z", "jr_nz", "jr_c", "jr_nc", "djnz"])
    def test_relative_jump_family(self, mnemonic, opcode):
        c = make_compiler()
        c.compile_source(f"::: w ( -- ) label here nop {mnemonic} here ;")
        body = _body_bytes(c, "w")
        assert body[0] == 0x00, "first byte should be the nop at label here"
        assert body[1] == opcode, f"second instruction should start with {opcode:#x}"
        assert body[2] == 0xFD, (
            f"{mnemonic} here from offset 1 to label at offset 0 should encode -3 as 0xFD"
        )

    def test_duplicate_label_inside_one_body(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="duplicate label"):
            c.compile_source("::: w ( -- ) label x nop label x ;")

    def test_unresolved_label_at_semicolon(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="undefined label 'missing'"):
            c.compile_source("::: w ( -- ) jp missing ;")

    def test_labels_are_scoped_to_definition(self):
        c = make_compiler()
        c.compile_source(
            "::: a ( -- ) label loop jp loop ;\n"
            "::: b ( -- ) label loop jp loop ;"
        )
        assert "a" in c.words and "b" in c.words, (
            "the same label name in two ::: bodies should not collide"
        )

    def test_label_must_have_a_name(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="label name must be a word"):
            c.compile_source("::: w ( -- ) label 42 ;")

    def test_jump_target_must_be_a_word(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="label name must be a word"):
            c.compile_source("::: w ( -- ) jp 42 ;")


class TestLabelsEndToEnd:

    def test_loop_increments_memory_cell(self):
        from zt.sim import Z80
        c = make_compiler()
        c.compile_source(
            "::: bump-3000-n-times ( n -- )\n"
            "  ld_b_l 3000 ld_hl_nn\n"
            "  label top\n"
            "    ld_a_ind_hl inc_a ld_ind_hl_a\n"
            "    djnz top\n"
            "  pop_hl ;\n"
            ": main 5 bump-3000-n-times halt ;"
        )
        c.compile_main_call()
        image = c.build()
        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "program should halt cleanly"
        assert m.mem[3000] == 5, (
            "djnz loop with B=5 should increment (3000) exactly 5 times"
        )


class TestCrossBodyByName:

    def test_call_resolves_to_other_word(self):
        c = make_compiler()
        c.compile_source(
            "::: helper ( -- ) inc_a ;\n"
            "::: caller ( -- ) call helper ;"
        )
        body = _body_bytes(c, "caller")
        helper_addr = c.words["helper"].address
        lo, hi = helper_addr & 0xFF, (helper_addr >> 8) & 0xFF
        assert body == bytes([0xCD, lo, hi]), (
            "call helper should emit 0xCD followed by helper's address (little-endian)"
        )

    def test_jp_resolves_to_other_word(self):
        c = make_compiler()
        c.compile_source(
            "::: target ( -- ) inc_a ;\n"
            "::: caller ( -- ) jp target ;"
        )
        body = _body_bytes(c, "caller")
        target_addr = c.words["target"].address
        lo, hi = target_addr & 0xFF, (target_addr >> 8) & 0xFF
        assert body == bytes([0xC3, lo, hi]), (
            "jp target should emit 0xC3 followed by target's address"
        )

    @pytest.mark.parametrize("mnemonic,opcode", [
        ("jp",    0xC3),
        ("jp_z",  0xCA),
        ("jp_nz", 0xC2),
        ("jp_p",  0xF2),
        ("jp_m",  0xFA),
        ("call",  0xCD),
    ])
    def test_all_absolute_jumps_resolve_word_names(self, mnemonic, opcode):
        c = make_compiler()
        c.compile_source(
            "::: t ( -- ) inc_a ;\n"
            f"::: w ( -- ) {mnemonic} t ;"
        )
        body = _body_bytes(c, "w")
        addr = c.words["t"].address
        assert body == bytes([opcode, addr & 0xFF, (addr >> 8) & 0xFF]), (
            f"{mnemonic} t should resolve t to its dictionary address"
        )

    def test_local_label_with_word_name_uses_word(self):
        c = make_compiler()
        c.compile_source(
            "::: helper ( -- ) inc_a ;\n"
            "::: w ( -- ) call helper ;"
        )
        helper_addr = c.words["helper"].address
        body = _body_bytes(c, "w")
        assert body[1] == helper_addr & 0xFF and body[2] == (helper_addr >> 8) & 0xFF, (
            "when name matches a global word, call should resolve to the word's address"
        )

    def test_label_declaration_is_always_local(self):
        c = make_compiler()
        c.compile_source(
            "::: dup-the-data ( -- ) inc_a ;\n"
            "::: w ( -- ) label dup-the-data jr dup-the-data ;"
        )
        body = _body_bytes(c, "w")
        assert body == bytes([0x18, 0xFE]), (
            "label whose name matches a word should still declare a local; "
            "jr uses the local (jr to self at offset 0 from PC after = -2 = 0xFE)"
        )

    def test_call_to_undeclared_name_errors_at_semicolon(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="undefined label 'no-such-thing'"):
            c.compile_source("::: w ( -- ) call no-such-thing ;")

    def test_jp_tail_call_runtime_correctness(self):
        from zt.sim import Z80
        c = make_compiler()
        c.compile_source(
            "::: store-1-at-3000 ( -- )\n"
            "  1 ld_a_n  3000 ld_hl_nn  ld_ind_hl_a ;\n"
            "::: store-2-at-3001-then-tail ( -- )\n"
            "  2 ld_a_n  3001 ld_hl_nn  ld_ind_hl_a\n"
            "  jp store-1-at-3000 ;\n"
            ": main store-2-at-3001-then-tail halt ;"
        )
        c.compile_main_call()
        image = c.build()
        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "program should halt cleanly"
        assert m.mem[3001] == 2, "first half: 2 should land at 3001"
        assert m.mem[3000] == 1, (
            "second half: jp tail-call to store-1-at-3000 should run, "
            "leaving 1 at 3000; subsequent dispatch should return to main"
        )


class TestTickInsideAsmWord:

    def test_tick_pushes_word_address_to_host_stack(self):
        c = make_compiler()
        c.compile_source(
            ": helper ;\n"
            "::: w ( -- ) ' helper ld_hl_nn pop_hl ;"
        )
        helper_addr = c.words["helper"].address
        body = _body_bytes(c, "w")
        assert body == bytes([0x21, helper_addr & 0xFF, (helper_addr >> 8) & 0xFF, 0xE1]), (
            "' helper ld_hl_nn should emit LD HL, <helper-addr>; pop_hl follows"
        )

    def test_tick_inside_asm_runtime(self):
        from zt.sim import Z80
        c = make_compiler()
        c.compile_source(
            ": target ;\n"
            "::: store-target-addr ( -- )\n"
            "  ' target ld_hl_nn  3000 ld_ind_nn_hl ;\n"
            ": main store-target-addr halt ;"
        )
        c.compile_main_call()
        image = c.build()
        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run()
        target_addr = c.words["target"].address
        stored_lo = m.mem[3000]
        stored_hi = m.mem[3001]
        assert (stored_hi << 8) | stored_lo == target_addr, (
            f"' target ld_hl_nn should load HL with target's address ({target_addr:#x}); "
            "store at 3000 should reflect that address little-endian"
        )

    def test_tick_unknown_word_in_asm(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unknown word 'no-such'"):
            c.compile_source("::: w ( -- ) ' no-such ld_hl_nn ;")


class TestBracketTickInInlinedColon:

    def test_bracket_tick_in_force_inline_compiles_to_word_literal(self):
        c = make_compiler()
        c.compile_source(": target ;\n:: w ['] target ;")
        body = c.words["w"].body
        from zt.compile.ir import WordLiteral
        assert WordLiteral("target") in body, (
            "['] target inside :: should compile a WordLiteral cell carrying "
            "the target's name so liveness can follow the reference"
        )

    def test_bracket_tick_runtime_in_inlined_word(self):
        from zt.compile.compiler import compile_and_run
        result = compile_and_run(
            ": target ;\n"
            ":: push-target-addr ['] target ;\n"
            ": main push-target-addr halt ;"
        )
        assert len(result) == 1, "stack should have exactly one value pushed by ['] target"
        assert result[0] != 0, (
            "['] target should push target's actual address, not zero"
        )
