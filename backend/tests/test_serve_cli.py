from pathlib import Path

from typer.testing import CliRunner

from annotool.cli import app

runner = CliRunner()
REPO = Path(__file__).resolve().parents[2]


def test_serve_help():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--project" in result.stdout


def test_serve_unknown_project_lists_the_real_ones(tmp_path):
    (tmp_path / "projects" / "demo" / "pages").mkdir(parents=True)
    result = runner.invoke(app, ["serve", "--project", "nope", "--data-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "nope" in result.stderr and "demo" in result.stderr


def test_serve_starts_uvicorn_on_localhost(tmp_path, monkeypatch):
    (tmp_path / "projects" / "demo" / "pages").mkdir(parents=True)
    calls = {}

    def fake_run(asgi_app, **kwargs):
        calls["app"], calls["kwargs"] = asgi_app, kwargs

    opened = []
    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setattr("webbrowser.open", opened.append)
    result = runner.invoke(
        app,
        [
            "serve",
            "--project",
            "demo",
            "--data-dir",
            str(tmp_path),
            "--taxonomy",
            str(REPO / "taxonomies" / "web-ui.yaml"),
            "--port",
            "8765",
            "--no-open",
        ],
    )
    assert result.exit_code == 0, result.output
    assert calls["kwargs"]["host"] == "127.0.0.1"
    assert calls["kwargs"]["port"] == 8765
    assert calls["app"].state.project == "demo"
    assert "http://127.0.0.1:8765" in result.stdout
    assert opened == []
