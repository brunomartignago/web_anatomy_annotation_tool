"""The DOM suggester (roadmap 4.2): boxes and labels from a captured page's dom.json.

Which elements become boxes: media (img, picture, video, canvas, svg, iframe), form
controls, links, elements with their own text, elements with an interactive or heading
role, and leaf elements painted with a background image.

Noise removal:
- A chain of wrappers that each have one child with the same box (IoU ≥ WRAPPER_IOU)
  becomes one box: the deepest element in it, with every member's hints. So
  `a > picture > img` is one "Image · Link" box.
- A wrapper with exactly one box inside passes its own hints down to it, so the link in
  `<h2><a>…</a></h2>` gets Heading (0.95 beats Link's 0.85).
- Boxes under MIN_SIZE px, and boxes fully covered by a fixed or sticky overlay that isn't
  their ancestor (a cookie banner over the first screen), are dropped.

Labels come from `web-ui.yaml › rules.dom_hints`. For attributes that inherit from their
parent (Component, Template section), the rules are matched against the element's
ancestors and the nearest match wins; for the others (Form, Function) against the element
itself, the first matching rule in YAML order. When several hints meet in one box, the most
confident one wins. `defaults` fills an attribute no rule matched.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from annotool.capture.dom import DOM_NAME, DomElement, DomSnapshot
from annotool.models import DomRef
from annotool.suggest.base import AddBox, Proposal, SuggestContext, iou
from annotool.suggest.selectors import Selector, compile_selector, uncaptured_attributes
from annotool.taxonomy import Taxonomy

MIN_SIZE = 6  # px; smaller boxes are noise
WRAPPER_IOU = 0.9  # a single child this close to its parent's box is the same box
OVERLAY_MAX_VIEWPORT_SHARE = 0.5  # bigger fixed layers are backdrops, not covers

MEDIA_TAGS = {"img", "picture", "video", "canvas", "svg", "iframe"}
CONTROL_TAGS = {"input", "select", "textarea", "button"}
INTERACTIVE_TAGS = CONTROL_TAGS | {"a", "label"}
INTERACTIVE_ROLES = {
    "button", "link", "checkbox", "radio", "tab", "menuitem", "combobox", "switch",
    "textbox", "searchbox", "option",
}  # fmt: skip
ELEMENT_ROLES = INTERACTIVE_ROLES | {"heading", "img"}
TEXT_NODE = "text_node"  # pseudo-selector: the element has its own text


@dataclass(frozen=True)
class _Rule:
    selector: Selector | None  # None for text_node
    value: str
    confidence: float
    max_size_px: float | None = None

    def matches(self, el: DomElement, by_index: dict[int, DomElement]) -> bool:
        if self.max_size_px is not None:
            _, _, w, h = el.bbox
            if w > self.max_size_px or h > self.max_size_px:
                return False
        if self.selector is None:
            return el.text_len > 0
        return self.selector.matches(el, by_index)


@dataclass
class _Hints:
    """Best value per attribute, with its confidence."""

    best: dict[str, tuple[str, float]] = field(default_factory=dict)

    def add(self, attr: str, value: str, confidence: float) -> None:
        if attr not in self.best or confidence > self.best[attr][1]:
            self.best[attr] = (value, confidence)

    def update(self, other: "_Hints") -> None:
        for attr, (value, confidence) in other.best.items():
            self.add(attr, value, confidence)


def _parse_rules(entries: Any, attr: str) -> list[_Rule]:
    rules = []
    for entry in entries or []:
        match = str(entry["match"])
        rules.append(
            _Rule(
                selector=None if match == TEXT_NODE else compile_selector(match),
                value=str(entry["value"]),
                confidence=float(entry.get("confidence", 0.5)),
                max_size_px=entry.get("max_size_px"),
            )
        )
    return rules


class DomSuggester:
    id = "dom"

    def __init__(
        self,
        own: dict[str, list[_Rule]],
        ancestor: dict[str, list[_Rule]],
        defaults: dict[str, tuple[str, float]],
        uncaptured: list[str],
    ):
        self.own = own
        self.ancestor = ancestor
        self.defaults = defaults
        self.uncaptured = uncaptured  # hint attributes dom.json doesn't record

    @classmethod
    def from_taxonomy(cls, taxonomy: Taxonomy) -> "DomSuggester":
        hints = dict((taxonomy.rules or {}).get("dom_hints") or {})
        raw_defaults = hints.pop("defaults", None) or {}
        inherited = {a.id for a in taxonomy.attributes if a.inherit_from_parent}
        own, ancestor = {}, {}
        selectors = []
        for attr, entries in hints.items():
            rules = _parse_rules(entries, attr)
            (ancestor if attr in inherited else own)[attr] = rules
            selectors += [str(e["match"]) for e in entries or [] if e["match"] != TEXT_NODE]
        defaults = {
            attr: (str(d["value"]), float(d.get("confidence", 0.3)))
            for attr, d in raw_defaults.items()
        }
        return cls(own, ancestor, defaults, uncaptured_attributes(selectors))

    # ── Suggester protocol ──

    def suggest(self, context: SuggestContext) -> Sequence[Proposal]:
        if context.folder is None or not (context.folder / DOM_NAME).exists():
            return []
        snapshot = DomSnapshot.model_validate_json(
            (context.folder / DOM_NAME).read_text(encoding="utf-8")
        )
        return self.proposals(snapshot, context.page.page.width, context.page.page.height)

    # ── The work ──

    def proposals(self, snapshot: DomSnapshot, width: float, height: float) -> list[AddBox]:
        els = snapshot.elements
        by_index = {e.i: e for e in els}
        children: dict[int, list[int]] = defaultdict(list)
        for e in els:
            if e.parent is not None and e.parent in by_index:
                children[e.parent].append(e.i)

        def is_element(e: DomElement) -> bool:
            if e.tag in ("html", "body"):
                return False
            return (
                e.tag in MEDIA_TAGS
                or e.tag in CONTROL_TAGS
                or e.text_len > 0
                or e.href
                or e.role in ELEMENT_ROLES
                or (e.bg_image and not children[e.i])
            )

        # Elements are in document order (parents before children), so walking backwards
        # sees children first. rep: the deepest element of a same-box wrapper chain.
        rep: dict[int, int] = {}
        for e in reversed(els):
            kids = children[e.i]
            same = len(kids) == 1 and iou(e.bbox, by_index[kids[0]].bbox) >= WRAPPER_IOU
            rep[e.i] = rep[kids[0]] if same else e.i
        chains: dict[int, list[int]] = defaultdict(list)
        for e in els:
            chains[rep[e.i]].append(e.i)

        # One box per chain with an element in it, anchored on its deepest element.
        boxes: dict[int, list[int]] = {}
        for members in chains.values():
            found = [m for m in members if is_element(by_index[m])]
            if found:
                boxes[max(found)] = members
        member_of = {m: anchor for anchor, members in boxes.items() for m in members}

        hints: dict[int, _Hints] = {}
        for anchor, members in boxes.items():
            hints[anchor] = _Hints()
            for m in members:
                hints[anchor].update(self._own_hints(by_index[m], by_index))

        # A wrapper with exactly one box inside passes its hints down to it.
        count: dict[int, int] = {}
        sole: dict[int, int | None] = {}
        for e in reversed(els):
            n = 1 if e.i in boxes else 0
            only = e.i if e.i in boxes else None
            for k in children[e.i]:
                n += count[k]
                if count[k] == 1:
                    only = sole[k]
            count[e.i] = n
            sole[e.i] = only if n == 1 else None
        for e in els:
            if e.i not in member_of and count[e.i] == 1 and sole[e.i] is not None:
                wrapper = self._own_hints(e, by_index)
                if wrapper.best:
                    hints[sole[e.i]].update(wrapper)

        overlays = self._overlays(snapshot, els)
        result = []
        for anchor, members in sorted(boxes.items()):
            el = by_index[anchor]
            bbox = self._box(el, [by_index[m] for m in members], width, height)
            if bbox is None or self._covered(el, bbox, overlays, by_index):
                continue
            labels = hints[anchor]
            for attr, rules in self.ancestor.items():
                found = self._nearest(el, rules, by_index)
                if found is not None:
                    labels.add(attr, *found)
            for attr, (value, confidence) in self.defaults.items():
                if attr not in labels.best:
                    labels.add(attr, value, confidence)
            result.append(
                AddBox(
                    bbox=bbox,
                    kind="element",
                    labels={a: v for a, (v, _) in labels.best.items()},
                    confidence={a: c for a, (_, c) in labels.best.items()},
                    dom=DomRef(index=el.i, tag=el.tag, role=el.role),
                )
            )
        return result

    def _own_hints(self, el: DomElement, by_index: dict[int, DomElement]) -> _Hints:
        found = _Hints()
        for attr, rules in self.own.items():
            for rule in rules:
                if rule.matches(el, by_index):
                    found.add(attr, rule.value, rule.confidence)
                    break  # the first matching rule, in YAML order
        return found

    def _nearest(
        self, el: DomElement, rules: list[_Rule], by_index: dict[int, DomElement]
    ) -> tuple[str, float] | None:
        node = by_index.get(el.parent) if el.parent is not None else None
        while node is not None:
            for rule in rules:
                if rule.matches(node, by_index):
                    return rule.value, rule.confidence
            node = by_index.get(node.parent) if node.parent is not None else None
        return None

    @staticmethod
    def _box(
        el: DomElement, members: list[DomElement], width: float, height: float
    ) -> tuple[float, float, float, float] | None:
        interactive = any(
            m.tag in INTERACTIVE_TAGS or m.href or m.role in INTERACTIVE_ROLES for m in members
        )
        media = el.tag in MEDIA_TAGS or el.tag in CONTROL_TAGS
        # Plain text gets the tight box around its text, not the (often full-width) block.
        x, y, w, h = el.bbox if interactive or media or el.text_bbox is None else el.text_bbox
        left, top = max(0.0, x), max(0.0, y)
        right, bottom = min(float(width), x + w), min(float(height), y + h)
        if right - left < MIN_SIZE or bottom - top < MIN_SIZE:
            return None
        r = lambda v: round(v, 1)  # noqa: E731
        return (r(left), r(top), r(right - left), r(bottom - top))

    @staticmethod
    def _overlays(snapshot: DomSnapshot, els: list[DomElement]) -> list[DomElement]:
        limit = OVERLAY_MAX_VIEWPORT_SHARE * snapshot.viewport.width * snapshot.viewport.height
        return [
            e for e in els if e.position in ("fixed", "sticky") and e.bbox[2] * e.bbox[3] <= limit
        ]

    @staticmethod
    def _covered(
        el: DomElement,
        bbox: tuple[float, float, float, float],
        overlays: list[DomElement],
        by_index: dict[int, DomElement],
    ) -> bool:
        if not overlays:
            return False
        ancestors = set()
        node: DomElement | None = el
        while node is not None:
            ancestors.add(node.i)
            node = by_index.get(node.parent) if node.parent is not None else None
        x, y, w, h = bbox
        for o in overlays:
            if o.i in ancestors:
                continue  # the overlay's own content
            ox, oy, ow, oh = o.bbox
            if x >= ox and y >= oy and x + w <= ox + ow and y + h <= oy + oh:
                return True
        return False
