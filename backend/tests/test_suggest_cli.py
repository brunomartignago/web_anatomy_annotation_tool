"""`annotool suggest <project>`: batch suggestions (roadmap 4.1)."""

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

import annotool.suggest as suggest_package
from annotool.cli import app
from annotool.suggest.base import AddBox

FIXTURES = Path(__file__).parent / "fixtures" / "legacy"


class _Footer:
    id = "rule"

    def suggest(self, context):
        page = context.page.page
        return [AddBox(bbox=(0, page.height - 50, page.width, 50), labels={"Taxonomy": "Footer"})]


@pytest.fixture
def data_dir(tmp_path):
    pages = tmp_path / "projects" / "demo" / "pages"
    annotated = pages / "stackoverflow_com"
    annotated.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "stackoverflow_com.json", annotated / "annotations.json")
    Image.new("RGB", (40, 3572), "white").save(annotated / "page.png")
    captured = pages / "captured_page"
    captured.mkdir()
    meta = {"page_id": "captured_page", "url": "https://example.org", "width": 40, "height": 300}
    (captured / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    Image.new("RGB", (40, 300), "white").save(captured / "page.png")
    return tmp_path


def _run(*args):
    return CliRunner().invoke(app, ["suggest", *args])


def _boxes(data_dir, page_id):
    path = data_dir / "projects" / "demo" / "pages" / page_id / "annotations.json"
    return json.loads(path.read_text(encoding="utf-8"))["annotations"] if path.exists() else []


def test_without_suggesters_it_says_so(data_dir, monkeypatch):
    monkeypatch.setattr(suggest_package, "default_suggesters", lambda taxonomy: [])
    result = _run("demo", "--data-dir", str(data_dir))
    assert result.exit_code == 0, result.output
    assert "No suggesters" in result.output


def test_runs_on_every_page_and_saves(data_dir, monkeypatch):
    monkeypatch.setattr(suggest_package, "default_suggesters", lambda taxonomy: [_Footer()])
    result = _run("demo", "--data-dir", str(data_dir))
    assert result.exit_code == 0, result.output
    assert "captured_page: rule +1 box" in result.output
    assert "2 pages, 2 changed" in result.output
    assert _boxes(data_dir, "captured_page")[0]["labels"] == {"Taxonomy": "Footer"}
    assert len(_boxes(data_dir, "stackoverflow_com")) == 2  # the legacy box is kept


def test_dry_run_and_page_filter(data_dir, monkeypatch):
    monkeypatch.setattr(suggest_package, "default_suggesters", lambda taxonomy: [_Footer()])
    result = _run("demo", "--data-dir", str(data_dir), "--page", "captured_page", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "1 pages, 1 changed (dry run: nothing written)" in result.output
    assert _boxes(data_dir, "captured_page") == []
    assert len(_boxes(data_dir, "stackoverflow_com")) == 1


def test_unknown_suggester_or_page_fails(data_dir, monkeypatch):
    monkeypatch.setattr(suggest_package, "default_suggesters", lambda taxonomy: [_Footer()])
    assert _run("demo", "--data-dir", str(data_dir), "--only", "llm").exit_code == 1
    assert _run("demo", "--data-dir", str(data_dir), "--page", "nope").exit_code == 1
