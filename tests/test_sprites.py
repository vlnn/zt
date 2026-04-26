"""
Tests for the SP-stream sprite primitives:
BLIT8, BLIT8C, BLIT8X, BLIT8XC, MULTI-BLIT, and LOCK-SPRITES.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.sprite_primitives import (
    create_blit8,
    create_blit8c,
    create_blit8x,
    create_blit8xc,
    create_lock_sprites,
    create_multi_blit,
    create_unlock_sprites,
)
from zt.sim import (
    SPECTRUM_ATTR_BASE,
    SPECTRUM_SCREEN_BASE,
    ForthMachine,
    screen_addr,
)


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _compile_primitive(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


def _compile_sprite_primitive(creator) -> bytes:
    """Compile a sprite primitive together with the scratch slots it references."""
    from zt.assemble.sprite_primitives import create_sprite_scratch
    a = _asm_with_next()
    creator(a)
    create_sprite_scratch(a)
    return a.resolve()


def _attr_addr(row: int, col: int) -> int:
    return SPECTRUM_ATTR_BASE + row * 32 + col


@pytest.fixture
def fm() -> ForthMachine:
    return ForthMachine()


def _load_bytes(fm: ForthMachine, addr: int, data: bytes) -> int:
    """Helper: write `data` at `addr` so the ForthMachine sees it on next run."""
    return addr


def _run_with_data(fm: ForthMachine, src_addr: int, src_data: bytes, cells: list) -> None:
    """
    Build a body that pre-loads src_data into RAM, then runs the given cells.
    Done by issuing a sequence of (lit value, lit addr, c!) cells before the
    primitive call. Returns nothing; callers inspect fm._last_m.mem.
    """
    pre: list = []
    for i, b in enumerate(src_data):
        pre.extend([fm.label("LIT"), b, fm.label("LIT"), src_addr + i, fm.label("C_STORE")])
    fm.run(pre + cells)


SAMPLE_8_BYTES = bytes([0x81, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x81])


class TestLockSprites:

    def test_lock_sprites_emits_di(self):
        out = _compile_primitive(create_lock_sprites)
        assert out[0] == 0xF3, "LOCK-SPRITES should start with DI"

    def test_unlock_sprites_emits_ei(self):
        out = _compile_primitive(create_unlock_sprites)
        assert out[0] == 0xFB, "UNLOCK-SPRITES should start with EI"

    def test_lock_sprites_registered_in_machine(self, fm):
        assert "LOCK_SPRITES" in fm._prim_asm.labels, (
            "LOCK_SPRITES label should be registered"
        )
        assert "lock-sprites" in fm._prim_asm.labels, (
            "lock-sprites alias should be registered"
        )

    def test_unlock_sprites_registered_in_machine(self, fm):
        assert "UNLOCK_SPRITES" in fm._prim_asm.labels, (
            "UNLOCK_SPRITES label should be registered"
        )
        assert "unlock-sprites" in fm._prim_asm.labels, (
            "unlock-sprites alias should be registered"
        )


class TestBlit8ByteShape:

    def test_blit8_registered(self, fm):
        assert "BLIT8" in fm._prim_asm.labels, "BLIT8 label should be registered"
        assert "blit8" in fm._prim_asm.labels, "blit8 alias should be registered"

    def test_blit8_saves_sp_via_ed73(self):
        out = _compile_sprite_primitive(create_blit8)
        assert bytes([0xED, 0x73]) in out, (
            "BLIT8 should contain ED 73 to save SP via ld (nn),sp"
        )

    def test_blit8_restores_sp_via_ed7b(self):
        out = _compile_sprite_primitive(create_blit8)
        assert bytes([0xED, 0x7B]) in out, (
            "BLIT8 should contain ED 7B to restore SP via ld sp,(nn)"
        )

    def test_blit8_uses_ld_sp_hl(self):
        out = _compile_sprite_primitive(create_blit8)
        assert 0xF9 in out, "BLIT8 should use ld sp,hl (0xF9) to redirect SP at the source"

    def test_blit8_does_not_di_or_ei(self):
        out = _compile_sprite_primitive(create_blit8)
        assert 0xF3 not in out, "BLIT8 must not emit DI; caller is responsible"
        assert 0xFB not in out, "BLIT8 must not emit EI; caller is responsible"

    def test_blit8_pops_four_bc_pairs(self):
        out = _compile_sprite_primitive(create_blit8)
        assert out.count(0xC1) == 4, (
            "BLIT8 should issue exactly four POP BC to fetch 8 source bytes"
        )

    def test_blit8_uses_ld_ind_hl_b_and_c(self):
        out = _compile_sprite_primitive(create_blit8)
        assert out.count(0x71) == 4, "BLIT8 should write C four times via ld (hl),c"
        assert out.count(0x70) == 4, "BLIT8 should write B four times via ld (hl),b"


class TestBlit8Integration:

    def _assemble_blit_call(
        self,
        fm: ForthMachine,
        src: int,
        col: int,
        row: int,
    ) -> list:
        return [
            fm.label("LIT"), src,
            fm.label("LIT"), col,
            fm.label("LIT"), row,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8"),
        ]

    def test_blit8_writes_8_bytes_at_origin(self, fm):
        src = 0xC000
        cells = self._assemble_blit_call(fm, src, col=0, row=0)
        _run_with_data(fm, src, SAMPLE_8_BYTES, cells)
        m = fm._last_m
        for line in range(8):
            addr = screen_addr(0, 0, line)
            assert m.mem[addr] == SAMPLE_8_BYTES[line], (
                f"BLIT8 should put byte {line} at screen line {line}; "
                f"got {m.mem[addr]:#04x} at {addr:#06x}"
            )

    @pytest.mark.parametrize("col,row", [
        (0, 0),
        (10, 5),
        (31, 23),
        (16, 12),
        (0, 8),
        (0, 16),
    ])
    def test_blit8_lands_at_correct_char_cell(self, fm, col, row):
        src = 0xC100
        cells = self._assemble_blit_call(fm, src, col=col, row=row)
        _run_with_data(fm, src, SAMPLE_8_BYTES, cells)
        m = fm._last_m
        for line in range(8):
            addr = screen_addr(row, col, line)
            assert m.mem[addr] == SAMPLE_8_BYTES[line], (
                f"BLIT8 at (col={col}, row={row}) line {line}: "
                f"expected {SAMPLE_8_BYTES[line]:#04x} at {addr:#06x}, "
                f"got {m.mem[addr]:#04x}"
            )

    def test_blit8_does_not_touch_neighboring_cell(self, fm):
        src = 0xC200
        cells = self._assemble_blit_call(fm, src, col=5, row=5)
        _run_with_data(fm, src, SAMPLE_8_BYTES, cells)
        m = fm._last_m
        for line in range(8):
            for ncol in (4, 6):
                addr = screen_addr(5, ncol, line)
                assert m.mem[addr] == 0, (
                    f"BLIT8 should not touch col={ncol}, line={line}"
                )

    def test_blit8_consumes_three_stack_items(self, fm):
        src = 0xC300
        cells = (
            [fm.label("LIT"), 0x1234]
            + [fm.label("LIT"), src, fm.label("LIT"), 0, fm.label("LIT"), 0]
            + [fm.label("LOCK_SPRITES"), fm.label("BLIT8")]
        )
        _run_with_data(fm, src, SAMPLE_8_BYTES, cells)
        result = fm._last_m
        m_top = result.hl
        assert m_top == 0x1234, (
            "BLIT8 should consume (src col row), leaving the prior TOS in HL"
        )


class TestBlit8cByteShape:

    def test_blit8c_registered(self, fm):
        assert "BLIT8C" in fm._prim_asm.labels, "BLIT8C label should be registered"
        assert "blit8c" in fm._prim_asm.labels, "blit8c alias should be registered"

    def test_blit8c_does_not_di_or_ei(self):
        out = _compile_sprite_primitive(create_blit8c)
        assert 0xF3 not in out, "BLIT8C must not emit DI; caller is responsible"
        assert 0xFB not in out, "BLIT8C must not emit EI; caller is responsible"


class TestBlit8cIntegration:

    @pytest.mark.parametrize("col,row,attr", [
        (0, 0, 0x47),
        (15, 11, 0x05),
        (31, 23, 0x38),
        (5, 16, 0x0F),
    ])
    def test_blit8c_writes_pixels_and_attr(self, fm, col, row, attr):
        src = 0xC400
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), attr,
            fm.label("LIT"), col,
            fm.label("LIT"), row,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8C"),
        ]
        _run_with_data(fm, src, SAMPLE_8_BYTES, cells)
        m = fm._last_m
        for line in range(8):
            addr = screen_addr(row, col, line)
            assert m.mem[addr] == SAMPLE_8_BYTES[line], (
                f"BLIT8C should blit pixels: row={row} col={col} line={line}"
            )
        assert m.mem[_attr_addr(row, col)] == attr, (
            f"BLIT8C should write attr {attr:#04x} at row={row} col={col}"
        )

    def test_blit8c_attr_does_not_leak_to_neighbors(self, fm):
        src = 0xC500
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), 0x47,
            fm.label("LIT"), 5,
            fm.label("LIT"), 5,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8C"),
        ]
        _run_with_data(fm, src, SAMPLE_8_BYTES, cells)
        m = fm._last_m
        for ncol in (4, 6):
            assert m.mem[_attr_addr(5, ncol)] == 0, (
                f"BLIT8C should not touch attr at neighbor col={ncol}"
            )
        for nrow in (4, 6):
            assert m.mem[_attr_addr(nrow, 5)] == 0, (
                f"BLIT8C should not touch attr at neighbor row={nrow}"
            )

    def test_blit8c_consumes_four_stack_items(self, fm):
        src = 0xC600
        cells = (
            [fm.label("LIT"), 0xBEEF]
            + [
                fm.label("LIT"), src,
                fm.label("LIT"), 0x07,
                fm.label("LIT"), 0,
                fm.label("LIT"), 0,
            ]
            + [fm.label("LOCK_SPRITES"), fm.label("BLIT8C")]
        )
        _run_with_data(fm, src, SAMPLE_8_BYTES, cells)
        m = fm._last_m
        assert m.hl == 0xBEEF, (
            "BLIT8C should consume (src attr col row), leaving prior TOS in HL"
        )


class TestBlit8xByteShape:

    def test_blit8x_registered(self, fm):
        assert "BLIT8X" in fm._prim_asm.labels, "BLIT8X label should be registered"
        assert "blit8x" in fm._prim_asm.labels, "blit8x alias should be registered"

    def test_blit8x_does_not_di_or_ei(self):
        out = _compile_sprite_primitive(create_blit8x)
        assert 0xF3 not in out, "BLIT8X must not emit DI; caller is responsible"
        assert 0xFB not in out, "BLIT8X must not emit EI; caller is responsible"

    def test_blit8x_pops_eight_bc_pairs(self):
        out = _compile_sprite_primitive(create_blit8x)
        assert out.count(0xC1) == 8, (
            "BLIT8X should issue exactly eight POP BC (16 bytes = 8 word-pairs)"
        )


def _make_pre_shifted(sprite_bytes: bytes) -> bytes:
    """Build a 128-byte (8 shifts × 16 bytes) pre-shifted block.

    Layout: shift0_row0_left, shift0_row0_right, shift0_row1_left, ...
    For shift s: row r writes (sprite[r] >> s) at left col, ((sprite[r] << (8-s)) & 0xFF) at right col.
    """
    block = bytearray()
    for shift in range(8):
        for row in range(8):
            byte = sprite_bytes[row]
            if shift == 0:
                left = byte
                right = 0
            else:
                left = byte >> shift
                right = (byte << (8 - shift)) & 0xFF
            block.append(left)
            block.append(right)
    return bytes(block)


class TestBlit8xIntegration:

    @pytest.mark.parametrize("x,y", [
        (0, 0),
        (8, 8),
        (16, 16),
        (24, 0),
        (0, 64),
        (0, 128),
    ])
    def test_blit8x_byte_aligned_x_writes_left_col_only(self, fm, x, y):
        src = 0xC700
        sprite = SAMPLE_8_BYTES
        block = _make_pre_shifted(sprite)
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), x,
            fm.label("LIT"), y,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8X"),
        ]
        _run_with_data(fm, src, block, cells)
        m = fm._last_m
        col = x >> 3
        row = y >> 3
        for line in range(8):
            addr = screen_addr(row, col, line)
            assert m.mem[addr] == sprite[line], (
                f"BLIT8X(x={x},y={y}) line {line}: left col should hold sprite byte"
            )
        for line in range(8):
            addr = screen_addr(row, col + 1, line)
            assert m.mem[addr] == 0, (
                f"BLIT8X(x={x},y={y}) line {line}: right col should be 0 for shift=0"
            )

    @pytest.mark.parametrize("x,y", [
        (3, 0),
        (5, 24),
        (7, 16),
    ])
    def test_blit8x_pixel_shifted_writes_both_cols(self, fm, x, y):
        src = 0xC800
        sprite = SAMPLE_8_BYTES
        block = _make_pre_shifted(sprite)
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), x,
            fm.label("LIT"), y,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8X"),
        ]
        _run_with_data(fm, src, block, cells)
        m = fm._last_m
        col = x >> 3
        row = y >> 3
        shift = x & 7
        for line in range(8):
            expected_left = sprite[line] >> shift
            expected_right = (sprite[line] << (8 - shift)) & 0xFF
            addr_l = screen_addr(row, col, line)
            addr_r = screen_addr(row, col + 1, line)
            assert m.mem[addr_l] == expected_left, (
                f"BLIT8X(x={x},y={y},shift={shift}) line {line}: "
                f"left col expected {expected_left:#04x}, got {m.mem[addr_l]:#04x}"
            )
            assert m.mem[addr_r] == expected_right, (
                f"BLIT8X(x={x},y={y},shift={shift}) line {line}: "
                f"right col expected {expected_right:#04x}, got {m.mem[addr_r]:#04x}"
            )

    @pytest.mark.parametrize("y", [
        1,
        4,
        7,
        12,
        62,
        100,
    ])
    def test_blit8x_pixel_y_crosses_char_rows(self, fm, y):
        src = 0xC900
        sprite = SAMPLE_8_BYTES
        block = _make_pre_shifted(sprite)
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), 0,
            fm.label("LIT"), y,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8X"),
        ]
        _run_with_data(fm, src, block, cells)
        m = fm._last_m
        for sprite_row in range(8):
            target_y = y + sprite_row
            char_row = target_y >> 3
            scanline = target_y & 7
            addr = screen_addr(char_row, 0, scanline)
            assert m.mem[addr] == sprite[sprite_row], (
                f"BLIT8X(x=0,y={y}) sprite row {sprite_row} -> y={target_y}: "
                f"expected {sprite[sprite_row]:#04x} at {addr:#06x}, "
                f"got {m.mem[addr]:#04x}"
            )


class TestBlit8xcByteShape:

    def test_blit8xc_registered(self, fm):
        assert "BLIT8XC" in fm._prim_asm.labels, "BLIT8XC label should be registered"
        assert "blit8xc" in fm._prim_asm.labels, "blit8xc alias should be registered"

    def test_blit8xc_does_not_di_or_ei(self):
        out = _compile_sprite_primitive(create_blit8xc)
        assert 0xF3 not in out, "BLIT8XC must not emit DI; caller is responsible"
        assert 0xFB not in out, "BLIT8XC must not emit EI; caller is responsible"


class TestBlit8xcIntegration:

    def test_blit8xc_pixel_aligned_paints_one_attr_cell(self, fm):
        src = 0xCA00
        block = _make_pre_shifted(SAMPLE_8_BYTES)
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), 0x47,
            fm.label("LIT"), 16,
            fm.label("LIT"), 16,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8XC"),
        ]
        _run_with_data(fm, src, block, cells)
        m = fm._last_m
        assert m.mem[_attr_addr(2, 2)] == 0x47, (
            "BLIT8XC at (16,16) should paint attr at (row=2,col=2)"
        )

    def test_blit8xc_horizontal_shift_paints_two_attr_cells(self, fm):
        src = 0xCB00
        block = _make_pre_shifted(SAMPLE_8_BYTES)
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), 0x07,
            fm.label("LIT"), 19,
            fm.label("LIT"), 16,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8XC"),
        ]
        _run_with_data(fm, src, block, cells)
        m = fm._last_m
        assert m.mem[_attr_addr(2, 2)] == 0x07, (
            "BLIT8XC with x_shift>0 should paint left attr cell"
        )
        assert m.mem[_attr_addr(2, 3)] == 0x07, (
            "BLIT8XC with x_shift>0 should paint right attr cell"
        )

    def test_blit8xc_y_shift_paints_two_rows_of_attr_cells(self, fm):
        src = 0xCC00
        block = _make_pre_shifted(SAMPLE_8_BYTES)
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), 0x05,
            fm.label("LIT"), 16,
            fm.label("LIT"), 19,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8XC"),
        ]
        _run_with_data(fm, src, block, cells)
        m = fm._last_m
        assert m.mem[_attr_addr(2, 2)] == 0x05, (
            "BLIT8XC with y_shift>0 should paint upper attr cell"
        )
        assert m.mem[_attr_addr(3, 2)] == 0x05, (
            "BLIT8XC with y_shift>0 should paint lower attr cell"
        )

    def test_blit8xc_full_shift_paints_four_attr_cells(self, fm):
        src = 0xCD00
        block = _make_pre_shifted(SAMPLE_8_BYTES)
        cells = [
            fm.label("LIT"), src,
            fm.label("LIT"), 0x0D,
            fm.label("LIT"), 19,
            fm.label("LIT"), 19,
            fm.label("LOCK_SPRITES"),
            fm.label("BLIT8XC"),
        ]
        _run_with_data(fm, src, block, cells)
        m = fm._last_m
        for r, c in [(2, 2), (2, 3), (3, 2), (3, 3)]:
            assert m.mem[_attr_addr(r, c)] == 0x0D, (
                f"BLIT8XC with both shifts > 0 should paint 2x2 attr cell at (row={r},col={c})"
            )


class TestMultiBlitByteShape:

    def test_multi_blit_registered(self, fm):
        assert "MULTI_BLIT" in fm._prim_asm.labels, "MULTI_BLIT label should be registered"
        assert "multi-blit" in fm._prim_asm.labels, "multi-blit alias should be registered"


class TestMultiBlitIntegration:

    def test_multi_blit_renders_count_of_zero(self, fm):
        table = 0xCE00
        cells = (
            [fm.label("LIT"), 0, fm.label("LIT"), table, fm.label("C_STORE")]
            + [
                fm.label("LIT"), table,
                fm.label("LIT"), 0,
                fm.label("LIT"), 0,
                fm.label("LOCK_SPRITES"),
                fm.label("MULTI_BLIT"),
            ]
        )
        fm.run(cells)
        m = fm._last_m
        for addr in range(SPECTRUM_SCREEN_BASE, SPECTRUM_SCREEN_BASE + 16):
            assert m.mem[addr] == 0, "MULTI-BLIT with count=0 should leave screen untouched"

    def test_multi_blit_renders_two_sprites_at_offsets(self, fm):
        sprite1 = 0xCF00
        sprite2 = 0xCF80
        table = 0xD000
        block1 = _make_pre_shifted(SAMPLE_8_BYTES)
        block2 = _make_pre_shifted(bytes([0xFF] * 8))
        table_bytes = bytes([
            2,
            0, 0, sprite1 & 0xFF, sprite1 >> 8,
            16, 0, sprite2 & 0xFF, sprite2 >> 8,
        ])
        pre: list = []
        for i, b in enumerate(block1):
            pre.extend([fm.label("LIT"), b, fm.label("LIT"), sprite1 + i, fm.label("C_STORE")])
        for i, b in enumerate(block2):
            pre.extend([fm.label("LIT"), b, fm.label("LIT"), sprite2 + i, fm.label("C_STORE")])
        for i, b in enumerate(table_bytes):
            pre.extend([fm.label("LIT"), b, fm.label("LIT"), table + i, fm.label("C_STORE")])
        cells = pre + [
            fm.label("LIT"), table,
            fm.label("LIT"), 0,
            fm.label("LIT"), 0,
            fm.label("LOCK_SPRITES"),
            fm.label("MULTI_BLIT"),
        ]
        fm.run(cells)
        m = fm._last_m
        for line in range(8):
            assert m.mem[screen_addr(0, 0, line)] == SAMPLE_8_BYTES[line], (
                f"MULTI-BLIT first sprite at (0,0): line {line}"
            )
        for line in range(8):
            assert m.mem[screen_addr(0, 2, line)] == 0xFF, (
                f"MULTI-BLIT second sprite at (16,0): line {line}"
            )
