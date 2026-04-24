"""
Tests for M4b: compiler-side bank-scoped CREATE/,/C,/ALLOT. `in-bank` switches
subsequent data emissions into a named bank; `end-bank` switches back to the
main (code) bank. Data addresses emitted under `in-bank n` land in the
$C000–$FFFF range so the paged slot sees them when bank n is mapped.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, CompileError
from zt.sim import (
    DEFAULT_DATA_STACK_TOP_128K,
    DEFAULT_RETURN_STACK_TOP_128K,
)


def _compile_128k(source: str) -> Compiler:
    c = Compiler(
        data_stack_top=DEFAULT_DATA_STACK_TOP_128K,
        return_stack_top=DEFAULT_RETURN_STACK_TOP_128K,
    )
    c.include_stdlib()
    c.compile_source(source)
    c.compile_main_call()
    c.build()
    return c


class TestCreateInBank:

    def test_create_data_address_in_paged_slot(self):
        c = _compile_128k("""
            0 in-bank
              create my-table 1 , 2 , 3 ,
            end-bank
            : main begin again ;
        """)
        addr = c.words["my-table"].data_address
        assert 0xC000 <= addr < 0x10000, (
            f"my-table data_address should be in the paged slot ($C000+); "
            f"got {addr:#06x}"
        )

    def test_code_shim_lives_in_main_bank(self):
        c = _compile_128k("""
            0 in-bank
              create my-table 1 ,
            end-bank
            : main begin again ;
        """)
        code_addr = c.words["my-table"].address
        assert 0x8000 <= code_addr < 0xC000, (
            f"my-table code shim should live in main bank 2 ($8000-$BFFF); "
            f"got {code_addr:#06x}"
        )

    def test_bank_contents_include_emitted_data(self):
        c = _compile_128k("""
            0 in-bank
              create my-cells 1 , 2 , 3 ,
            end-bank
            : main begin again ;
        """)
        bank0 = c.bank_image(0)
        start = c.words["my-cells"].data_address - 0xC000
        assert bank0[start:start + 2] == bytes([1, 0]), "first cell should be 1 (little-endian)"
        assert bank0[start + 2:start + 4] == bytes([2, 0]), "second cell should be 2"
        assert bank0[start + 4:start + 6] == bytes([3, 0]), "third cell should be 3"

    def test_c_comma_in_bank_writes_bytes(self):
        c = _compile_128k("""
            0 in-bank
              create bytes-table $AA c, $BB c, $CC c,
            end-bank
            : main begin again ;
        """)
        bank0 = c.bank_image(0)
        start = c.words["bytes-table"].data_address - 0xC000
        assert bank0[start:start + 3] == bytes([0xAA, 0xBB, 0xCC]), (
            "c, should emit raw bytes into the active bank"
        )

    def test_allot_reserves_zeroed_space(self):
        c = _compile_128k("""
            0 in-bank
              create buffer 100 allot
            end-bank
            : main begin again ;
        """)
        bank0 = c.bank_image(0)
        start = c.words["buffer"].data_address - 0xC000
        assert bank0[start:start + 100] == bytes(100), (
            "allot should reserve zero-filled bytes in the active bank"
        )


class TestEndBankSwitchesBackToMain:

    def test_create_after_end_bank_lives_in_main(self):
        c = _compile_128k("""
            0 in-bank
              create in-zero 1 ,
            end-bank
            create in-main 2 ,
            : main begin again ;
        """)
        in_zero_addr = c.words["in-zero"].data_address
        in_main_addr = c.words["in-main"].data_address
        assert in_zero_addr >= 0xC000, "in-zero should be in the paged slot"
        assert in_main_addr < 0xC000, "in-main (after end-bank) should be in main bank"

    def test_two_banks_keep_separate_here_pointers(self):
        c = _compile_128k("""
            0 in-bank  create a 1 , 2 ,  end-bank
            1 in-bank  create b 3 , 4 ,  end-bank
            : main begin again ;
        """)
        a_addr = c.words["a"].data_address
        b_addr = c.words["b"].data_address
        assert a_addr >= 0xC000 and b_addr >= 0xC000, (
            "both a and b should have paged-slot addresses"
        )
        bank0 = c.bank_image(0)
        bank1 = c.bank_image(1)
        a_start = a_addr - 0xC000
        b_start = b_addr - 0xC000
        assert bank0[a_start:a_start + 4] == bytes([1, 0, 2, 0]), (
            "bank 0 should hold a's cells"
        )
        assert bank1[b_start:b_start + 4] == bytes([3, 0, 4, 0]), (
            "bank 1 should hold b's cells"
        )

    def test_address_does_not_collide_across_banks(self):
        c = _compile_128k("""
            0 in-bank create first-in-zero 1 , end-bank
            1 in-bank create first-in-one  2 , end-bank
            : main begin again ;
        """)
        a_start = c.words["first-in-zero"].data_address
        b_start = c.words["first-in-one"].data_address
        assert a_start == b_start, (
            "first definition in each bank should start at the same address "
            f"($C000 in this simple case); got a={a_start:#06x}, b={b_start:#06x}"
        )


class TestValidationErrors:

    @pytest.mark.parametrize("bank", [-1, 8, 99])
    def test_rejects_out_of_range_bank(self, bank):
        with pytest.raises(CompileError, match="bank"):
            _compile_128k(f"""
                {bank} in-bank
                : main begin again ;
            """)

    def test_end_bank_without_in_bank_errors(self):
        with pytest.raises(CompileError, match="bank"):
            _compile_128k("""
                end-bank
                : main begin again ;
            """)


class TestBuildIntegratesBanks:

    def test_build_128k_sna_embeds_bank_contents(self, tmp_path):
        from zt.format.image_loader import load_sna_128
        import subprocess
        import sys

        src = tmp_path / "banked.fs"
        src.write_text("""
            0 in-bank create level-0 $11 c, $22 c, $33 c, end-bank
            3 in-bank create palette $44 c, $55 c, end-bank
            : main begin again ;
        """)
        out = tmp_path / "banked.sna"

        repo_root = __import__("pathlib").Path(__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "zt.cli", "build",
             str(src), "-o", str(out), "--target", "128k"],
            capture_output=True, text=True, cwd=repo_root,
        )
        assert result.returncode == 0, (
            f"--target 128k with in-bank data should build cleanly; "
            f"stderr={result.stderr}"
        )

        image = load_sna_128(out)
        bank0 = image.memory[0 * 0x4000:(0 + 1) * 0x4000]
        bank3 = image.memory[3 * 0x4000:(3 + 1) * 0x4000]
        assert bank0[0:3] == bytes([0x11, 0x22, 0x33]), (
            "bank 0 bytes should appear at the start of the bank in the .sna"
        )
        assert bank3[0:2] == bytes([0x44, 0x55]), (
            "bank 3 bytes should appear at the start of bank 3 in the .sna"
        )


class TestDoesNotAffect48kPath:

    def test_48k_compile_still_works_without_in_bank(self):
        c = Compiler()
        c.include_stdlib()
        c.compile_source("""
            create foo 1 , 2 ,
            : main foo @ begin again ;
        """)
        c.compile_main_call()
        c.build()
        assert "foo" in c.words, "48k CREATE should still work as before"
        assert c.words["foo"].data_address < 0xC000, (
            "48k CREATE data should NOT land in the paged slot by default"
        )
