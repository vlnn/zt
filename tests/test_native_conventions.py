"""
Byte-level tests for the three native calling conventions and for the start stub.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from native_harness import compile_program
from zt.compile.native.labels import (
    colon_label,
    return_operand_label,
    return_slot_label,
)

POP_IX = bytes([0xDD, 0xE1])
JP_IX = bytes([0xDD, 0xE9])
POP_BC_STORE = bytes([0xC1, 0xED, 0x43])
FRAME_ENTRY = bytes([0xD1, 0xFD, 0x2B, 0xFD, 0x2B, 0xFD, 0x73, 0x00, 0xFD, 0x72, 0x01])
FRAME_RETURN = bytes([0xFD, 0x5E, 0x00, 0xFD, 0x56, 0x01, 0xFD, 0x23, 0xFD, 0x23, 0xD5, 0xC9])
CALL = 0xCD
JP = 0xC3

SOURCE = """
: leaf      ( n -- n )  1+ 2* ;
: caller    ( n -- n )  dup * leaf ;
: fact      ( n -- n )  dup 1 > if dup 1- recurse * then ;
: apply     ( xt -- )   execute ;
: early     ( n -- n )  dup 0= if exit then dup * ;
: big-leaf  ( n -- n )  1+ 1+ 1+ 1+ 1+ 1+ 1+ 1+ 1+ 1+ 1+ 1+ ;
: main  3 caller fact ['] big-leaf apply early big-leaf halt ;
"""


@pytest.fixture(scope="module")
def built():
    compiler = compile_program(SOURCE)
    image, start = compiler.build_native()
    return compiler, image, start


def _code_at(built, label: str, length: int) -> bytes:
    compiler, image, _ = built
    offset = compiler.asm.labels[label] - compiler.origin
    return image[offset:offset + length]


def _address(built, label: str) -> int:
    return built[0].asm.labels[label]


class TestLeafConvention:

    def test_leaf_entry_pops_return_address_into_ix(self, built):
        assert _code_at(built, colon_label("big-leaf"), 2) == POP_IX, \
            "a leaf word should keep its return address in IX"

    def test_leaf_returns_through_ix(self, built):
        body = _code_at(built, colon_label("big-leaf"), 2 + 12 + 2)
        assert body.endswith(JP_IX), "a leaf word should return with JP (IX)"

    def test_small_leaf_is_pasted_and_not_emitted(self, built):
        assert colon_label("leaf") not in built[0].asm.labels, \
            "a small leaf that is only called should disappear into its callers"


class TestStaticConvention:

    def test_static_entry_patches_its_return_slot(self, built):
        assert _code_at(built, colon_label("caller"), 3) == POP_BC_STORE, \
            "a non-reentrant word should store its return address into its return slot"

    def test_static_entry_targets_its_own_slot_operand(self, built):
        entry = _code_at(built, colon_label("caller"), 5)
        operand = entry[3] | (entry[4] << 8)
        assert operand == _address(built, return_operand_label("caller")), \
            "the entry should patch the operand of the word's own return jump"

    def test_static_return_is_a_patchable_jump(self, built):
        assert _code_at(built, return_slot_label("caller"), 1)[0] == JP, \
            "the return slot should be a JP whose operand the entry overwrites"

    def test_slot_operand_follows_the_jump_opcode(self, built):
        slot = _address(built, return_slot_label("caller"))
        assert _address(built, return_operand_label("caller")) == slot + 1, \
            "the patched operand should sit right after the JP opcode"

    def test_early_exit_jumps_to_the_single_slot(self, built):
        compiler, image, _ = built
        start = _address(built, colon_label("early")) - compiler.origin
        slot = _address(built, return_slot_label("early"))
        body = image[start:slot - compiler.origin]
        jump = bytes([JP, slot & 0xFF, slot >> 8])
        assert jump in body, "an early EXIT should jump to the word's one return slot"


class TestFrameConvention:

    @pytest.mark.parametrize("name,reason", [
        ("fact", "it is recursive"),
        ("apply", "it contains EXECUTE"),
        ("main", "it reaches EXECUTE"),
    ])
    def test_reentrant_word_saves_return_address_on_return_stack(self, built, name, reason):
        assert _code_at(built, colon_label(name), len(FRAME_ENTRY)) == FRAME_ENTRY, \
            f"{name!r} should push its return address on the IY stack because {reason}"

    def test_frame_word_returns_from_return_stack(self, built):
        compiler, image, _ = built
        start = _address(built, colon_label("apply")) - compiler.origin
        assert FRAME_RETURN in image[start:start + 40], \
            "a frame word should pop its return address from the IY stack and RET"


class TestStartStub:

    def test_image_starts_with_the_start_stub(self, built):
        compiler, _, start = built
        assert start == compiler.origin, "the native start stub should sit at the origin"

    def test_start_stub_disables_interrupts_first(self, built):
        assert _code_at(built, "_start", 1)[0] == 0xF3, "_start should begin with DI"

    def test_start_stub_calls_main(self, built):
        stub = _code_at(built, "_start", 11)
        target = stub[9] | (stub[10] << 8)
        assert stub[8] == CALL and target == _address(built, colon_label("main")), \
            "_start should CALL main after setting up both stacks"

    def test_start_stub_parks_in_a_halt_loop(self, built):
        assert _code_at(built, "__halt__", 3) == bytes([0x76, 0x18, 0xFD]), \
            "after main returns the stub should HALT in a loop"


class TestCommittedDictionary:

    def test_start_word_points_at_the_stub(self, built):
        compiler, _, start = built
        assert compiler.words["_start"].address == start, \
            "the dictionary's _start should point at the native stub"

    def test_emitted_colon_gets_its_native_address(self, built):
        compiler, _, _ = built
        assert compiler.words["caller"].address == _address(built, colon_label("caller")), \
            "an emitted colon should be relocated to its native entry"

    def test_pasted_colon_has_no_address(self, built):
        assert built[0].words["leaf"].address == 0, \
            "a colon that was pasted into its callers should have no address"

    def test_dead_stdlib_words_are_dropped(self, built):
        assert "spaces" not in built[0].words, \
            "words unreachable from main should be dropped from the dictionary"

    def test_source_map_is_cleared(self, built):
        assert built[0].source_map == [], \
            "threaded cell addresses no longer exist, so the source map should be empty"


class TestVariablesAfterBuild:

    def test_variable_is_relocated_to_its_data(self):
        compiler = compile_program("variable v : main 5 v ! halt ;")
        compiler.build_native()
        word = compiler.words["v"]
        assert word.address == word.data_address != 0, \
            "a variable has no code shim natively, so both addresses should be its data"
