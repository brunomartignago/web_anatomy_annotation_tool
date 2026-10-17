"""A small CSS selector matcher for `web-ui.yaml › dom_hints`, run against dom.json.

dom.json keeps only some of each element's attributes, so selectors can only test those:

    tag, id, class (the first three classes), role, aria-label, type (inputs),
    href (present or not), style*=background-image (a background image is set)

Supported syntax: `tag`, `*`, `[attr]`, `[attr=v]`, `[attr*=v]`, `[attr^=v]`, `[attr$=v]`,
`:not(<compound>)`, descendant combinators (`nav a`, `nav *`) and comma lists. Anything
else raises SelectorError, so a typo in the YAML fails loudly instead of matching nothing.
A test on an attribute dom.json doesn't capture (e.g. `src`) never matches;
`uncaptured_attributes` lists them so the gap is visible.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from annotool.capture.dom import DomElement

CAPTURED = {"id", "class", "role", "aria-label", "type", "href", "style"}


class SelectorError(ValueError):
    pass


@dataclass(frozen=True)
class _Attr:
    name: str
    op: str | None  # None = present; "=", "*=", "^=", "$="
    value: str


@dataclass(frozen=True)
class _Compound:
    tag: str | None  # None = any
    attrs: tuple[_Attr, ...]
    negated: tuple["_Compound", ...]

    def matches(self, el: DomElement) -> bool:
        if self.tag is not None and el.tag != self.tag:
            return False
        return all(_attr_matches(a, el) for a in self.attrs) and not any(
            n.matches(el) for n in self.negated
        )


def _attr_value(name: str, el: DomElement) -> str | None:
    if name == "id":
        return el.id
    if name == "class":
        return " ".join(el.classes) if el.classes else None
    if name == "role":
        return el.role
    if name == "aria-label":
        return el.aria_label
    if name == "type":
        return el.input_type
    if name == "href":
        return "" if el.href else None
    if name == "style":
        return "background-image" if el.bg_image else None
    return None  # not captured in dom.json


def _attr_matches(attr: _Attr, el: DomElement) -> bool:
    value = _attr_value(attr.name, el)
    if value is None:
        return False
    if attr.op is None:
        return True
    if attr.op == "=":
        return value == attr.value
    if attr.op == "*=":
        return attr.value in value
    if attr.op == "^=":
        return value.startswith(attr.value)
    return value.endswith(attr.value)  # "$="


@dataclass(frozen=True)
class _Complex:
    """Compounds joined by descendant combinators; the last one is the element itself."""

    parts: tuple[_Compound, ...]

    def matches(self, el: DomElement, by_index: Mapping[int, DomElement]) -> bool:
        *ancestors, last = self.parts
        if not last.matches(el):
            return False
        node = el
        for wanted in reversed(ancestors):
            node = _parent(node, by_index)
            while node is not None and not wanted.matches(node):
                node = _parent(node, by_index)
            if node is None:
                return False
        return True


def _parent(el: DomElement, by_index: Mapping[int, DomElement]) -> DomElement | None:
    return by_index.get(el.parent) if el.parent is not None else None


@dataclass(frozen=True)
class Selector:
    source: str
    alternatives: tuple[_Complex, ...]

    def matches(self, el: DomElement, by_index: Mapping[int, DomElement]) -> bool:
        return any(alt.matches(el, by_index) for alt in self.alternatives)

    def attributes(self) -> set[str]:
        names: set[str] = set()

        def walk(compound: _Compound) -> None:
            names.update(a.name for a in compound.attrs)
            for n in compound.negated:
                walk(n)

        for alt in self.alternatives:
            for part in alt.parts:
                walk(part)
        return names


_TAG = re.compile(r"\*|[a-zA-Z][a-zA-Z0-9-]*")
_ATTR = re.compile(
    r"\[\s*([a-zA-Z][a-zA-Z0-9_-]*)\s*(?:([*^$]?=)\s*(\"[^\"]*\"|'[^']*'|[^\]\s]+)\s*)?\]"
)


def _parse_compound(text: str, pos: int) -> tuple[_Compound, int]:
    start = pos
    tag = None
    match = _TAG.match(text, pos)
    if match:
        tag = None if match.group() == "*" else match.group().lower()
        pos = match.end()
    attrs: list[_Attr] = []
    negated: list[_Compound] = []
    while pos < len(text) and text[pos] not in " ,":
        if text[pos] == "[":
            match = _ATTR.match(text, pos)
            if not match:
                raise SelectorError(f"bad attribute test at {text[pos:]!r}")
            name, op, value = match.group(1).lower(), match.group(2), match.group(3) or ""
            attrs.append(_Attr(name, op, value.strip("\"'")))
            pos = match.end()
        elif text.startswith(":not(", pos):
            inner, end = _parse_compound(text, pos + 5)
            if end >= len(text) or text[end] != ")":
                raise SelectorError(f"unclosed :not( in {text!r}")
            negated.append(inner)
            pos = end + 1
        elif text[pos] == ")":
            break  # end of a :not(...)
        else:
            raise SelectorError(f"unsupported selector syntax at {text[pos:]!r}")
    if pos == start:
        raise SelectorError(f"empty selector in {text!r}")
    return _Compound(tag, tuple(attrs), tuple(negated)), pos


def _split_commas(text: str) -> list[str]:
    parts, depth, current = [], 0, []
    for char in text:
        if char in "[(":
            depth += 1
        elif char in "])":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def compile_selector(text: str) -> Selector:
    alternatives = []
    for part in _split_commas(text):
        part = " ".join(part.split())
        if not part:
            raise SelectorError(f"empty selector in {text!r}")
        compounds, pos = [], 0
        while pos < len(part):
            compound, pos = _parse_compound(part, pos)
            if pos < len(part) and part[pos] == ")":
                raise SelectorError(f"unexpected ')' in {part!r}")
            compounds.append(compound)
            if pos < len(part):
                pos += 1  # the space between compounds
        alternatives.append(_Complex(tuple(compounds)))
    return Selector(text, tuple(alternatives))


def uncaptured_attributes(selectors: Iterable[str]) -> list[str]:
    """Attributes used by these selectors that dom.json doesn't record (sorted)."""
    names: set[str] = set()
    for text in selectors:
        names |= compile_selector(text).attributes()
    return sorted(names - CAPTURED)
