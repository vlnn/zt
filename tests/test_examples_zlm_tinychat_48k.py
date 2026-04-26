"""Layout invariants and end-to-end runtime test for the 48K port of zlm-tinychat.

The port hoists the big activations (acts0, acts1, acts2) above the image,
parks acts3 in the 48K printer-buffer area at $5B00 (invisible to the
display), and inlines a minimal stdlib so the small per-layer buffers and
scalar variables fit in the image. Tests pin the arithmetic so a future
image-size regression fails loudly, and run the SNA in the simulator to
confirm the model still answers "HELLO" with "HI".
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    decode_screen_text,
)

ORIGIN = 0x5C00
RSTACK_TOP = 0xFF80
DSTACK_TOP = 0xFFC0
STACK_BUDGET = 32

ACTS3_LO, ACTS3_HI = 0x5B00, 0x5C00
ACTS2_LO, ACTS2_HI = 0xF9E0, 0xFB60
ACTS0_LO, ACTS0_HI = 0xFB60, 0xFD60
ACTS1_LO, ACTS1_HI = 0xFD60, 0xFF60

IMAGE_END_MAX = ACTS2_LO


@pytest.fixture(scope="module")
def example_dir() -> Path:
    return ROOT / "examples" / "zlm-tinychat-48k"


@pytest.fixture(scope="module")
def compiled(example_dir):
    src = (example_dir / "main.fs").read_text()
    c = Compiler(
        include_dirs=[example_dir, ROOT / "stdlib"],
        origin=ORIGIN,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    return c


def test_no_bank_data_is_emitted(compiled) -> None:
    assert not compiled.banks(), (
        "48K port should not emit any bank data; in-bank/end-bank were dropped"
    )


def test_image_ends_below_acts2(compiled) -> None:
    image_end = ORIGIN + len(compiled._main_asm.code)
    headroom = IMAGE_END_MAX - image_end
    assert image_end <= IMAGE_END_MAX, (
        f"image ends ${image_end:04X}; must not cross ${IMAGE_END_MAX:04X} "
        f"(acts2 lives there). headroom={headroom:+d} bytes"
    )


def test_acts3_is_invisible_to_display() -> None:
    """acts3 at $5B00..$5C00 sits in the 48K printer-buffer area; the screen
    pixel area ($4000..$57FF) and attrs ($5800..$5AFF) never touch it."""
    assert ACTS3_HI <= 0x5C00, "acts3 should not extend into image area"
    assert ACTS3_LO >= 0x5B00, (
        f"acts3 should sit at or above $5B00 to stay out of screen attrs; "
        f"got ${ACTS3_LO:04X}"
    )


@pytest.mark.parametrize(
    "name,lo,hi",
    [
        ("acts3", ACTS3_LO, ACTS3_HI),
        ("acts2", ACTS2_LO, ACTS2_HI),
        ("acts0", ACTS0_LO, ACTS0_HI),
        ("acts1", ACTS1_LO, ACTS1_HI),
    ],
)
def test_buffer_outside_image(compiled, name, lo, hi) -> None:
    image_end = ORIGIN + len(compiled._main_asm.code)
    above_image = lo >= image_end
    below_image = hi <= ORIGIN
    assert above_image or below_image, (
        f"buffer {name} (${lo:04X}..${hi:04X}) should not overlap image "
        f"(${ORIGIN:04X}..${image_end:04X})"
    )


def test_acts1_clears_rstack_region() -> None:
    rstack_floor = RSTACK_TOP - STACK_BUDGET
    assert ACTS1_HI <= rstack_floor, (
        f"acts1 ends ${ACTS1_HI:04X}; rstack region starts ${rstack_floor:04X}"
    )


def test_rstack_clears_dstack_region() -> None:
    dstack_floor = DSTACK_TOP - STACK_BUDGET
    assert RSTACK_TOP <= dstack_floor, (
        f"rstack-top ${RSTACK_TOP:04X} should not collide with dstack region "
        f"(starts ${dstack_floor:04X})"
    )


@pytest.fixture(scope="module")
def screen_text(example_dir):
    src = (example_dir / "main.fs").read_text()
    c = Compiler(
        include_dirs=[example_dir, ROOT / "stdlib"],
        origin=ORIGIN,
        data_stack_top=DSTACK_TOP,
        return_stack_top=RSTACK_TOP,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    c.compile_main_call()
    image = c.build()

    m = Z80(mode="48k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = c.words["_start"].address
    m.input_buffer = bytearray(b"HELLO\r")
    m.run(max_ticks=80_000_000)

    raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0)
    return raw.decode("ascii", errors="replace")


@pytest.mark.slow
def test_query_appears_on_first_line(screen_text) -> None:
    assert "HELLO" in screen_text, (
        f"the typed query 'HELLO' should appear on screen; got:\n{screen_text}"
    )


@pytest.mark.slow
def test_response_is_HI(screen_text) -> None:
    lines = [ln for ln in screen_text.split("\r") if ln.strip()]
    non_query_lines = [ln for ln in lines if "HELLO" not in ln]
    assert non_query_lines, (
        f"after the query line there should be a response line; full screen:\n"
        f"{screen_text}"
    )
    response = non_query_lines[0].strip()
    assert response == "HI", (
        f"48K port should answer 'HELLO' with 'HI' (same as 128K reference); "
        f"got {response!r}; full screen:\n{screen_text}"
    )
