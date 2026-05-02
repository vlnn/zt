"""Tests for the EXECUTE primitive: byte layout, behaviour over primitives /
colon words / constants, and the :: inlining rejection."""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitives import PRIMITIVES, create_execute
from zt.compile.compiler import CompileError, compile_and_run


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _compile_primitive(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


class TestExecuteBytes:

    def test_byte_sequence_is_ex_pop_push_ret(self):
        out = _compile_primitive(create_execute)
        assert out[:4] == bytes([0xEB, 0xE1, 0xD5, 0xC9]), (
            "EXECUTE should be EX DE,HL; POP HL; PUSH DE; RET — "
            "the four-byte indirect-call dispatch idiom"
        )

    def test_total_body_is_four_bytes(self):
        out = _compile_primitive(create_execute)
        assert len(out) == 4, (
            "EXECUTE must be exactly four bytes; got " + str(list(out))
        )

    def test_alias_points_to_primary(self):
        a = _asm_with_next()
        create_execute(a)
        assert a.labels["execute"] == a.labels["EXECUTE"], (
            "lowercase 'execute' alias should resolve to the same address as 'EXECUTE'"
        )

    def test_appears_in_full_primitive_set(self):
        assert create_execute in PRIMITIVES, (
            "create_execute should be registered in the PRIMITIVES list"
        )


class TestExecuteRunsPrimitives:

    def test_execute_dup_with_value_below_xt(self):
        result = compile_and_run(": main 42 ['] dup execute halt ;")
        assert result == [42, 42], (
            "['] dup execute should call dup, leaving the value below xt duplicated"
        )

    def test_execute_drop(self):
        result = compile_and_run(": main 7 99 ['] drop execute halt ;")
        assert result == [7], (
            "['] drop execute should drop the value below xt"
        )

    def test_execute_plus(self):
        result = compile_and_run(": main 10 32 ['] + execute halt ;")
        assert result == [42], (
            "['] + execute should add the two values below xt"
        )

    @pytest.mark.parametrize("a,b,expected", [
        (3, 4, 7),
        (100, 200, 300),
        (0, 5, 5),
    ])
    def test_execute_plus_parametrised(self, a, b, expected):
        result = compile_and_run(f": main {a} {b} ['] + execute halt ;")
        assert result == [expected], (
            f"['] + execute on ({a}, {b}) should leave {expected}"
        )


class TestExecuteRunsColonWords:

    def test_execute_simple_colon(self):
        result = compile_and_run(
            ": double dup + ; "
            ": main 21 ['] double execute halt ;"
        )
        assert result == [42], (
            "['] double execute should run the colon body and return"
        )

    def test_execute_chained_colon(self):
        result = compile_and_run(
            ": double  dup + ; "
            ": quad    double double ; "
            ": main 5 ['] quad execute halt ;"
        )
        assert result == [20], (
            "EXECUTE of a colon that calls other colons should compose normally"
        )

    def test_execute_returns_to_caller(self):
        result = compile_and_run(
            ": double dup + ; "
            ": main 10 ['] double execute 7 + halt ;"
        )
        assert result == [27], (
            "after EXECUTE returns, the caller's threaded interpreter should "
            "continue with the next cell (here: + 7)"
        )


class TestExecuteRunsConstants:

    def test_execute_constant_pushes_value(self):
        result = compile_and_run(
            "42 constant answer "
            ": main ['] answer execute halt ;"
        )
        assert result == [42], (
            "EXECUTE of a constant's xt should run its pusher and leave the value"
        )

    def test_execute_constant_after_existing_stack(self):
        result = compile_and_run(
            "100 constant hundred "
            ": main 7 ['] hundred execute halt ;"
        )
        assert result == [7, 100], (
            "EXECUTE of a constant should push its value above existing stack"
        )


class TestExecuteWithTickInTable:
    """Combine ' (interpret-state tick) with EXECUTE for table-driven dispatch.
    This is the idiom CASE replaces for small dispatches but is still useful
    for larger ones."""

    def test_table_dispatch_via_execute(self):
        result = compile_and_run(
            ": say-1 1 ; "
            ": say-2 2 ; "
            ": say-3 3 ; "
            "create handlers ' say-1 , ' say-2 , ' say-3 , "
            ": call-nth  ( n -- val )  2 *  handlers + @ execute ; "
            ": main 1 call-nth halt ;"
        )
        assert result == [2], (
            "indexing into a table of xts and calling EXECUTE should "
            "dispatch to the corresponding colon word"
        )

    @pytest.mark.parametrize("idx,expected", [
        (0, 10),
        (1, 20),
        (2, 30),
    ])
    def test_table_dispatch_each_index(self, idx, expected):
        result = compile_and_run(
            ": ten   10 ; "
            ": twenty 20 ; "
            ": thirty 30 ; "
            "create tbl ' ten , ' twenty , ' thirty , "
            f": main {idx} 2 *  tbl + @ execute halt ;"
        )
        assert result == [expected], (
            f"tbl[{idx}] should dispatch to the {expected}-pushing word"
        )


class TestExecuteRejectionInDoubleColon:

    def test_execute_in_double_colon_raises_compile_error(self):
        src = ":: bad-helper  ['] dup execute ; : main 1 bad-helper halt ;"
        with pytest.raises(CompileError, match="execute"):
            compile_and_run(src)
