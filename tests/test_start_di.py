"""Pin: _start must begin with DI so programs defend against any caller
that leaves interrupts enabled. Critical for 48K builds whose origin
overlaps the Spectrum system variables area ($5C00..$5CB6) — without DI,
the ROM IM 1 handler corrupts FRAMES at $5C78 every 50Hz, which sits
inside live primitive bodies (R> at $5C77 in tinychat-48k).
"""
import pytest

from zt.compile.compiler import Compiler


def _compile(source, **kw):
    c = Compiler(
        origin=0x8000, optimize=False, inline_next=True,
        inline_primitives=True, **kw,
    )
    c.compile_source(source, source='<test>')
    c.compile_main_call()
    return c


class TestStartDisablesInterrupts:

    def test_threaded_start_begins_with_DI(self):
        c = _compile(': main 1 ;')
        image = c.build()
        start_offset = c.words['_start'].address - c.origin
        assert image[start_offset] == 0xF3, (
            f"_start should begin with DI (0xF3) so programs defend against "
            f"any caller leaving interrupts enabled; got 0x{image[start_offset]:02X}"
        )

    def test_threaded_start_followed_by_ld_sp(self):
        c = _compile(': main 1 ;')
        image = c.build()
        start_offset = c.words['_start'].address - c.origin
        assert image[start_offset + 1] == 0x31, (
            "after DI, _start should LD SP, NN (opcode 0x31)"
        )

    def test_native_start_begins_with_DI(self):
        c = _compile(': main 1 ;', native_control_flow=True)
        image = c.build()
        start_offset = c.words['_start'].address - c.origin
        assert image[start_offset] == 0xF3, (
            f"native _start should also begin with DI; "
            f"got 0x{image[start_offset]:02X}"
        )

    def test_tree_shaken_threaded_start_begins_with_DI(self):
        c = _compile(': main 1 ;')
        image, start_addr = c.build_tree_shaken()
        start_offset = start_addr - c.origin
        assert image[start_offset] == 0xF3, (
            f"tree-shaken _start should also begin with DI; "
            f"got 0x{image[start_offset]:02X}"
        )
