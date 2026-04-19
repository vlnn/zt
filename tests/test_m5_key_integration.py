"""Milestone-5 tests for `KEY` / `EMIT` keyboard echo under the real-hardware port-scan model."""
from __future__ import annotations

from zt.compile.compiler import compile_and_run_with_output


class TestKeyEcho:

    def test_single_key_echo(self):
        source = ': main key emit halt ;'
        _, out = compile_and_run_with_output(source, input_buffer=b"Q")
        assert out == b"Q", "key emit should echo the held key"

    def test_held_key_repeats_on_repeated_calls(self):
        source = ': main key emit key emit key emit halt ;'
        _, out = compile_and_run_with_output(source, pressed_keys={ord("A")})
        assert out == b"AAA", (
            "three key-emit cycles with A held continuously should echo AAA; "
            "this is real-keyboard semantics, unlike the old hook model"
        )

    def test_key_on_empty_keyboard_returns_zero(self):
        source = """
        : main
            key dup if emit else 78 emit then halt ;
        """
        _, out = compile_and_run_with_output(source)
        assert out == b"N", "KEY with nothing held should return 0 (false branch)"


class TestKeyQueryAndKey:

    def test_key_query_guards_key(self):
        source = """
        : main
            key? if key emit else ." none" then halt ;
        """
        _, with_input = compile_and_run_with_output(source, input_buffer=b"Z")
        _, no_input = compile_and_run_with_output(source)
        assert with_input == b"Z", "key? true path should emit the held char"
        assert no_input == b"none", "key? false path should print the fallback"

    def test_key_state_distinguishes_held_from_other_keys(self):
        source = """
        : main
            65 key-state if 43 emit else 45 emit then
            66 key-state if 43 emit else 45 emit then halt ;
        """
        _, out = compile_and_run_with_output(source, pressed_keys={ord("A")})
        assert out == b"+-", (
            "with only A held, A's key-state is true (+) and B's is false (-)"
        )

    def test_key_state_detects_simultaneous_keys(self):
        source = """
        : main
            65 key-state if 43 emit then
            83 key-state if 43 emit then
            68 key-state if 43 emit then halt ;
        """
        _, out = compile_and_run_with_output(
            source, pressed_keys={ord("A"), ord("S"), ord("D")},
        )
        assert out == b"+++", (
            "A, S, D held together should each register as pressed via key-state"
        )
