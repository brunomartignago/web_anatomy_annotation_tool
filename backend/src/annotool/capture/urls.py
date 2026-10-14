"""URL lists and page ids."""

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

MAX_PAGE_ID_LENGTH = 100

# Accepted header spellings (lowercased) for each column of a URL list.
_COLUMNS = {
    "url": {"url", "website url", "website_url"},
    "category": {"category"},
    "page_type": {"page_type", "page type"},
}


class UrlListError(ValueError):
    """A URL list or URL argument can't be used."""


@dataclass(frozen=True)
class UrlEntry:
    url: str
    category: str | None = None
    page_type: str | None = None

    @property
    def page_id(self) -> str:
        return page_id_for_url(self.url)


def _slug(text: str, sep: str) -> str:
    return re.sub(r"[^a-z0-9]+", sep, text.lower()).strip(sep)


def page_id_for_url(url: str) -> str:
    """`https://www.adobe.com/products/` -> `www_adobe_com-products`.

    The hostname keeps the legacy convention (dots become underscores); the path, if any,
    is appended as a dash-separated slug. Query strings and fragments are ignored.
    """
    parts = urlsplit(url)
    if parts.scheme == "file":
        page_id = "file-" + _slug(Path(parts.path).stem, "-")
    else:
        page_id = _slug(parts.hostname or "", "_")
        path = _slug(parts.path, "-")
        if path:
            page_id += "-" + path
    if len(page_id) > MAX_PAGE_ID_LENGTH:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        page_id = page_id[: MAX_PAGE_ID_LENGTH - 9].rstrip("-_") + "-" + digest
    return page_id or "page"


def read_url_list(path: Path) -> list[UrlEntry]:
    """Read a CSV with a URL column and optional category / page_type columns."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = {(h or "").strip().lower(): h for h in reader.fieldnames or []}
        columns = {
            name: next((headers[h] for h in spellings if h in headers), None)
            for name, spellings in _COLUMNS.items()
        }
        if columns["url"] is None:
            raise UrlListError(f"{path}: no URL column (expected 'Website URL' or 'url')")

        def cell(row: dict, name: str) -> str | None:
            column = columns[name]
            value = (row.get(column) or "").strip() if column else ""
            return value or None

        return [
            UrlEntry(url=url, category=cell(row, "category"), page_type=cell(row, "page_type"))
            for row in reader
            if (url := cell(row, "url"))
        ]


def entries_from_sources(sources: list[str], notes: list[str] | None = None) -> list[UrlEntry]:
    """Each source is a URL (http, https or file) or a path to a URL-list CSV.

    A URL listed twice keeps its first row (a note is appended to `notes`). Two different
    URLs that would share a page id are an error, since one would overwrite the other.
    """
    entries: list[UrlEntry] = []
    for source in sources:
        if urlsplit(source).scheme in {"http", "https", "file"}:
            entries.append(UrlEntry(url=source))
        elif Path(source).is_file():
            entries += read_url_list(Path(source))
        else:
            raise UrlListError(f"{source!r} is neither a URL (with https://) nor a CSV file")

    unique: dict[str, UrlEntry] = {}
    for entry in entries:
        first = unique.get(entry.page_id)
        if first is None:
            unique[entry.page_id] = entry
        elif first.url.rstrip("/") == entry.url.rstrip("/"):
            if notes is not None:
                notes.append(
                    f"{entry.page_id} is listed twice; keeping the first row "
                    f"(category {first.category!r}, not {entry.category!r})"
                )
        else:
            raise UrlListError(f"{entry.url} and {first.url} both map to page id {entry.page_id!r}")
    return list(unique.values())
