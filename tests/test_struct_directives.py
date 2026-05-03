"""
Tests for the struct-directive trio: `--`, `STRUCT`, and `record`.

`--` is `( offset size -- offset+size )` with a side effect: it registers a
new immediate word that emits the offset as a literal in compile state, and
pushes the offset to the host stack in interpret state (for chaining with
another `--`).

`STRUCT` is `( size -- )` and behaves like `--` minus the size-pop, defining
the struct's total-size word with `kind="struct"` so future introspection
can find it.

`record` is `( size -- )` and behaves like `create` followed by `allot size`,
giving every instance the right amount of zeroed data in one word.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, CompileError, Word, compile_and_run
from zt.compile.ir import Literal, ColonRef


def make_compiler(origin: int = 0x8000) -> Compiler:
    return Compiler(origin=origin, inline_primitives=False, inline_next=False)


def compile_only(source: str) -> Compiler:
    c = make_compiler()
    c.compile_source(source)
    return c


class TestDoubleDashFieldOffsets:

    def test_first_field_has_offset_zero(self):
        c = compile_only("0  2 -- .x  : main halt ;")
        assert c.words[".x"].value == 0, "first field after `0` should land at offset 0"

    def test_second_field_offset_equals_first_size(self):
        c = compile_only("0  2 -- .x  2 -- .y  : main halt ;")
        assert c.words[".y"].value == 2, ".y should follow .x at offset 2"

    @pytest.mark.parametrize("source,name,expected", [
        ("0  1 -- a",                       "a", 0),
        ("0  1 -- a  2 -- b",               "b", 1),
        ("0  1 -- a  2 -- b  20 -- c",      "c", 3),
        ("0  1 -- a  2 -- b  20 -- c  4 -- d", "d", 23),
    ], ids=["a", "b", "c", "d"])
    def test_offsets_are_running_sums(self, source, name, expected):
        c = compile_only(f"{source}  : main halt ;")
        assert c.words[name].value == expected, (
            f"{name} should land at offset {expected} given prior field sizes"
        )

    def test_total_size_is_offset_plus_last_size(self):
        c = compile_only("0  1 -- a  2 -- b  20 -- c  STRUCT /thing  : main halt ;")
        assert c.words["/thing"].value == 23, (
            "/thing's total size should be the running sum after all fields (1+2+20)"
        )


class TestDoubleDashRegistrationShape:

    def test_field_word_is_immediate(self):
        c = compile_only("0  2 -- .x  : main halt ;")
        assert c.words[".x"].immediate is True, (
            "-- fields must be immediate so their compile_action runs in both states"
        )

    def test_field_word_has_compile_action(self):
        c = compile_only("0  2 -- .x  : main halt ;")
        assert c.words[".x"].compile_action is not None, (
            "-- fields need a compile_action to emit a Literal cell"
        )

    def test_field_word_kind_is_constant(self):
        c = compile_only("0  2 -- .x  : main halt ;")
        assert c.words[".x"].kind == "constant", (
            "-- fields are conceptually constants (small numeric values)"
        )

    def test_field_word_value_set(self):
        c = compile_only("0  2 -- .x  2 -- .y  : main halt ;")
        assert c.words[".y"].value == 2, (
            "-- fields should stash their offset on Word.value"
        )


class TestDoubleDashEmitsLiteralNotPusher:

    def test_field_in_colon_body_emits_literal(self):
        c = compile_only(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            ": read-x  .x ; "
            ": main halt ;"
        )
        body = c.words["read-x"].body
        assert Literal(0) in body, (
            ".x in compile state should emit Literal(0), not a ColonRef to a pusher"
        )

    def test_field_does_not_emit_colon_ref(self):
        c = compile_only(
            "0  2 -- .x  : read-x  .x ; : main halt ;"
        )
        body = c.words["read-x"].body
        assert not any(isinstance(cell, ColonRef) and cell.name == ".x" for cell in body), (
            ".x must NOT compile as ColonRef — that would invoke a pusher word"
        )

    def test_struct_size_in_colon_body_emits_literal(self):
        c = compile_only(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            ": size-of-point  /point ; "
            ": main halt ;"
        )
        body = c.words["size-of-point"].body
        assert Literal(4) in body, (
            "STRUCT-defined size word should also emit a Literal in compile state"
        )

    def test_field_runtime_value_via_colon(self):
        result = compile_and_run(
            "0  2 -- .x  2 -- .y  : get-x-offset  .x ; : main get-x-offset halt ;"
        )
        assert result == [0], (
            ".x called from a colon should push 0 at runtime"
        )

    def test_second_field_runtime_value_via_colon(self):
        result = compile_and_run(
            "0  2 -- .x  2 -- .y  : get-y-offset  .y ; : main get-y-offset halt ;"
        )
        assert result == [2], "field .y at runtime should push 2"

    def test_struct_size_runtime_value_via_colon(self):
        result = compile_and_run(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            ": size  /point ; : main size halt ;"
        )
        assert result == [4], "/point at runtime should push its size of 4"


class TestStructDirective:

    def test_struct_word_kind_is_struct(self):
        c = compile_only("0  2 -- .x  STRUCT /point  : main halt ;")
        assert c.words["/point"].kind == "struct", (
            "STRUCT should tag with kind='struct' — the future-introspection hook"
        )

    def test_struct_word_has_value(self):
        c = compile_only("0  2 -- .x  2 -- .y  STRUCT /point  : main halt ;")
        assert c.words["/point"].value == 4, (
            "STRUCT-defined word should stash size on .value like a constant does"
        )

    def test_struct_is_immediate(self):
        c = compile_only("0  2 -- .x  STRUCT /point  : main halt ;")
        assert c.words["/point"].immediate is True, (
            "STRUCT-defined size should be a literal-emitter, like field words"
        )

    def test_empty_struct(self):
        c = compile_only("0 STRUCT /empty  : main halt ;")
        assert c.words["/empty"].value == 0, (
            "an empty struct (no fields) should have size 0"
        )

    def test_single_field_struct(self):
        c = compile_only("0  4 -- .only  STRUCT /single  : main halt ;")
        assert c.words["/single"].value == 4, (
            "a one-field struct's size should equal its sole field's size"
        )


class TestRecordDirective:

    def test_record_creates_variable_word(self):
        c = compile_only(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            "/point record origin  "
            ": main halt ;"
        )
        assert c.words["origin"].kind == "variable", (
            "record-allocated instance is a variable-shaped word (has data_address)"
        )

    def test_record_has_data_address(self):
        c = compile_only(
            "0  2 -- .x  STRUCT /point  /point record origin  : main halt ;"
        )
        assert c.words["origin"].data_address is not None, (
            "record-allocated instance must have a data_address users can read/write"
        )

    @pytest.mark.parametrize("size", [1, 2, 4, 13, 64])
    def test_record_allocates_exactly_size_bytes(self, size):
        c = compile_only(
            f"{size} STRUCT /thing  /thing record buf  : main halt ;"
        )
        c.compile_main_call()
        image = c.build()
        data_addr = c.words["buf"].data_address
        offset = data_addr - c.origin
        for i in range(size):
            assert image[offset + i] == 0, (
                f"buf[{i}] should be zero-initialised by record"
            )

    def test_record_initialises_to_zero(self):
        result = compile_and_run(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            "/point record origin  "
            ": main origin .x + @ halt ;"
        )
        assert result == [0], "freshly-recorded instance should read zeros from any field"

    def test_two_records_get_distinct_addresses(self):
        c = compile_only(
            "4 STRUCT /thing  /thing record a  /thing record b  : main halt ;"
        )
        a_addr = c.words["a"].data_address
        b_addr = c.words["b"].data_address
        assert a_addr != b_addr, "two record-allocated instances must be at distinct addresses"
        assert abs(b_addr - a_addr) >= 4, (
            "consecutive records must not overlap — each gets its own /thing-sized data area"
        )


class TestStructEndToEnd:

    def test_read_write_roundtrip_through_field(self):
        result = compile_and_run(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            "/point record origin  "
            ": main 42 origin .x + !  origin .x + @ halt ;"
        )
        assert result == [42], (
            "write to .x then read should round-trip through composed accessor"
        )

    def test_two_fields_independent(self):
        result = compile_and_run(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            "/point record origin  "
            ": main "
            "  10 origin .x + !  20 origin .y + ! "
            "  origin .x + @  origin .y + @ "
            "halt ;"
        )
        assert result == [10, 20], (
            ".x and .y writes must not interfere — separate offsets in the same instance"
        )

    def test_two_instances_independent(self):
        result = compile_and_run(
            "0  2 -- .x  STRUCT /point  "
            "/point record a  /point record b  "
            ": main 100 a .x + !  200 b .x + ! "
            "  a .x + @  b .x + @ halt ;"
        )
        assert result == [100, 200], (
            "writes through one instance must not leak into another"
        )

    def test_inheritance_via_struct_size_as_base_offset(self):
        c = compile_only(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            "/point  2 -- .radius  STRUCT /circle  "
            ": main halt ;"
        )
        assert c.words[".radius"].value == 4, (
            ".radius should land at /point's size — that's how inheritance works here"
        )
        assert c.words["/circle"].value == 6, (
            "/circle = /point + .radius's size = 4 + 2 = 6"
        )

    def test_two_structs_share_base_independently(self):
        c = compile_only(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            "/point  2 -- .r  STRUCT /circle  "
            "/point  2 -- .w  2 -- .h  STRUCT /rect  "
            ": main halt ;"
        )
        assert c.words[".r"].value == 4, ".r in /circle should sit at /point's end"
        assert c.words[".w"].value == 4, ".w in /rect should sit at /point's end too"
        assert c.words[".h"].value == 6, ".h follows .w in /rect"
        assert c.words["/circle"].value == 6, "/circle has /point + 2 = 6"
        assert c.words["/rect"].value == 8, "/rect has /point + 2 + 2 = 8"

    def test_nested_struct_as_field_size(self):
        c = compile_only(
            "0  2 -- .x  2 -- .y  STRUCT /point  "
            "0  /point -- .top-left  /point -- .bottom-right  STRUCT /bbox  "
            ": main halt ;"
        )
        assert c.words[".top-left"].value == 0, ".top-left is the first field"
        assert c.words[".bottom-right"].value == 4, (
            ".bottom-right follows a /point-sized embed at offset 4"
        )
        assert c.words["/bbox"].value == 8, "/bbox is two embedded points"

    def test_array_field_via_size_arithmetic(self):
        c = compile_only(
            "0  2 -- .id  32 -- .slots  STRUCT /actor  : main halt ;"
        )
        assert c.words[".slots"].value == 2, ".slots offset is 2 (after .id)"
        assert c.words["/actor"].value == 34, "/actor = 2 + 32 (16 cells)"

    def test_arithmetic_in_interpret_state_not_yet_lifted(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected word '\\*'"):
            c.compile_source("0  2 16 * -- .slots  STRUCT /actor  : main halt ;")

    def test_byte_field_in_mixed_struct(self):
        c = compile_only(
            "0  2 -- .id  1 -- .hp  2 -- .x  STRUCT /actor  : main halt ;"
        )
        assert c.words[".hp"].value == 2, ".hp at offset 2 (byte-packed after .id)"
        assert c.words[".x"].value == 3, ".x follows the 1-byte .hp at offset 3"
        assert c.words["/actor"].value == 5, "/actor = 2 + 1 + 2 = 5"


class TestStructWithMultipleInheritanceLevels:

    def test_three_level_chain(self):
        c = compile_only(
            "0  2 -- .a  STRUCT /base  "
            "/base  2 -- .b  STRUCT /mid  "
            "/mid   2 -- .c  STRUCT /leaf  "
            ": main halt ;"
        )
        assert c.words[".a"].value == 0, ".a at offset 0 in /base"
        assert c.words[".b"].value == 2, ".b at /base's size = 2"
        assert c.words[".c"].value == 4, ".c at /mid's size = 4"
        assert c.words["/leaf"].value == 6, "/leaf = 2 + 2 + 2 = 6"

    def test_leaf_instance_can_use_base_field(self):
        result = compile_and_run(
            "0  2 -- .a  STRUCT /base  "
            "/base  2 -- .b  STRUCT /derived  "
            "/derived record obj  "
            ": main 7 obj .a + !  obj .a + @ halt ;"
        )
        assert result == [7], (
            "writing through a base-class field on a derived instance should round-trip"
        )


class TestStructDirectiveErrorPaths:

    def test_double_dash_underflow_offset_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="host stack underflow"):
            c.compile_source("2 -- .x  : main halt ;")

    def test_double_dash_underflow_size_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="host stack underflow"):
            c.compile_source("0 -- .x  : main halt ;")

    def test_struct_underflow_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="host stack underflow"):
            c.compile_source("STRUCT /thing  : main halt ;")

    def test_record_underflow_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="host stack underflow"):
            c.compile_source("record buf  : main halt ;")
