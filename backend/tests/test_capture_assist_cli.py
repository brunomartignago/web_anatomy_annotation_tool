"""`annotool capture --assist` end to end, headless, with answers typed on stdin.

A separate module from test_capture_assist.py because the CLI starts its own Playwright
(see conftest.py).
"""

import json
from dataclasses import replace

import pytest
from typer.testing import CliRunner

from annotool.capture.browser import Capturer
from annotool.cli import app


@pytest.fixture
def headless_assist(monkeypatch):
    """--assist opens a visible window; tests (and CI) run it headless instead."""
    original = Capturer.__enter__

    def enter(self):
        self.settings = replace(self.settings, headless=True)
        return original(self)

    monkeypatch.setattr(Capturer, "__enter__", enter)


def run_assist(site, data_dir, answers):
    urls = [site + "/", site + "/home"]
    args = ["capture", *urls, "--project", "demo", "--data-dir", str(data_dir), "--assist"]
    args += ["--delay", "0"]
    return CliRunner().invoke(app, args, input=answers)


def meta_path(data_dir, page_id):
    return data_dir / "projects" / "demo" / "pages" / page_id / "meta.json"


def test_enter_captures_and_s_skips(chromium_available, headless_assist, site, tmp_path):
    result = run_assist(site, tmp_path, "\ns\n")
    assert result.exit_code == 0, result.output
    assert "press Enter" in result.output
    first = json.loads(meta_path(tmp_path, "127_0_0_1").read_text(encoding="utf-8"))
    assert first["assisted"] is True
    assert not meta_path(tmp_path, "127_0_0_1-home").exists()  # skipped
    assert "1 skipped" in result.output


def test_q_stops_the_batch(chromium_available, headless_assist, site, tmp_path):
    result = run_assist(site, tmp_path, "q\n")
    assert result.exit_code == 0, result.output
    assert not meta_path(tmp_path, "127_0_0_1").exists()
    assert not meta_path(tmp_path, "127_0_0_1-home").exists()
    assert "stopped" in result.output
