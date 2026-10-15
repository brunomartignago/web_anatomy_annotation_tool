import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from annotool.models import Annotation, PageFile
from annotool.server.store import (
    EMPTY_ETAG,
    InvalidPage,
    PageNotFound,
    PageStore,
    StaleWrite,
    etag_for,
    etag_matches,
    page_progress,
)
from annotool.taxonomy import load_taxonomy

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "legacy"
ATTRS = ["Form", "Function", "Component", "Taxonomy"]


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy(REPO / "taxonomies" / "web-ui.yaml")


def _box(labels, status="accepted", n=0, kind="element"):
    return Annotation(
        id=f"01J{n:023d}",
        kind=kind,
        bbox=(0, 0, 10, 10),
        labels=labels,
        source="human",
        status=status,
    )


def _meta(page_id, **extra):
    return {
        "page_id": page_id,
        "url": f"https://{page_id}.example",
        "final_url": f"https://{page_id}.example/",
        "title": f"{page_id} title",
        "category": "News & Media",
        "image": "page.png",
        "width": 40,
        "height": 3000,
        "viewport": {"width": 1920, "height": 1080},
        "captured_at": "2026-10-14T19:47:39-03:00",
        **extra,
    }


@pytest.fixture
def data_dir(tmp_path):
    """Project `demo`: one annotated page, one captured page, one blocked capture."""
    pages = tmp_path / "projects" / "demo" / "pages"
    annotated = pages / "stackoverflow_com"
    annotated.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "stackoverflow_com.json", annotated / "annotations.json")

    captured = pages / "captured_page"
    captured.mkdir()
    (captured / "meta.json").write_text(json.dumps(_meta("captured_page")), encoding="utf-8")
    (captured / "dom.json").write_text("{}", encoding="utf-8")
    Image.new("RGB", (40, 3000), "white").save(captured / "page.png")

    blocked = pages / "blocked_page"
    blocked.mkdir()
    meta = _meta("blocked_page", blocked=True, blocked_reasons=["HTTP 403"], height=1080)
    (blocked / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    (pages / "empty_folder").mkdir()
    (tmp_path / "projects" / "other" / "pages").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def store(data_dir, taxonomy):
    return PageStore(data_dir, taxonomy)


# ── ETags ──


def test_etag_is_quoted_and_content_based():
    assert etag_for(b"abc") == etag_for(b"abc")
    assert etag_for(b"abc") != etag_for(b"abd")
    assert etag_for(b"abc").startswith('"') and etag_for(b"abc").endswith('"')
    assert etag_for(None) == EMPTY_ETAG


@pytest.mark.parametrize(
    ("header", "matches"),
    [
        ('"abc"', True),
        ('W/"abc"', True),  # weak prefix added by some proxies
        ('"zzz", "abc"', True),
        ('"zzz"', False),
        ("abc", False),  # unquoted is not a valid entity tag
        ("*", True),
    ],
)
def test_etag_matches(header, matches):
    assert etag_matches(header, '"abc"', exists=True) is matches


def test_star_does_not_match_a_missing_file():
    assert etag_matches("*", EMPTY_ETAG, exists=False) is False
    assert etag_matches(EMPTY_ETAG, EMPTY_ETAG, exists=False) is True


# ── Progress ──


def test_progress_counts_by_completeness():
    page = PageFile.model_validate_json((FIXTURES / "stackoverflow_com.json").read_bytes())
    full = dict(page.annotations[0].labels)
    page.annotations = [
        _box({}, n=1),
        _box({"Form": "Typo"}, n=2),
        _box(full, n=3),
        _box(full, status="suggested", n=4),
        _box({"Form": "Typo"}, status="rejected", n=5),  # rejected boxes don't count
    ]
    progress = page_progress(page, ATTRS)
    assert progress.boxes == 4
    assert (progress.empty, progress.partial, progress.complete) == (1, 1, 2)
    assert progress.suggested == 1
    assert progress.labeled == {"Form": 3, "Function": 2, "Component": 2, "Taxonomy": 2}


def test_progress_leaves_out_section_and_component_boxes():
    page = PageFile.model_validate_json((FIXTURES / "stackoverflow_com.json").read_bytes())
    page.annotations = [
        _box({}, n=1),
        _box({"Taxonomy": "Header"}, n=2, kind="section"),  # a container, not work to label
        _box({"Component": "Card"}, n=3, kind="component"),
    ]
    progress = page_progress(page, ATTRS)
    assert (progress.boxes, progress.empty, progress.partial) == (1, 1, 0)
    assert progress.labeled == dict.fromkeys(ATTRS, 0)


def test_progress_of_an_empty_page():
    progress = page_progress(None, ATTRS)
    assert progress.boxes == progress.complete == progress.suggested == 0
    assert progress.labeled == dict.fromkeys(ATTRS, 0)


# ── Listing ──


def test_list_projects(store):
    projects = {p.name: p.pages for p in store.projects()}
    assert projects == {"demo": 3, "other": 0}


def test_list_pages_includes_unannotated_captures(store):
    pages = {p.id: p for p in store.list_pages("demo")}
    assert list(pages) == ["blocked_page", "captured_page", "stackoverflow_com"]  # sorted

    annotated = pages["stackoverflow_com"]
    assert annotated.has_annotations and annotated.progress.complete == 1
    assert annotated.title == "Newest Questions - Stack Overflow"
    assert annotated.height == 3572

    captured = pages["captured_page"]
    assert not captured.has_annotations
    assert captured.has_dom and captured.has_image and not captured.blocked
    assert captured.progress.boxes == 0
    assert (captured.url, captured.category) == ("https://captured_page.example/", "News & Media")
    assert captured.strips == 2

    blocked = pages["blocked_page"]
    assert blocked.blocked and blocked.blocked_reasons == ["HTTP 403"]
    assert not blocked.has_image and blocked.strips == 0


def test_list_pages_reports_a_broken_file_instead_of_failing(store, data_dir):
    path = data_dir / "projects" / "demo" / "pages" / "captured_page" / "annotations.json"
    path.write_text("{ not json", encoding="utf-8")
    pages = {p.id: p for p in store.list_pages("demo")}
    assert pages["captured_page"].error
    assert pages["stackoverflow_com"].error is None


def test_unknown_project(store):
    with pytest.raises(PageNotFound):
        store.list_pages("nope")
    with pytest.raises(PageNotFound):
        store.list_pages("../demo")


# ── Loading ──


def test_load_annotated_page(store):
    loaded = store.load("demo", "stackoverflow_com")
    assert loaded.page.page.id == "stackoverflow_com"
    assert loaded.etag == etag_for((FIXTURES / "stackoverflow_com.json").read_bytes())
    assert loaded.meta is None


def test_load_captured_page_builds_an_empty_file_from_meta(store, taxonomy):
    loaded = store.load("demo", "captured_page")
    assert loaded.etag == EMPTY_ETAG
    assert loaded.page.annotations == []
    assert loaded.page.taxonomy.id == taxonomy.id
    assert loaded.page.taxonomy.version == taxonomy.version
    info = loaded.page.page
    assert (info.id, info.width, info.height, info.image) == ("captured_page", 40, 3000, "page.png")
    assert info.url == "https://captured_page.example/"  # final_url: where the screenshot is
    assert info.captured_at is not None and info.captured_at.utcoffset() is not None
    assert loaded.meta["category"] == "News & Media"
    assert loaded.has_dom
    # Nothing is written until the first save.
    assert not (store.page_folder("demo", "captured_page") / "annotations.json").exists()


def test_load_falls_back_to_the_image_size(store, data_dir):
    folder = data_dir / "projects" / "demo" / "pages" / "captured_page"
    meta = _meta("captured_page")
    del meta["width"], meta["height"]  # e.g. an older meta.json
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    info = store.load("demo", "captured_page").page.page
    assert (info.width, info.height) == (40, 3000)


@pytest.mark.parametrize("page_id", ["blocked_page", "empty_folder", "missing", "..", "A_B"])
def test_load_unavailable_pages(store, page_id):
    with pytest.raises(PageNotFound):
        store.load("demo", page_id)


# ── Saving ──


def _with_box(page: PageFile, labels=None) -> PageFile:
    page = page.model_copy(deep=True)
    page.annotations.append(_box(labels or {"Form": "Typo"}, n=len(page.annotations) + 7))
    return page


def test_first_save_creates_the_file(store):
    loaded = store.load("demo", "captured_page")
    etag = store.save("demo", "captured_page", _with_box(loaded.page), if_match=loaded.etag)
    path = store.page_folder("demo", "captured_page") / "annotations.json"
    assert etag == etag_for(path.read_bytes()) != EMPTY_ETAG
    saved = PageFile.model_validate_json(path.read_bytes())
    assert len(saved.annotations) == 1
    assert "null" not in path.read_text(encoding="utf-8")  # optional fields are omitted
    assert [p.name for p in path.parent.iterdir() if p.name.endswith(".tmp")] == []


def test_save_then_save_again_with_the_new_etag(store):
    loaded = store.load("demo", "stackoverflow_com")
    etag = store.save("demo", "stackoverflow_com", _with_box(loaded.page), if_match=loaded.etag)
    page2 = _with_box(store.load("demo", "stackoverflow_com").page)
    etag2 = store.save("demo", "stackoverflow_com", page2, if_match=etag)
    assert etag2 != etag
    assert len(store.load("demo", "stackoverflow_com").page.annotations) == 3


def test_stale_save_is_refused_and_the_file_is_untouched(store):
    path = store.page_folder("demo", "stackoverflow_com") / "annotations.json"
    tab_a = store.load("demo", "stackoverflow_com")
    tab_b = store.load("demo", "stackoverflow_com")
    newer = store.save("demo", "stackoverflow_com", _with_box(tab_a.page), if_match=tab_a.etag)
    before = path.read_bytes()

    with pytest.raises(StaleWrite) as info:
        store.save("demo", "stackoverflow_com", _with_box(tab_b.page), if_match=tab_b.etag)
    assert info.value.current_etag == newer
    assert path.read_bytes() == before


def test_creating_over_an_existing_file_is_stale(store):
    page = store.load("demo", "stackoverflow_com").page
    with pytest.raises(StaleWrite):
        store.save("demo", "stackoverflow_com", page, if_match=EMPTY_ETAG)


@pytest.mark.parametrize(
    ("labels", "message"),
    [
        ({"Colour": "Red"}, "unknown attribute 'Colour'"),
        ({"Form": "Typography"}, "Form value 'Typography' is not an option"),
    ],
)
def test_save_rejects_labels_outside_the_taxonomy(store, labels, message):
    loaded = store.load("demo", "captured_page")
    with pytest.raises(InvalidPage) as info:
        store.save("demo", "captured_page", _with_box(loaded.page, labels), if_match=loaded.etag)
    assert any(message in e for e in info.value.errors)
    assert not (store.page_folder("demo", "captured_page") / "annotations.json").exists()


def test_save_rejects_a_mismatched_page_id_and_duplicate_box_ids(store):
    loaded = store.load("demo", "stackoverflow_com")
    page = loaded.page.model_copy(deep=True)
    page.page.id = "someone_else"
    page.annotations.append(page.annotations[0])
    with pytest.raises(InvalidPage) as info:
        store.save("demo", "stackoverflow_com", page, if_match=loaded.etag)
    assert any("page.id" in e for e in info.value.errors)
    assert any("duplicate annotation id" in e for e in info.value.errors)


def test_save_accepts_proposed_values(store, taxonomy):
    proposed = next((a.id, o.value) for a in taxonomy.attributes for o in a.proposed_options)
    loaded = store.load("demo", "captured_page")
    page = _with_box(loaded.page, {proposed[0]: proposed[1]})
    store.save("demo", "captured_page", page, if_match=loaded.etag)
