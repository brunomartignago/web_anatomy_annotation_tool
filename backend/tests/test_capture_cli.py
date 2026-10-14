"""`annotool capture` end to end on a local HTML page (no network). See conftest.py."""

import yaml
from typer.testing import CliRunner

from annotool.cli import app

PAGE = '<!doctype html><html lang="en"><title>CLI test</title><body style="height:3000px">'


def run_capture(url, data_dir, *extra):
    args = ["capture", url, "--project", "demo", "--data-dir", str(data_dir), *extra]
    return CliRunner().invoke(app, args)


def test_writes_project_and_protects_annotated_pages(chromium_available, tmp_path):
    html = tmp_path / "home.html"
    html.write_text(PAGE, encoding="utf-8")
    data_dir = tmp_path / "data"

    result = run_capture(html.as_uri(), data_dir)
    assert result.exit_code == 0, result.output
    project = data_dir / "projects" / "demo"
    page = project / "pages" / "file-home"
    assert (page / "page.png").exists() and (page / "meta.json").exists()
    assert yaml.safe_load((project / "project.yaml").read_text(encoding="utf-8"))["name"] == "demo"

    # Once a page has annotations, recapturing would move the image under the labels.
    (page / "annotations.json").write_text("{}", encoding="utf-8")
    before = (page / "page.png").stat().st_mtime_ns
    result = run_capture(html.as_uri(), data_dir)
    assert result.exit_code == 0, result.output
    assert "skipped" in result.output
    assert (page / "page.png").stat().st_mtime_ns == before

    result = run_capture(html.as_uri(), data_dir, "--force")
    assert result.exit_code == 0, result.output
    assert (page / "page.png").stat().st_mtime_ns != before


def test_reports_failed_pages_and_exits_nonzero(chromium_available, tmp_path):
    missing = (tmp_path / "missing.html").as_uri()
    result = run_capture(missing, tmp_path / "data")
    assert result.exit_code == 1
    assert "failed" in result.output


def test_rejects_bad_project_name(tmp_path):
    result = run_capture("https://example.com", tmp_path / "data", "--project", "My Project")
    assert result.exit_code == 1
