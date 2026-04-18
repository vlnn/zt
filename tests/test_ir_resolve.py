import pytest

from zt.ir import Branch, ColonRef, Label, Literal, PrimRef, StringRef, cell_size, resolve


@pytest.fixture
def word_addrs():
    return {
        "dup": 0x1000,
        "swap": 0x1004,
        "lit": 0x1008,
        "branch": 0x100C,
        "0branch": 0x1010,
        "_str_0": 0x9000,
        "my-word": 0x9100,
    }


class TestEmptyInput:

    def test_empty_cell_list_produces_empty_bytes(self, word_addrs):
        assert resolve([], word_addrs) == b"", (
            "empty cell list should produce empty bytes"
        )


class TestSimpleReferences:

    @pytest.mark.parametrize("cell, expected", [
        (PrimRef("dup"), bytes([0x00, 0x10])),
        (PrimRef("swap"), bytes([0x04, 0x10])),
        (ColonRef("my-word"), bytes([0x00, 0x91])),
        (StringRef("_str_0"), bytes([0x00, 0x90])),
    ])
    def test_single_cell_emits_address_little_endian(self, word_addrs, cell, expected):
        out = resolve([cell], word_addrs)
        assert out == expected, (
            f"{type(cell).__name__} should emit its address as 2 little-endian bytes"
        )


class TestLiteral:

    def test_literal_emits_lit_addr_then_value(self, word_addrs):
        out = resolve([Literal(0x1234)], word_addrs)
        assert out == bytes([0x08, 0x10, 0x34, 0x12]), (
            "Literal(0x1234) should emit lit_addr then value, both little-endian"
        )

    @pytest.mark.parametrize("value, expected_tail", [
        (0x0000, bytes([0x00, 0x00])),
        (0x00FF, bytes([0xFF, 0x00])),
        (0xFF00, bytes([0x00, 0xFF])),
        (0xFFFF, bytes([0xFF, 0xFF])),
        (0xABCD, bytes([0xCD, 0xAB])),
    ])
    def test_literal_value_bytes_are_little_endian(self, word_addrs, value, expected_tail):
        out = resolve([Literal(value)], word_addrs)
        assert out[2:] == expected_tail, (
            f"Literal({value:#06x}) should emit value bytes {expected_tail!r} after lit_addr"
        )


class TestBranchForwardLabel:

    def test_forward_label_resolves_to_post_cell_offset(self, word_addrs):
        cells = [
            Branch("0branch", Label(1)),
            PrimRef("dup"),
            Label(1),
        ]
        out = resolve(cells, word_addrs, base_address=0x8000)
        expected = bytes([
            0x10, 0x10,
            0x06, 0x80,
            0x00, 0x10,
        ])
        assert out == expected, (
            "forward Label should resolve to base_address + byte offset after Branch and dup"
        )


class TestBranchBackwardLabel:

    def test_backward_label_resolves_to_its_offset(self, word_addrs):
        cells = [
            Label(0),
            PrimRef("dup"),
            Branch("branch", Label(0)),
        ]
        out = resolve(cells, word_addrs, base_address=0x8000)
        expected = bytes([
            0x00, 0x10,
            0x0C, 0x10,
            0x00, 0x80,
        ])
        assert out == expected, (
            "backward Label should resolve to base_address + its own byte offset"
        )


class TestBaseAddressDefault:

    def test_default_base_address_is_zero(self, word_addrs):
        cells = [Branch("branch", Label(0)), Label(0)]
        out = resolve(cells, word_addrs)
        assert out[2:4] == bytes([0x04, 0x00]), (
            "with default base_address=0, forward Label after 4 bytes should resolve to 0x0004"
        )


class TestCellSizes:

    @pytest.mark.parametrize("cell, expected_size", [
        (PrimRef("dup"), 2),
        (ColonRef("my-word"), 2),
        (StringRef("_str_0"), 2),
        (Literal(0), 4),
        (Branch("branch", Label(0)), 4),
        (Label(0), 0),
    ])
    def test_cell_size_reports_expected_byte_count(self, cell, expected_size):
        assert cell_size(cell) == expected_size, (
            f"cell_size({type(cell).__name__}) should be {expected_size}"
        )

    def test_label_emits_nothing(self, word_addrs):
        out = resolve([Label(5), Label(99)], word_addrs)
        assert out == b"", "Label cells should not emit any bytes"


class TestErrors:

    def test_unknown_label_raises_with_useful_message(self, word_addrs):
        cells = [Branch("branch", Label(99))]
        with pytest.raises(KeyError, match="99"):
            resolve(cells, word_addrs)

    def test_unknown_label_message_lists_defined_labels(self, word_addrs):
        cells = [Label(1), Label(2), Branch("branch", Label(99))]
        with pytest.raises(KeyError) as exc_info:
            resolve(cells, word_addrs)
        message = str(exc_info.value)
        assert "1" in message and "2" in message, (
            "unresolved-label error should list known label ids to help diagnosis"
        )

    def test_unknown_primitive_raises(self, word_addrs):
        with pytest.raises(KeyError, match="nonexistent"):
            resolve([PrimRef("nonexistent")], word_addrs)

    def test_unknown_colon_word_raises(self, word_addrs):
        with pytest.raises(KeyError, match="nonexistent"):
            resolve([ColonRef("nonexistent")], word_addrs)

    def test_missing_lit_word_raises_when_literal_present(self):
        with pytest.raises(KeyError, match="lit"):
            resolve([Literal(42)], word_addrs={})

    def test_duplicate_label_definition_raises(self, word_addrs):
        cells = [Label(1), PrimRef("dup"), Label(1)]
        with pytest.raises(ValueError, match="duplicate label"):
            resolve(cells, word_addrs)


class TestMixedSequence:

    def test_full_sequence_of_all_cell_kinds(self, word_addrs):
        cells = [
            Literal(0x1234),
            PrimRef("dup"),
            ColonRef("my-word"),
            Branch("0branch", Label(0)),
            StringRef("_str_0"),
            Label(0),
        ]
        out = resolve(cells, word_addrs, base_address=0x8000)
        expected = bytes([
            0x08, 0x10, 0x34, 0x12,
            0x00, 0x10,
            0x00, 0x91,
            0x10, 0x10, 0x0E, 0x80,
            0x00, 0x90,
        ])
        assert out == expected, (
            "a mixed sequence should resolve each cell kind in order with correct label offset"
        )
