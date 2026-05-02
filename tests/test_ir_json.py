"""Tests for `cells_to_json` / `cells_from_json` round-trips over every cell kind."""
import pytest

from zt.compile.ir import (
    Branch,
    ColonRef,
    Label,
    Literal,
    PrimRef,
    StringRef,
    WordLiteral,
    cells_from_json,
    cells_to_json,
)


class TestCellsToJson:

    @pytest.mark.parametrize("cell, expected", [
        (PrimRef("dup"), ["prim", "dup"]),
        (ColonRef("my-word"), ["colon", "my-word"]),
        (Literal(42), ["lit", 42]),
        (WordLiteral("my-isr"), ["wordlit", "my-isr"]),
        (Label(3), ["label", 3]),
        (Branch("0branch", Label(7)), ["branch", "0branch", 7]),
        (StringRef("_str_0"), ["str", "_str_0"]),
    ])
    def test_each_cell_kind_produces_expected_json_shape(self, cell, expected):
        assert cells_to_json([cell]) == [expected], (
            f"cells_to_json should encode {type(cell).__name__} as {expected!r}"
        )

    def test_empty_list_produces_empty_json(self):
        assert cells_to_json([]) == [], (
            "empty cell list should serialize to empty JSON list"
        )

    def test_multiple_cells_preserve_order(self):
        cells = [PrimRef("dup"), Literal(5), PrimRef("+")]
        assert cells_to_json(cells) == [
            ["prim", "dup"], ["lit", 5], ["prim", "+"],
        ], "cells_to_json should preserve order"


class TestCellsFromJson:

    @pytest.mark.parametrize("json_form, expected", [
        (["prim", "dup"], PrimRef("dup")),
        (["colon", "my-word"], ColonRef("my-word")),
        (["lit", 42], Literal(42)),
        (["wordlit", "my-isr"], WordLiteral("my-isr")),
        (["label", 3], Label(3)),
        (["branch", "0branch", 7], Branch("0branch", Label(7))),
        (["str", "_str_0"], StringRef("_str_0")),
    ])
    def test_each_json_shape_decodes_to_expected_cell(self, json_form, expected):
        assert cells_from_json([json_form]) == [expected], (
            f"cells_from_json should decode {json_form!r} to {expected!r}"
        )

    def test_unknown_cell_tag_raises(self):
        with pytest.raises(ValueError, match="unknown"):
            cells_from_json([["mystery", "value"]])


class TestRoundtrip:

    @pytest.mark.parametrize("cells", [
        [],
        [PrimRef("dup"), PrimRef("+"), PrimRef("exit")],
        [Literal(0), Literal(0xFFFF)],
        [Branch("0branch", Label(0)), PrimRef("dup"), Label(0)],
        [PrimRef("lit"), StringRef("_str_0"), Literal(5)],
        [Branch("branch", Label(1)), Branch("(loop)", Label(1)), Label(1)],
        [WordLiteral("rainbow-isr"), PrimRef("im2-handler!")],
    ])
    def test_roundtrip_preserves_cells(self, cells):
        assert cells_from_json(cells_to_json(cells)) == cells, (
            f"roundtrip through JSON should preserve {cells!r}"
        )
