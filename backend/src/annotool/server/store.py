"""Read and write a project's page folders for the server.

A page folder may hold `annotations.json` (schema v1), `meta.json` (from `capture`),
`page.png` and `dom.json`. Captured pages have no `annotations.json` until the first save:
they are listed from `meta.json` with zero progress, and loading one builds an empty
`PageFile` in memory.

Saves are guarded by an ETag (a hash of the file's bytes). The client sends the ETag it
loaded in `If-Match`. If the file changed since (another tab, a batch suggester run), the
save is refused instead of silently overwriting newer work.
"""

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from annotool.images import image_size
from annotool.models import PageFile, PageInfo, TaxonomyRef, Viewport
from annotool.project import page_dir, project_dir, write_json_atomic
from annotool.server.tiles import strip_count
from annotool.taxonomy import Taxonomy

ANNOTATIONS_NAME = "annotations.json"
META_NAME = "meta.json"
DOM_NAME = "dom.json"
IMAGE_NAME = "page.png"

# The ETag of a page that has no annotations.json yet. Never equal to a content hash.
EMPTY_ETAG = '"empty"'
_PAGE_ID = re.compile(r"^[a-z0-9_\-]+$")

_locks: dict[Path, threading.Lock] = {}
_locks_guard = threading.Lock()


class PageNotFound(LookupError):
    """No such project or page, or the page has nothing to annotate (no screenshot)."""


class StaleWrite(Exception):
    """`If-Match` doesn't match the file on disk: someone saved in between."""

    def __init__(self, current_etag: str):
        self.current_etag = current_etag
        super().__init__(f"annotations changed on disk (now {current_etag})")


class InvalidPage(ValueError):
    """The page file is valid JSON Schema but inconsistent with the URL or the taxonomy."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def etag_for(data: bytes | None) -> str:
    if data is None:
        return EMPTY_ETAG
    return f'"{hashlib.sha256(data).hexdigest()[:20]}"'


def etag_matches(if_match: str, current: str, *, exists: bool) -> bool:
    """RFC 9110 If-Match: `*` matches any existing file; otherwise one of the listed tags."""
    if if_match.strip() == "*":
        return exists
    tags = [t.strip().removeprefix("W/") for t in if_match.split(",")]
    return current in tags


# ── Progress ──

Completeness = Literal["empty", "partial", "complete"]


class Progress(BaseModel):
    """Box counts for one page. Rejected boxes are left out of every count."""

    boxes: int = 0
    empty: int = 0  # no attribute labeled
    partial: int = 0
    complete: int = 0  # every taxonomy attribute labeled
    suggested: int = 0  # still waiting for review (status `suggested`)
    labeled: dict[str, int] = {}  # attribute id -> boxes that have it


def completeness(labels: dict[str, str], attribute_ids: list[str]) -> Completeness:
    done = sum(1 for a in attribute_ids if labels.get(a))
    if done == 0:
        return "empty"
    return "complete" if done == len(attribute_ids) else "partial"


def page_progress(page: PageFile | None, attribute_ids: list[str]) -> Progress:
    progress = Progress(labeled=dict.fromkeys(attribute_ids, 0))
    for box in page.annotations if page else []:
        if box.status == "rejected":
            continue
        progress.boxes += 1
        state = completeness(box.labels, attribute_ids)
        setattr(progress, state, getattr(progress, state) + 1)
        progress.suggested += box.status == "suggested"
        for a in attribute_ids:
            progress.labeled[a] += bool(box.labels.get(a))
    return progress


# ── API shapes ──


class ProjectSummary(BaseModel):
    name: str
    pages: int


class PageSummary(BaseModel):
    """One row of the page queue."""

    id: str
    url: str | None = None
    title: str | None = None
    category: str | None = None
    page_type: str | None = None
    width: int | None = None
    height: int | None = None
    blocked: bool = False
    blocked_reasons: list[str] = []
    has_annotations: bool = False
    has_image: bool = False
    has_dom: bool = False
    strips: int = 0
    progress: Progress
    error: str | None = None  # the page's files couldn't be read


@dataclass
class LoadedPage:
    page: PageFile
    etag: str
    meta: dict[str, Any] | None
    has_dom: bool
    folder: Path


# ── Store ──


def _lock_for(path: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(path.resolve(), threading.Lock())


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return data


def _short_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return f"{exc.error_count()} validation error(s), first: {exc.errors()[0]['msg']}"
    return str(exc).splitlines()[0] if str(exc) else type(exc).__name__


class PageStore:
    def __init__(self, data_dir: Path, taxonomy: Taxonomy):
        self.data_dir = Path(data_dir)
        self.taxonomy = taxonomy
        self.attribute_ids = [a.id for a in taxonomy.attributes]

    # Paths

    def _project(self, project: str) -> Path:
        try:
            folder = project_dir(self.data_dir, project)
        except ValueError as exc:
            raise PageNotFound(str(exc)) from exc
        if not folder.is_dir():
            raise PageNotFound(f"no project {project!r} in {self.data_dir / 'projects'}")
        return folder

    def page_folder(self, project: str, page_id: str) -> Path:
        self._project(project)
        if not _PAGE_ID.match(page_id):
            raise PageNotFound(f"invalid page id {page_id!r}")
        return page_dir(self.data_dir, project, page_id)

    def _page_ids(self, project: str) -> list[str]:
        pages = self._project(project) / "pages"
        if not pages.is_dir():
            return []
        return sorted(
            p.name
            for p in pages.iterdir()
            if p.is_dir()
            and _PAGE_ID.match(p.name)
            and ((p / ANNOTATIONS_NAME).exists() or (p / META_NAME).exists())
        )

    # Reading

    def projects(self) -> list[ProjectSummary]:
        root = self.data_dir / "projects"
        if not root.is_dir():
            return []
        return [
            ProjectSummary(name=p.name, pages=len(self._page_ids(p.name)))
            for p in sorted(root.iterdir())
            if p.is_dir() and not p.name.startswith(".")
        ]

    def list_pages(self, project: str) -> list[PageSummary]:
        return [self._summary(project, page_id) for page_id in self._page_ids(project)]

    def _summary(self, project: str, page_id: str) -> PageSummary:
        folder = page_dir(self.data_dir, project, page_id)
        summary = PageSummary(
            id=page_id,
            has_image=(folder / IMAGE_NAME).exists(),
            has_dom=(folder / DOM_NAME).exists(),
            progress=page_progress(None, self.attribute_ids),
        )
        try:
            meta = _read_json(folder / META_NAME)
            raw = folder / ANNOTATIONS_NAME
            page = PageFile.model_validate_json(raw.read_bytes()) if raw.exists() else None
        except (OSError, ValueError) as exc:
            summary.error = _short_error(exc)
            return summary
        if meta:
            summary.url = meta.get("final_url") or meta.get("url")
            summary.title = meta.get("title")
            summary.category = meta.get("category")
            summary.page_type = meta.get("page_type")
            summary.width, summary.height = meta.get("width"), meta.get("height")
            summary.blocked = bool(meta.get("blocked"))
            summary.blocked_reasons = list(meta.get("blocked_reasons") or [])
        if page:
            info = page.page
            summary.url = info.url or summary.url
            summary.title = info.title or summary.title
            summary.category = info.category or summary.category
            summary.page_type = info.page_type or summary.page_type
            summary.width, summary.height = info.width, info.height
            summary.has_annotations = True
            summary.progress = page_progress(page, self.attribute_ids)
        if summary.has_image and summary.height:
            summary.strips = strip_count(summary.height)
        return summary

    def load(self, project: str, page_id: str) -> LoadedPage:
        folder = self.page_folder(project, page_id)
        meta = _read_json(folder / META_NAME)
        raw_path = folder / ANNOTATIONS_NAME
        raw = raw_path.read_bytes() if raw_path.exists() else None
        if raw is not None:
            page = PageFile.model_validate_json(raw)
        elif (folder / IMAGE_NAME).exists():
            page = self._empty_page(page_id, folder, meta or {})
        else:
            raise PageNotFound(f"page {page_id!r} has no {IMAGE_NAME} to annotate")
        return LoadedPage(
            page=page,
            etag=etag_for(raw),
            meta=meta,
            has_dom=(folder / DOM_NAME).exists(),
            folder=folder,
        )

    def _empty_page(self, page_id: str, folder: Path, meta: dict[str, Any]) -> PageFile:
        """An annotation file for a page that was captured but never saved."""
        width, height = meta.get("width"), meta.get("height")
        if not (isinstance(width, int) and isinstance(height, int)):
            width, height = image_size(folder / IMAGE_NAME)
        viewport = meta.get("viewport")
        return PageFile(
            taxonomy=TaxonomyRef(id=self.taxonomy.id, version=self.taxonomy.version),
            page=PageInfo(
                id=page_id,
                # final_url: the address the screenshot actually shows (after redirects).
                url=meta.get("final_url") or meta.get("url"),
                title=meta.get("title"),
                category=meta.get("category"),
                page_type=meta.get("page_type"),
                image=IMAGE_NAME,
                width=width,
                height=height,
                viewport=Viewport.model_validate(viewport) if viewport else None,
                captured_at=meta.get("captured_at"),
                locale=meta.get("locale"),
            ),
            annotations=[],
        )

    # Writing

    def check(self, page_id: str, page: PageFile) -> list[str]:
        """Problems that the JSON Schema can't catch: URL/page mismatch and taxonomy values."""
        errors: list[str] = []
        if page.page.id != page_id:
            errors.append(f"page.id {page.page.id!r} doesn't match the URL ({page_id!r})")
        if page.taxonomy.id != self.taxonomy.id:
            errors.append(
                f"taxonomy {page.taxonomy.id!r} isn't the one being served ({self.taxonomy.id!r})"
            )
        attributes = {a.id: a for a in self.taxonomy.attributes}
        seen: set[str] = set()
        for n, box in enumerate(page.annotations):
            where = f"annotations[{n}] ({box.id})"
            if box.id in seen:
                errors.append(f"{where}: duplicate annotation id")
            seen.add(box.id)
            for attr_id, value in box.labels.items():
                attr = attributes.get(attr_id)
                if attr is None:
                    errors.append(f"{where}: unknown attribute {attr_id!r}")
                elif value not in {o.value for o in attr.options}:
                    errors.append(f"{where}: {attr_id} value {value!r} is not an option")
            for field in ("label_sources", "confidence"):
                for attr_id in getattr(box, field) or {}:
                    if attr_id not in attributes:
                        errors.append(f"{where}: {field} has unknown attribute {attr_id!r}")
        return errors

    def save(self, project: str, page_id: str, page: PageFile, *, if_match: str) -> str:
        """Write annotations.json atomically if `if_match` is current. Returns the new ETag."""
        folder = self.page_folder(project, page_id)
        if not folder.is_dir():
            raise PageNotFound(f"no page {page_id!r} in project {project!r}")
        errors = self.check(page_id, page)
        if errors:
            raise InvalidPage(errors)
        path = folder / ANNOTATIONS_NAME
        with _lock_for(path):
            exists = path.exists()
            current = etag_for(path.read_bytes() if exists else None)
            if not etag_matches(if_match, current, exists=exists):
                raise StaleWrite(current)
            write_json_atomic(path, page.to_json_dict())
            return etag_for(path.read_bytes())
