"""The small CSS selector matcher used by dom_hints (roadmap 4.2a)."""

import pytest

from annotool.capture.dom import DomElement
from annotool.suggest.selectors import SelectorError, compile_selector, uncaptured_attributes


def el(i, tag, parent=None, **extra):
    return DomElement(i=i, parent=parent, tag=tag, bbox=(0, 0, 10, 10), position="static", **extra)


# nav[aria-label=Breadcrumb] > ol > li > a.crumb-link
NAV = el(0, "nav", aria_label="Breadcrumb")
OL = el(1, "ol", parent=0)
LI = el(2, "li", parent=1)
LINK = el(3, "a", parent=2, href=True, classes=["crumb-link", "x"])
TREE = [NAV, OL, LI, LINK]


def matches(selector, element, elements=TREE):
    by_index = {e.i: e for e in elements}
    return compile_selector(selector).matches(element, by_index)


@pytest.mark.parametrize(
    ("selector", "element", "expected"),
    [
        ("a", LINK, True),
        ("A", LINK, True),  # tags ignore case
        ("li,a", LINK, True),
        ("p,span", LINK, False),
        ("a[href]", LINK, True),
        ("li[href]", LI, False),
        ("[class*=crumb]", LINK, True),
        ("[class*=card]", LINK, False),
        ("[class^=crumb]", LINK, True),
        ("[aria-label*=readcrumb] *", LINK, True),  # descendant of the breadcrumb nav
        ("[aria-label*=readcrumb] *", NAV, False),  # but not the nav itself
        ("nav li a", LINK, True),
        ("nav li a", LI, False),
        ("ol nav a", LINK, False),  # ancestors must appear in order
        ("*", NAV, True),
    ],
)
def test_matching(selector, element, expected):
    assert matches(selector, element) is expected


def test_attributes_from_dom_fields():
    checkbox = el(0, "input", input_type="checkbox")
    text = el(1, "input", input_type="text")
    banner = el(2, "div", role="banner", id="ad-top", bg_image=True)
    elements = [checkbox, text, banner]
    assert matches("input[type=checkbox],[role=checkbox]", checkbox, elements)
    assert matches("input[type=text]", text, elements)
    assert not matches("input[type=checkbox]", text, elements)
    assert matches("[role=banner]", banner, elements)
    assert matches("[id^=ad-]", banner, elements)
    assert matches("[style*=background-image]", banner, elements)
    assert matches('[role="banner"]', banner, elements)  # quoted values


def test_not():
    plain = el(0, "input")  # dom_extract records a missing type as "text"
    assert matches("input:not([type=checkbox])", plain, [plain])
    assert not matches("input:not([type])", el(1, "input", input_type="text"), [plain])


def test_attributes_that_are_not_captured_never_match_and_are_reported():
    frame = el(0, "iframe")
    assert not matches("iframe[src*=doubleclick]", frame, [frame])
    assert matches("iframe[src*=doubleclick],iframe", frame, [frame])
    selectors = ["iframe[src*=doubleclick],[data-ad-slot]", "[aria-haspopup=listbox]", "a[href]"]
    assert uncaptured_attributes(selectors) == ["aria-haspopup", "data-ad-slot", "src"]


@pytest.mark.parametrize("bad", ["", "a >", "a > b", "[href", "a:hover", "a,,b", "[x~=y]"])
def test_unsupported_selectors_fail_loudly(bad):
    with pytest.raises(SelectorError):
        compile_selector(bad)
