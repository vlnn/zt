"""Milestone-5 tests for `KEY` / `EMIT` keyboard echo using the simulator's input buffer."""
from __future__ import annotations

from zt.compile.compiler import compile_and_run_with_output


class TestKeyEcho:

    def test_single_key_echo(self):
        source = ': main key emit halt ;'
        _, out = compile_and_run_with_output(source, input_buffer=b"Q")
        assert out == b"Q", "key emit should echo the one buffered char"

    def test_three_key_echo(self):
        source = ': main key emit key emit key emit halt ;'
        _, out = compile_and_run_with_output(source, input_buffer=b"ABC")
        assert out == b"ABC", "three key-emit cycles should echo three chars"

    def test_key_until_null(self):
        source = """
        : main
            begin key dup while emit repeat drop halt ;
        """
        _, out = compile_and_run_with_output(source, input_buffer=b"hi!")
        assert out == b"hi!", "begin/while on key should echo until buffer empty"


class TestKeyQueryAndKey:

    def test_key_query_guards_key(self):
        source = """
        : main
            key? if key emit else ." none" then halt ;
        """
        _, with_input = compile_and_run_with_output(source, input_buffer=b"Z")
        _, no_input = compile_and_run_with_output(source, input_buffer=b"")
        assert with_input == b"Z", "key? true path should emit the char"
        assert no_input == b"none", "key? false path should print the fallback"
