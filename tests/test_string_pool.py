"""
Tests for `StringPool`: sequential label allocation, flush order, clearing on flush, empty behaviour, and data preservation.
"""
import pytest

from zt.asm import Asm
from zt.string_pool import StringPool


@pytest.fixture
def pool() -> StringPool:
    return StringPool()


class TestLabelAllocation:

    def test_first_allocation_is_str_0(self, pool):
        label = pool.allocate(b"hello")
        assert label == "_str_0", "first allocated label should be '_str_0'"

    def test_labels_are_sequential(self, pool):
        labels = [pool.allocate(f"s{i}".encode()) for i in range(4)]
        assert labels == ["_str_0", "_str_1", "_str_2", "_str_3"], (
            "subsequent labels should use increasing integer suffixes"
        )

    def test_equal_strings_still_get_distinct_labels(self, pool):
        a = pool.allocate(b"hello")
        b = pool.allocate(b"hello")
        assert a != b, (
            "identical strings must still receive distinct labels (no dedup)"
        )


class TestFlushOrder:

    def test_flush_writes_labels_in_insertion_order(self, pool):
        pool.allocate(b"AB")
        pool.allocate(b"CD")
        asm = Asm(0x8000, inline_next=False)
        pool.flush(asm)
        assert asm.labels["_str_0"] < asm.labels["_str_1"], (
            "earlier-allocated strings should be laid out at lower addresses"
        )

    def test_flush_writes_bytes_verbatim(self, pool):
        pool.allocate(b"AB")
        pool.allocate(b"CD")
        asm = Asm(0x8000, inline_next=False)
        pool.flush(asm)
        image = asm.resolve()
        assert image == b"ABCD", (
            "flush should write the raw bytes of allocated strings back-to-back"
        )

    def test_flush_registers_labels_in_asm(self, pool):
        pool.allocate(b"hi")
        asm = Asm(0x8000, inline_next=False)
        pool.flush(asm)
        assert "_str_0" in asm.labels, (
            "flush should register the allocated label in the Asm instance"
        )


class TestFlushClears:

    def test_flush_empties_the_pool(self, pool):
        pool.allocate(b"x")
        asm = Asm(0x8000, inline_next=False)
        pool.flush(asm)
        assert pool.pending_count == 0, (
            "flush should clear pending strings after writing them"
        )

    def test_second_flush_is_noop(self, pool):
        pool.allocate(b"x")
        asm1 = Asm(0x8000, inline_next=False)
        pool.flush(asm1)
        asm2 = Asm(0x8000, inline_next=False)
        pool.flush(asm2)
        assert asm2.resolve() == b"", (
            "a second flush after the first should produce no output"
        )

    def test_counter_keeps_advancing_across_flushes(self, pool):
        pool.allocate(b"a")
        asm = Asm(0x8000, inline_next=False)
        pool.flush(asm)
        label2 = pool.allocate(b"b")
        assert label2 == "_str_1", (
            "flush should not reset the label counter; _str_1 should come after _str_0"
        )


class TestEmpty:

    def test_flush_of_empty_pool_is_harmless(self, pool):
        asm = Asm(0x8000, inline_next=False)
        pool.flush(asm)
        assert asm.resolve() == b"", (
            "flushing an empty pool should produce no bytes"
        )

    def test_new_pool_has_zero_pending(self, pool):
        assert pool.pending_count == 0, (
            "a fresh StringPool should have no pending strings"
        )


class TestDataPreservation:

    @pytest.mark.parametrize("data", [
        b"",
        b"a",
        b"hello world",
        bytes(range(256)),
    ])
    def test_flush_preserves_exact_bytes(self, pool, data):
        pool.allocate(data)
        asm = Asm(0x8000, inline_next=False)
        pool.flush(asm)
        assert asm.resolve() == data, (
            f"flush should preserve data of length {len(data)} exactly"
        )
