"""Milestone-5 end-to-end hello-world tests over the full compile-and-simulate path."""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler, compile_and_run_with_output


HELLO_HALTING = """
: banner
    ." ==================" cr
    ."   FORTH ON Z80"     cr
    ."   cross-compiled"   cr
    ." ==================" cr ;

: count-to-ten
    11 1 do i . loop cr ;

: hello
    banner
    ." counting: " count-to-ten
    ." goodbye!" cr ;

: main  hello halt ;
"""


class TestHelloExampleFile:

    def test_hello_fs_exists(self):
        path = Path(__file__).parent.parent / "examples" / "hello.fs"
        assert path.exists(), "examples/hello.fs should be present"

    def test_hello_fs_compiles(self):
        path = Path(__file__).parent.parent / "examples" / "hello.fs"
        c = Compiler()
        c.include_stdlib()
        c.compile_source(path.read_text(), source=str(path))
        c.compile_main_call()
        image = c.build()
        assert len(image) > 100, "hello.fs compile should yield non-trivial image"


class TestHelloOutput:

    @pytest.fixture(scope="class")
    def hello_output(self):
        _, out = compile_and_run_with_output(HELLO_HALTING, stdlib=True)
        return out

    def test_contains_banner_header(self, hello_output):
        assert b"FORTH ON Z80" in hello_output, "banner text should appear"

    def test_contains_counting_prefix(self, hello_output):
        assert b"counting:" in hello_output, "counting prefix should appear"

    def test_contains_all_ten_numbers(self, hello_output):
        for n in range(1, 11):
            assert f"{n} ".encode() in hello_output, (
                f"hello output should contain '{n} '"
            )

    def test_numbers_in_order(self, hello_output):
        positions = [hello_output.find(f"{n} ".encode()) for n in range(1, 11)]
        assert all(p > 0 for p in positions), "all digits should be found"
        assert positions == sorted(positions), (
            "numbers 1..10 should appear in ascending order in the output"
        )

    def test_contains_goodbye(self, hello_output):
        assert b"goodbye!" in hello_output, "farewell message should appear"

    def test_ends_with_cr_after_goodbye(self, hello_output):
        idx = hello_output.rfind(b"goodbye!")
        tail = hello_output[idx + len(b"goodbye!"):]
        assert b"\r" in tail, "there should be a CR after 'goodbye!'"


class TestIntegrationSmoke:

    def test_string_number_string_mix(self):
        source = """
        : main
            ." answer is: " 42 . ." done" cr halt ;
        """
        _, out = compile_and_run_with_output(source, stdlib=True)
        assert out == b"answer is: 42 done\r", (
            "mixed strings + number + cr should compose cleanly"
        )

    def test_loop_with_dot_prints(self):
        source = ': main 6 0 do i . loop halt ;'
        _, out = compile_and_run_with_output(source, stdlib=True)
        assert out == b"0 1 2 3 4 5 ", (
            "DO loop with . should print each index space-separated"
        )

    def test_conditional_print(self):
        source = """
        : sign-of ( n -- )
            dup 0< if drop ." negative" exit then
            0= if ." zero" exit then
            ." positive" ;
        : main -5 sign-of cr 0 sign-of cr 7 sign-of halt ;
        """
        _, out = compile_and_run_with_output(source, stdlib=True)
        assert out == b"negative\rzero\rpositive", (
            "conditional string output should track runtime value"
        )
