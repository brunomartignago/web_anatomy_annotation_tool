"""Debug overlay: draw `dom.json` boxes on the screenshot to check that they line up."""

from pathlib import Path

from PIL import Image, ImageDraw

from annotool.capture.dom import DomElement, DomSnapshot

CATEGORY_COLORS = {
    "container": (150, 150, 150),
    "text": (30, 100, 255),
    "media": (0, 170, 60),
    "interactive": (255, 120, 0),
}
_MEDIA = {"img", "picture", "video", "canvas", "svg", "iframe"}
_INTERACTIVE = {"a", "button", "input", "select", "textarea"}
_INTERACTIVE_ROLES = {"button", "link", "checkbox", "radio", "tab", "menuitem", "combobox"}


def category(el: DomElement) -> str:
    if el.tag in _INTERACTIVE or el.href or el.role in _INTERACTIVE_ROLES:
        return "interactive"
    if el.tag in _MEDIA or el.bg_image:
        return "media"
    if el.text_len:
        return "text"
    return "container"


def render_dom_overlay(image_path: Path, dom: DomSnapshot, out_path: Path) -> dict[str, int]:
    """Write the screenshot with every DOM box outlined. Returns counts per category."""
    with Image.open(image_path) as img:
        canvas = img.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    counts = dict.fromkeys(CATEGORY_COLORS, 0)
    # Containers first (thin), so the more specific boxes are drawn on top.
    ordered = sorted(dom.elements, key=lambda e: category(e) != "container")
    for el in ordered:
        kind = category(el)
        counts[kind] += 1
        x, y, w, h = el.bbox
        width = 1 if kind == "container" else 2
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=CATEGORY_COLORS[kind], width=width)
    _legend(draw, counts)
    canvas.save(out_path)
    return counts


def _legend(draw: ImageDraw.ImageDraw, counts: dict[str, int]) -> None:
    x, y = 8, 8
    draw.rectangle([x - 4, y - 4, x + 190, y + 18 * len(counts)], fill=(255, 255, 255))
    for kind, color in CATEGORY_COLORS.items():
        draw.rectangle([x, y + 3, x + 10, y + 13], fill=color)
        draw.text((x + 16, y), f"{kind} ({counts[kind]})", fill=(0, 0, 0))
        y += 18
