"""
Milestone-5 tests for `."` and `s"` string literals, their use inside colon definitions, error cases, and storage layout.
"""
from __future__ import annotations

import pytest

from zt.compiler import (
    Compiler,
    CompileError,
    compile_and_run_with_output,
)


class TestDotQuoteBasics:

    def test_simple_string(self):
        stack, out = compile_and_run_with_output(
            ': main ." hello" halt ;'
        )
        assert out == b"hello", '." hello" should emit "hello"'
        assert stack == [], '." should leave stack clean'

    def test_empty_string(self):
        stack, out = compile_and_run_with_output(
            ': main ." " halt ;'
        )
        assert out == b"", '." "" should emit nothing'
        assert stack == [], "empty string should leave stack clean"

    def test_two_strings(self):
        stack, out = compile_and_run_with_output(
            ': main ." foo" ." bar" halt ;'
        )
        assert out == b"foobar", "two dot-quotes should concatenate"

    def test_string_around_computation(self):
        stack, out = compile_and_run_with_output(
            ': main ." x=" 65 emit ." done" halt ;'
        )
        assert out == b"x=Adone", "dot-quote should mix with EMIT"

    @pytest.mark.parametrize("body", [
        "hello",
        "Hello, World!",
        "1234567890",
        "a",
        "short body under 32 chars",
    ])
    def test_various_bodies(self, body):
        stack, out = compile_and_run_with_output(
            f': main ." {body}" halt ;'
        )
        assert out == body.encode("latin-1"), (
            f'." {body}" should emit {body!r}'
        )


class TestDotQuoteInColonWords:

    def test_called_from_main(self):
        stack, out = compile_and_run_with_output(
            ': greet ." hi" ; : main greet halt ;'
        )
        assert out == b"hi", "dot-quote inside non-main colon should work"

    def test_called_twice(self):
        stack, out = compile_and_run_with_output(
            ': greet ." hi" ; : main greet greet halt ;'
        )
        assert out == b"hihi", "calling a string-printing word twice should produce twice the output"


class TestSQuoteBasics:

    def test_s_quote_pushes_addr_and_len(self):
        stack, out = compile_and_run_with_output(
            ': main s" abc" halt ;'
        )
        assert out == b"", 's" should not print'
        assert len(stack) == 2, 's" should push (addr, len)'
        assert stack[-1] == 3, 'top of stack after s" abc" should be length 3'

    def test_s_quote_with_type(self):
        stack, out = compile_and_run_with_output(
            ': main s" wxyz" type halt ;'
        )
        assert out == b"wxyz", 's" ... type should emit the string'
        assert stack == [], "type should consume (addr len)"

    def test_s_quote_empty(self):
        stack, out = compile_and_run_with_output(
            ': main s" " halt ;'
        )
        assert len(stack) == 2, 'empty s" should still push (addr, 0)'
        assert stack[-1] == 0, 'empty s" should have length 0'


class TestStringErrors:

    def test_dot_quote_outside_colon_raises(self):
        c = Compiler()
        with pytest.raises(CompileError, match=r'\." outside colon'):
            c.compile_source('." hello"')

    def test_s_quote_outside_colon_raises(self):
        c = Compiler()
        with pytest.raises(CompileError, match=r's" outside colon'):
            c.compile_source('s" hello"')

    def test_dot_quote_works_between_colon_defs(self):
        stack, out = compile_and_run_with_output(
            ': a ." A" ; : b ." B" ; : main a b halt ;'
        )
        assert out == b"AB", "strings in separate colon defs should both work"


class TestStringStorageLayout:

    def test_strings_stored_once_per_occurrence(self):
        c = Compiler()
        c.compile_source(': main ." hi" ." hi" halt ;')
        c.compile_main_call()
        image = c.build()
        assert image.count(b"hi") >= 2, (
            "two separate occurrences of the same string should each allocate bytes"
        )

    def test_string_data_before_start(self):
        c = Compiler()
        c.compile_source(': main ." hello" halt ;')
        c.compile_main_call()
        image = c.build()
        start_offset = c.words["_start"].address - c.origin
        hello_offset = image.find(b"hello")
        assert 0 <= hello_offset < start_offset, (
            "string bytes should be placed before _start"
        )
