import copy
import json
import typing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from annotool.models import (
    Annotation,
    DomRef,
    History,
    LabelSource,
    PageFile,
    PageInfo,
    Source,
    Status,
    TaxonomyRef,
    Viewport,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (REPO_ROOT / "schema" / "annotation.v1.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)


def full_page_file() -> PageFile:
    """A file that uses every optional field at least once."""
    now = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    return PageFile(
        taxonomy=TaxonomyRef(id="web-ui", version="1.0"),
        page=PageInfo(
            id="edition_cnn_com",
            url="https://edition.cnn.com",
            title="CNN",
            category="News & Media",
            page_type="home",
            image="page.png",
            width=1920,
            height=8037,
            viewport=Viewport(width=1920, height=1080),
            captured_at=now,
            locale="en-US",
        ),
        annotations=[
            Annotation(
                id="01JA0000000000000000000000",
                kind="section",
                bbox=(0, 0, 1920, 250.5),
                labels={"Taxonomy": "Header"},
                source="human",
                status="accepted",
            ),
            Annotation(
                id="01JA0000000000000000000001",
                kind="element",
                bbox=(473.0, 2.48, 970.86, 250.78),
                labels={"Form": "Typo", "Function": "Link", "Taxonomy": "Header"},
                parent_id="01JA0000000000000000000000",
                source="dom",
                status="suggested",
                label_sources={"Form": "dom", "Function": "dom", "Taxonomy": "inherited"},
                confidence={"Form": 0.85, "Function": 0.85},
                dom=DomRef(index=42, tag="a", role="link", selector="header nav a"),
                note="logo link",
                created_at=now,
                updated_at=now,
            ),
        ],
        history=History(actions=3, seconds_active=12.5, migrated_from="legacy-v2"),
    )


def minimal_page_file() -> PageFile:
    return PageFile(
        taxonomy=TaxonomyRef(id="web-ui", version="1.0"),
        page=PageInfo(id="p", image="page.png", width=10, height=10),
        annotations=[],
    )


# ── Model output validates against the JSON Schema ───────────────────────────


def test_schema_itself_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("factory", [full_page_file, minimal_page_file])
def test_model_output_validates_against_schema(factory):
    VALIDATOR.validate(factory().to_json_dict())


def test_round_trip_through_json():
    original = full_page_file()
    restored = PageFile.model_validate_json(json.dumps(original.to_json_dict()))
    assert restored == original


def test_optional_fields_are_omitted_not_null():
    data = minimal_page_file().to_json_dict()
    assert "history" not in data
    assert set(data["page"]) == {"id", "image", "width", "height"}


def test_bbox_is_written_as_a_four_number_list():
    data = full_page_file().to_json_dict()
    assert data["annotations"][0]["bbox"] == [0, 0, 1920, 250.5]


# ── The models mirror the schema (catches drift in either direction) ─────────


def _schema_at(path: str) -> dict:
    node = SCHEMA
    for part in path.split("/"):
        if part:
            node = node[part]
    return node


@pytest.mark.parametrize(
    ("model", "schema_path"),
    [
        (PageFile, ""),
        (TaxonomyRef, "properties/taxonomy"),
        (PageInfo, "properties/page"),
        (Viewport, "properties/page/properties/viewport"),
        (History, "properties/history"),
        (Annotation, "$defs/annotation"),
        (DomRef, "$defs/annotation/properties/dom"),
    ],
)
def test_model_fields_match_schema(model: type[BaseModel], schema_path: str):
    schema = _schema_at(schema_path)
    assert set(model.model_fields) == set(schema["properties"])
    required = {name for name, field in model.model_fields.items() if field.is_required()}
    # schema_version has a default in the model, but is required in the file.
    assert required | ({"schema_version"} if model is PageFile else set()) == set(
        schema.get("required", [])
    )


def test_bbox_schema_keeps_item_type_for_typescript_generation():
    # json-schema-to-typescript ignores prefixItems; without `items` the frontend gets unknown[].
    assert _schema_at("$defs/annotation/properties/bbox")["items"] == {"type": "number"}


@pytest.mark.parametrize(
    ("literal", "schema_path"),
    [
        (typing.get_args(Annotation.model_fields["kind"].annotation), "properties/kind"),
        (typing.get_args(Source), "properties/source"),
        (typing.get_args(Status), "properties/status"),
        (typing.get_args(LabelSource), "properties/label_sources/additionalProperties"),
    ],
)
def test_enums_match_schema(literal, schema_path):
    assert set(literal) == set(_schema_at(f"$defs/annotation/{schema_path}")["enum"])


# ── Invalid data is rejected by both the models and the schema ───────────────


def _set(path: str, value):
    def mutate(data: dict) -> None:
        *parents, last = path.split(".")
        node = data
        for part in parents:
            node = node[int(part)] if part.isdigit() else node[part]
        node[int(last) if last.isdigit() else last] = value

    return mutate


INVALID = {
    "negative x": _set("annotations.0.bbox.0", -1),
    "zero width": _set("annotations.0.bbox.2", 0),
    "bbox with 3 numbers": _set("annotations.0.bbox", [0, 0, 10]),
    "unknown kind": _set("annotations.0.kind", "group"),
    "unknown source": _set("annotations.0.source", "magic"),
    "unknown status": _set("annotations.0.status", "done"),
    "empty label value": _set("annotations.0.labels.Form", ""),
    "confidence above 1": _set("annotations.1.confidence.Form", 1.5),
    "uppercase page id": _set("page.id", "CNN"),
    "zero page width": _set("page.width", 0),
    "wrong schema version": _set("schema_version", "2.0"),
    "unknown top-level field": _set("expanded", False),
    "unknown annotation field": _set("annotations.0.Area", 12.5),
    "negative action count": _set("history.actions", -1),
}


@pytest.mark.parametrize("mutate", INVALID.values(), ids=INVALID.keys())
def test_invalid_data_is_rejected_by_model_and_schema(mutate):
    data = copy.deepcopy(full_page_file().to_json_dict())
    mutate(data)
    assert not VALIDATOR.is_valid(data)
    with pytest.raises(ValidationError):
        PageFile.model_validate(data)


def test_timestamps_without_timezone_are_rejected():
    # JSON Schema "date-time" (RFC 3339) requires an offset; naive times are ambiguous.
    data = full_page_file().to_json_dict()
    data["page"]["captured_at"] = "2025-06-09T09:34:16"
    with pytest.raises(ValidationError):
        PageFile.model_validate(data)
