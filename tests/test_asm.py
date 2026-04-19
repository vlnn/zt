"""
Tests for the `Asm` class: label registration, opcode method emission, fixup resolution, and alias handling.
"""
import pytest

from zt.assemble.asm import Asm


def test_here_starts_at_origin():
    a = Asm(0x8000)
    assert a.here == 0x8000, "here should equal origin before any compilation"


def test_opcode_method_advances_here():
    a = Asm(0x8000)
    a.inc_ix()
    assert a.here == 0x8002, "inc_ix should compile 2 bytes and advance here"


def test_label_captures_current_address():
    a = Asm(0x8000)
    a.inc_ix()
    a.label("foo")
    assert a.labels["foo"] == 0x8002, "label should capture origin + length"


def test_duplicate_label_raises():
    a = Asm(0x8000)
    a.label("foo")
    with pytest.raises(ValueError, match="duplicate"):
        a.label("foo")


@pytest.mark.parametrize("addr,lo,hi", [
    (0x0000, 0x00, 0x00),
    (0x8000, 0x00, 0x80),
    (0x8005, 0x05, 0x80),
    (0xABCD, 0xCD, 0xAB),
    (0xFFFF, 0xFF, 0xFF),
])
def test_word_label_resolves_little_endian(addr, lo, hi):
    a = Asm(addr)
    a.label("t")
    a.word("t")
    out = a.resolve()
    assert out[0] == lo, f"low byte of {addr:#06x} should be {lo:#04x}"
    assert out[1] == hi, f"high byte of {addr:#06x} should be {hi:#04x}"


@pytest.mark.parametrize("value,lo,hi", [
    (0x0000, 0x00, 0x00),
    (0x00FF, 0xFF, 0x00),
    (0x1234, 0x34, 0x12),
    (0xFFFF, 0xFF, 0xFF),
])
def test_word_literal_compiles_little_endian(value, lo, hi):
    a = Asm(0x8000)
    a.word(value)
    assert bytes(a.code) == bytes([lo, hi]), f"{value:#06x} should compile lo,hi"


def test_unresolved_label_raises():
    a = Asm(0x8000)
    a.word("nowhere")
    with pytest.raises(KeyError, match="nowhere"):
        a.resolve()


def test_jp_compiles_c3_plus_address():
    a = Asm(0x8000)
    a.label("target")
    a.jp("target")
    out = a.resolve()
    assert out[0] == 0xC3, "JP opcode should be 0xC3"
    assert out[1:3] == bytes([0x00, 0x80]), "JP operand should be target address"


def test_call_compiles_cd_plus_address():
    a = Asm(0x8000)
    a.label("target")
    a.call("target")
    out = a.resolve()
    assert out[0] == 0xCD, "CALL opcode should be 0xCD"


# -- alias tests --

def test_alias_resolves_to_same_address():
    a = Asm(0x8000)
    a.nop()
    a.label("FOO")
    a.alias("foo", "FOO")
    a.word("foo")
    out = a.resolve()
    assert out[1] == 0x01, "alias should resolve to same address as target"
    assert out[2] == 0x80, "alias should resolve to same address as target"


def test_alias_duplicate_raises():
    a = Asm(0x8000)
    a.label("FOO")
    a.alias("foo", "FOO")
    with pytest.raises(ValueError, match="duplicate"):
        a.alias("foo", "FOO")


def test_alias_missing_target_raises():
    a = Asm(0x8000)
    with pytest.raises(KeyError, match="alias target not found"):
        a.alias("foo", "MISSING")


# -- relative jump tests --

def test_jr_forward_offset():
    a = Asm(0x8000)
    a.jr_to("target")
    a.nop()
    a.nop()
    a.label("target")
    out = a.resolve()
    assert out[0] == 0x18, "JR opcode should be 0x18"
    assert out[1] == 0x02, "JR forward by 2 bytes should have offset 0x02"


def test_jr_backward_offset():
    a = Asm(0x8000)
    a.label("target")
    a.nop()
    a.jr_to("target")
    out = a.resolve()
    assert out[1] == 0x18, "JR opcode at offset 1"
    assert out[2] == 0xFD, "JR backward by 3 bytes should have offset -3 (0xFD)"


@pytest.mark.parametrize("method,opcode", [
    ("jr_to", 0x18),
    ("jr_nz_to", 0x20),
    ("jr_z_to", 0x28),
    ("jr_nc_to", 0x30),
    ("jr_c_to", 0x38),
    ("djnz_to", 0x10),
])
def test_jr_variant_opcodes(method, opcode):
    a = Asm(0x8000)
    a.label("target")
    getattr(a, method)("target")
    out = a.resolve()
    assert out[0] == opcode, f"{method} should emit opcode {opcode:#04x}"


def test_jr_out_of_range_raises():
    a = Asm(0x8000)
    a.label("target")
    for _ in range(200):
        a.nop()
    with pytest.raises(ValueError, match="out of range"):
        a.jr_to("target")
        a.resolve()


def test_jr_unresolved_label_raises():
    a = Asm(0x8000)
    a.jr_to("missing")
    with pytest.raises(KeyError, match="missing"):
        a.resolve()


# -- conditional JP tests --

@pytest.mark.parametrize("method,opcode", [
    ("jp_z", 0xCA),
    ("jp_nz", 0xC2),
    ("jp_p", 0xF2),
    ("jp_m", 0xFA),
])
def test_conditional_jp_opcodes(method, opcode):
    a = Asm(0x8000)
    a.label("target")
    getattr(a, method)("target")
    out = a.resolve()
    assert out[0] == opcode, f"{method} should emit opcode {opcode:#04x}"
    assert out[1:3] == bytes([0x00, 0x80]), f"{method} should emit target address"


# -- new opcode method tests --

@pytest.mark.parametrize("method,expected", [
    ("push_bc", [0xC5]),
    ("pop_bc", [0xC1]),
    ("push_af", [0xF5]),
    ("pop_af", [0xF1]),
    ("add_hl_hl", [0x29]),
    ("add_hl_bc", [0x09]),
    ("dec_hl", [0x2B]),
    ("inc_de", [0x13]),
    ("dec_de", [0x1B]),
    ("inc_bc", [0x03]),
    ("dec_bc", [0x0B]),
    ("xor_a", [0xAF]),
    ("sub_l", [0x95]),
    ("sub_h", [0x94]),
    ("sbc_a_a", [0x9F]),
    ("add_a_e", [0x83]),
    ("adc_a_d", [0x8A]),
    ("dec_a", [0x3D]),
    ("and_d", [0xA2]),
    ("and_e", [0xA3]),
    ("or_c", [0xB1]),
    ("or_d", [0xB2]),
    ("or_e", [0xB3]),
    ("or_l", [0xB5]),
    ("xor_d", [0xAA]),
    ("xor_e", [0xAB]),
    ("cpl", [0x2F]),
    ("ld_a_b", [0x78]),
    ("ld_a_d", [0x7A]),
    ("ld_a_e", [0x7B]),
    ("ld_a_h", [0x7C]),
    ("ld_a_l", [0x7D]),
    ("ld_h_a", [0x67]),
    ("ld_h_b", [0x60]),
    ("ld_h_d", [0x62]),
    ("ld_l_a", [0x6F]),
    ("ld_l_c", [0x69]),
    ("ld_l_e", [0x6B]),
    ("ld_b_h", [0x44]),
    ("ld_c_l", [0x4D]),
    ("ld_d_h", [0x54]),
    ("ld_e_l", [0x5D]),
    ("ld_l_ind_hl", [0x6E]),
    ("ld_ind_hl_a", [0x77]),
    ("ld_a_ind_hl", [0x7E]),
    ("sra_h", [0xCB, 0x2C]),
    ("rr_l", [0xCB, 0x1D]),
    ("srl_h", [0xCB, 0x3C]),
    ("bit_7_h", [0xCB, 0x7C]),
    ("ldir", [0xED, 0xB0]),
    ("di", [0xF3]),
    ("ei", [0xFB]),
    ("nop", [0x00]),
])
def test_opcode_byte_sequence(method, expected):
    a = Asm(0x8000)
    getattr(a, method)()
    assert bytes(a.code) == bytes(expected), f"{method} should emit {expected}"


@pytest.mark.parametrize("method,arg,expected", [
    ("ld_hl_nn", 0x1234, [0x21, 0x34, 0x12]),
    ("ld_de_nn", 0x1234, [0x11, 0x34, 0x12]),
    ("ld_bc_nn", 0x1234, [0x01, 0x34, 0x12]),
    ("ld_b_n", 0x42, [0x06, 0x42]),
    ("ld_h_n", 0x42, [0x26, 0x42]),
    ("ld_l_n", 0x42, [0x2E, 0x42]),
    ("out_n_a", 0xFE, [0xD3, 0xFE]),
])
def test_opcode_with_arg_byte_sequence(method, arg, expected):
    a = Asm(0x8000)
    getattr(a, method)(arg)
    assert bytes(a.code) == bytes(expected), f"{method}({arg}) should emit {expected}"


@pytest.mark.parametrize("method,disp,expected", [
    ("ld_iy_l", 0, [0xFD, 0x75, 0x00]),
    ("ld_iy_h", 1, [0xFD, 0x74, 0x01]),
    ("ld_l_iy", 0, [0xFD, 0x6E, 0x00]),
    ("ld_h_iy", 1, [0xFD, 0x66, 0x01]),
])
def test_iy_indexed_byte_sequence(method, disp, expected):
    a = Asm(0x8000)
    getattr(a, method)(disp)
    assert bytes(a.code) == bytes(expected), f"{method}({disp}) should emit {expected}"
