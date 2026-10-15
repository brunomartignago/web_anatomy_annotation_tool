"""Real-browser capture tests on a local HTML page (no network). See conftest.py."""

import json
from datetime import datetime

import pytest
from PIL import Image

from annotool.capture.urls import UrlEntry

PAGE_HEIGHT = 20000  # long enough that a smooth scroll back to the top takes > 1 s
RED, BLUE, GREEN = (255, 0, 0), (0, 0, 255), (0, 160, 0)

# A fixed header, a sticky bar, and a block that only turns green once scrolled into view.
TEST_PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Sticky test page</title>
<style>
  html {{ scroll-behavior: smooth; }}  /* like MDN: scrollTo() animates unless told not to */
  body {{ margin: 0; background: #fff; }}
  header {{ position: fixed; top: 0; left: 0; right: 0; height: 100px;
           background: rgb{RED}; z-index: 10; }}
  main {{ height: {PAGE_HEIGHT}px; padding-top: 100px; box-sizing: border-box; }}
  #sticky {{ position: sticky; top: 100px; height: 50px; background: rgb{BLUE}; }}
  #lazy {{ position: absolute; top: 4000px; width: 300px; height: 300px; background: #888; }}
  #lazy.loaded {{ background: rgb{GREEN}; }}
</style></head>
<body>
  <header></header>
  <main><div id="sticky"></div></main>
  <div id="lazy"></div>
  <script>
    const lazy = document.getElementById('lazy');
    new IntersectionObserver(entries => {{
      if (entries.some(e => e.isIntersecting)) lazy.classList.add('loaded');
    }}).observe(lazy);
  </script>
</body></html>
"""


@pytest.fixture
def test_page_url(tmp_path) -> str:
    page = tmp_path / "sticky.html"
    page.write_text(TEST_PAGE, encoding="utf-8")
    return page.as_uri()


@pytest.fixture
def captured(capturer, test_page_url, tmp_path):
    out = tmp_path / "out"
    meta = capturer.capture(UrlEntry(url=test_page_url, category="Test"), out)
    image = Image.open(out / "page.png").convert("RGB")
    return out, meta, image


def test_one_full_page_screenshot_at_1920_wide(captured):
    _, meta, image = captured
    assert image.size == (1920, PAGE_HEIGHT)
    assert (meta.width, meta.height) == image.size


def test_fixed_header_appears_once(captured):
    _, _, image = captured
    assert image.getpixel((10, 50)) == RED
    # Where a stitched capture would repeat it: one viewport down, and further.
    for y in (1080 + 50, 2 * 1080 + 50, PAGE_HEIGHT - 50):
        assert image.getpixel((10, y)) != RED, y


def test_sticky_bar_stays_in_place(captured):
    _, _, image = captured
    assert image.getpixel((10, 125)) == BLUE
    assert image.getpixel((10, 1080 + 125)) != BLUE


def test_scrolling_triggers_lazy_content(captured):
    _, _, image = captured
    assert image.getpixel((150, 4150)) == GREEN


def test_meta_json_matches_the_png(captured, test_page_url):
    out, meta, _ = captured
    data = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert data["image"] == "page.png" and (out / data["image"]).exists()  # AUDIT #18
    assert data["url"] == test_page_url
    assert data["title"] == "Sticky test page"
    assert data["category"] == "Test"
    assert data["locale"] == "en"
    assert data["viewport"] == {"width": 1920, "height": 1080}
    assert (data["width"], data["height"]) == (1920, PAGE_HEIGHT)
    assert datetime.fromisoformat(data["captured_at"]).tzinfo is not None
    assert data["scroll"]["reached_end"] and data["scroll"]["returned_to_top"]
    assert not list(out.glob("*.tmp"))


def test_page_that_redirects_while_scrolling_is_captured(capturer, tmp_path):
    # Like kayak.com: the page navigates away in the middle of the scroll pass.
    (tmp_path / "landing.html").write_text(
        "<!doctype html><title>Landing</title>"
        '<body style="margin:0;height:4000px;background:#eee">',
        encoding="utf-8",
    )
    start = tmp_path / "start.html"
    start.write_text(
        '<!doctype html><title>Start</title><body style="height:6000px">'
        "<script>addEventListener('scroll', () => {"
        "  if (scrollY > 2000) location.href = 'landing.html'; });</script>",
        encoding="utf-8",
    )
    meta = capturer.capture(UrlEntry(url=start.as_uri()), tmp_path / "out")
    assert meta.final_url.endswith("landing.html")
    assert meta.title == "Landing"
    assert meta.height == 4000
