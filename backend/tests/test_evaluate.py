"""Evaluating suggestions against hand-made boxes (roadmap 4.2a)."""

import json
import shutil

import pytest
from typer.testing import CliRunner

from annotool.cli import app
from annotool.models import Annotation
from annotool.suggest.evaluate import evaluate, ground_truth, summarize

ATTRS = ["Form", "Function", "Component", "Taxonomy"]


def box(box_id, bbox, labels=None, **extra):
    fields = {"kind": "element", "source": "human", "status": "accepted", **extra}
    return Annotation(id=box_id, bbox=bbox, labels=labels or {}, **fields)


def test_ground_truth_is_hand_made_element_boxes():
    boxes = [
        box("h", (0, 0, 10, 10)),
        box("legacy", (0, 0, 10, 10), source="legacy", status="edited"),
        box("sug", (0, 0, 10, 10), source="dom", status="suggested"),
        box("acc", (0, 0, 10, 10), source="dom", status="accepted"),  # biased by the suggester
        box("rej", (0, 0, 10, 10), status="rejected"),
        box("sec", (0, 0, 10, 10), kind="section"),
    ]
    assert [b.id for b in ground_truth(boxes)] == ["h", "legacy"]


def test_matching_recall_precision_and_attribute_accuracy():
    truth = [
        box("t1", (0, 0, 100, 50), {"Form": "Typo", "Function": "Heading", "Component": "Blank"}),
        box("t2", (0, 100, 100, 50), {"Form": "Image", "Function": "Link"}),
        box("t3", (500, 500, 100, 100), {"Form": "Icon"}),  # never found
    ]
    proposed = [
        box("p1", (2, 0, 100, 50), {"Form": "Typo", "Function": "Link", "Component": "Blank"}),
        box("p2", (0, 110, 100, 50), {"Form": "Image"}),  # IoU 0.67 with t2
        box("p3", (0, 0, 98, 52), {"Form": "Typo"}),  # also overlaps t1, but t1 is taken
        box("p4", (900, 900, 10, 10), {}),
    ]
    result = evaluate(truth, proposed, ATTRS)
    assert result.truth == 3 and result.proposed == 4 and result.matched == 2
    assert result.recall == pytest.approx(2 / 3)
    assert result.precision == pytest.approx(2 / 4)
    assert result.pairs == [("t1", "p1"), ("t2", "p2")]  # best IoU first, one to one
    form = result.attributes["Form"]
    assert (form.labeled, form.suggested, form.correct) == (2, 2, 2)
    function = result.attributes["Function"]
    assert (function.labeled, function.suggested, function.correct) == (2, 1, 0)
    assert function.accuracy == 0.0 and function.coverage == 0.5
    assert result.confusion["Function"] == {("Heading", "Link"): 1, ("Link", None): 1}


def test_pages_add_up():
    one = evaluate(
        [box("t", (0, 0, 10, 10), {"Form": "Typo"})],
        [box("p", (0, 0, 10, 10), {"Form": "Typo"})],
        ATTRS,
    )
    two = evaluate([box("t", (0, 0, 10, 10), {"Form": "Icon"})], [], ATTRS)
    total = summarize([one, two])
    assert (total.truth, total.matched, total.recall) == (2, 1, 0.5)
    assert total.attributes["Form"].correct == 1


def test_empty_pages_have_no_ratios():
    result = evaluate([], [], ATTRS)
    assert result.recall is None and result.precision is None
    assert result.attributes["Form"].accuracy is None


# ── annotool eval ──


def test_eval_cli(tmp_path):
    from test_dom_suggester import ELEMENTS, write_dom

    folder = write_dom(tmp_path / "projects" / "demo" / "pages" / "news_page")
    truth = {
        "schema_version": "1.0",
        "taxonomy": {"id": "web-ui", "version": "1.0"},
        "page": {"id": "news_page", "image": "page.png", "width": 1920, "height": 3000},
        "annotations": [
            json.loads(
                box(
                    "h1", (100, 205, 500, 30), {"Form": "Typo", "Function": "Heading"}
                ).model_dump_json(exclude_none=True)
            ),
            json.loads(
                box("h2", (1700, 2000, 100, 100), {"Form": "Icon"}).model_dump_json(
                    exclude_none=True
                )
            ),
        ],
    }
    (folder / "annotations.json").write_text(json.dumps(truth), encoding="utf-8")
    assert ELEMENTS  # the same synthetic DOM as the suggester tests
    result = CliRunner().invoke(app, ["eval", "demo", "--data-dir", str(tmp_path), "--markdown"])
    assert result.exit_code == 0, result.output
    assert "news_page" in result.output
    assert "| Box recall (IoU ≥ 0.5) | 1/2 (50%) |" in result.output
    assert "| Function | 1/1 (100%) | 1/1 (100%) |" in result.output
    shutil.rmtree(tmp_path / "projects")


def test_eval_cli_without_labeled_pages(tmp_path):
    (tmp_path / "projects" / "demo" / "pages").mkdir(parents=True)
    result = CliRunner().invoke(app, ["eval", "demo", "--data-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "no page" in result.output.lower()
