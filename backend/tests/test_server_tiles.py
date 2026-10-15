import os

import pytest
from PIL import Image

from annotool.server.tiles import StripCache, strip_bounds, strip_count


def _banded_png(path, width=40, height=5000, band=1000):
    """A PNG whose colour changes every `band` rows, so strips can be told apart."""
    img = Image.new("RGB", (width, height))
    for top in range(0, height, band):
        shade = (top // band) * 40
        img.paste((shade, 255 - shade, 128), (0, top, width, min(top + band, height)))
    img.save(path)
    return img


def test_strip_count_rounds_up():
    assert strip_count(1, 2048) == 1
    assert strip_count(2048, 2048) == 1
    assert strip_count(2049, 2048) == 2
    assert strip_count(91_086, 2048) == 45


def test_strip_bounds_last_strip_is_shorter():
    assert strip_bounds(0, 5000, 2048) == (0, 2048)
    assert strip_bounds(1, 5000, 2048) == (2048, 4096)
    assert strip_bounds(2, 5000, 2048) == (4096, 5000)


@pytest.mark.parametrize("n", [-1, 3, 100])
def test_strip_bounds_out_of_range(n):
    with pytest.raises(IndexError):
        strip_bounds(n, 5000, 2048)


def test_strips_are_cut_from_the_screenshot(tmp_path):
    _banded_png(tmp_path / "page.png")
    cache = StripCache(tmp_path, strip_height=2048)
    assert cache.count() == 3

    sizes = []
    for n in range(3):
        path = cache.path(n)
        assert path.parent == tmp_path / ".cache" / "strips"
        with Image.open(path) as strip:
            assert strip.format == "WEBP"
            sizes.append(strip.size)
            if n == 1:
                # Row 0 of strip 1 is page row 2048, in the third band (rows 2000-2999).
                r, g, _ = strip.convert("RGB").getpixel((20, 0))
                assert abs(r - 80) < 12 and abs(g - 175) < 12
    assert sizes == [(40, 2048), (40, 2048), (40, 904)]


def test_strip_out_of_range_raises(tmp_path):
    _banded_png(tmp_path / "page.png", height=100)
    with pytest.raises(IndexError):
        StripCache(tmp_path).path(1)


def test_strips_are_reused_while_the_screenshot_is_unchanged(tmp_path):
    _banded_png(tmp_path / "page.png")
    first = StripCache(tmp_path, strip_height=2048).path(0)
    stamp = first.stat().st_mtime_ns
    again = StripCache(tmp_path, strip_height=2048).path(0)
    assert again == first and again.stat().st_mtime_ns == stamp


def test_recapture_invalidates_the_cache(tmp_path):
    png = tmp_path / "page.png"
    _banded_png(png, height=5000)
    cache = StripCache(tmp_path, strip_height=2048)
    cache.path(2)
    version = cache.version()

    _banded_png(png, height=3000)  # a recapture: shorter page, new file
    os.utime(png, ns=(png.stat().st_atime_ns, png.stat().st_mtime_ns + 10**9))
    cache = StripCache(tmp_path, strip_height=2048)
    assert cache.count() == 2
    assert cache.version() != version
    with Image.open(cache.path(1)) as strip:
        assert strip.size == (40, 952)
    assert not (tmp_path / ".cache" / "strips" / "2.webp").exists()


def test_rgba_and_palette_screenshots_are_supported(tmp_path):
    Image.new("RGBA", (30, 50), (10, 20, 30, 255)).save(tmp_path / "page.png")
    with Image.open(StripCache(tmp_path).path(0)) as strip:
        assert strip.size == (30, 50)
    Image.new("P", (30, 50)).save(tmp_path / "page.png")
    os.utime(tmp_path / "page.png", ns=(0, 10**9))
    with Image.open(StripCache(tmp_path).path(0)) as strip:
        assert strip.size == (30, 50)


def test_missing_screenshot(tmp_path):
    with pytest.raises(FileNotFoundError):
        StripCache(tmp_path).count()
