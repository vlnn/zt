"""
Tests for `TokenStream`: empty behaviour, `advance` / `next`, `has_more`, `peek`, `lookahead`, `advance_by`, and in-place splice.
"""
import pytest

from zt.compile.token_stream import TokenStream, TokenStreamExhausted
from zt.compile.tokenizer import Token


def _tok(value: str, kind: str = "word", line: int = 1, col: int = 1) -> Token:
    return Token(value=value, kind=kind, line=line, col=col, source="<test>")


@pytest.fixture
def stream_abc() -> TokenStream:
    return TokenStream([_tok("a"), _tok("b"), _tok("c")])


class TestEmpty:

    def test_new_stream_is_empty(self):
        s = TokenStream([])
        assert not s.has_more(), "empty stream should report no more tokens"

    def test_next_on_empty_raises(self):
        s = TokenStream([])
        with pytest.raises(TokenStreamExhausted):
            s.next()


class TestAdvance:

    def test_next_returns_first_token(self, stream_abc):
        assert stream_abc.next().value == "a", "next() should return the first token"

    def test_next_advances_position(self, stream_abc):
        stream_abc.next()
        assert stream_abc.next().value == "b", (
            "second next() should return the second token"
        )

    def test_next_at_end_raises(self, stream_abc):
        stream_abc.next()
        stream_abc.next()
        stream_abc.next()
        with pytest.raises(TokenStreamExhausted):
            stream_abc.next()


class TestHasMore:

    def test_true_when_tokens_remain(self, stream_abc):
        assert stream_abc.has_more(), "has_more should be True initially"

    def test_false_after_all_consumed(self, stream_abc):
        for _ in range(3):
            stream_abc.next()
        assert not stream_abc.has_more(), (
            "has_more should be False after all tokens have been consumed"
        )


class TestPeek:

    def test_peek_returns_next_without_advancing(self, stream_abc):
        peeked = stream_abc.peek()
        assert peeked is not None and peeked.value == "a", (
            "peek should return the next-to-be-read token"
        )
        assert stream_abc.next().value == "a", (
            "subsequent next() should still return that same token"
        )

    def test_peek_at_end_returns_none(self, stream_abc):
        for _ in range(3):
            stream_abc.next()
        assert stream_abc.peek() is None, (
            "peek at end-of-stream should return None rather than raise"
        )


class TestLookaheadSlice:

    def test_lookahead_returns_up_to_n_tokens(self, stream_abc):
        head = stream_abc.lookahead(2)
        assert [t.value for t in head] == ["a", "b"], (
            "lookahead(2) should return the next two tokens"
        )
        assert stream_abc.peek().value == "a", (
            "lookahead must not advance the position"
        )

    def test_lookahead_returns_available_when_requesting_more(self, stream_abc):
        head = stream_abc.lookahead(10)
        assert [t.value for t in head] == ["a", "b", "c"], (
            "lookahead should return what's available when N exceeds remaining tokens"
        )

    def test_lookahead_respects_current_position(self, stream_abc):
        stream_abc.next()
        head = stream_abc.lookahead(2)
        assert [t.value for t in head] == ["b", "c"], (
            "lookahead should start from the current position, not from the beginning"
        )


class TestAdvanceBy:

    def test_advance_by_skips_tokens(self, stream_abc):
        stream_abc.advance_by(2)
        assert stream_abc.next().value == "c", (
            "advance_by(2) should skip the first two tokens"
        )

    def test_advance_by_zero_is_noop(self, stream_abc):
        stream_abc.advance_by(0)
        assert stream_abc.next().value == "a", (
            "advance_by(0) should not advance the position"
        )


class TestSplice:

    def test_splice_inserts_at_current_position(self, stream_abc):
        stream_abc.next()
        stream_abc.splice_in([_tok("x"), _tok("y")])
        values = [stream_abc.next().value for _ in range(4)]
        assert values == ["x", "y", "b", "c"], (
            "splice_in should insert tokens at the current position, before the next read"
        )

    def test_splice_at_end_appends(self, stream_abc):
        for _ in range(3):
            stream_abc.next()
        stream_abc.splice_in([_tok("x")])
        assert stream_abc.next().value == "x", (
            "splice_in at end-of-stream should make the new tokens readable next"
        )

    def test_splice_empty_list_is_noop(self, stream_abc):
        stream_abc.splice_in([])
        assert stream_abc.next().value == "a", (
            "splicing an empty list should leave the stream unchanged"
        )
