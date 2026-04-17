from __future__ import annotations

import pytest

from zt.tokenizer import Token, TokenizeError, tokenize


def tok(value: str, kind: str = "word") -> tuple[str, str]:
    return (value, kind)


def values_and_kinds(tokens: list[Token]) -> list[tuple[str, str]]:
    return [(t.value, t.kind) for t in tokens]


class TestBasicWords:

    @pytest.mark.parametrize("src, expected", [
        ("dup", [tok("dup")]),
        ("+", [tok("+")]),
        (": foo + ;", [tok(":"), tok("foo"), tok("+"), tok(";")]),
        ("swap drop", [tok("swap"), tok("drop")]),
    ])
    def test_word_tokens(self, src, expected):
        result = values_and_kinds(tokenize(src))
        assert result == expected, f"tokenizing {src!r} should produce {expected}"

    def test_empty_input(self):
        assert tokenize("") == [], "empty input should produce no tokens"

    def test_whitespace_only(self):
        assert tokenize("   \t\n  ") == [], "whitespace-only input should produce no tokens"

    @pytest.mark.parametrize("src, expected", [
        ("  dup  ", [tok("dup")]),
        ("\tswap\n", [tok("swap")]),
        ("a   b\tc\nd", [tok("a"), tok("b"), tok("c"), tok("d")]),
    ])
    def test_various_whitespace(self, src, expected):
        result = values_and_kinds(tokenize(src))
        assert result == expected, f"whitespace variants in {src!r} should be handled"


class TestCaseInsensitivity:

    @pytest.mark.parametrize("src, expected_value", [
        ("DUP", "dup"),
        ("Dup", "dup"),
        ("BEGIN", "begin"),
        (">R", ">r"),
        ("C@", "c@"),
    ])
    def test_words_lowercased(self, src, expected_value):
        tokens = tokenize(src)
        assert tokens[0].value == expected_value, f"{src!r} should be lowercased to {expected_value!r}"


class TestNumbers:

    @pytest.mark.parametrize("src, expected_value", [
        ("42", "42"),
        ("-7", "-7"),
        ("0", "0"),
        ("$FF", "$ff"),
        ("$ff", "$ff"),
        ("$0A", "$0a"),
        ("%1010", "%1010"),
        ("%0", "%0"),
        ("-1", "-1"),
        ("65535", "65535"),
    ])
    def test_number_classification(self, src, expected_value):
        tokens = tokenize(src)
        assert tokens[0].kind == "number", f"{src!r} should be classified as number"
        assert tokens[0].value == expected_value, f"{src!r} value should be {expected_value!r}"

    @pytest.mark.parametrize("src", [
        "$", "$GG", "%2", "%", "-", "$-1",
    ])
    def test_non_numbers_are_words(self, src):
        tokens = tokenize(src)
        assert tokens[0].kind == "word", f"{src!r} should be classified as word, not number"

    def test_numbers_among_words(self):
        result = values_and_kinds(tokenize(": foo 5 + ;"))
        expected = [tok(":"), tok("foo"), tok("5", "number"), tok("+"), tok(";")]
        assert result == expected, "numbers mixed with words should be classified correctly"


class TestLineComments:

    @pytest.mark.parametrize("src, expected", [
        ("1 2 + \\ comment", [tok("1", "number"), tok("2", "number"), tok("+")]),
        ("\\ whole line comment", []),
        ("dup \\ comment\nswap", [tok("dup"), tok("swap")]),
        ("dup \\", [tok("dup")]),
    ])
    def test_line_comment(self, src, expected):
        result = values_and_kinds(tokenize(src))
        assert result == expected, f"line comment in {src!r} should be stripped"


class TestBlockComments:

    @pytest.mark.parametrize("src, expected", [
        ("( block ) 3", [tok("3", "number")]),
        ("( multi word comment ) dup", [tok("dup")]),
        ("a ( comment ) b", [tok("a"), tok("b")]),
        ("( )", []),
    ])
    def test_block_comment(self, src, expected):
        result = values_and_kinds(tokenize(src))
        assert result == expected, f"block comment in {src!r} should be stripped"

    def test_block_comment_across_lines(self):
        src = "a ( multi\nline\ncomment ) b"
        result = values_and_kinds(tokenize(src))
        assert result == [tok("a"), tok("b")], "block comment should span lines"

    def test_unclosed_block_comment_raises(self):
        with pytest.raises(TokenizeError, match="unclosed"):
            tokenize("( oops")

    def test_paren_inside_word_is_not_comment(self):
        result = values_and_kinds(tokenize("foo(bar"))
        assert result == [tok("foo(bar")], "paren inside a word should not start a comment"


class TestStrings:

    @pytest.mark.parametrize("src, expected", [
        ('.\" hello\"', [tok('.\"'), tok("hello", "string")]),
        ('s\" world\"', [tok('s\"'), tok("world", "string")]),
        ('.\" two words\"', [tok('.\"'), tok("two words", "string")]),
        ('.\" \"', [tok('.\"'), tok("", "string")]),
    ])
    def test_string_tokens(self, src, expected):
        result = values_and_kinds(tokenize(src))
        assert result == expected, f"string in {src!r} should produce word + string token"

    def test_string_preserves_case(self):
        tokens = tokenize('.\" Hello World\"')
        string_tok = [t for t in tokens if t.kind == "string"][0]
        assert string_tok.value == "Hello World", "string content should preserve case"

    def test_unclosed_string_raises(self):
        with pytest.raises(TokenizeError, match="unclosed"):
            tokenize('.\" oops')

    def test_string_with_trailing_content(self):
        result = values_and_kinds(tokenize('.\" hi\" 42'))
        expected = [tok('.\"'), tok("hi", "string"), tok("42", "number")]
        assert result == expected, "content after string should be tokenized"


class TestSourceTracking:

    def test_line_and_col_first_token(self):
        tokens = tokenize("dup")
        assert tokens[0].line == 1, "first token should be on line 1"
        assert tokens[0].col == 1, "first token should start at col 1"

    def test_line_and_col_second_line(self):
        tokens = tokenize("dup\nswap")
        assert tokens[1].line == 2, "token after newline should be on line 2"
        assert tokens[1].col == 1, "first token on new line should start at col 1"

    def test_col_after_spaces(self):
        tokens = tokenize("  dup")
        assert tokens[0].col == 3, "token after two spaces should be at col 3"

    def test_source_propagated(self):
        tokens = tokenize("dup", source="test.fs")
        assert tokens[0].source == "test.fs", "source should be propagated to tokens"

    def test_default_source(self):
        tokens = tokenize("dup")
        assert tokens[0].source == "<input>", "default source should be <input>"


class TestEdgeCases:

    def test_comment_at_eof_no_newline(self):
        result = values_and_kinds(tokenize("dup \\ no newline"))
        assert result == [tok("dup")], "line comment at EOF without newline should work"

    def test_consecutive_comments(self):
        src = "\\ first\n\\ second\ndup"
        result = values_and_kinds(tokenize(src))
        assert result == [tok("dup")], "consecutive line comments should work"

    def test_block_comment_immediately_after_word(self):
        src = "dup( comment ) swap"
        result = values_and_kinds(tokenize(src))
        assert result == [tok("dup("), tok("comment"), tok(")"), tok("swap")], \
            "paren not preceded by whitespace should not start a comment"

    def test_many_tokens(self):
        src = " ".join(str(i) for i in range(100))
        tokens = tokenize(src)
        assert len(tokens) == 100, "should handle many tokens"
        assert all(t.kind == "number" for t in tokens), "all should be numbers"

    def test_forth_style_names(self):
        names = [">r", "r>", "r@", "2dup", "0=", "c!", "+!", "2*", "2/"]
        for name in names:
            tokens = tokenize(name)
            assert tokens[0].kind == "word", f"{name!r} should be a word"
            assert tokens[0].value == name, f"{name!r} value should be preserved"


class TestRealisticSource:

    def test_colon_definition(self):
        src = ": double  ( n -- 2n )\n  dup + ;"
        result = values_and_kinds(tokenize(src))
        expected = [tok(":"), tok("double"), tok("dup"), tok("+"), tok(";")]
        assert result == expected, "colon definition with comment should tokenize cleanly"

    def test_hex_and_words(self):
        src = "$4000 constant screen-start"
        result = values_and_kinds(tokenize(src))
        expected = [tok("$4000", "number"), tok("constant"), tok("screen-start")]
        assert result == expected, "hex constant definition should tokenize correctly"

    def test_string_output(self):
        src = ': greet  .\" Hello, Spectrum!\" cr ;'
        result = values_and_kinds(tokenize(src))
        expected = [
            tok(":"), tok("greet"),
            tok('.\"'), tok("Hello, Spectrum!", "string"),
            tok("cr"), tok(";"),
        ]
        assert result == expected, "string printing word should tokenize correctly"
