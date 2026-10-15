"""DOM extraction in a real browser (local page with known positions). See conftest.py.

The key property: every DOM box lines up with the screenshot within 2 px, including the
classic traps (fixed and sticky elements, 100vh sections, bars fixed to the bottom).
"""

import json

import pytest
from PIL import Image

from annotool.capture.dom import DomSnapshot
from annotool.capture.urls import UrlEntry

RED, BLUE, GREEN, PURPLE, ORANGE = (
    (255, 0, 0),
    (0, 0, 255),
    (0, 160, 0),
    (128, 0, 128),
    (255, 140, 0),
)

SCROLL_ITEMS = "".join(f'<div id="item{i}" style="height: 40px">Item {i}</div>' for i in range(20))

PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>DOM test page</title>
<style>
  body {{ margin: 0; font-family: sans-serif; }}
  #header {{ position: fixed; top: 0; left: 0; width: 1920px; height: 100px;
             background: rgb{RED}; z-index: 5; }}
  #hero {{ height: 100vh; background: rgb{GREEN}; padding-top: 100px; box-sizing: border-box; }}
  #sticky {{ position: sticky; top: 100px; height: 40px; background: rgb{BLUE}; }}
  #block {{ position: absolute; left: 300px; top: 1500px; width: 400px; height: 200px;
            background: rgb{ORANGE}; }}
  #bottom-bar {{ position: fixed; bottom: 0; left: 0; width: 1920px; height: 60px;
                 background: rgb{PURPLE}; z-index: 5; }}
  #filler {{ height: 3000px; }}
  #bg {{ width: 50px; height: 50px; background-image: linear-gradient(red, blue); }}
</style></head>
<body>
  <div id="header" role="banner"><a id="logo" href="/" style="margin-left: 500px">Logo</a></div>
  <section id="hero">
    <h1 id="title" style="font-size: 48px; font-weight: 700; margin: 0">Big headline</h1>
    <input id="email" type="email" aria-label="Your email">
    <svg id="icon" width="24" height="24"><path d="M0 0 L24 24"/><circle cx="5" cy="5" r="3"/></svg>
    <div id="bg"></div>
  </section>
  <div id="sticky"></div>
  <div id="block" class="card card--big promo extra"><p id="inside">Text in a card</p></div>
  <div id="scroller" style="position: absolute; left: 1000px; top: 1500px; width: 300px;
       height: 200px; overflow: auto">
    {SCROLL_ITEMS}
  </div>
  <script>document.getElementById('scroller').scrollTop = 410;</script>
  <div id="filler"></div>
  <div id="bottom-bar"></div>
  <div id="gone" style="display: none">hidden</div>
  <div id="invisible" style="visibility: hidden; height: 20px">invisible</div>
  <div style="opacity: 0"><p id="faded">faded</p></div>
  <div id="empty" style="height: 0"></div>
</body></html>
"""


@pytest.fixture(scope="module")
def captured(capturer, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("dom")
    page = tmp / "dom.html"
    page.write_text(PAGE, encoding="utf-8")
    out = tmp / "out"
    meta = capturer.capture(UrlEntry(url=page.as_uri()), out)
    dom = DomSnapshot.model_validate_json((out / "dom.json").read_text(encoding="utf-8"))
    image = Image.open(out / "page.png").convert("RGB")
    by_id = {e.id: e for e in dom.elements if e.id}
    return meta, dom, image, by_id


def test_dom_json_is_written_and_counted(captured):
    meta, dom, image, _ = captured
    assert meta.dom_elements == len(dom.elements) > 5
    assert (dom.page.width, dom.page.height) == image.size
    assert dom.scroll.x == 0 and dom.scroll.y == 0


@pytest.mark.parametrize(
    ("element_id", "bbox"),
    [
        ("header", (0, 0, 1920, 100)),
        ("hero", (0, 0, 1920, 1080)),  # 100vh = the 1080 px viewport, not the full page
        ("sticky", (0, 1080, 1920, 40)),
        ("block", (300, 1500, 400, 200)),
        ("bottom-bar", (0, 1020, 1920, 60)),  # fixed to the bottom of the first screen
    ],
)
def test_boxes_have_the_expected_document_coordinates(captured, element_id, bbox):
    _, _, _, by_id = captured
    assert by_id[element_id].bbox == pytest.approx(bbox, abs=0.5)


@pytest.mark.parametrize(
    ("element_id", "color"),
    [
        ("header", RED),
        ("sticky", BLUE),
        ("block", ORANGE),
        ("bottom-bar", PURPLE),
    ],
)
def test_boxes_line_up_with_the_screenshot_within_2px(captured, element_id, color):
    _, _, image, by_id = captured
    x, y, w, h = by_id[element_id].bbox
    inside = [(x + 2, y + 2), (x + w - 3, y + 2), (x + 2, y + h - 3), (x + w - 3, y + h - 3)]
    for px, py in inside:
        assert image.getpixel((int(px), int(py))) == color, (element_id, px, py)
    if y >= 3:  # just above the box is something else
        assert image.getpixel((int(x + w / 2), int(y - 3))) != color, element_id
    if y + h + 3 < image.height:
        assert image.getpixel((int(x + w / 2), int(y + h + 2))) != color, element_id


def test_hidden_and_empty_elements_are_skipped(captured):
    _, _, _, by_id = captured
    for element_id in ["gone", "invisible", "faded", "empty"]:
        assert element_id not in by_id


def test_items_scrolled_out_of_an_inner_scroll_box_are_dropped(captured):
    # Like MDN's sidebar: the box is scrolled to item 10, so items 0-9 aren't on screen.
    _, _, _, by_id = captured
    for i in range(10):
        assert f"item{i}" not in by_id, i
    assert "item11" in by_id and not by_id["item11"].clipped


def test_partly_visible_items_are_clipped_to_the_scroll_box(captured):
    _, _, _, by_id = captured
    scroller_x, scroller_y, _, scroller_h = by_id["scroller"].bbox
    item = by_id["item10"]  # starts 10 px above the visible area
    assert item.clipped
    assert item.bbox[1] == pytest.approx(scroller_y, abs=0.5)
    assert item.bbox[3] == pytest.approx(30, abs=0.5)
    for el in by_id.values():  # nothing inside spills out of the box
        if el.id and el.id.startswith("item"):
            assert scroller_y - 0.5 <= el.bbox[1]
            assert el.bbox[1] + el.bbox[3] <= scroller_y + scroller_h + 0.5


def test_svg_is_one_box_without_its_shapes(captured):
    _, dom, _, by_id = captured
    assert "icon" in by_id
    assert not any(e.tag in {"path", "circle"} for e in dom.elements)


def test_parents_point_to_the_nearest_kept_ancestor(captured):
    _, dom, _, by_id = captured
    parent = dom.elements[by_id["inside"].parent]
    assert parent.id == "block"
    assert dom.elements[by_id["logo"].parent].id == "header"


def test_element_attributes(captured):
    _, _, _, by_id = captured
    assert by_id["header"].position == "fixed" and by_id["header"].role == "banner"
    assert by_id["sticky"].position == "sticky"
    assert by_id["logo"].href is True and by_id["logo"].tag == "a"
    assert by_id["email"].input_type == "email" and by_id["email"].aria_label == "Your email"
    assert by_id["title"].font_size == 48 and by_id["title"].font_weight == 700
    assert by_id["title"].text_len == len("Big headline")
    assert by_id["bg"].bg_image is True
    assert by_id["block"].classes == ["card", "card--big", "promo"]  # first three


def test_text_bbox_hugs_the_text_inside_the_element(captured):
    _, _, _, by_id = captured
    title = by_id["title"]
    tx, ty, tw, th = title.text_bbox
    x, y, w, h = title.bbox
    assert x <= tx and y <= ty and tx + tw <= x + w + 0.5 and ty + th <= y + h + 0.5
    assert tw < w / 2  # "Big headline" is much narrower than the full-width h1
    assert by_id["block"].text_bbox is None  # no text of its own (it's in the <p>)


def test_meta_json_records_the_element_count(captured):
    meta, _, _, _ = captured
    data = json.loads(meta.model_dump_json())
    assert data["dom_elements"] == meta.dom_elements
