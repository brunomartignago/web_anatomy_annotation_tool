"""Pydantic models for one page's annotation file.

These mirror `schema/annotation.v1.schema.json`, which is the contract shared
with the frontend. `tests/test_models.py` checks field names, required fields
and enums against the schema, so a change to one without the other fails CI.

Coordinates are image pixels `[x, y, width, height]` with a top-left origin.
"""

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat

SCHEMA_VERSION = "1.0"

Kind = Literal["element", "section", "component"]
Source = Literal["human", "dom", "rule", "prior", "model", "llm", "legacy"]
Status = Literal["suggested", "accepted", "edited", "rejected"]
LabelSource = Literal[
    "human", "dom", "rule", "prior", "model", "llm", "legacy", "inherited", "preset"
]

# [x, y, width, height]: x and y >= 0, width and height > 0.
BBox = tuple[NonNegativeFloat, NonNegativeFloat, PositiveFloat, PositiveFloat]
LabelValue = Annotated[str, Field(min_length=1)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class _Model(BaseModel):
    # Every object in the schema has additionalProperties: false.
    model_config = ConfigDict(extra="forbid")


class TaxonomyRef(_Model):
    id: str
    version: str


class Viewport(_Model):
    width: int | None = None
    height: int | None = None


class PageInfo(_Model):
    id: str = Field(pattern=r"^[a-z0-9_\-]+$")
    url: str | None = None
    title: str | None = None
    category: str | None = None
    page_type: str | None = None
    image: str  # file name relative to the page folder
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    viewport: Viewport | None = None
    captured_at: AwareDatetime | None = None
    locale: str | None = None


class DomRef(_Model):
    """Link back to the captured DOM node, when the box came from the DOM."""

    index: int | None = None
    tag: str | None = None
    role: str | None = None
    selector: str | None = None


class Annotation(_Model):
    id: str  # ULID, never reused after delete
    kind: Kind
    bbox: BBox
    labels: dict[str, LabelValue]  # attribute id -> option value; missing = not labeled yet
    parent_id: str | None = None
    source: Source
    status: Status
    label_sources: dict[str, LabelSource] | None = None
    confidence: dict[str, Confidence] | None = None
    dom: DomRef | None = None
    note: str | None = None
    created_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None


class History(_Model):
    """Lightweight effort metrics for measuring click reduction."""

    actions: int | None = Field(default=None, ge=0)
    seconds_active: float | None = Field(default=None, ge=0)
    migrated_from: str | None = None


class PageFile(_Model):
    """The whole `annotations.json` for one page."""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    taxonomy: TaxonomyRef
    page: PageInfo
    annotations: list[Annotation]
    history: History | None = None

    def to_json_dict(self) -> dict[str, Any]:
        """JSON-ready dict. Unset optional fields are omitted rather than written as null."""
        return self.model_dump(mode="json", exclude_none=True)
