"""Migrate the legacy tkinter tool's JSON (v1 and v2) to schema v1.

Legacy format: `{"selections": [{"coords": [x0, y0, x1, y1], "Form": ..., "Function": ...,
"Component": ..., "Taxonomy": ..., "Area": ..., "expanded": ...}], "image": ...}`.

- v1 (`annotation_tool.py`) stores `expanded` UI state and has no `image` field. It didn't
  sort coordinates, so some boxes are inverted (AUDIT #13, #14).
- v2 (`annotation_tool_v2.py`) adds `image` and stores unlabeled attributes as "".

The migration sorts and clamps coordinates, converts corners to `[x, y, w, h]`, drops
`Area` and `expanded`, removes empty labels, assigns ULIDs, and refuses anything it
doesn't recognise rather than silently dropping it.
"""

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any

from annotool.ids import new_ulid
from annotool.models import Annotation, History, PageFile, PageInfo, TaxonomyRef, Viewport
from annotool.taxonomy import Taxonomy

LEGACY_ATTRIBUTES = ("Form", "Function", "Component", "Taxonomy")
DROPPED_FIELDS = {"Area", "expanded"}

# The legacy capture ran in Brazil and wrote naive local timestamps.
DEFAULT_TZ = timezone(timedelta(hours=-3))


class LegacyMigrationError(ValueError):
    """A legacy file contains something the migration can't convert safely."""


def selections_of(data: Any) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("selections"), list):
        return data["selections"]
    raise LegacyMigrationError("not a legacy annotation file: expected a 'selections' list")


def detect_format(data: Any) -> str:
    """'legacy-v1' or 'legacy-v2'. Only v2 writes the `image` field."""
    selections = selections_of(data)
    if isinstance(data, dict) and "image" in data:
        if any("expanded" in s for s in selections):
            return "legacy-v1"
        return "legacy-v2"
    return "legacy-v1"


def normalize_coords(coords: Any, width: int, height: int) -> tuple[float, float, float, float]:
    """Corner coords (any order) to `[x, y, w, h]`, clamped to the image."""
    if not isinstance(coords, list | tuple) or len(coords) != 4:
        raise LegacyMigrationError(f"expected 4 coords, got {coords!r}")
    x0, y0, x1, y1 = (float(c) for c in coords)
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    left, right = max(left, 0.0), min(right, float(width))
    top, bottom = max(top, 0.0), min(bottom, float(height))
    if right <= left or bottom <= top:
        raise LegacyMigrationError(f"box {coords!r} lies outside the {width}x{height} image")
    return (left, top, right - left, bottom - top)


def convert_selection(sel: dict, width: int, height: int, taxonomy: Taxonomy) -> Annotation:
    unexpected = set(sel) - {"coords", *LEGACY_ATTRIBUTES, *DROPPED_FIELDS}
    if unexpected:
        raise LegacyMigrationError(f"unexpected field(s) {sorted(unexpected)} in {sel!r}")

    labels: dict[str, str] = {}
    for attr in LEGACY_ATTRIBUTES:
        value = sel.get(attr) or ""
        if not value:
            continue
        known = [o.value for o in taxonomy.attribute(attr).options]
        if value not in known:
            raise LegacyMigrationError(f"{attr} value {value!r} is not in taxonomy {taxonomy.id}")
        labels[attr] = value

    complete = len(labels) == len(LEGACY_ATTRIBUTES)
    return Annotation(
        id=new_ulid(),
        kind="element",
        bbox=normalize_coords(sel.get("coords"), width, height),
        labels=labels,
        source="legacy",
        # Exports skip "suggested", so unfinished legacy boxes don't leak into results.
        status="accepted" if complete else "suggested",
        label_sources={attr: "legacy" for attr in labels} or None,
    )


def parse_offset(offset: str) -> tzinfo:
    """'-03:00' -> a fixed-offset timezone."""
    try:
        tz = datetime.fromisoformat(f"2000-01-01T00:00:00{offset}").tzinfo
    except ValueError as exc:
        raise ValueError(f"not a UTC offset like -03:00: {offset!r}") from exc
    if tz is None:
        raise ValueError(f"not a UTC offset like -03:00: {offset!r}")
    return tz


def _parse_size(value: Any) -> Viewport | None:
    """'1920x893' -> Viewport(1920, 893); anything else -> None."""
    if not value:
        return None
    try:
        width, height = (int(part) for part in str(value).lower().split("x"))
    except ValueError:
        return None
    return Viewport(width=width, height=height)


def _page_info(
    page_id: str, image: str, width: int, height: int, meta: dict | None, tz: tzinfo
) -> PageInfo:
    meta = meta or {}
    captured_at = None
    if meta.get("timestamp"):
        captured_at = datetime.fromisoformat(meta["timestamp"])
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=tz)
    # Width and height come from the PNG, never from the legacy metadata: stitched
    # captures are padded to whole viewports, so `full_page_size` is wrong (AUDIT #17).
    return PageInfo(
        id=page_id,
        url=meta.get("url"),
        title=meta.get("title"),
        image=image,
        width=width,
        height=height,
        viewport=_parse_size(meta.get("viewport_size")),
        captured_at=captured_at,
        locale=meta.get("language"),
    )


def migrate_legacy(
    files: list[Any],
    *,
    page_id: str,
    image: str,
    width: int,
    height: int,
    taxonomy: Taxonomy,
    meta: dict | None = None,
    tz: tzinfo = DEFAULT_TZ,
) -> PageFile:
    """Merge one or more legacy files for the same screenshot into one page file."""
    annotations: list[Annotation] = []
    formats: list[str] = []
    for data in files:
        fmt = detect_format(data)
        if fmt not in formats:
            formats.append(fmt)
        annotations += [
            convert_selection(sel, width, height, taxonomy) for sel in selections_of(data)
        ]
    return PageFile(
        taxonomy=TaxonomyRef(id=taxonomy.id, version=taxonomy.version),
        page=_page_info(page_id, image, width, height, meta, tz),
        annotations=annotations,
        history=History(migrated_from="+".join(sorted(formats))),
    )
