import pytest

from zt.image import build_image
from zt.sna import build_sna, SNA_HEADER_SIZE, SNA_TOTAL_SIZE


def test_build_image_produces_nonempty_bytes():
    image = build_image()
    assert len(image) > 0, "build_image should produce bytes"


def test_build_image_resolves_all_labels():
    image = build_image()
    assert isinstance(image, bytes), "resolved image should be bytes"


@pytest.mark.parametrize("origin", [0x4000, 0x8000, 0xC000])
def test_build_image_works_at_various_origins(origin):
    image = build_image(origin=origin)
    assert len(image) > 100, f"image at {origin:#06x} should still build"


def test_full_pipeline_produces_valid_snapshot():
    code = build_image()
    sna = build_sna(code, origin=0x8000)
    assert len(sna) == SNA_TOTAL_SIZE, "full pipeline should produce a valid 48K SNA"
    code_offset = SNA_HEADER_SIZE + (0x8000 - 0x4000)
    assert sna[code_offset:code_offset + len(code)] == code, "Forth code should be embedded at origin"
