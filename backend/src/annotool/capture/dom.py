"""`dom.json`: the rendered elements of a captured page, from `dom_extract.js`.

Boxes are `[x, y, width, height]` in document pixels with a top-left origin, which equal
screenshot pixels (device scale factor 1, captured scrolled to the top).
"""

from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict

DOM_NAME = "dom.json"
EXTRACT_JS = files("annotool.capture").joinpath("dom_extract.js").read_text(encoding="utf-8")

Box = tuple[float, float, float, float]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Size(_Model):
    width: int
    height: int


class Scroll(_Model):
    x: float
    y: float


class DomElement(_Model):
    i: int
    parent: int | None  # index of the nearest kept ancestor
    tag: str
    bbox: Box
    position: str  # static | relative | absolute | fixed | sticky
    font_size: float | None = None
    font_weight: int | None = None
    id: str | None = None
    classes: list[str] | None = None  # first three
    role: str | None = None
    aria_label: str | None = None
    input_type: str | None = None
    href: bool = False
    bg_image: bool = False
    text_len: int = 0  # length of the element's own text (not its children's)
    text_bbox: Box | None = None  # tight box around that text
    clipped: bool = False  # partly hidden by a scrolling/overflow ancestor; bbox = visible part


class DomSnapshot(_Model):
    version: Literal[1] = 1
    page: Size
    viewport: Size
    scroll: Scroll
    elements: list[DomElement]
