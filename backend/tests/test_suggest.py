"""Suggester framework (roadmap 4.1): proposals, the merge policy and the pipeline."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from annotool.models import Annotation, DomRef, PageFile, PageInfo, TaxonomyRef
from annotool.suggest.base import (
    AddBox,
    LabelBox,
    SuggestContext,
    merge,
    run_suggesters,
)
from annotool.taxonomy import load_taxonomy

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy(REPO / "taxonomies" / "web-ui.yaml")


def _box(box_id, bbox=(0, 0, 100, 50), labels=None, **extra):
    fields = {"kind": "element", "source": "human", "status": "accepted", **extra}
    return Annotation(id=box_id, bbox=bbox, labels=labels or {}, **fields)


def _page(*boxes):
    return PageFile(
        taxonomy=TaxonomyRef(id="web-ui", version="1.0"),
        page=PageInfo(id="p", image="page.png", width=1920, height=5000),
        annotations=list(boxes),
    )


def _get(page, box_id):
    return next(b for b in page.annotations if b.id == box_id)


# ── Adding boxes ──


def test_a_new_box_is_a_suggestion_with_its_sources_and_confidence(taxonomy):
    proposal = AddBox(
        bbox=(10, 20, 300, 40),
        labels={"Form": "Typo", "Function": "Heading"},
        confidence={"Form": 0.9, "Function": 0.7},
        dom=DomRef(index=12, tag="h2"),
    )
    page, report = merge(_page(), [proposal], "dom", taxonomy, NOW)
    [box] = page.annotations
    assert len(box.id) == 26  # a ULID
    assert (box.kind, box.source, box.status) == ("element", "dom", "suggested")
    assert box.bbox == (10, 20, 300, 40)
    assert box.labels == {"Form": "Typo", "Function": "Heading"}
    assert box.label_sources == {"Form": "dom", "Function": "dom"}
    assert box.confidence == {"Form": 0.9, "Function": 0.7}
    assert box.dom == DomRef(index=12, tag="h2")
    assert box.created_at == NOW
    assert (report.boxes_added, report.labels_set) == (1, 2)


def test_a_box_matching_an_existing_one_labels_it_instead_of_duplicating(taxonomy):
    existing = _box(
        "a",
        bbox=(10, 20, 300, 40),
        source="legacy",
        labels={"Form": "Typo"},
        label_sources={"Form": "legacy"},
    )
    proposal = AddBox(
        bbox=(11, 20, 299, 41),
        labels={"Function": "Link"},
        confidence={"Function": 0.8},
        dom=DomRef(index=3),
    )
    page, report = merge(_page(existing), [proposal], "dom", taxonomy, NOW)
    [box] = page.annotations
    assert box.id == "a"
    assert box.labels == {"Form": "Typo", "Function": "Link"}
    assert box.label_sources == {"Form": "legacy", "Function": "dom"}
    assert box.dom == DomRef(index=3)  # the DOM link is filled in when missing
    assert (report.boxes_added, report.boxes_matched) == (0, 1)


def test_a_box_of_another_kind_is_not_a_match(taxonomy):
    section = _box("sec", bbox=(0, 0, 1920, 400), kind="section")
    page, report = merge(_page(section), [AddBox(bbox=(0, 0, 1920, 400))], "rule", taxonomy, NOW)
    assert len(page.annotations) == 2 and report.boxes_added == 1


def test_a_box_the_person_rejected_is_not_proposed_again(taxonomy):
    rejected = _box("gone", bbox=(10, 20, 300, 40), status="rejected", source="dom")
    proposals = [
        AddBox(bbox=(10, 20, 300, 40), labels={"Form": "Typo"}, confidence={"Form": 1}),
        LabelBox(box_id="gone", labels={"Form": "Image"}, confidence={"Form": 1}),
    ]
    page, report = merge(_page(rejected), proposals, "dom", taxonomy, NOW)
    assert page.annotations == [rejected]
    assert report.skipped_rejected == 2


# ── Labels: humans always win ──


@pytest.mark.parametrize("source", ["human", "preset", "legacy", "inherited", None])
def test_a_human_label_is_never_overwritten(taxonomy, source):
    sources = {"Form": source} if source else None
    box = _box("a", labels={"Form": "Typo"}, label_sources=sources)
    proposal = LabelBox(
        box_id="a",
        labels={"Form": "Image", "Function": "Text"},
        confidence={"Form": 1.0, "Function": 0.6},
    )
    page, report = merge(_page(box), [proposal], "rule", taxonomy, NOW)
    merged = _get(page, "a")
    assert merged.labels == {"Form": "Typo", "Function": "Text"}  # the empty one is filled
    assert (merged.label_sources or {}).get("Function") == "rule"
    assert merged.confidence == {"Function": 0.6}
    assert merged.status == "accepted"  # a reviewed box stays reviewed
    assert (report.kept_human, report.labels_set) == (1, 1)


def test_between_suggesters_higher_confidence_wins_and_ties_go_to_the_later(taxonomy):
    def dom_box():
        return _box(
            "a",
            source="dom",
            status="suggested",
            labels={"Form": "Typo"},
            label_sources={"Form": "dom"},
            confidence={"Form": 0.6},
        )

    def propose(confidence):
        return [LabelBox(box_id="a", labels={"Form": "Image"}, confidence={"Form": confidence})]

    higher, _ = merge(_page(dom_box()), propose(0.7), "rule", taxonomy, NOW)
    assert _get(higher, "a").labels["Form"] == "Image"
    assert _get(higher, "a").label_sources == {"Form": "rule"}
    assert _get(higher, "a").confidence == {"Form": 0.7}
    assert _get(higher, "a").status == "suggested"

    lower, report = merge(_page(dom_box()), propose(0.5), "rule", taxonomy, NOW)
    assert _get(lower, "a").labels["Form"] == "Typo"
    assert report.kept_better == 1

    tie, _ = merge(_page(dom_box()), propose(0.6), "rule", taxonomy, NOW)
    assert _get(tie, "a").labels["Form"] == "Image"


def test_a_machine_label_without_confidence_counts_as_zero(taxonomy):
    box = _box(
        "a",
        source="dom",
        status="suggested",
        labels={"Form": "Typo"},
        label_sources={"Form": "dom"},
    )
    page, _ = merge(
        _page(box), [LabelBox(box_id="a", labels={"Form": "Image"})], "rule", taxonomy, NOW
    )
    assert _get(page, "a").labels["Form"] == "Image"


def test_values_must_be_active_taxonomy_options(taxonomy):
    proposals = [
        LabelBox(
            box_id="a",
            labels={
                "Form": "Hologram",
                "Colour": "Red",
                "Taxonomy": "Column 5",
                "Function": "Link",
            },
        ),
        LabelBox(box_id="missing", labels={"Form": "Typo"}),
    ]
    page, report = merge(_page(_box("a")), proposals, "rule", taxonomy, NOW)
    assert _get(page, "a").labels == {"Function": "Link"}
    assert len(report.dropped) == 4
    assert any("Column 5" in d for d in report.dropped)  # proposed values aren't suggested
    assert any("missing" in d for d in report.dropped)


def test_changes_stamp_updated_at_and_no_change_returns_the_page_untouched(taxonomy):
    page = _page(_box("a", labels={"Form": "Typo"}, label_sources={"Form": "human"}))
    same, report = merge(
        page, [LabelBox(box_id="a", labels={"Form": "Image"})], "rule", taxonomy, NOW
    )
    assert same == page and report.changed is False
    changed, report = merge(
        page, [LabelBox(box_id="a", labels={"Function": "Text"})], "rule", taxonomy, NOW
    )
    assert _get(changed, "a").updated_at == NOW and report.changed is True
    assert page.annotations[0].labels == {"Form": "Typo"}  # the input is not modified


# ── The pipeline ──


class _Fake:
    def __init__(self, suggester_id, make):
        self.id = suggester_id
        self._make = make

    def suggest(self, context: SuggestContext):
        return self._make(context)


def test_suggesters_run_in_order_and_each_sees_the_previous_result(taxonomy):
    adds = _Fake("dom", lambda ctx: [AddBox(bbox=(0, 0, 200, 80), labels={"Form": "Typo"})])

    def label_new_boxes(ctx):
        return [LabelBox(box_id=b.id, labels={"Taxonomy": "Header"}) for b in ctx.page.annotations]

    labels = _Fake("rule", label_new_boxes)

    def crash(ctx):
        raise RuntimeError("boom")

    page, reports = run_suggesters(
        _page(), [adds, labels, _Fake("prior", crash)], taxonomy=taxonomy, now=NOW
    )
    [box] = page.annotations
    assert box.labels == {"Form": "Typo", "Taxonomy": "Header"}
    assert box.label_sources == {"Form": "dom", "Taxonomy": "rule"}
    assert [r.suggester for r in reports] == ["dom", "rule", "prior"]
    assert reports[2].error == "RuntimeError: boom"  # one failure doesn't stop the others


def test_running_twice_changes_nothing_the_second_time(taxonomy):
    adds = _Fake(
        "dom",
        lambda ctx: [
            AddBox(bbox=(0, 0, 200, 80), labels={"Form": "Typo"}, confidence={"Form": 0.9})
        ],
    )
    once, _ = run_suggesters(_page(), [adds], taxonomy=taxonomy, now=NOW)
    twice, reports = run_suggesters(once, [adds], taxonomy=taxonomy, now=NOW)
    assert twice == once and reports[0].changed is False


def test_a_suggester_needs_a_machine_source_id(taxonomy):
    page, [report] = run_suggesters(
        _page(), [_Fake("human", lambda ctx: [])], taxonomy=taxonomy, now=NOW
    )
    assert "not a suggester source" in report.error
