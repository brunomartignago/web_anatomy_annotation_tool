import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from annotool.server.app import create_app
from annotool.server.store import EMPTY_ETAG

REPO = Path(__file__).resolve().parents[2]
TAXONOMY = REPO / "taxonomies" / "web-ui.yaml"
FIXTURES = Path(__file__).parent / "fixtures" / "legacy"


@pytest.fixture
def data_dir(tmp_path):
    pages = tmp_path / "projects" / "demo" / "pages"
    annotated = pages / "stackoverflow_com"
    annotated.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "stackoverflow_com.json", annotated / "annotations.json")
    Image.new("RGB", (40, 3572), "white").save(annotated / "page.png")

    captured = pages / "captured_page"
    captured.mkdir()
    meta = {"page_id": "captured_page", "url": "https://example.org", "width": 40, "height": 2100}
    (captured / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    Image.new("RGB", (40, 2100), "white").save(captured / "page.png")

    other = tmp_path / "projects" / "other" / "pages" / "captured_page"
    other.mkdir(parents=True)
    (other / "meta.json").write_text(json.dumps({**meta, "width": 99}), encoding="utf-8")
    Image.new("RGB", (99, 10), "white").save(other / "page.png")
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(data_dir, "demo", TAXONOMY, frontend_dir=None))


def test_taxonomy(client):
    body = client.get("/api/taxonomy").json()
    assert body["id"] == "web-ui"
    assert [a["id"] for a in body["attributes"]] == ["Form", "Function", "Component", "Taxonomy"]
    assert body["presets"] and "rules" in body


def test_projects(client):
    body = client.get("/api/projects").json()
    assert body["current"] == "demo"
    assert {p["name"]: p["pages"] for p in body["projects"]} == {"demo": 2, "other": 1}


def test_pages_with_progress(client):
    pages = client.get("/api/projects/demo/pages").json()
    by_id = {p["id"]: p for p in pages}
    assert by_id["stackoverflow_com"]["progress"]["complete"] == 1
    assert by_id["captured_page"]["progress"]["boxes"] == 0
    assert by_id["captured_page"]["has_annotations"] is False
    assert client.get("/api/projects/nope/pages").status_code == 404


def test_get_page(client):
    response = client.get("/api/pages/captured_page")
    assert response.status_code == 200
    body = response.json()
    assert response.headers["etag"] == body["etag"] == EMPTY_ETAG
    assert body["project"] == "demo"
    assert body["annotations"]["page"]["width"] == 40
    assert body["annotations"]["annotations"] == []
    assert body["strips"] == {"height": 2048, "count": 2}
    assert body["has_dom"] is False
    assert "null" not in response.text  # unset optional fields are omitted


def test_get_page_of_another_project(client):
    body = client.get("/api/pages/captured_page", params={"project": "other"}).json()
    assert body["project"] == "other" and body["annotations"]["page"]["width"] == 99


@pytest.mark.parametrize("page_id", ["missing", "..%2F..%2Fsecret", "UPPER"])
def test_get_missing_page(client, page_id):
    assert client.get(f"/api/pages/{page_id}").status_code == 404


def _add_box(page_body):
    doc = page_body["annotations"]
    doc["annotations"].append(
        {
            "id": "01J00000000000000000000099",
            "kind": "element",
            "bbox": [1, 2, 3, 4],
            "labels": {"Form": "Typo"},
            "source": "human",
            "status": "edited",
        }
    )
    return doc


def test_put_saves_and_returns_a_new_etag(client, data_dir):
    page = client.get("/api/pages/captured_page").json()
    response = client.put(
        "/api/pages/captured_page/annotations",
        json=_add_box(page),
        headers={"If-Match": page["etag"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["etag"] == response.headers["etag"] != page["etag"]
    assert body["progress"]["partial"] == 1
    saved = data_dir / "projects" / "demo" / "pages" / "captured_page" / "annotations.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["annotations"][0]["labels"] == {
        "Form": "Typo"
    }
    listed = {p["id"]: p for p in client.get("/api/projects/demo/pages").json()}
    assert listed["captured_page"]["has_annotations"] is True


def test_put_with_a_stale_etag_is_refused(client):
    page = client.get("/api/pages/stackoverflow_com").json()
    first = client.put(
        "/api/pages/stackoverflow_com/annotations",
        json=_add_box(page),
        headers={"If-Match": page["etag"]},
    )
    assert first.status_code == 200

    stale = client.put(
        "/api/pages/stackoverflow_com/annotations",
        json=page["annotations"],
        headers={"If-Match": page["etag"]},
    )
    assert stale.status_code == 412
    assert stale.json()["etag"] == first.json()["etag"] == stale.headers["etag"]
    assert len(client.get("/api/pages/stackoverflow_com").json()["annotations"]["annotations"]) == 2


def test_put_without_if_match_is_refused(client):
    page = client.get("/api/pages/captured_page").json()
    response = client.put("/api/pages/captured_page/annotations", json=page["annotations"])
    assert response.status_code == 428


def test_put_invalid_labels(client):
    page = client.get("/api/pages/captured_page").json()
    doc = _add_box(page)
    doc["annotations"][0]["labels"] = {"Form": "Nonsense"}
    response = client.put(
        "/api/pages/captured_page/annotations", json=doc, headers={"If-Match": page["etag"]}
    )
    assert response.status_code == 422
    assert "Nonsense" in response.text


def test_put_schema_violation(client):
    page = client.get("/api/pages/captured_page").json()
    doc = _add_box(page)
    doc["annotations"][0]["bbox"] = [0, 0, -5, 4]
    response = client.put(
        "/api/pages/captured_page/annotations", json=doc, headers={"If-Match": page["etag"]}
    )
    assert response.status_code == 422


def test_strips(client, data_dir):
    response = client.get("/api/pages/captured_page/strips/1.webp")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "no-cache"
    cached = data_dir / "projects" / "demo" / "pages" / "captured_page" / ".cache" / "strips"
    assert (cached / "1.webp").exists()

    again = client.get(
        "/api/pages/captured_page/strips/1.webp",
        headers={"If-None-Match": response.headers["etag"]},
    )
    assert again.status_code == 304

    assert client.get("/api/pages/captured_page/strips/2.webp").status_code == 404
    assert client.get("/api/pages/captured_page/strips/x.webp").status_code in (404, 422)
    assert client.get("/api/pages/missing/strips/0.webp").status_code == 404


# ── Suggestions (4.1) ──


class _Header:
    """A stand-in suggester: one box across the top, labeled Header."""

    id = "rule"

    def suggest(self, context):
        from annotool.suggest.base import AddBox

        width = context.page.page.width
        return [
            AddBox(
                bbox=(0, 0, width, 100), labels={"Taxonomy": "Header"}, confidence={"Taxonomy": 0.8}
            )
        ]


@pytest.fixture
def suggest_client(data_dir):
    app = create_app(data_dir, "demo", TAXONOMY, frontend_dir=None, suggesters=[_Header()])
    return TestClient(app)


def test_suggesters_are_listed(client, suggest_client):
    assert client.get("/api/suggesters").json() == []  # none registered yet (4.2+ add them)
    assert suggest_client.get("/api/suggesters").json() == ["rule"]


def test_suggest_merges_saves_and_reports(suggest_client, data_dir):
    page = suggest_client.get("/api/pages/captured_page").json()
    response = suggest_client.post(
        "/api/pages/captured_page/suggest", headers={"If-Match": page["etag"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["etag"] == response.headers["etag"] != page["etag"]
    [box] = body["annotations"]["annotations"]
    assert (box["source"], box["status"], box["labels"]) == (
        "rule",
        "suggested",
        {"Taxonomy": "Header"},
    )
    assert body["reports"][0] == {
        "suggester": "rule",
        "boxes_added": 1,
        "boxes_matched": 0,
        "labels_set": 1,
        "kept_human": 0,
        "kept_better": 0,
        "skipped_rejected": 0,
        "dropped": [],
        "error": None,
        "changed": True,
    }
    assert body["progress"]["boxes"] == 1
    saved = data_dir / "projects" / "demo" / "pages" / "captured_page" / "annotations.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["annotations"][0]["source"] == "rule"

    again = suggest_client.post(
        "/api/pages/captured_page/suggest", headers={"If-Match": body["etag"]}
    ).json()
    assert again["etag"] == body["etag"]  # nothing new: the file isn't rewritten
    assert again["reports"][0]["changed"] is False


def test_suggest_needs_a_current_etag(suggest_client):
    url = "/api/pages/captured_page/suggest"
    assert suggest_client.post(url).status_code == 428
    stale = suggest_client.post(url, headers={"If-Match": '"old"'})
    assert stale.status_code == 412 and stale.json()["etag"]


def test_suggest_can_run_only_some_suggesters(suggest_client):
    page = suggest_client.get("/api/pages/captured_page").json()
    url = "/api/pages/captured_page/suggest"
    headers = {"If-Match": page["etag"]}
    assert suggest_client.post(url, params={"only": "dom"}, headers=headers).status_code == 422
    body = suggest_client.post(url, params={"only": "rule"}, headers=headers).json()
    assert [r["suggester"] for r in body["reports"]] == ["rule"]


def test_root_without_a_built_frontend(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "/docs" in response.text


def test_built_frontend_is_served(data_dir, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>annotool ui</html>", encoding="utf-8")
    client = TestClient(create_app(data_dir, "demo", TAXONOMY, frontend_dir=dist))
    assert "annotool ui" in client.get("/").text
    assert client.get("/api/taxonomy").status_code == 200


def test_unknown_served_project_fails_early(data_dir):
    with pytest.raises(ValueError, match="nope"):
        create_app(data_dir, "nope", TAXONOMY)
