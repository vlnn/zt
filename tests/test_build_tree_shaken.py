from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler


def _make_compiler():
    return Compiler(
        origin=0x8000, optimize=False,
        inline_next=True, inline_primitives=True,
        include_sprites=True,
    )


def _compile(source):
    c = _make_compiler()
    c.compile_source(source)
    c.compile_main_call()
    return c


def _run(image, origin, start_addr, dstack_top):
    from zt.sim import Z80, _read_data_stack
    m = Z80()
    m.load(origin, image)
    m.pc = start_addr
    m.run()
    if not m.halted:
        raise TimeoutError("execution timed out")
    return _read_data_stack(m, dstack_top, False)


@pytest.fixture
def parity():
    def _do(source):
        eager_c = _compile(source)
        tree_shaken_c = _compile(source)
        eager_image = eager_c.build()
        eager_start = eager_c.words["_start"].address
        tree_shaken_image, tree_shaken_start = tree_shaken_c.build_tree_shaken()
        eager_stack = _run(eager_image, eager_c.origin, eager_start, eager_c.data_stack_top)
        tree_shaken_stack = _run(tree_shaken_image, tree_shaken_c.origin, tree_shaken_start, tree_shaken_c.data_stack_top)
        return {
            "eager_size": len(eager_image),
            "tree_shaken_size": len(tree_shaken_image),
            "eager_stack": eager_stack,
            "tree_shaken_stack": tree_shaken_stack,
        }
    return _do


class TestRuntimeParity:

    def test_trivial_arithmetic(self, parity):
        result = parity(": main 1 2 + ;")
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "tree_shaken image should produce same final stack as eager image"
        )
        assert result["tree_shaken_stack"] == [3], (
            "1 2 + should leave 3 on the stack"
        )

    @pytest.mark.parametrize("source, expected_top", [
        (": main 5 3 - ;", 2),
        (": main 7 dup * ;", 49),
        (": main 10 5 swap drop ;", 5),
        (": main 1 2 3 rot ;", 1),
        (": main 100 200 over ;", 100),
    ])
    def test_arithmetic_and_stack_ops(self, parity, source, expected_top):
        result = parity(source)
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            f"tree_shaken/eager mismatch for {source!r}"
        )
        assert result["tree_shaken_stack"][-1] == expected_top, (
            f"top of stack should be {expected_top} for {source!r}"
        )

    def test_user_colon_call(self, parity):
        source = """
        : double dup + ;
        : main 7 double ;
        """
        result = parity(source)
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "user colon definition should work identically in tree_shaken image"
        )
        assert result["tree_shaken_stack"] == [14], (
            "double of 7 should be 14"
        )

    def test_nested_colons(self, parity):
        source = """
        : square dup * ;
        : sum-of-squares square swap square + ;
        : main 3 4 sum-of-squares ;
        """
        result = parity(source)
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "nested colons should resolve correctly under tree-shaking"
        )
        assert result["tree_shaken_stack"] == [25], (
            "3*3 + 4*4 should be 25"
        )

    def test_if_then(self, parity):
        source = """
        : main 5 0 > if 42 then ;
        """
        result = parity(source)
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "if/then should produce same result"
        )
        assert result["tree_shaken_stack"] == [42], (
            "5 > 0 is true so 42 should be pushed"
        )

    def test_begin_until_loop(self, parity):
        source = """
        : main 10 begin 1- dup 0 = until ;
        """
        result = parity(source)
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "begin/until should produce same result"
        )


class TestSizeReduction:

    def test_tree_shaken_is_smaller_for_trivial_program(self, parity):
        result = parity(": main 1 2 + ;")
        assert result["tree_shaken_size"] < result["eager_size"], (
            f"tree_shaken image ({result['tree_shaken_size']} bytes) should be smaller "
            f"than eager image ({result['eager_size']} bytes) for a trivial program"
        )

    def test_tree_shaken_savings_are_substantial(self, parity):
        result = parity(": main 1 2 + ;")
        savings_pct = (1 - result["tree_shaken_size"] / result["eager_size"]) * 100
        assert savings_pct > 50, (
            f"trivial program should shave more than 50% of image size, got {savings_pct:.1f}%"
        )


class TestStringSupport:

    def test_s_quote_then_drop_drop(self, parity):
        result = parity('''
            : main s" hi" drop drop ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            's" addr len; drop drop should leave empty stack identically'
        )
        assert result["tree_shaken_stack"] == [], (
            'after drop drop there should be nothing on the stack'
        )

    def test_s_quote_length_only(self, parity):
        result = parity('''
            : main s" hello" nip ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            'string length should match between eager and tree_shaken'
        )
        assert result["tree_shaken_stack"] == [5], (
            's" hello" nip should leave the length 5 on the stack'
        )

    def test_two_distinct_strings(self, parity):
        result = parity('''
            : main s" abc" nip s" defgh" nip + ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "two string lengths summed should match"
        )
        assert result["tree_shaken_stack"] == [8], (
            "len('abc') + len('defgh') = 8"
        )

    def test_strings_used_in_user_colon(self, parity):
        result = parity('''
            : len-of s" probe" nip ;
            : main len-of len-of + ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "string referenced from a user colon should resolve correctly under tree-shaking"
        )
        assert result["tree_shaken_stack"] == [10], (
            "twice len('probe') = 10"
        )


class TestConstantSupport:

    def test_constant_pushes_value(self, parity):
        result = parity('''
            42 constant the-answer
            : main the-answer ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "constant should push its value identically in both images"
        )
        assert result["tree_shaken_stack"] == [42], (
            "the-answer should push 42"
        )

    def test_multiple_constants(self, parity):
        result = parity('''
            10 constant a
            20 constant b
            : main a b + ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "two constants summed should match"
        )
        assert result["tree_shaken_stack"] == [30], "10 + 20 = 30"

    def test_unused_constant_is_dead(self, parity):
        result = parity('''
            999 constant unused-thing
            42 constant used-thing
            : main used-thing ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "unused constant should be dropped without affecting behavior"
        )
        assert result["tree_shaken_stack"] == [42]


class TestVariableSupport:

    def test_variable_store_and_fetch(self, parity):
        result = parity('''
            variable counter
            : main 42 counter ! counter @ ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "variable store-then-fetch should match"
        )
        assert result["tree_shaken_stack"] == [42], (
            "after !42 then @, top should be 42"
        )

    def test_variable_initial_value_zero(self, parity):
        result = parity('''
            variable v
            : main v @ ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "variable initial fetch should match"
        )
        assert result["tree_shaken_stack"] == [0], (
            "uninitialized variable should fetch as 0"
        )

    def test_two_variables_independent(self, parity):
        result = parity('''
            variable a
            variable b
            : main 11 a ! 22 b ! a @ b @ + ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "two distinct variables should each retain their own values"
        )
        assert result["tree_shaken_stack"] == [33], "11 + 22 = 33"

    def test_create_with_comma_data(self, parity):
        result = parity('''
            create table  10 , 20 , 30 ,
            : main table @ table 2 + @ + ;
        ''')
        assert result["tree_shaken_stack"] == result["eager_stack"], (
            "create + comma data should be re-emitted with correct contents"
        )
        assert result["tree_shaken_stack"] == [30], (
            "table[0]=10 + table[1]=20 should be 30"
        )


class TestCanonicalCaseInvariant:

    def test_lit_primitive_only_uppercase_label_resolves_correctly(self, parity):
        result = parity(": main 42 ;")
        assert result["tree_shaken_stack"] == [42], (
            "literal 42 routes through the LIT primitive (uppercase canonical, "
            "no lowercase alias); tree-shaking must resolve `lit` from liveness "
            "to the LIT blob's address"
        )

    def test_word_addrs_dict_is_lowercase_canonical(self):
        from zt.compile.tree_shake import _primitive_addrs
        from zt.assemble.asm import Asm
        from zt.assemble.primitive_blob import emit_blob, harvest_primitive
        from zt.assemble.primitives import create_dup
        new_asm = Asm(origin=0x8000)
        emit_blob(new_asm, harvest_primitive(create_dup, inline_next=True))
        addrs = _primitive_addrs(new_asm)
        assert all(k == k.lower() for k in addrs), (
            f"_primitive_addrs should return only lowercase keys; got mixed-case: "
            f"{[k for k in addrs if k != k.lower()]}"
        )
        assert "dup" in addrs, "lowercase 'dup' should be in word_addrs"


class TestBuildTreeShakenPostState:

    def test_compiler_words_main_address_matches_tree_shaken_image(self):
        c = _compile(": main 1 2 + ;")
        tree_shaken_image, _ = c.build_tree_shaken()
        assert c.words["main"].address < c.origin + len(tree_shaken_image), (
            "after build_tree_shaken, compiler.words['main'].address should fall "
            "within the tree_shaken image"
        )

    def test_start_address_in_compiler_words_matches_returned_start(self):
        c = _compile(": main 1 ;")
        _, returned_start = c.build_tree_shaken()
        assert c.words["_start"].address == returned_start, (
            "compiler.words['_start'].address must match the start_addr returned "
            "from build_tree_shaken so CLI/write_output can use it uniformly"
        )

    def test_dead_user_colons_dropped_from_dictionary(self):
        c = _compile('''
            : unused-helper 99 99 + ;
            : main 1 ;
        ''')
        assert "unused-helper" in c.words, (
            "before build_tree_shaken, dead colon should still be in dictionary"
        )
        c.build_tree_shaken()
        assert "unused-helper" not in c.words, (
            "after build_tree_shaken, dead user colon should be removed from "
            "compiler.words so debug artifacts (mapfile, sld) reflect the "
            "tree_shaken image"
        )

    def test_live_user_colon_address_updates(self):
        c = _compile(": main 1 ;")
        before_addr = c.words["main"].address
        c.build_tree_shaken()
        after_addr = c.words["main"].address
        assert after_addr != before_addr, (
            "main's address should shift in the tree_shaken image (it's packed "
            "tighter against fewer primitives)"
        )

    def test_compiler_asm_replaced_with_tree_shaken_image(self):
        c = _compile(": main 1 ;")
        tree_shaken_image, _ = c.build_tree_shaken()
        assert bytes(c.asm.code) == tree_shaken_image, (
            "after build_tree_shaken, compiler.asm should hold the tree_shaken image "
            "so write_output / write_map can use the same compiler reference"
        )


class TestRealExamples:

    @pytest.mark.parametrize("path", [
        "examples/sierpinski/main.fs",
    ])
    def test_halting_example_runs_with_full_parity(self, path):
        from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80, _read_data_stack
        text = open(path).read()
        eager_c = Compiler(
            origin=0x8000, optimize=False, inline_next=True,
            inline_primitives=True, include_sprites=True,
        )
        eager_c.include_stdlib()
        eager_c.compile_source(text, source=path)
        eager_c.compile_main_call()
        eager_image = eager_c.build()
        eager_start = eager_c.words["_start"].address

        tree_shaken_c = Compiler(
            origin=0x8000, optimize=False, inline_next=True,
            inline_primitives=True, include_sprites=True,
        )
        tree_shaken_c.include_stdlib()
        tree_shaken_c.compile_source(text, source=path)
        tree_shaken_c.compile_main_call()
        tree_shaken_image, tree_shaken_start = tree_shaken_c.build_tree_shaken()

        def run(image, start):
            m = Z80()
            m.load(0x8000, image)
            m.load(SPECTRUM_FONT_BASE, TEST_FONT)
            m.pc = start
            m.run(max_ticks=5_000_000)
            return m.halted, _read_data_stack(m, eager_c.data_stack_top, False)

        eager_halted, eager_stk = run(eager_image, eager_start)
        tree_shaken_halted, tree_shaken_stk = run(tree_shaken_image, tree_shaken_start)
        assert eager_halted, f"eager build of {path} should halt under tick budget"
        assert tree_shaken_halted, f"tree_shaken build of {path} should halt under tick budget"
        assert eager_stk == tree_shaken_stk, (
            f"halt-state stacks should match for {path}: "
            f"eager={eager_stk}, tree_shaken={tree_shaken_stk}"
        )
        assert len(tree_shaken_image) < len(eager_image), (
            f"tree_shaken image of {path} should be smaller than eager: "
            f"eager={len(eager_image)}, tree_shaken={len(tree_shaken_image)}"
        )

    @pytest.mark.parametrize("path", [
        "examples/plasma4/main.fs",
        "examples/reaction/main.fs",
        "examples/mined-out/main.fs",
    ])
    def test_real_example_compiles_to_smaller_image(self, path):
        text = open(path).read()
        c = Compiler(
            origin=0x8000, optimize=False, inline_next=True,
            inline_primitives=True, include_sprites=True,
        )
        c.include_stdlib()
        c.compile_source(text, source=path)
        c.compile_main_call()
        eager_size = len(c.build())

        c2 = Compiler(
            origin=0x8000, optimize=False, inline_next=True,
            inline_primitives=True, include_sprites=True,
        )
        c2.include_stdlib()
        c2.compile_source(text, source=path)
        c2.compile_main_call()
        tree_shaken_image, _ = c2.build_tree_shaken()
        assert len(tree_shaken_image) < eager_size, (
            f"tree_shaken image of {path} should be smaller: "
            f"eager={eager_size}, tree_shaken={len(tree_shaken_image)}"
        )


class TestUnsupportedFeaturesRoutedClearly:

    def test_tick_directive_rejected(self):
        c = _compile('''
            : main 1 ;
            ' main constant main-addr
            : run main-addr ;
        ''')
        with pytest.raises(NotImplementedError, match="tick|address-as-data"):
            c.build_tree_shaken()

    def test_bracket_tick_rejected(self):
        c = _compile('''
            : helper 1 + ;
            : main 7 ['] helper drop ;
        ''')
        with pytest.raises(NotImplementedError, match="bracket-tick|\\[']"):
            c.build_tree_shaken()

    def test_banked_code_rejected(self):
        from zt.compile.compiler import Compiler

        c = Compiler(
            origin=0x8000, optimize=False, inline_next=True,
            inline_primitives=True, include_sprites=False,
        )
        c.compile_source(
            "0 in-bank create banked-data $42 c, end-bank\n"
            ": main 1 ;\n",
            source="<banked>",
        )
        c.compile_main_call()
        with pytest.raises(NotImplementedError, match="banked code|in-bank"):
            c.build_tree_shaken()
