import pytest

from zt.asm import Asm
from zt.primitives import create_next, create_dup, create_plus, create_border, create_branch


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
    a = Asm(0x8000)
    a.label("NEXT")
    create_dup(a)
    out = a.resolve()
    assert out[0] == 0xE5, "DUP should start with PUSH HL"
    assert out[1] == 0xC3, "DUP should jump to NEXT after PUSH HL"


def test_plus_is_pop_de_add_hl_de_then_jp_next():
    a = Asm(0x8000)
    a.label("NEXT")
    create_plus(a)
    out = a.resolve()
    assert out[:3] == bytes([0xD1, 0x19, 0xC3]), "PLUS should be POP DE; ADD HL,DE; JP NEXT"


def test_border_compiles_out_to_port_fe():
    a = Asm(0x8000)
    a.label("NEXT")
    create_border(a)
    out = a.resolve()
    assert out[0] == 0x7D, "BORDER should start with LD A,L"
    assert out[1:3] == bytes([0xD3, 0xFE]), "BORDER should OUT (0xFE),A"
    assert out[3] == 0xE1, "BORDER should POP HL for new TOS"


def test_branch_layout():
    a = Asm(0x8000)
    a.label("NEXT")
    create_branch(a)
    out = a.resolve()
    assert out[0:3] == bytes([0xDD, 0x5E, 0x00]), "BRANCH should start with LD E,(IX+0)"
    assert out[3:6] == bytes([0xDD, 0x56, 0x01]), "then LD D,(IX+1)"
    assert out[6] == 0xD5, "then PUSH DE"
    assert out[7:9] == bytes([0xDD, 0xE1]), "then POP IX"
