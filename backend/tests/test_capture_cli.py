"""`annotool capture` end to end on a local HTML page (no network). See conftest.py."""

import json

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


COLORFUL = "".join(
    f'<div style="height:300px;margin:20px;background:hsl({i * 37},60%,50%)"></div>'
    for i in range(12)
)


def write_page(path, title, body=COLORFUL):
    path.write_text(
        f'<!doctype html><html lang="en"><title>{title}</title><body>{body}</body>',
        encoding="utf-8",
    )
    return path.as_uri()


def meta_of(data_dir, page_id):
    path = data_dir / "projects" / "demo" / "pages" / page_id / "meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_retry_blocked_recaptures_only_blocked_pages(chromium_available, tmp_path):
    data_dir = tmp_path / "data"
    denied = write_page(tmp_path / "denied.html", "Access Denied", "<h1>Access Denied</h1>")
    fine = write_page(tmp_path / "fine.html", "Fine")

    result = CliRunner().invoke(
        app, ["capture", denied, fine, "--project", "demo", "--data-dir", str(data_dir)]
    )
    assert result.exit_code == 0, result.output
    assert "blocked" in result.output
    assert meta_of(data_dir, "file-denied")["blocked"] is True
    assert meta_of(data_dir, "file-fine")["blocked"] is False
    fine_before = meta_of(data_dir, "file-fine")["captured_at"]

    write_page(tmp_path / "denied.html", "Now open")  # the wall went away
    result = CliRunner().invoke(
        app,
        ["capture", denied, fine, "--project", "demo", "--data-dir", str(data_dir)]
        + ["--retry-blocked"],
    )
    assert result.exit_code == 0, result.output
    assert meta_of(data_dir, "file-denied")["blocked"] is False
    assert meta_of(data_dir, "file-fine")["captured_at"] == fine_before  # not recaptured


def test_consent_clicks_come_from_project_yaml(chromium_available, tmp_path):
    data_dir = tmp_path / "data"
    banner = (
        '<div id="onetrust-banner-sdk" style="position:fixed;bottom:0;width:100%;height:150px">'
        '<button id="reject" onclick="this.parentElement.remove()">Reject</button></div>'
    )
    url = write_page(tmp_path / "news.html", "News", COLORFUL + banner)
    project = data_dir / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "project.yaml").write_text(
        "name: demo\ntaxonomy: web-ui\nconsent_clicks:\n  - '#reject'\n", encoding="utf-8"
    )

    result = run_capture(url, data_dir)
    assert result.exit_code == 0, result.output
    assert meta_of(data_dir, "file-news")["consent_clicked"] == "#reject"


def test_rejects_unknown_browser(tmp_path):
    result = run_capture("https://example.com", tmp_path / "data", "--browser", "firefox")
    assert result.exit_code != 0


def test_rejects_bad_project_name(tmp_path):
    result = run_capture("https://example.com", tmp_path / "data", "--project", "My Project")
    assert result.exit_code == 1
