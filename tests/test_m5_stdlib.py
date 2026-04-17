from __future__ import annotations

import pytest

from zt.compiler import compile_and_run_with_output


def _run(source: str) -> tuple[list[int], bytes]:
    return compile_and_run_with_output(source, stdlib=True)


class TestCrAndSpace:

    def test_cr_emits_byte_13(self):
        _, out = _run(': main cr halt ;')
        assert out == b"\r", "cr should emit a single CR"

    def test_space_emits_byte_32(self):
        _, out = _run(': main space halt ;')
        assert out == b" ", "space should emit a single ASCII space"

    def test_cr_and_space_mix(self):
        _, out = _run(': main 65 emit cr 66 emit halt ;')
        assert out == b"A\rB", "A cr B should produce 'A\\rB'"


class TestSpaces:

    @pytest.mark.parametrize("n,expected", [
        (0, b""),
        (1, b" "),
        (3, b"   "),
        (10, b" " * 10),
    ])
    def test_spaces_counts(self, n, expected):
        _, out = _run(f': main {n} spaces halt ;')
        assert out == expected, f"{n} spaces should produce {expected!r}"

    def test_spaces_zero_does_not_underflow(self):
        stack, _ = _run(': main 0 spaces halt ;')
        assert stack == [], "0 spaces should leave an empty stack, no underflow"

    def test_spaces_leaves_stack_clean(self):
        stack, _ = _run(': main 42 5 spaces halt ;')
        assert stack == [42], "spaces should consume only its count, not the value below"


class TestUnsignedPrint:

    @pytest.mark.parametrize("n,expected", [
        (0, b"0 "),
        (1, b"1 "),
        (9, b"9 "),
        (10, b"10 "),
        (42, b"42 "),
        (100, b"100 "),
        (999, b"999 "),
        (1000, b"1000 "),
        (12345, b"12345 "),
        (65535, b"65535 "),
    ])
    def test_u_dot(self, n, expected):
        _, out = _run(f': main {n} u. halt ;')
        assert out == expected, f"{n} u. should produce {expected!r}"

    def test_u_dot_trailing_space(self):
        _, out = _run(': main 7 u. halt ;')
        assert out.endswith(b" "), "u. should emit a trailing space"

    def test_several_u_dots(self):
        _, out = _run(': main 1 u. 22 u. 333 u. halt ;')
        assert out == b"1 22 333 ", (
            "three u.-printed numbers should appear space-separated"
        )


class TestSignedPrint:

    @pytest.mark.parametrize("n,expected", [
        (0, b"0 "),
        (1, b"1 "),
        (-1, b"-1 "),
        (42, b"42 "),
        (-42, b"-42 "),
        (100, b"100 "),
        (-100, b"-100 "),
        (12345, b"12345 "),
        (-12345, b"-12345 "),
        (32767, b"32767 "),
        (-32767, b"-32767 "),
    ])
    def test_dot_signed(self, n, expected):
        _, out = _run(f': main {n} . halt ;')
        assert out == expected, f"{n} . should produce {expected!r}"


class TestSlashMod:

    @pytest.mark.parametrize("a,b,q,r", [
        (10,  3,  3,  1),
        (10, -3, -3,  1),
        (-10, 3, -3, -1),
        (-10,-3,  3, -1),
        ( 7,  2,  3,  1),
        (-7,  2, -3, -1),
        ( 0,  5,  0,  0),
        (100, 10, 10, 0),
    ])
    def test_slash_mod(self, a, b, q, r):
        stack, _ = _run(f': main {a} {b} /mod halt ;')
        expected_r = r if r >= 0 else r + 0x10000
        expected_q = q if q >= 0 else q + 0x10000
        assert stack == [expected_r, expected_q], (
            f"{a} /mod {b} should give r={r}, q={q}"
        )

    @pytest.mark.parametrize("a,b,q", [
        (10, 3, 3),
        (-10, 3, -3),
        (12345, 100, 123),
    ])
    def test_slash(self, a, b, q):
        stack, _ = _run(f': main {a} {b} / halt ;')
        expected_q = q if q >= 0 else q + 0x10000
        assert stack == [expected_q], f"{a} / {b} should give {q}"

    @pytest.mark.parametrize("a,b,r", [
        (10, 3, 1),
        (-10, 3, -1),
        (12345, 100, 45),
    ])
    def test_mod(self, a, b, r):
        stack, _ = _run(f': main {a} {b} mod halt ;')
        expected_r = r if r >= 0 else r + 0x10000
        assert stack == [expected_r], f"{a} mod {b} should give {r}"


class TestPrintArithmetic:

    def test_print_computed_value(self):
        _, out = _run(': main 6 7 * . halt ;')
        assert out == b"42 ", "6*7 . should print '42 '"

    def test_print_negative_computation(self):
        _, out = _run(': main 5 10 - . halt ;')
        assert out == b"-5 ", "5-10 . should print '-5 '"

    def test_print_label_number_cr(self):
        _, out = _run(': main ." x=" 42 . cr halt ;')
        assert out == b"x=42 \r", "label + number + cr should compose"
