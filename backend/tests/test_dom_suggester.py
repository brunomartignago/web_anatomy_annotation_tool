"""The DOM suggester (roadmap 4.2a) on a small synthetic dom.json."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from annotool.models import PageFile, PageInfo, TaxonomyRef
from annotool.suggest import default_suggesters
from annotool.suggest.base import SuggestContext, run_suggesters
from annotool.suggest.dom import DomSuggester
from annotool.taxonomy import load_taxonomy

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy(REPO / "taxonomies" / "web-ui.yaml")


def el(i, parent, tag, bbox, **extra):
    return {"i": i, "parent": parent, "tag": tag, "bbox": bbox, "position": "static", **extra}


ELEMENTS = [
    el(0, None, "body", [0, 0, 1920, 3000]),
    el(1, 0, "header", [0, 0, 1920, 100]),
    el(2, 1, "nav", [0, 0, 1920, 100]),
    el(3, 2, "a", [20, 30, 80, 20], href=True, text_len=4, text_bbox=[22, 32, 70, 16]),
    el(4, 2, "a", [120, 30, 80, 20], href=True, text_len=5, text_bbox=[122, 32, 72, 16]),
    el(22, 2, "button", [1500, 30, 100, 40], text_len=7, text_bbox=[1510, 40, 80, 20]),
    el(5, 0, "main", [0, 100, 1920, 2700]),
    # A heading wrapper whose only box is a link: the link becomes a Heading.
    el(6, 5, "h2", [100, 200, 800, 40]),
    el(7, 6, "a", [100, 205, 500, 30], href=True, text_len=30, text_bbox=[100, 207, 480, 26]),
    # a > picture > img, all the same box: one Image·Link box.
    el(8, 5, "a", [100, 300, 400, 300], href=True),
    el(9, 8, "picture", [100, 300, 400, 300]),
    el(10, 9, "img", [100, 300, 400, 300]),
    # Plain text: the tight text box, not the full-width block.
    el(11, 5, "p", [100, 650, 800, 60], text_len=120, text_bbox=[100, 652, 780, 56]),
    el(12, 5, "span", [100, 720, 4, 4], text_len=1),  # under 6x6: dropped
    el(13, 5, "svg", [950, 200, 24, 24]),  # small svg: Icon
    el(14, 5, "svg", [950, 300, 100, 100]),  # too big for Icon
    el(15, 5, "article", [1000, 800, 400, 400]),
    el(16, 15, "p", [1010, 810, 380, 40], text_len=50, text_bbox=[1010, 812, 370, 36]),
    el(23, 5, "input", [1500, 700, 16, 16], input_type="checkbox"),
    # An ad slot wrapping one image: the image gets Ad.
    el(24, 5, "div", [1400, 1300, 300, 250], classes=["advert-slot"]),
    el(25, 24, "img", [1400, 1300, 300, 250]),
    el(17, 0, "footer", [0, 2800, 1920, 200]),
    el(18, 17, "a", [20, 2850, 100, 20], href=True, text_len=7, text_bbox=[22, 2852, 90, 16]),
    # A fixed cookie banner at the bottom of the first screen covers what's under it.
    el(19, 0, "div", [0, 980, 1920, 100], position="fixed"),
    el(20, 19, "p", [20, 1000, 600, 20], text_len=40, text_bbox=[20, 1000, 590, 20]),
    el(21, 5, "p", [100, 1010, 300, 20], text_len=30, text_bbox=[100, 1010, 290, 20]),
]


def write_dom(folder: Path, elements=ELEMENTS):
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "version": 1,
        "page": {"width": 1920, "height": 3000},
        "viewport": {"width": 1920, "height": 1080},
        "scroll": {"x": 0, "y": 0},
        "elements": elements,
    }
    (folder / "dom.json").write_text(json.dumps(snapshot), encoding="utf-8")
    return folder


def blank_page():
    return PageFile(
        taxonomy=TaxonomyRef(id="web-ui", version="1.0"),
        page=PageInfo(id="p", image="page.png", width=1920, height=3000),
        annotations=[],
    )


@pytest.fixture
def boxes(taxonomy, tmp_path):
    """Run the DOM suggester; the new boxes by the DOM index they came from."""
    folder = write_dom(tmp_path / "page")
    page, [report] = run_suggesters(
        blank_page(),
        [DomSuggester.from_taxonomy(taxonomy)],
        taxonomy=taxonomy,
        folder=folder,
        now=NOW,
    )
    assert report.error is None, report.error
    return {b.dom.index: b for b in page.annotations}


def test_which_elements_become_boxes(boxes):
    assert sorted(boxes) == [3, 4, 7, 10, 11, 13, 14, 16, 18, 20, 22, 23, 25]
    # 12 is tiny, 21 is under the cookie banner, wrappers (6, 8, 9, 24) are folded in.


def test_boxes_are_suggestions_from_the_dom(boxes):
    box = boxes[3]
    assert (box.kind, box.source, box.status) == ("element", "dom", "suggested")
    assert (box.dom.tag, box.dom.index) == ("a", 3)
    assert set(box.label_sources.values()) == {"dom"}


def test_links_in_a_header_nav(boxes):
    link = boxes[3]
    assert link.bbox == (20, 30, 80, 20)  # interactive: the element's own box
    assert link.labels == {
        "Form": "Typo",
        "Function": "Link",
        "Component": "Menu",
        "Taxonomy": "Header",
    }
    assert link.confidence == {"Form": 0.85, "Function": 0.85, "Component": 0.75, "Taxonomy": 0.8}
    assert boxes[22].labels["Function"] == "Button"


def test_a_heading_wrapper_passes_heading_to_its_only_link(boxes):
    heading = boxes[7]
    assert heading.labels["Function"] == "Heading"  # 0.95 from <h2> beats Link's 0.85
    assert heading.confidence["Function"] == 0.95
    assert heading.labels["Component"] == "Blank"  # no component ancestor: the YAML default
    assert heading.confidence["Component"] == 0.4
    assert "Taxonomy" not in heading.labels


def test_same_box_wrappers_collapse_into_one_box(boxes):
    image = boxes[10]
    assert image.bbox == (100, 300, 400, 300)
    assert (image.labels["Form"], image.labels["Function"]) == ("Image", "Link")
    ad = boxes[25]
    assert (ad.labels["Form"], ad.labels["Function"]) == ("Image", "Ad")


def test_text_uses_its_tight_box(boxes):
    text = boxes[11]
    assert text.bbox == (100, 652, 780, 56)
    assert (text.labels["Form"], text.labels["Function"]) == ("Typo", "Text")


def test_icons_need_to_be_small(boxes):
    assert boxes[13].labels["Form"] == "Icon"
    assert "Form" not in boxes[14].labels


def test_component_comes_from_the_nearest_ancestor(boxes):
    assert boxes[16].labels["Component"] == "Card"
    assert boxes[16].confidence["Component"] == 0.45


def test_controls_and_footer(boxes):
    assert boxes[23].labels["Function"] == "Checkbox"
    assert boxes[18].labels["Taxonomy"] == "Footer"
    assert boxes[20].labels["Function"] == "Text"  # the banner's own text is kept


def test_no_dom_json_means_no_proposals(taxonomy, tmp_path):
    suggester = DomSuggester.from_taxonomy(taxonomy)
    context = SuggestContext(page=blank_page(), taxonomy=taxonomy, folder=tmp_path)
    assert list(suggester.suggest(context)) == []
    context = SuggestContext(page=blank_page(), taxonomy=taxonomy, folder=None)
    assert list(suggester.suggest(context)) == []


def test_it_is_registered_and_a_second_run_adds_nothing(taxonomy, tmp_path):
    assert [s.id for s in default_suggesters(taxonomy)] == ["dom"]
    folder = write_dom(tmp_path / "page")
    suggesters = default_suggesters(taxonomy)
    once, _ = run_suggesters(blank_page(), suggesters, taxonomy=taxonomy, folder=folder, now=NOW)
    twice, [report] = run_suggesters(once, suggesters, taxonomy=taxonomy, folder=folder, now=NOW)
    assert twice == once and report.changed is False


def test_reports_hint_attributes_that_dom_json_does_not_capture(taxonomy):
    missing = DomSuggester.from_taxonomy(taxonomy).uncaptured
    assert "src" in missing and "data-ad-slot" in missing
