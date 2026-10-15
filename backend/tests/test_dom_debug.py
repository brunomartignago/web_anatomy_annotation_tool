"""DOM overlay rendering and `annotool debug-dom` (no browser needed)."""

from PIL import Image
from typer.testing import CliRunner

from annotool.capture.debug import CATEGORY_COLORS, category, render_dom_overlay
from annotool.capture.dom import DomElement, DomSnapshot
from annotool.cli import app


def element(i, tag, bbox, parent=None, **extra):
    return DomElement(i=i, parent=parent, tag=tag, bbox=bbox, position="static", **extra)


def snapshot(*elements):
    return DomSnapshot(
        page={"width": 400, "height": 300},
        viewport={"width": 1920, "height": 1080},
        scroll={"x": 0, "y": 0},
        elements=list(elements),
    )


def test_categories():
    assert category(element(0, "p", (0, 0, 10, 10), text_len=5)) == "text"
    assert category(element(0, "img", (0, 0, 10, 10))) == "media"
    assert category(element(0, "div", (0, 0, 10, 10), bg_image=True)) == "media"
    assert category(element(0, "a", (0, 0, 10, 10), href=True, text_len=4)) == "interactive"
    assert category(element(0, "input", (0, 0, 10, 10), input_type="text")) == "interactive"
    assert category(element(0, "div", (0, 0, 10, 10), role="button")) == "interactive"
    assert category(element(0, "div", (0, 0, 10, 10))) == "container"


def test_overlay_draws_boxes_in_category_colors(tmp_path):
    image = tmp_path / "page.png"
    Image.new("RGB", (400, 300), "white").save(image)
    dom = snapshot(
        element(0, "img", (50, 50, 100, 80)),
        element(1, "a", (200, 100, 120, 40), href=True, text_len=4),
    )
    out = tmp_path / "debug-dom.png"
    render_dom_overlay(image, dom, out)

    result = Image.open(out).convert("RGB")
    assert result.size == (400, 300)
    assert result.getpixel((50, 90)) == CATEGORY_COLORS["media"]  # left edge of the img box
    assert result.getpixel((260, 100)) == CATEGORY_COLORS["interactive"]  # top edge of the link
    assert result.getpixel((100, 90)) == (255, 255, 255)  # inside a box stays untouched


def test_cli_debug_dom(tmp_path):
    folder = tmp_path / "page"
    folder.mkdir()
    Image.new("RGB", (400, 300), "white").save(folder / "page.png")
    (folder / "dom.json").write_text(
        snapshot(element(0, "img", (10, 10, 50, 50))).model_dump_json(), encoding="utf-8"
    )
    result = CliRunner().invoke(app, ["debug-dom", str(folder)])
    assert result.exit_code == 0, result.output
    assert (folder / "debug-dom.png").exists()
    assert "1 elements" in result.output


def test_cli_debug_dom_without_dom_json_explains(tmp_path):
    result = CliRunner().invoke(app, ["debug-dom", str(tmp_path)])
    assert result.exit_code == 1
    assert "dom.json" in result.output
