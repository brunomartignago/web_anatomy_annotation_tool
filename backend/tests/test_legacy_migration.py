import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from PIL import Image
from typer.testing import CliRunner

from annotool.cli import app
from annotool.io.migrations.legacy_v0 import (
    LegacyMigrationError,
    convert_selection,
    detect_format,
    migrate_legacy,
    normalize_coords,
    parse_offset,
)
from annotool.taxonomy import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = REPO_ROOT / "taxonomies" / "web-ui.yaml"
TAXONOMY = load_taxonomy(TAXONOMY_PATH)
SCHEMA = json.loads(
    (REPO_ROOT / "schema" / "annotation.v1.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)
FIXTURES = Path(__file__).parent / "fixtures"

LABELS = {"Form": "Typo", "Function": "Text", "Component": "Blank", "Taxonomy": "Column 0"}
BRAZIL = timezone(timedelta(hours=-3))


def v1_box(coords, **labels):
    return {"coords": coords, **LABELS, **labels, "Area": 1.0, "expanded": False}


def v2_box(coords, **labels):
    return {"coords": coords, **LABELS, **labels, "Area": 1.0}


def v1_file(*boxes):
    return {"selections": list(boxes)}


def v2_file(*boxes):
    return {"selections": list(boxes), "image": "page_full.png"}


def migrate(*files, meta=None, width=1000, height=2000):
    return migrate_legacy(
        list(files),
        page_id="page",
        image="page.png",
        width=width,
        height=height,
        taxonomy=TAXONOMY,
        meta=meta,
        tz=BRAZIL,
    )


# ── Format detection ─────────────────────────────────────────────────────────


def test_detects_v1_by_expanded_flag_or_missing_image():
    assert detect_format(v1_file(v1_box([0, 0, 10, 10]))) == "legacy-v1"
    assert detect_format({"selections": [v2_box([0, 0, 10, 10])]}) == "legacy-v1"


def test_detects_v2_by_image_field():
    assert detect_format(v2_file(v2_box([0, 0, 10, 10]))) == "legacy-v2"


def test_bare_list_is_treated_as_v1():
    assert detect_format([v1_box([0, 0, 10, 10])]) == "legacy-v1"


# ── Coordinates (AUDIT #13) ──────────────────────────────────────────────────


def test_corner_coords_become_xywh():
    assert normalize_coords([10, 20, 110, 50], 1000, 1000) == (10, 20, 100, 30)


def test_inverted_coords_are_normalized():
    assert normalize_coords([110, 50, 10, 20], 1000, 1000) == (10, 20, 100, 30)


def test_coords_are_clamped_to_the_image():
    # The CNN file has a box ending half a pixel below the image.
    assert normalize_coords([-5, 7990, 50, 8037.5], 1920, 8037) == (0, 7990, 50, 47)


def test_box_outside_the_image_is_an_error():
    with pytest.raises(LegacyMigrationError):
        normalize_coords([1100, 0, 1200, 10], 1000, 1000)


def test_wrong_number_of_coords_is_an_error():
    with pytest.raises(LegacyMigrationError):
        normalize_coords([0, 0, 10], 1000, 1000)


# ── Labels, status and dropped fields (AUDIT #14) ────────────────────────────


def test_complete_box_is_accepted_with_legacy_sources():
    ann = convert_selection(v1_box([0, 0, 10, 10]), 100, 100, TAXONOMY)
    assert ann.labels == LABELS
    assert ann.status == "accepted"
    assert ann.source == "legacy"
    assert ann.kind == "element"
    assert ann.label_sources == {attr: "legacy" for attr in LABELS}


def test_empty_labels_are_dropped_and_box_is_suggested():
    box = v2_box([0, 0, 10, 10], Function="", Component="", Taxonomy="")
    ann = convert_selection(box, 100, 100, TAXONOMY)
    assert ann.labels == {"Form": "Typo"}
    assert ann.status == "suggested"


def test_fully_empty_box_has_no_label_sources():
    box = v2_box([0, 0, 10, 10], Form="", Function="", Component="", Taxonomy="")
    ann = convert_selection(box, 100, 100, TAXONOMY)
    assert ann.labels == {}
    assert ann.label_sources is None


def test_area_and_expanded_are_not_carried_over():
    data = convert_selection(v1_box([0, 0, 10, 10]), 100, 100, TAXONOMY).model_dump()
    assert "Area" not in data and "expanded" not in data


def test_unexpected_field_is_an_error_not_silently_dropped():
    box = {**v2_box([0, 0, 10, 10]), "comment": "keep me"}
    with pytest.raises(LegacyMigrationError, match="comment"):
        convert_selection(box, 100, 100, TAXONOMY)


def test_unknown_label_value_is_an_error():
    box = v2_box([0, 0, 10, 10], Function="Hero")
    with pytest.raises(LegacyMigrationError, match="Hero"):
        convert_selection(box, 100, 100, TAXONOMY)


# ── Whole-page migration ─────────────────────────────────────────────────────


def test_merges_several_files_for_the_same_page():
    page = migrate(
        v1_file(v1_box([0, 0, 10, 10]), v1_box([20, 20, 10, 10])),
        v2_file(v2_box([50, 50, 60, 60])),
    )
    assert len(page.annotations) == 3
    assert page.history.migrated_from == "legacy-v1+legacy-v2"
    assert len({a.id for a in page.annotations}) == 3  # stable unique ids (AUDIT #15)


def test_page_info_comes_from_image_and_metadata():
    meta = {
        "url": "https://edition.cnn.com",
        "title": "CNN",
        "timestamp": "2025-06-09T09:28:51",
        "viewport_size": "1920x893",
        "screenshot_file": "edition_cnn_com.png",  # wrong name in legacy meta (AUDIT #18)
    }
    page = migrate(v1_file(v1_box([0, 0, 10, 10])), meta=meta, width=1920, height=8037)
    assert page.page.width == 1920 and page.page.height == 8037  # from the PNG (AUDIT #10)
    assert page.page.image == "page.png"
    assert page.page.url == "https://edition.cnn.com"
    assert page.page.captured_at == datetime(2025, 6, 9, 9, 28, 51, tzinfo=BRAZIL)
    assert (page.page.viewport.width, page.page.viewport.height) == (1920, 893)
    assert (page.taxonomy.id, page.taxonomy.version) == ("web-ui", "1.0")


def test_migrated_page_validates_against_schema():
    page = migrate(
        v1_file(v1_box([110, 50, 10, 20])),
        v2_file(v2_box([0, 0, 10, 10], Form="", Function="", Component="", Taxonomy="")),
        meta={"url": "https://example.com", "timestamp": "2025-06-09T09:28:51"},
    )
    VALIDATOR.validate(page.to_json_dict())


def test_parse_offset():
    assert parse_offset("-03:00") == BRAZIL
    assert parse_offset("+00:00") == UTC
    with pytest.raises(ValueError):
        parse_offset("Brazil")


# ── CLI end to end ───────────────────────────────────────────────────────────


@pytest.fixture
def legacy_page(tmp_path):
    image = tmp_path / "site_com_full.png"
    Image.new("RGB", (200, 300), "white").save(image)
    v1 = tmp_path / "site_com_full.json"
    v1.write_text(json.dumps(v1_file(v1_box([150, 250, 10, 10]))), encoding="utf-8")
    v2 = tmp_path / "site_com_full.autosave.json"
    v2.write_text(json.dumps(v2_file(v2_box([0, 0, 50, 50]))), encoding="utf-8")
    meta = tmp_path / "site_com.json"
    meta.write_text(
        json.dumps({"url": "https://site.com", "timestamp": "2025-06-09T09:00:00"}),
        encoding="utf-8",
    )
    return {"image": image, "files": [v1, v2], "meta": meta, "out": tmp_path / "out" / "site"}


def run_migrate(page, *extra):
    args = ["migrate", *map(str, page["files"]), "--image", str(page["image"])]
    args += ["--out", str(page["out"]), "--meta", str(page["meta"])]
    args += ["--taxonomy", str(TAXONOMY_PATH), *extra]
    return CliRunner().invoke(app, args)


def test_cli_writes_a_valid_page_folder(legacy_page):
    result = run_migrate(legacy_page)
    assert result.exit_code == 0, result.output
    out = legacy_page["out"]
    data = json.loads((out / "annotations.json").read_text(encoding="utf-8"))
    VALIDATOR.validate(data)
    assert data["page"]["id"] == "site_com"  # from the image name, without "_full"
    assert (data["page"]["width"], data["page"]["height"]) == (200, 300)
    assert len(data["annotations"]) == 2
    assert (out / "page.png").exists()
    assert "2 boxes" in result.output


def test_cli_refuses_to_overwrite_without_force(legacy_page):
    assert run_migrate(legacy_page).exit_code == 0
    assert run_migrate(legacy_page).exit_code != 0
    assert run_migrate(legacy_page, "--force").exit_code == 0


# ── Committed fixtures (migrated from the real legacy data) ──────────────────


@pytest.mark.parametrize(
    ("name", "boxes", "complete"),
    [("edition_cnn_com", 210, 210), ("stackoverflow_com", 1, 1)],
)
def test_committed_fixture_is_valid(name, boxes, complete):
    data = json.loads((FIXTURES / "legacy" / f"{name}.json").read_text(encoding="utf-8"))
    VALIDATOR.validate(data)
    assert len(data["annotations"]) == boxes
    assert sum(a["status"] == "accepted" for a in data["annotations"]) == complete
    for ann in data["annotations"]:
        for attr, value in ann["labels"].items():
            assert value in [o.value for o in TAXONOMY.attribute(attr).options]
