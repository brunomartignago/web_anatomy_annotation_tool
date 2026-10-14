"""Assisted capture: a human handles the page's check, then the tool captures (roadmap 1.2b).

Runs headless: the "human" is simulated by the pause callback. See conftest.py.
"""

from annotool.capture.urls import UrlEntry

# `site` (conftest.py): "/" is a 403 bot wall, "/home" the real page behind it.


def test_without_help_the_wall_is_flagged(capturer, site, tmp_path):
    meta = capturer.capture(UrlEntry(url=site + "/"), tmp_path)
    assert meta.blocked and meta.http_status == 403
    assert not meta.assisted


def test_after_the_human_step_the_real_page_is_captured(capturer, site, tmp_path):
    def human(page):
        page.goto(site + "/home")  # what passing the check looks like: a new document
        return True

    meta = capturer.capture(UrlEntry(url=site + "/"), tmp_path, before_capture=human)
    assert meta.assisted
    assert not meta.blocked, meta.blocked_reasons
    assert meta.http_status == 200  # of the page that was captured, not the first 403
    assert meta.final_url.endswith("/home")
    assert meta.title == "Real home page"


def test_human_can_skip_a_page(capturer, site, tmp_path):
    meta = capturer.capture(UrlEntry(url=site + "/"), tmp_path, before_capture=lambda _: False)
    assert meta is None
    assert not (tmp_path / "page.png").exists() and not (tmp_path / "meta.json").exists()
