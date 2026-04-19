"""
Tests for `INLINABLE_PRIMITIVES` safety predicates (mid-body dispatch / absolute jumps / whitelist audit) and the expected shape of whitelisted primitive bodies.
"""
from __future__ import annotations

import pytest

from zt.assemble.inline_bodies import (
    INLINABLE_PRIMITIVES,
    build_inline_registry,
    extract_inline_body,
    has_absolute_jump_in_body,
    has_mid_body_dispatch,
    is_primitive_inlinable,
    primitive_name,
)
from zt.assemble.primitives import (
    PRIMITIVES,
    create_branch,
    create_halt,
    create_lit,
    create_zbranch,
)


class TestIsPrimitiveInlinable:

    @pytest.mark.parametrize("name", [
        "dup", "drop", "swap", "over", "nip", "rot", "tuck",
        "2dup", "2drop",
        "plus", "minus",
        "one_plus", "one_minus", "two_star", "two_slash",
        "zero", "one",
        "negate",
        "and", "or", "xor", "invert",
        "fetch", "store", "c_fetch", "c_store", "plus_store", "dup_fetch",
        "border",
        "lshift",
    ])
    def test_known_safe_primitives_are_inlinable(self, name):
        assert is_primitive_inlinable(name), \
            f"{name!r} should be whitelisted for inlining"

    @pytest.mark.parametrize("name", [
        "next", "docol", "exit",
        "lit", "branch", "zbranch",
        "do_rt", "loop_rt", "ploop_rt",
        "i_index", "j_index", "unloop",
        "halt",
        "less_than", "greater_than",
        "min", "max", "abs",
        "multiply", "u_mod_div",
        "emit", "key", "key_query", "type",
    ])
    def test_threaded_or_unsafe_primitives_are_not_inlinable(self, name):
        assert not is_primitive_inlinable(name), \
            f"{name!r} must not be inlinable (threaded or uses absolute jumps)"

    def test_unknown_primitive_is_not_inlinable(self):
        assert not is_primitive_inlinable("this-does-not-exist"), \
            "unknown primitive names must conservatively report as non-inlinable"

    def test_empty_name_is_not_inlinable(self):
        assert not is_primitive_inlinable(""), \
            "empty string is not a valid primitive name"


class TestWhitelistConsistency:

    def test_every_whitelisted_name_has_an_inline_body(self):
        registry = build_inline_registry(PRIMITIVES)
        missing = INLINABLE_PRIMITIVES - set(registry)
        assert not missing, \
            f"every whitelisted primitive must have an extractable body; missing: {sorted(missing)}"

    @pytest.mark.parametrize("threading_name", [
        "next", "docol", "exit",
        "lit", "branch", "zbranch",
        "do_rt", "loop_rt", "ploop_rt",
        "i_index", "j_index", "unloop",
        "halt",
    ])
    def test_no_threading_primitive_leaked_into_whitelist(self, threading_name):
        assert threading_name not in INLINABLE_PRIMITIVES, \
            f"threading primitive {threading_name!r} must never be whitelisted"


class TestHasMidBodyDispatch:

    @pytest.mark.parametrize("creator", [create_zbranch])
    def test_multi_dispatch_primitives_are_flagged(self, creator):
        assert has_mid_body_dispatch(creator), \
            f"{creator.__name__} has an intermediate JP NEXT and must be flagged"

    def test_single_dispatch_primitives_are_not_flagged(self):
        from zt.assemble.primitives import create_dup, create_plus, create_fetch
        for creator in (create_dup, create_plus, create_fetch):
            assert not has_mid_body_dispatch(creator), \
                f"{creator.__name__} has only its trailing dispatch and must not be flagged"

    def test_non_extractable_primitive_is_not_flagged(self):
        assert not has_mid_body_dispatch(create_halt), \
            "halt has no dispatch at all and cannot have a mid-body one"

    def test_lit_reads_ix_but_has_single_dispatch(self):
        assert not has_mid_body_dispatch(create_lit), \
            "lit is single-dispatch; its non-inlinability comes from (IX), not mid-body JP"


class TestHasAbsoluteJumpInBody:

    def test_zbranch_is_flagged_due_to_two_dispatch_sites(self):
        assert has_absolute_jump_in_body(create_zbranch), \
            "zbranch has two dispatch sites; stripping the last leaves a JP NEXT in the body"

    def test_branch_is_not_flagged(self):
        assert not has_absolute_jump_in_body(create_branch), \
            "branch has only a trailing dispatch; no absolute fixup should remain in the body"

    def test_simple_primitive_has_no_absolute_jump(self):
        from zt.assemble.primitives import create_dup, create_drop, create_plus
        for creator in (create_dup, create_drop, create_plus):
            assert not has_absolute_jump_in_body(creator), \
                f"{creator.__name__} body should have no absolute-addressed fixup"

    def test_non_extractable_primitive_is_not_flagged(self):
        assert not has_absolute_jump_in_body(create_halt), \
            "halt has no extractable body and cannot be flagged"

    def test_abs_flagged_due_to_conditional_jp_z(self):
        from zt.assemble.primitives import create_abs
        assert has_absolute_jump_in_body(create_abs), \
            "abs uses `jp_z _abs_done` (absolute JP Z,nn) and must be flagged as relocation-unsafe"

    def test_less_than_flagged_due_to_conditional_jp_p(self):
        from zt.assemble.primitives import create_less_than
        assert has_absolute_jump_in_body(create_less_than), \
            "less_than uses `jp_p _lt_done` (absolute JP P,nn) and must be flagged"

    def test_greater_than_flagged_due_to_conditional_jp_p(self):
        from zt.assemble.primitives import create_greater_than
        assert has_absolute_jump_in_body(create_greater_than), \
            "greater_than uses `jp_p _gt_done` (absolute JP P,nn) and must be flagged"

    def test_lshift_is_not_false_positive_despite_unsafe_operand_byte(self):
        from zt.assemble.primitives import create_lshift
        assert not has_absolute_jump_in_body(create_lshift), \
            "lshift contains byte 0xFC as a jr displacement operand (not an opcode); " \
            "the audit must not false-positive on operand bytes"

    def test_rshift_is_not_flagged(self):
        from zt.assemble.primitives import create_rshift
        assert not has_absolute_jump_in_body(create_rshift), \
            "rshift uses only relative jumps (jr_z_to, jr_nz_to) and must not be flagged"

    def test_min_is_not_flagged(self):
        from zt.assemble.primitives import create_min
        assert not has_absolute_jump_in_body(create_min), \
            "min uses only `jr_c_to` (relative) and must not be flagged"

    def test_equals_is_not_flagged(self):
        from zt.assemble.primitives import create_equals
        assert not has_absolute_jump_in_body(create_equals), \
            "equals uses only `jr_nz_to` (relative) and must not be flagged"


class TestWhitelistSafetyAudit:

    @pytest.mark.parametrize("name", sorted(INLINABLE_PRIMITIVES))
    def test_no_whitelisted_primitive_has_a_mid_body_dispatch(self, name):
        creator = _find_creator(name)
        assert creator is not None, \
            f"could not find create_{name} in PRIMITIVES"
        assert not has_mid_body_dispatch(creator), \
            f"{name!r} has a mid-body JP NEXT and is unsafe to paste as a block"

    @pytest.mark.parametrize("name", sorted(INLINABLE_PRIMITIVES))
    def test_no_whitelisted_primitive_has_an_absolute_jump(self, name):
        creator = _find_creator(name)
        assert creator is not None, \
            f"could not find create_{name} in PRIMITIVES"
        assert not has_absolute_jump_in_body(creator), \
            f"{name!r} body contains a 0xC3 byte — possibly an absolute JP, unsafe to relocate"


class TestBodyShapeForWhitelistedPrimitives:

    @pytest.mark.parametrize("name", [
        "one_plus", "one_minus", "two_star", "nip", "drop",
    ])
    def test_tiny_primitives_are_under_four_bytes(self, name):
        body = extract_inline_body(_find_creator(name))
        assert body is not None and len(body) <= 4, \
            f"{name!r} should be tiny (≤4 bytes) to justify the default threshold"

    @pytest.mark.parametrize("name", sorted(INLINABLE_PRIMITIVES))
    def test_whitelisted_bodies_are_under_twenty_bytes(self, name):
        body = extract_inline_body(_find_creator(name))
        assert body is not None, \
            f"{name!r} must be extractable"
        assert len(body) <= 20, \
            f"{name!r} body is {len(body)} bytes; whitelist should favour short bodies"


def _find_creator(name: str):
    for creator in PRIMITIVES:
        if primitive_name(creator) == name:
            return creator
    return None
