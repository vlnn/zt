import pytest

from zt.sim import ForthMachine


@pytest.fixture
def fm():
    return ForthMachine()


def _words(fm, *tokens):
    """Translate a mix of word names and literal ints into cell addresses."""
    cells = []
    for tok in tokens:
        if isinstance(tok, str):
            cells.append(fm.label(tok))
        else:
            cells.append(tok)
    return cells


def _run(fm, *tokens, stack=None):
    return fm.run(_words(fm, *tokens), initial_stack=stack)


class TestForthExpressions:

    @pytest.mark.parametrize("expr,expected", [
        (("LIT", 3, "LIT", 4, "PLUS"),               [7]),
        (("LIT", 10, "LIT", 3, "MINUS"),              [7]),
        (("LIT", 7, "DUP", "PLUS"),                   [14]),
        (("LIT", 5, "LIT", 3, "SWAP"),                [3, 5]),
        (("LIT", 1, "LIT", 2, "LIT", 3, "ROT"),       [2, 3, 1]),
    ], ids=["3+4", "10-3", "7 dup +", "5 3 swap", "1 2 3 rot"])
    def test_basic_expressions(self, fm, expr, expected):
        result = _run(fm, *expr)
        assert result.data_stack == expected, f"expression should yield {expected}"

    @pytest.mark.parametrize("expr,expected", [
        (("LIT", 6, "DUP", "PLUS"),                    [12]),
        (("LIT", 100, "DUP", "PLUS", "DUP", "PLUS"),   [400]),
        (("LIT", 0xAB, "LIT", 8, "LSHIFT",
          "LIT", 0xCD, "OR"),                           [0xABCD]),
        (("LIT", 0xABCD, "LIT", 0xFF, "AND"),          [0xCD]),
        (("LIT", 0xABCD, "LIT", 8, "RSHIFT"),          [0xAB]),
    ], ids=["double", "quadruple", "byte-merge", "low-byte-mask", "high-byte-extract"])
    def test_compound_arithmetic(self, fm, expr, expected):
        result = _run(fm, *expr)
        assert result.data_stack == expected, f"compound expression should yield {expected}"

    def test_negate_round_trip(self, fm):
        result = _run(fm, "LIT", 42, "NEGATE", "NEGATE")
        assert result.data_stack == [42], "double negate should be identity"

    def test_abs_of_negate(self, fm):
        result = _run(fm, "LIT", 42, "NEGATE", "ABS")
        assert result.data_stack == [42], "abs(negate(42)) should be 42"

    def test_min_max_bracket(self, fm):
        result = _run(fm, "LIT", 50, "LIT", 0, "MAX", "LIT", 100, "MIN")
        assert result.data_stack == [50], "clamp(50, 0, 100) should be 50"

    def test_clamp_below(self, fm):
        result = _run(fm, "LIT", 0, "LIT", 10, "MAX", "LIT", 100, "MIN")
        assert result.data_stack == [10], "clamp(0, 10, 100) should clamp up to 10"

    def test_clamp_above(self, fm):
        result = _run(fm, "LIT", 200, "LIT", 0, "MAX", "LIT", 100, "MIN")
        assert result.data_stack == [100], "clamp(200, 0, 100) should clamp down to 100"


class TestStackManipulation:

    def test_over_plus_is_add_without_consuming(self, fm):
        result = _run(fm, "LIT", 10, "LIT", 3, "OVER", "PLUS")
        assert result.data_stack == [10, 13], "a b -- a a+b via OVER PLUS"

    def test_tuck_idiom(self, fm):
        result = _run(fm, "LIT", 1, "LIT", 2, "TUCK")
        assert result.data_stack == [2, 1, 2], "TUCK should copy TOS below second"

    def test_2dup_equals_over_over(self, fm):
        r1 = _run(fm, "LIT", 3, "LIT", 7, "2DUP")
        r2 = _run(fm, "LIT", 3, "LIT", 7, "OVER", "OVER")
        assert r1.data_stack == r2.data_stack, "2DUP and OVER OVER should be equivalent"

    def test_nip_equals_swap_drop(self, fm):
        r1 = _run(fm, "LIT", 3, "LIT", 7, "NIP")
        r2 = _run(fm, "LIT", 3, "LIT", 7, "SWAP", "DROP")
        assert r1.data_stack == r2.data_stack, "NIP and SWAP DROP should be equivalent"

    def test_2swap_pairs(self, fm):
        result = _run(fm, "LIT", 1, "LIT", 2, "LIT", 3, "LIT", 4, "2SWAP")
        assert result.data_stack == [3, 4, 1, 2], "2SWAP should exchange pairs"


class TestReturnStackPatterns:

    def test_temporary_stash(self, fm):
        result = _run(fm,
            "LIT", 10,
            "LIT", 20,
            "LIT", 30,
            ">R", "PLUS", "R>",
        )
        assert result.data_stack == [30, 30], "stash 30, add 10+20, restore 30"

    def test_round_trip_via_return_stack(self, fm):
        result = _run(fm,
            "LIT", 1, "LIT", 2, "LIT", 3,
            ">R", ">R", ">R",
            "R>", "R>", "R>",
        )
        assert result.data_stack == [1, 2, 3], ">R >R >R R> R> R> should round-trip (LIFO identity)"

    def test_r_fetch_peeks_without_consuming(self, fm):
        result = _run(fm,
            "LIT", 42,
            ">R", "R@", "R@", "R>",
            "DROP",
        )
        assert result.data_stack == [42, 42], "R@ should copy without consuming"


class TestMemoryOperations:

    def test_cell_round_trip(self, fm):
        addr = 0xC000
        result = _run(fm,
            "LIT", 0xBEEF, "LIT", addr, "STORE",
            "LIT", addr, "FETCH",
        )
        assert result.data_stack == [0xBEEF], "store then fetch should round-trip"

    def test_byte_round_trip(self, fm):
        addr = 0xC000
        result = _run(fm,
            "LIT", 0x42, "LIT", addr, "C_STORE",
            "LIT", addr, "C_FETCH",
        )
        assert result.data_stack == [0x42], "c! then c@ should round-trip a byte"

    def test_c_fetch_zero_extends(self, fm):
        addr = 0xC000
        result = _run(fm,
            "LIT", 0xFFFF, "LIT", addr, "STORE",
            "LIT", addr, "C_FETCH",
        )
        assert result.data_stack == [0xFF], "c@ should zero-extend to 16 bits"

    def test_increment_memory_cell(self, fm):
        addr = 0xC000
        result = _run(fm,
            "LIT", 100, "LIT", addr, "STORE",
            "LIT", 7, "LIT", addr, "PLUS_STORE",
            "LIT", addr, "FETCH",
        )
        assert result.data_stack == [107], "+! should add to stored value"

    def test_fill_memory_region(self, fm):
        addr = 0xC000
        result = _run(fm,
            "LIT", addr, "LIT", 4, "LIT", 0xAA, "FILL",
            "LIT", addr, "C_FETCH",
            "LIT", addr + 3, "C_FETCH",
        )
        assert result.data_stack == [0xAA, 0xAA], "FILL should write byte to entire region"

    def test_cmove_copies_block(self, fm):
        src, dst = 0xC000, 0xC100
        result = _run(fm,
            "LIT", 0x1234, "LIT", src, "STORE",
            "LIT", src, "LIT", dst, "LIT", 2, "CMOVE",
            "LIT", dst, "FETCH",
        )
        assert result.data_stack == [0x1234], "CMOVE should copy memory block"

    def test_store_and_plus_store_accumulate(self, fm):
        addr = 0xC000
        result = _run(fm,
            "LIT", 0, "LIT", addr, "STORE",
            "LIT", 10, "LIT", addr, "PLUS_STORE",
            "LIT", 20, "LIT", addr, "PLUS_STORE",
            "LIT", 30, "LIT", addr, "PLUS_STORE",
            "LIT", addr, "FETCH",
        )
        assert result.data_stack == [60], "repeated +! should accumulate"


class TestComparisons:

    TRUE = 0xFFFF
    FALSE = 0x0000

    @pytest.mark.parametrize("a,b,lt,gt,eq", [
        (3, 5, True, False, False),
        (5, 3, False, True, False),
        (5, 5, False, False, True),
        (0, 0, False, False, True),
    ])
    def test_comparison_triangle(self, fm, a, b, lt, gt, eq):
        r_lt = _run(fm, "LIT", a, "LIT", b, "LESS_THAN")
        r_gt = _run(fm, "LIT", a, "LIT", b, "GREATER_THAN")
        r_eq = _run(fm, "LIT", a, "LIT", b, "EQUALS")
        assert r_lt.data_stack == [self.TRUE if lt else self.FALSE], f"{a} < {b} should be {lt}"
        assert r_gt.data_stack == [self.TRUE if gt else self.FALSE], f"{a} > {b} should be {gt}"
        assert r_eq.data_stack == [self.TRUE if eq else self.FALSE], f"{a} = {b} should be {eq}"

    def test_equals_and_not_equals_are_complementary(self, fm):
        for a, b in [(5, 5), (5, 3), (0, 1)]:
            r_eq = _run(fm, "LIT", a, "LIT", b, "EQUALS")
            r_ne = _run(fm, "LIT", a, "LIT", b, "NOT_EQUALS")
            assert r_eq.data_stack[0] ^ r_ne.data_stack[0] == 0xFFFF, (
                f"= and <> should be complementary for ({a}, {b})"
            )

    def test_zero_equals_as_logical_not(self, fm):
        r1 = _run(fm, "LIT", 0, "ZERO_EQUALS")
        r2 = _run(fm, "LIT", 1, "ZERO_EQUALS")
        r3 = _run(fm, "LIT", 0xBEEF, "ZERO_EQUALS")
        assert r1.data_stack == [self.TRUE], "0= of 0 should be true"
        assert r2.data_stack == [self.FALSE], "0= of nonzero should be false"
        assert r3.data_stack == [self.FALSE], "0= of nonzero should be false"


class TestColonDefinitions:

    def test_double(self, fm):
        result = fm.run_colon(
            body_cells=["DUP", "PLUS", "EXIT"],
            main_cells=["LIT", 21, "DOUBLE"],
        )
        assert result.data_stack == [42], ": double dup + ; 21 double should give 42"

    def test_quadruple_via_double_double(self, fm):
        result = fm.run_colon(
            body_cells=["DUP", "PLUS", "EXIT"],
            main_cells=["LIT", 10, "DOUBLE", "DOUBLE"],
        )
        assert result.data_stack == [40], "double(double(10)) should give 40"

    def test_colon_preserves_stack_below(self, fm):
        result = fm.run_colon(
            body_cells=["DUP", "PLUS", "EXIT"],
            main_cells=["LIT", 99, "LIT", 5, "DOUBLE"],
        )
        assert result.data_stack == [99, 10], "colon word should not disturb items below"


class TestBranching:

    def test_unconditional_branch_skips_code(self, fm):
        cells = [
            fm.label("LIT"), 1,
            fm.label("BRANCH"), "SKIP",
            fm.label("LIT"), 999,
            ("label", "SKIP"),
            fm.label("LIT"), 2,
        ]
        result = fm.run(cells)
        assert result.data_stack == [1, 2], "BRANCH should skip over LIT 999"


class TestBorderIO:

    def test_border_sequence(self, fm):
        result = _run(fm,
            "LIT", 0, "LIT", 1, "LIT", 2,
            "BORDER", "BORDER", "BORDER",
        )
        assert result.border_writes == [2, 1, 0], "BORDER should output values in TOS order"
        assert result.data_stack == [], "three BORDERs should consume three items"


class TestInitialStack:

    def test_run_with_preloaded_stack(self, fm):
        result = _run(fm, "DUP", "PLUS", stack=[21])
        assert result.data_stack == [42], "initial stack [21] then dup + should give 42"

    def test_multiple_initial_values(self, fm):
        result = _run(fm, "PLUS", "PLUS", stack=[10, 20, 12])
        assert result.data_stack == [42], "10 + 20 + 12 via initial stack should give 42"


class TestEdgeCases:

    def test_sixteen_bit_overflow(self, fm):
        result = _run(fm, "LIT", 0xFFFF, "LIT", 1, "PLUS")
        assert result.data_stack == [0], "0xFFFF + 1 should wrap to 0"

    def test_sixteen_bit_underflow(self, fm):
        result = _run(fm, "LIT", 0, "LIT", 1, "MINUS")
        assert result.data_stack == [0xFFFF], "0 - 1 should wrap to 0xFFFF"

    def test_shift_by_zero_is_identity(self, fm):
        result = _run(fm, "LIT", 0xABCD, "LIT", 0, "LSHIFT")
        assert result.data_stack == [0xABCD], "LSHIFT 0 should be identity"

    def test_shift_full_width(self, fm):
        result = _run(fm, "LIT", 1, "LIT", 15, "LSHIFT")
        assert result.data_stack == [0x8000], "1 LSHIFT 15 should give 0x8000"

    def test_invert_is_self_inverse(self, fm):
        result = _run(fm, "LIT", 0xBEEF, "INVERT", "INVERT")
        assert result.data_stack == [0xBEEF], "INVERT INVERT should be identity"

    def test_negate_of_zero(self, fm):
        result = _run(fm, "LIT", 0, "NEGATE")
        assert result.data_stack == [0], "NEGATE 0 should be 0"

    def test_two_slash_preserves_sign(self, fm):
        neg_four = (-4) & 0xFFFF
        result = _run(fm, "LIT", neg_four, "2/")
        assert result.data_stack == [(-2) & 0xFFFF], "2/ should arithmetic-shift (preserve sign)"

    def test_empty_program(self, fm):
        result = fm.run([])
        assert result.data_stack == [], "empty program should produce empty stack"

    def test_infinite_loop_times_out(self, fm):
        with pytest.raises(TimeoutError, match="exceeded"):
            fm.run([
                ("label", "LOOP"),
                fm.label("BRANCH"), "LOOP",
            ])
