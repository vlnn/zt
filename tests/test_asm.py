import pytest

from zt.asm import Asm


def test_here_starts_at_origin():
    a = Asm(0x8000)
    assert a.here == 0x8000, "here should equal origin before any compilaton"


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
