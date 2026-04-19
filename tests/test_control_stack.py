"""
Tests for `ControlStack`: push/pop LIFO, tag mismatch errors, underflow, peek, clear, iteration, and `find_innermost`.
"""
import pytest

from zt.control_stack import ControlStack, ControlStackError


@pytest.fixture
def stack() -> ControlStack:
    return ControlStack()


class TestPushPop:

    def test_new_stack_is_empty(self, stack):
        assert len(stack) == 0, "fresh ControlStack should have length 0"
        assert not stack, "fresh ControlStack should be falsy"

    def test_push_increases_length(self, stack):
        stack.push("if", 42)
        assert len(stack) == 1, "push should bump length by 1"
        assert stack, "non-empty ControlStack should be truthy"

    def test_pop_returns_pushed_value(self, stack):
        stack.push("if", 42)
        value = stack.pop("if")
        assert value == 42, "pop should return the value that was pushed with the matching tag"

    def test_pop_decreases_length(self, stack):
        stack.push("if", 42)
        stack.pop("if")
        assert len(stack) == 0, "pop should drop length back to 0"


class TestLIFO:

    def test_pops_in_reverse_push_order(self, stack):
        stack.push("if", 1)
        stack.push("else", 2)
        assert stack.pop("else") == 2, "most-recently-pushed frame should come out first"
        assert stack.pop("if") == 1, "earlier frame should come out last"


class TestTagMismatch:

    def test_pop_with_wrong_tag_raises(self, stack):
        stack.push("begin", 0x8400)
        with pytest.raises(ControlStackError, match="begin"):
            stack.pop("if")

    @pytest.mark.parametrize("pushed_tag, expected_tag", [
        ("begin", "if"),
        ("if", "begin"),
        ("do", "while"),
        ("else", "begin"),
    ])
    def test_mismatch_message_mentions_both_tags(self, stack, pushed_tag, expected_tag):
        stack.push(pushed_tag, None)
        with pytest.raises(ControlStackError) as exc_info:
            stack.pop(expected_tag)
        msg = str(exc_info.value)
        assert pushed_tag in msg and expected_tag in msg, (
            f"mismatch error should mention both pushed tag {pushed_tag!r} and expected tag {expected_tag!r}"
        )


class TestUnderflow:

    def test_pop_empty_raises(self, stack):
        with pytest.raises(ControlStackError, match="underflow"):
            stack.pop("if")

    def test_pop_any_empty_raises(self, stack):
        with pytest.raises(ControlStackError, match="underflow"):
            stack.pop_any(["if", "else"])

    def test_peek_empty_raises(self, stack):
        with pytest.raises(ControlStackError, match="underflow"):
            stack.peek()


class TestPopAny:

    @pytest.mark.parametrize("pushed", ["if", "else"])
    def test_pop_any_accepts_listed_tag(self, stack, pushed):
        stack.push(pushed, 99)
        tag, value = stack.pop_any(["if", "else"])
        assert tag == pushed, f"pop_any should return the actual tag {pushed!r}"
        assert value == 99, "pop_any should return the stored value alongside the tag"

    def test_pop_any_rejects_unlisted_tag(self, stack):
        stack.push("begin", 0)
        with pytest.raises(ControlStackError) as exc_info:
            stack.pop_any(["if", "else"])
        msg = str(exc_info.value)
        assert "if" in msg and "else" in msg and "begin" in msg, (
            "pop_any mismatch error should list both the allowed tags and the actual tag"
        )


class TestPeek:

    def test_peek_returns_top_without_popping(self, stack):
        stack.push("do", {"addr": 0x8100})
        top = stack.peek()
        assert top == ("do", {"addr": 0x8100}), "peek should return the top (tag, value) pair"
        assert len(stack) == 1, "peek must not remove the frame"


class TestClear:

    def test_clear_empties_the_stack(self, stack):
        stack.push("if", 1)
        stack.push("begin", 2)
        stack.clear()
        assert len(stack) == 0, "clear should leave the stack empty"


class TestLengthAndIteration:

    def test_len_matches_push_count(self, stack):
        for i in range(5):
            stack.push("if", i)
        assert len(stack) == 5, "len should reflect the number of pushed frames"

    def test_iteration_yields_oldest_first(self, stack):
        stack.push("if", 1)
        stack.push("begin", 2)
        stack.push("do", 3)
        frames = list(stack)
        assert frames == [("if", 1), ("begin", 2), ("do", 3)], (
            "iteration should yield frames from oldest to newest (push order)"
        )


class TestFindInnermost:

    def test_returns_none_when_absent(self, stack):
        stack.push("if", 1)
        assert stack.find_innermost("do") is None, (
            "find_innermost should return None when the tag is not on the stack"
        )

    def test_returns_none_on_empty_stack(self, stack):
        assert stack.find_innermost("do") is None, (
            "find_innermost should return None on an empty stack (not raise)"
        )

    def test_finds_single_matching_frame(self, stack):
        payload = {"addr": 0x8400}
        stack.push("do", payload)
        assert stack.find_innermost("do") == ("do", payload), (
            "find_innermost should return the matching (tag, value) frame"
        )

    def test_finds_innermost_when_multiple_match(self, stack):
        stack.push("do", {"name": "outer"})
        stack.push("if", 42)
        stack.push("do", {"name": "inner"})
        tag, value = stack.find_innermost("do")
        assert value == {"name": "inner"}, (
            "find_innermost should return the most recently pushed matching frame (LIFO)"
        )

    def test_does_not_pop(self, stack):
        stack.push("do", {"addr": 0x8400})
        stack.find_innermost("do")
        assert len(stack) == 1, "find_innermost must not modify the stack"


class TestDictValuePayload:

    def test_do_payload_survives_round_trip(self, stack):
        payload = {"addr": 0x8400, "label_id": 7, "leaves": []}
        stack.push("do", payload)
        popped = stack.pop("do")
        assert popped is payload, "pop should return the exact same object, not a copy"

    def test_nested_payload_can_be_mutated_by_reference(self, stack):
        payload = {"addr": 0x8400, "leaves": []}
        stack.push("do", payload)
        payload["leaves"].append(0x8410)
        popped = stack.pop("do")
        assert popped["leaves"] == [0x8410], (
            "mutating the payload after push should be visible after pop (stored by reference)"
        )
