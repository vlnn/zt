import pytest

from zt.compiler import Compiler
from zt.sim import Z80

ATTR_BASE = 22528
ATTR_SIZE = 768
BRIGHT_WHITE = 56


def _run_sierpinski() -> Z80:
    src = (
        ": sierpinski "
        "  24 0 do "
        "    32 0 do "
        "      i j and 0= if 56 else 0 then "
        "      j 32 * i + 22528 + c! "
        "    loop "
        "  loop ; "
        ": main sierpinski halt ;"
    )
    c = Compiler()
    c.compile_source(src)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(c.origin, image)
    m.pc = c.words["_start"].address
    m.run()
    assert m.halted, "sierpinski should halt after drawing"
    return m


@pytest.fixture(scope="module")
def drawn() -> Z80:
    return _run_sierpinski()


def attr_addr(col: int, row: int) -> int:
    return ATTR_BASE + row * 32 + col


class TestSierpinskiCompiles:

    def test_compiles_from_fs_file(self):
        from pathlib import Path

        fs_path = Path(__file__).parent.parent / "examples" / "sierpinski.fs"
        source = fs_path.read_text()

        c = Compiler()
        c.compile_source(source, source=str(fs_path))
        assert "sierpinski" in c.words, "sierpinski word should be defined"
        assert "main" in c.words, "main word should be defined"

    def test_uses_all_m4_features(self):
        from pathlib import Path

        fs_path = Path(__file__).parent.parent / "examples" / "sierpinski.fs"
        source = fs_path.read_text()

        c = Compiler()
        c.compile_source(source, source=str(fs_path))
        image = c.build()
        assert len(image) > 200, "sierpinski should produce substantial code"


class TestFirstRowAllBright:

    def test_row_0_is_all_bright(self, drawn):
        for col in range(32):
            addr = attr_addr(col, 0)
            assert drawn.mem[addr] == BRIGHT_WHITE, \
                f"row 0, col {col} should be {BRIGHT_WHITE} (anything AND 0 = 0)"


class TestFirstColumnAllBright:

    def test_col_0_is_all_bright(self, drawn):
        for row in range(24):
            addr = attr_addr(0, row)
            assert drawn.mem[addr] == BRIGHT_WHITE, \
                f"row {row}, col 0 should be {BRIGHT_WHITE} (0 AND anything = 0)"


class TestSierpinskiPattern:

    @pytest.mark.parametrize("col,row", [
        (1, 1), (3, 1), (5, 1), (7, 1),
        (1, 3), (2, 3), (3, 3),
        (5, 3), (6, 3), (7, 3),
        (1, 5), (3, 5), (5, 5), (7, 5),
    ])
    def test_nonzero_and_gives_black(self, drawn, col, row):
        assert col & row != 0, f"precondition: {col} AND {row} should be nonzero"
        addr = attr_addr(col, row)
        assert drawn.mem[addr] == 0, \
            f"({col},{row}) should be 0 when col AND row != 0"

    @pytest.mark.parametrize("col,row", [
        (0, 0), (2, 1), (4, 1), (4, 2), (4, 3),
        (8, 1), (8, 2), (8, 4), (8, 7),
        (16, 1), (16, 8), (16, 15),
    ])
    def test_zero_and_gives_bright(self, drawn, col, row):
        assert col & row == 0, f"precondition: {col} AND {row} should be zero"
        addr = attr_addr(col, row)
        assert drawn.mem[addr] == BRIGHT_WHITE, \
            f"({col},{row}) should be {BRIGHT_WHITE} when col AND row == 0"


class TestSierpinskiCoverage:

    def test_all_768_cells_written(self, drawn):
        for row in range(24):
            for col in range(32):
                addr = attr_addr(col, row)
                val = drawn.mem[addr]
                expected = BRIGHT_WHITE if (col & row) == 0 else 0
                assert val == expected, \
                    f"attr({col},{row}) should be {expected}, got {val}"

    def test_bright_cell_count(self, drawn):
        count = sum(
            1 for row in range(24) for col in range(32)
            if drawn.mem[attr_addr(col, row)] == BRIGHT_WHITE
        )
        expected = sum(
            1 for row in range(24) for col in range(32)
            if (col & row) == 0
        )
        assert count == expected, \
            f"should have {expected} bright cells, got {count}"

    def test_no_writes_outside_attr_area(self, drawn):
        m_clean = Z80()
        m_run = drawn
        for addr in range(ATTR_BASE - 16, ATTR_BASE):
            assert m_run.mem[addr] == m_clean.mem[addr], \
                f"byte before attr area at {addr} should be untouched"
        for addr in range(ATTR_BASE + ATTR_SIZE, ATTR_BASE + ATTR_SIZE + 16):
            assert m_run.mem[addr] == m_clean.mem[addr], \
                f"byte after attr area at {addr} should be untouched"
