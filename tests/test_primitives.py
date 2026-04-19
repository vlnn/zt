"""
Byte-for-byte tests that each `create_*` primitive in `zt.assemble.primitives` compiles to its expected exact Z80 byte sequence.
"""
import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitives import (
    create_next, create_docol, create_exit,
    create_dup, create_drop, create_swap, create_over,
    create_rot, create_nip, create_tuck,
    create_2dup, create_2drop, create_2swap,
    create_to_r, create_r_from, create_r_fetch,
    create_plus, create_minus,
    create_one_plus, create_one_minus,
    create_two_star, create_two_slash,
    create_negate, create_abs,
    create_min, create_max,
    create_and, create_or, create_xor, create_invert,
    create_lshift, create_rshift,
    create_equals, create_not_equals,
    create_less_than, create_greater_than,
    create_zero_equals, create_zero_less,
    create_u_less,
    create_fetch, create_store,
    create_c_fetch, create_c_store,
    create_plus_store,
    create_cmove, create_fill,
    create_lit, create_branch, create_halt, create_border,
    create_u_mod_div, create_multiply,
    PRIMITIVES,
)


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _compile_primitive(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


def test_next_byte_sequence():
    a = Asm(0x8000)
    create_next(a)
    a.resolve()
    expected = bytes([
        0xDD, 0x5E, 0x00,
        0xDD, 0x56, 0x01,
        0xDD, 0x23,
        0xDD, 0x23,
        0xD5,
        0xC9,
    ])
    assert bytes(a.code) == expected, "NEXT should be the canonical 12-byte sequence"


def test_dup_is_push_hl_then_jp_next():
    out = _compile_primitive(create_dup)
    assert out[0] == 0xE5, "DUP should start with PUSH HL"
    assert out[1] == 0xC3, "DUP should jump to NEXT"


def test_plus_is_pop_de_add_hl_de_then_jp_next():
    out = _compile_primitive(create_plus)
    assert out[:3] == bytes([0xD1, 0x19, 0xC3]), "PLUS should be POP DE; ADD HL,DE; JP NEXT"


def test_border_compiles_out_to_port_fe():
    out = _compile_primitive(create_border)
    assert out[0] == 0x7D, "BORDER should start with LD A,L"
    assert out[1:3] == bytes([0xD3, 0xFE]), "BORDER should OUT (0xFE),A"
    assert out[3] == 0xE1, "BORDER should POP HL for new TOS"


def test_branch_layout():
    out = _compile_primitive(create_branch)
    assert out[0:3] == bytes([0xDD, 0x5E, 0x00]), "BRANCH should start with LD E,(IX+0)"
    assert out[3:6] == bytes([0xDD, 0x56, 0x01]), "then LD D,(IX+1)"
    assert out[6] == 0xD5, "then PUSH DE"
    assert out[7:9] == bytes([0xDD, 0xE1]), "then POP IX"


@pytest.mark.parametrize("creator,expected_prefix", [
    (create_drop,      [0xE1]),
    (create_swap,      [0xE3]),
    (create_nip,       [0xD1]),
    (create_2drop,     [0xE1, 0xE1]),
    (create_one_plus,  [0x23]),
    (create_one_minus, [0x2B]),
    (create_two_star,  [0x29]),
    (create_two_slash, [0xCB, 0x2C, 0xCB, 0x1D]),
    (create_halt,      [0x76]),
], ids=[
    "drop", "swap", "nip", "2drop",
    "1+", "1-", "2*", "2/", "halt",
])
def test_simple_primitive_prefix(creator, expected_prefix):
    out = _compile_primitive(creator)
    prefix = out[:len(expected_prefix)]
    assert prefix == bytes(expected_prefix), (
        f"{creator.__name__} should start with {[hex(b) for b in expected_prefix]}"
    )


@pytest.mark.parametrize("creator", [
    create_drop, create_swap, create_nip,
    create_2drop, create_one_plus, create_one_minus,
    create_two_star, create_two_slash,
], ids=[
    "drop", "swap", "nip", "2drop",
    "1+", "1-", "2*", "2/",
])
def test_simple_primitive_ends_with_jp_next(creator):
    out = _compile_primitive(creator)
    assert out[-3] == 0xC3, f"{creator.__name__} should end with JP"
    assert out[-2:] == bytes([0x00, 0x80]), f"{creator.__name__} should JP to NEXT at 0x8000"


def test_over_byte_sequence():
    out = _compile_primitive(create_over)
    assert out[:5] == bytes([0xD1, 0xD5, 0xE5, 0xEB, 0xC3]), (
        "OVER should be POP DE; PUSH DE; PUSH HL; EX DE,HL; JP NEXT"
    )


def test_rot_byte_sequence():
    out = _compile_primitive(create_rot)
    assert out[:7] == bytes([0xD1, 0xC1, 0xD5, 0xE5, 0x60, 0x69, 0xC3]), (
        "ROT should be POP DE; POP BC; PUSH DE; PUSH HL; LD H,B; LD L,C; JP NEXT"
    )


def test_tuck_byte_sequence():
    out = _compile_primitive(create_tuck)
    assert out[:4] == bytes([0xD1, 0xE5, 0xD5, 0xC3]), (
        "TUCK should be POP DE; PUSH HL; PUSH DE; JP NEXT"
    )


def test_2dup_byte_sequence():
    out = _compile_primitive(create_2dup)
    assert out[:5] == bytes([0xD1, 0xD5, 0xE5, 0xD5, 0xC3]), (
        "2DUP should be POP DE; PUSH DE; PUSH HL; PUSH DE; JP NEXT"
    )


def test_2swap_byte_sequence():
    out = _compile_primitive(create_2swap)
    assert out[:9] == bytes([
        0xEB,       # EX DE,HL
        0xE1,       # POP HL
        0xC1,       # POP BC
        0xE3,       # EX (SP),HL
        0xD5,       # PUSH DE
        0xE5,       # PUSH HL
        0x60,       # LD H,B
        0x69,       # LD L,C
        0xC3,       # JP NEXT
    ]), "2SWAP should be EX DE,HL; POP HL; POP BC; EX (SP),HL; PUSH DE; PUSH HL; LD H,B; LD L,C; JP NEXT"


def test_to_r_byte_sequence():
    out = _compile_primitive(create_to_r)
    assert out[:2] == bytes([0xFD, 0x2B]), ">R should start with DEC IY"
    assert out[2:4] == bytes([0xFD, 0x2B]), ">R should DEC IY twice"
    assert out[4:7] == bytes([0xFD, 0x75, 0x00]), ">R should LD (IY+0),L"
    assert out[7:10] == bytes([0xFD, 0x74, 0x01]), ">R should LD (IY+1),H"
    assert out[10] == 0xE1, ">R should POP HL for new TOS"


def test_r_from_byte_sequence():
    out = _compile_primitive(create_r_from)
    assert out[0] == 0xE5, "R> should start with PUSH HL"
    assert out[1:4] == bytes([0xFD, 0x6E, 0x00]), "R> should LD L,(IY+0)"
    assert out[4:7] == bytes([0xFD, 0x66, 0x01]), "R> should LD H,(IY+1)"
    assert out[7:9] == bytes([0xFD, 0x23]), "R> should INC IY"
    assert out[9:11] == bytes([0xFD, 0x23]), "R> should INC IY twice"


def test_r_fetch_byte_sequence():
    out = _compile_primitive(create_r_fetch)
    assert out[0] == 0xE5, "R@ should start with PUSH HL"
    assert out[1:4] == bytes([0xFD, 0x6E, 0x00]), "R@ should LD L,(IY+0)"
    assert out[4:7] == bytes([0xFD, 0x66, 0x01]), "R@ should LD H,(IY+1)"
    assert out[7] == 0xC3, "R@ should end with JP NEXT"


def test_minus_byte_sequence():
    out = _compile_primitive(create_minus)
    assert out[:5] == bytes([0xD1, 0xEB, 0xB7, 0xED, 0x52]), (
        "MINUS should be POP DE; EX DE,HL; OR A; SBC HL,DE"
    )


def test_negate_byte_sequence():
    out = _compile_primitive(create_negate)
    assert out[:6] == bytes([0xAF, 0x95, 0x6F, 0x9F, 0x94, 0x67]), (
        "NEGATE should be XOR A; SUB L; LD L,A; SBC A,A; SUB H; LD H,A"
    )


def test_abs_starts_with_bit_test():
    out = _compile_primitive(create_abs)
    assert out[:2] == bytes([0xCB, 0x7C]), "ABS should start with BIT 7,H"
    assert out[2] == 0xCA, "ABS should follow with JP Z (skip negate)"


def test_abs_contains_negate_body():
    out = _compile_primitive(create_abs)
    negate_seq = bytes([0xAF, 0x95, 0x6F, 0x9F, 0x94, 0x67])
    assert negate_seq in out, "ABS should contain the NEGATE sequence"


@pytest.mark.parametrize("creator,op_name,branch_byte,branch_mnemonic", [
    (create_min, "MIN", 0xFA, "JP M"),
    (create_max, "MAX", 0xF2, "JP P"),
])
def test_min_max_use_signed_branch(creator, op_name, branch_byte, branch_mnemonic):
    out = _compile_primitive(creator)
    assert out[0] == 0xD1, f"{op_name} should start with POP DE"
    assert out[1] == 0xB7, f"{op_name} should OR A to clear carry"
    assert out[2:4] == bytes([0xED, 0x52]), f"{op_name} should SBC HL,DE"
    assert out[4] == 0x19, f"{op_name} should ADD HL,DE to restore HL"
    assert out[5] == branch_byte, (
        f"{op_name} should use {branch_mnemonic} (signed branch) after the "
        "SBC+ADD pair to honor the S flag preserved by ADD HL,DE"
    )


def test_and_byte_sequence():
    out = _compile_primitive(create_and)
    assert out[:7] == bytes([0xD1, 0x7C, 0xA2, 0x67, 0x7D, 0xA3, 0x6F]), (
        "AND should be POP DE; LD A,H; AND D; LD H,A; LD A,L; AND E; LD L,A"
    )


def test_or_byte_sequence():
    out = _compile_primitive(create_or)
    assert out[:7] == bytes([0xD1, 0x7C, 0xB2, 0x67, 0x7D, 0xB3, 0x6F]), (
        "OR should be POP DE; LD A,H; OR D; LD H,A; LD A,L; OR E; LD L,A"
    )


def test_xor_byte_sequence():
    out = _compile_primitive(create_xor)
    assert out[:7] == bytes([0xD1, 0x7C, 0xAA, 0x67, 0x7D, 0xAB, 0x6F]), (
        "XOR should be POP DE; LD A,H; XOR D; LD H,A; LD A,L; XOR E; LD L,A"
    )


def test_invert_byte_sequence():
    out = _compile_primitive(create_invert)
    assert out[:6] == bytes([0x7C, 0x2F, 0x67, 0x7D, 0x2F, 0x6F]), (
        "INVERT should be LD A,H; CPL; LD H,A; LD A,L; CPL; LD L,A"
    )


def test_lshift_structure():
    out = _compile_primitive(create_lshift)
    assert out[0] == 0xD1, "LSHIFT should start with POP DE"
    assert out[1] == 0x7D, "LSHIFT should LD A,L for count"
    assert out[2] == 0xEB, "LSHIFT should EX DE,HL"
    assert out[3] == 0xB7, "LSHIFT should OR A to test zero"
    assert out[4] == 0x28, "LSHIFT should JR Z to skip loop"
    assert out[6] == 0x29, "LSHIFT loop should ADD HL,HL"
    assert out[7] == 0x3D, "LSHIFT loop should DEC A"
    assert out[8] == 0x20, "LSHIFT loop should JR NZ back"


def test_rshift_structure():
    out = _compile_primitive(create_rshift)
    assert out[0] == 0xD1, "RSHIFT should start with POP DE"
    assert out[6:8] == bytes([0xCB, 0x3C]), "RSHIFT loop should SRL H"
    assert out[8:10] == bytes([0xCB, 0x1D]), "RSHIFT loop should RR L"


def test_equals_byte_sequence():
    out = _compile_primitive(create_equals)
    assert out[0] == 0xD1, "= should start with POP DE"
    assert out[1] == 0xB7, "= should OR A"
    assert out[2:4] == bytes([0xED, 0x52]), "= should SBC HL,DE"
    assert out[4:7] == bytes([0x21, 0x00, 0x00]), "= should LD HL,0"
    assert out[7] == 0x20, "= should JR NZ (skip DEC HL)"
    assert out[9] == 0x2B, "= should DEC HL (set -1/true)"


def test_not_equals_byte_sequence():
    out = _compile_primitive(create_not_equals)
    assert out[7] == 0x28, "<> should JR Z (skip DEC HL, opposite of =)"


def test_zero_equals_byte_sequence():
    out = _compile_primitive(create_zero_equals)
    assert out[:2] == bytes([0x7C, 0xB5]), "0= should start with LD A,H; OR L"
    assert out[2:5] == bytes([0x21, 0x00, 0x00]), "0= should LD HL,0"
    assert out[5] == 0x20, "0= should JR NZ"


def test_zero_less_byte_sequence():
    out = _compile_primitive(create_zero_less)
    assert out[:2] == bytes([0xCB, 0x7C]), "0< should start with BIT 7,H"
    assert out[2:5] == bytes([0x21, 0x00, 0x00]), "0< should LD HL,0"
    assert out[5] == 0x28, "0< should JR Z"


def test_less_than_uses_signed_compare():
    out = _compile_primitive(create_less_than)
    assert out[0] == 0xD1, "< should POP DE"
    assert out[1] == 0xEB, "< should EX DE,HL (compute a-b)"
    assert out[2] == 0xB7, "< should OR A"
    assert out[3:5] == bytes([0xED, 0x52]), "< should SBC HL,DE"
    assert out[5:8] == bytes([0x21, 0x00, 0x00]), "< should LD HL,0"
    assert out[8] == 0xF2, "< should JP P (signed positive = not less)"


def test_greater_than_uses_signed_compare():
    out = _compile_primitive(create_greater_than)
    assert out[0] == 0xD1, "> should POP DE"
    assert out[1] == 0xB7, "> should OR A (no EX, compute b-a)"
    assert out[2:4] == bytes([0xED, 0x52]), "> should SBC HL,DE"


def test_u_less_uses_carry():
    out = _compile_primitive(create_u_less)
    assert out[0] == 0xD1, "U< should POP DE"
    assert out[1] == 0xEB, "U< should EX DE,HL"
    assert out[2] == 0xB7, "U< should OR A"
    assert out[3:5] == bytes([0xED, 0x52]), "U< should SBC HL,DE"
    assert out[5:8] == bytes([0x21, 0x00, 0x00]), "U< should LD HL,0"
    assert out[8] == 0x30, "U< should JR NC (no borrow = not less)"


def test_fetch_byte_sequence():
    out = _compile_primitive(create_fetch)
    assert out[:4] == bytes([0x5E, 0x23, 0x56, 0xEB]), (
        "@ should be LD E,(HL); INC HL; LD D,(HL); EX DE,HL"
    )


def test_store_byte_sequence():
    out = _compile_primitive(create_store)
    assert out[:5] == bytes([0xD1, 0x73, 0x23, 0x72, 0xE1]), (
        "! should be POP DE; LD (HL),E; INC HL; LD (HL),D; POP HL"
    )


def test_c_fetch_byte_sequence():
    out = _compile_primitive(create_c_fetch)
    assert out[:3] == bytes([0x6E, 0x26, 0x00]), (
        "C@ should be LD L,(HL); LD H,0"
    )


def test_c_store_byte_sequence():
    out = _compile_primitive(create_c_store)
    assert out[:3] == bytes([0xD1, 0x73, 0xE1]), (
        "C! should be POP DE; LD (HL),E; POP HL"
    )


def test_plus_store_byte_sequence():
    out = _compile_primitive(create_plus_store)
    assert out[:9] == bytes([0xD1, 0x7E, 0x83, 0x77, 0x23, 0x7E, 0x8A, 0x77, 0xE1]), (
        "+! should add 16-bit value at address"
    )


def test_cmove_uses_ldir():
    out = _compile_primitive(create_cmove)
    assert out[0] == 0x44, "CMOVE should start with LD B,H"
    assert out[1] == 0x4D, "CMOVE should LD C,L"
    assert out[2] == 0xD1, "CMOVE should POP DE (dst)"
    assert out[3] == 0xE1, "CMOVE should POP HL (src)"
    assert bytes([0xED, 0xB0]) in out, "CMOVE should contain LDIR"


def test_fill_uses_ldir():
    out = _compile_primitive(create_fill)
    assert out[0] == 0x7D, "FILL should start with LD A,L (byte)"
    assert out[1] == 0xC1, "FILL should POP BC (count)"
    assert out[2] == 0xE1, "FILL should POP HL (addr)"
    assert out[3] == 0x77, "FILL should LD (HL),A"
    assert bytes([0xED, 0xB0]) in out, "FILL should contain LDIR"


@pytest.mark.parametrize("creator,primary,alias", [
    (create_dup,           "DUP",          "dup"),
    (create_drop,          "DROP",         "drop"),
    (create_swap,          "SWAP",         "swap"),
    (create_over,          "OVER",         "over"),
    (create_rot,           "ROT",          "rot"),
    (create_nip,           "NIP",          "nip"),
    (create_tuck,          "TUCK",         "tuck"),
    (create_2dup,          "2DUP",         "2dup"),
    (create_2drop,         "2DROP",        "2drop"),
    (create_2swap,         "2SWAP",        "2swap"),
    (create_to_r,          ">R",           ">r"),
    (create_r_from,        "R>",           "r>"),
    (create_r_fetch,       "R@",           "r@"),
    (create_plus,          "PLUS",         "+"),
    (create_minus,         "MINUS",        "-"),
    (create_negate,        "NEGATE",       "negate"),
    (create_abs,           "ABS",          "abs"),
    (create_min,           "MIN",          "min"),
    (create_max,           "MAX",          "max"),
    (create_and,           "AND",          "and"),
    (create_or,            "OR",           "or"),
    (create_xor,           "XOR",          "xor"),
    (create_invert,        "INVERT",       "invert"),
    (create_lshift,        "LSHIFT",       "lshift"),
    (create_rshift,        "RSHIFT",       "rshift"),
    (create_equals,        "EQUALS",       "="),
    (create_not_equals,    "NOT_EQUALS",   "<>"),
    (create_less_than,     "LESS_THAN",    "<"),
    (create_greater_than,  "GREATER_THAN", ">"),
    (create_zero_equals,   "ZERO_EQUALS",  "0="),
    (create_zero_less,     "ZERO_LESS",    "0<"),
    (create_u_less,        "U_LESS",       "u<"),
    (create_fetch,         "FETCH",        "@"),
    (create_store,         "STORE",        "!"),
    (create_c_fetch,       "C_FETCH",      "c@"),
    (create_c_store,       "C_STORE",      "c!"),
    (create_plus_store,    "PLUS_STORE",   "+!"),
    (create_cmove,         "CMOVE",        "cmove"),
    (create_fill,          "FILL",         "fill"),
    (create_exit,          "EXIT",         "exit"),
    (create_border,        "BORDER",       "border"),
])
def test_alias_points_to_primary(creator, primary, alias):
    a = _asm_with_next()
    creator(a)
    assert a.labels[alias] == a.labels[primary], (
        f"alias '{alias}' should point to same address as '{primary}'"
    )


def test_all_primitives_resolve_together():
    a = Asm(0x8000)
    for creator in PRIMITIVES:
        creator(a)
    out = a.resolve()
    assert len(out) > 100, "full primitive set should produce substantial code"


def test_primitives_list_has_expected_count():
    assert len(PRIMITIVES) >= 45, (
        f"PRIMITIVES should have at least 45 entries, got {len(PRIMITIVES)}"
    )


def test_lit_pushes_hl_then_loads_from_ix():
    out = _compile_primitive(create_lit)
    assert out[0] == 0xE5, "LIT should start with PUSH HL"
    assert out[1:4] == bytes([0xDD, 0x6E, 0x00]), "LIT should LD L,(IX+0)"
    assert out[4:7] == bytes([0xDD, 0x66, 0x01]), "LIT should LD H,(IX+1)"


def test_docol_swaps_return_addr_with_ix_then_saves_old_ip():
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    create_docol(a)
    out = a.resolve()
    assert out[0:2] == bytes([0xDD, 0xE3]), "DOCOL should EX (SP), IX to swap call-return with old IP"
    assert out[2] == 0xD1, "DOCOL should POP DE to capture old IP"
    assert out[3:5] == bytes([0xFD, 0x2B]), "DOCOL should DEC IY"


def test_exit_restores_ip_from_return_stack():
    out = _compile_primitive(create_exit)
    assert out[0:3] == bytes([0xFD, 0x5E, 0x00]), "EXIT should LD E,(IY+0)"
    assert out[3:6] == bytes([0xFD, 0x56, 0x01]), "EXIT should LD D,(IY+1)"


def test_multiply_does_not_preserve_bc():
    out = _compile_primitive(create_multiply)
    assert 0xC5 not in out[:4], "MULTIPLY should not PUSH BC (BC is caller-clobber)"
    assert out[-4:-3] != bytes([0xC1]), "MULTIPLY should not POP BC before dispatch"


def test_u_mod_div_does_not_preserve_bc():
    out = _compile_primitive(create_u_mod_div)
    assert 0xC5 not in out[:6], "U_MOD_DIV should not PUSH BC (BC is caller-clobber)"


def test_wait_frame_saves_iy_around_halt():
    from zt.assemble.primitives import create_wait_frame
    out = _compile_primitive(create_wait_frame)
    header = bytes([0xFD, 0xE5, 0xFD, 0x21, 0x3A, 0x5C])
    assert out[:6] == header, (
        "WAIT_FRAME must PUSH IY then LD IY,$5C3A before halting so the "
        "Spectrum ROM's 50Hz interrupt handler writes system variables "
        "into the ROM area instead of zt's return stack"
    )
    assert bytes([0xFB, 0x76, 0xF3]) in out, (
        "WAIT_FRAME must still emit the ei; halt; di; sequence"
    )
    pop_iy_offset = out.index(bytes([0xFD, 0xE1]))
    halt_offset = out.index(bytes([0xFB, 0x76, 0xF3]))
    assert pop_iy_offset > halt_offset, (
        "POP IY must come after di to restore zt's return stack pointer"
    )


