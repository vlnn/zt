import pytest

from zt.ir import Branch, ColonRef, Label, Literal, PrimRef, StringRef


class TestFieldShape:

    @pytest.mark.parametrize("cls, kwargs, field, expected", [
        (PrimRef, {"name": "dup"}, "name", "dup"),
        (ColonRef, {"name": "my-word"}, "name", "my-word"),
        (Literal, {"value": 0x1234}, "value", 0x1234),
        (Label, {"id": 5}, "id", 5),
        (StringRef, {"label": "_str_0"}, "label", "_str_0"),
    ])
    def test_single_field_cells_expose_their_field(self, cls, kwargs, field, expected):
        cell = cls(**kwargs)
        assert getattr(cell, field) == expected, (
            f"{cls.__name__} should expose field {field!r} with the given value"
        )

    def test_branch_exposes_kind_and_target(self):
        target = Label(id=3)
        b = Branch(kind="branch", target=target)
        assert b.kind == "branch", "Branch should expose its kind"
        assert b.target == target, "Branch should expose its target Label"


class TestFrozen:

    @pytest.mark.parametrize("cell, attr, new_value", [
        (PrimRef("dup"), "name", "swap"),
        (ColonRef("foo"), "name", "bar"),
        (Literal(42), "value", 43),
        (Label(1), "id", 2),
        (Branch("branch", Label(0)), "kind", "0branch"),
        (StringRef("_s"), "label", "_t"),
    ])
    def test_cells_cannot_be_mutated(self, cell, attr, new_value):
        with pytest.raises(Exception) as exc_info:
            setattr(cell, attr, new_value)
        assert "frozen" in str(exc_info.value).lower() or isinstance(
            exc_info.value, AttributeError
        ), f"mutating {type(cell).__name__}.{attr} should raise a frozen-instance error"


class TestLiteralValidation:

    @pytest.mark.parametrize("value", [0, 1, 0x00FF, 0x1234, 0xFFFF])
    def test_in_range_values_are_accepted(self, value):
        lit = Literal(value=value)
        assert lit.value == value, f"Literal({value:#x}) should preserve its value"

    @pytest.mark.parametrize("value", [-1, -0x8000, 0x10000, 0x100000])
    def test_out_of_range_values_are_rejected(self, value):
        with pytest.raises(ValueError, match="16-bit"):
            Literal(value=value)


class TestBranchValidation:

    @pytest.mark.parametrize("kind", ["branch", "0branch", "(loop)", "(+loop)", "jump"])
    def test_non_empty_kinds_are_accepted(self, kind):
        b = Branch(kind=kind, target=Label(id=0))
        assert b.kind == kind, f"Branch({kind!r}) should preserve its kind"

    def test_empty_kind_is_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            Branch(kind="", target=Label(id=0))


class TestEquality:

    @pytest.mark.parametrize("a, b", [
        (PrimRef("dup"), PrimRef("dup")),
        (ColonRef("foo"), ColonRef("foo")),
        (Literal(42), Literal(42)),
        (Label(3), Label(3)),
        (Branch("branch", Label(1)), Branch("branch", Label(1))),
        (StringRef("_s"), StringRef("_s")),
    ])
    def test_equal_cells_compare_equal(self, a, b):
        assert a == b, f"{a!r} should equal {b!r}"
        assert hash(a) == hash(b), f"{a!r} and {b!r} should have equal hashes"

    @pytest.mark.parametrize("a, b", [
        (PrimRef("dup"), PrimRef("swap")),
        (PrimRef("dup"), ColonRef("dup")),
        (Literal(42), Literal(43)),
        (Label(1), Label(2)),
        (Branch("branch", Label(1)), Branch("0branch", Label(1))),
        (Branch("branch", Label(1)), Branch("branch", Label(2))),
        (StringRef("_a"), StringRef("_b")),
    ])
    def test_different_cells_compare_not_equal(self, a, b):
        assert a != b, f"{a!r} should not equal {b!r}"


class TestHashable:

    @pytest.mark.parametrize("cell", [
        PrimRef("dup"),
        ColonRef("foo"),
        Literal(42),
        Label(3),
        Branch("branch", Label(1)),
        StringRef("_s"),
    ])
    def test_cells_can_be_dict_keys(self, cell):
        d = {cell: "value"}
        assert d[cell] == "value", (
            f"{type(cell).__name__} should be usable as a dict key for peephole matching"
        )

    def test_cells_can_be_set_members(self):
        cells = {PrimRef("dup"), PrimRef("dup"), PrimRef("swap")}
        assert len(cells) == 2, "set should deduplicate equal PrimRefs"
