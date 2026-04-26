"""
Tests for the `'` (tick) directive: an interpret-state directive that consumes
the next word from the input and pushes its address onto the host (compile-time)
stack, allowing word addresses to be embedded into `create` data blocks.

For words with a data_address (variables, create), `'` pushes the data_address
since that's what the runtime form of the word resolves to. For primitives,
colons, and constants, `'` pushes the code address.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, CompileError, compile_and_run


def _make_compiler() -> Compiler:
    return Compiler(origin=0x8000, inline_primitives=False, inline_next=False)


class TestTickPushesDataAddress:

    def test_tick_pushes_create_data_address_into_cell(self):
        c = _make_compiler()
        c.compile_source(
            "create dst 0 , create src 99 , 88 , create tbl ' src , : main halt ;"
        )
        src_word = c.words["src"]
        tbl_word = c.words["tbl"]
        image = c.build()
        offset = tbl_word.data_address - c.origin
        cell = image[offset] | (image[offset + 1] << 8)
        assert cell == src_word.data_address, (
            f"' src , should embed src's data_address ({src_word.data_address:#06x}) "
            f"in tbl's first cell, got {cell:#06x}"
        )

    def test_tick_pushes_variable_data_address(self):
        c = _make_compiler()
        c.compile_source(
            "variable v create tbl ' v , : main halt ;"
        )
        v_word = c.words["v"]
        tbl_word = c.words["tbl"]
        image = c.build()
        offset = tbl_word.data_address - c.origin
        cell = image[offset] | (image[offset + 1] << 8)
        assert cell == v_word.data_address, (
            "' v , should embed v's data_address (the variable's slot)"
        )


class TestTickPushesCodeAddress:

    def test_tick_pushes_colon_code_address(self):
        c = _make_compiler()
        c.compile_source(
            ": noop ; create tbl ' noop , : main halt ;"
        )
        noop_word = c.words["noop"]
        tbl_word = c.words["tbl"]
        image = c.build()
        offset = tbl_word.data_address - c.origin
        cell = image[offset] | (image[offset + 1] << 8)
        assert cell == noop_word.address, (
            "' noop , should embed noop's code address since colons have no data slot"
        )

    def test_tick_pushes_constant_code_address(self):
        c = _make_compiler()
        c.compile_source(
            "42 constant answer create tbl ' answer , : main halt ;"
        )
        answer_word = c.words["answer"]
        tbl_word = c.words["tbl"]
        image = c.build()
        offset = tbl_word.data_address - c.origin
        cell = image[offset] | (image[offset + 1] << 8)
        assert cell == answer_word.address, (
            "' answer , should embed the constant's pusher address"
        )

    def test_tick_pushes_primitive_address(self):
        c = _make_compiler()
        c.compile_source("create tbl ' dup , : main halt ;")
        dup_word = c.words["dup"]
        tbl_word = c.words["tbl"]
        image = c.build()
        offset = tbl_word.data_address - c.origin
        cell = image[offset] | (image[offset + 1] << 8)
        assert cell == dup_word.address, (
            "' dup , should embed DUP's primitive address"
        )


class TestTickInputErrors:

    def test_tick_unknown_word_raises_compile_error(self):
        c = _make_compiler()
        with pytest.raises(CompileError) as excinfo:
            c.compile_source("create tbl ' nope , : main halt ;")
        assert "nope" in str(excinfo.value), (
            "error message should name the missing word"
        )

    def test_tick_at_end_of_input_raises_compile_error(self):
        c = _make_compiler()
        with pytest.raises(CompileError):
            c.compile_source("create tbl '")


class TestTickRoundTripsThroughRuntime:

    def test_fetch_via_tick_in_table_resolves_to_data(self):
        result = compile_and_run(
            "create payload 1234 , "
            "create tbl ' payload , "
            ": main tbl @ @ halt ;"
        )
        assert result == [1234], (
            "fetching tbl's first cell should give payload's data_address; "
            "fetching that should give 1234"
        )

    def test_three_addresses_in_a_row(self):
        result = compile_and_run(
            "create a 100 , "
            "create b 200 , "
            "create c 300 , "
            "create tbl ' a , ' b , ' c , "
            ": main tbl 2 + @ @ halt ;"
        )
        assert result == [200], (
            "tbl[1] should hold b's data_address; fetching it gives b's value 200"
        )
