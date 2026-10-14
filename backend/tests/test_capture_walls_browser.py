"""Blocked-page and consent-banner handling in a real browser (local pages). See conftest.py."""

import pytest

from annotool.capture.urls import UrlEntry

# Enough colored blocks that the page is clearly not blank.
CONTENT = "".join(
    f'<div style="height:300px;margin:20px;background:hsl({i * 37},60%,50%)"></div>'
    for i in range(12)
)

CONSENT_BANNER = """
<div id="onetrust-banner-sdk"
     style="position:fixed;bottom:0;left:0;right:0;height:200px;background:#222">
  <button id="onetrust-reject-all-handler" onclick="this.parentElement.remove()">Reject all</button>
</div>
"""

# Some consent tools (Sourcepoint, used by the Guardian) render inside an iframe.
CONSENT_IFRAME = """
<div id="sp_message_container_123" style="position:fixed;bottom:0;left:0;right:0;height:200px">
  <iframe style="width:100%;height:100%;border:0" srcdoc="
    <button title='Reject all'
      onclick=&quot;parent.document.getElementById('sp_message_container_123').remove()&quot;>
      Reject all</button>"></iframe>
</div>
"""


def page(tmp_path, name: str, title: str, body: str) -> str:
    path = tmp_path / f"{name}.html"
    path.write_text(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>'
        f'</head><body style="margin:0">{body}</body></html>',
        encoding="utf-8",
    )
    return path.as_uri()


def capture(capturer, tmp_path, url, **kwargs):
    return capturer.capture(UrlEntry(url=url), tmp_path / "out", **kwargs)


def test_normal_page_is_not_blocked(capturer, tmp_path):
    meta = capture(capturer, tmp_path, page(tmp_path, "ok", "Home", CONTENT))
    assert not meta.blocked
    assert meta.blocked_reasons == []
    assert meta.file_size > 0


def test_block_title_is_flagged(capturer, tmp_path):
    body = "<h1>Access Denied</h1><p>You don't have permission to access this server.</p>"
    meta = capture(capturer, tmp_path, page(tmp_path, "denied", "Access Denied", body))
    assert meta.blocked
    assert any("Access Denied" in r for r in meta.blocked_reasons)


def test_bot_wall_element_is_flagged(capturer, tmp_path):
    body = CONTENT + '<div id="px-captcha" style="width:300px;height:100px"></div>'
    meta = capture(capturer, tmp_path, page(tmp_path, "wall", "Shop", body))
    assert meta.blocked
    assert any("#px-captcha" in r for r in meta.blocked_reasons)


def test_hidden_bot_wall_element_is_ignored(capturer, tmp_path):
    body = CONTENT + '<div id="px-captcha" style="display:none"></div>'
    meta = capture(capturer, tmp_path, page(tmp_path, "hidden", "Shop", body))
    assert not meta.blocked


def test_consent_banner_without_click_list_is_a_warning(capturer, tmp_path):
    meta = capture(capturer, tmp_path, page(tmp_path, "c1", "News", CONTENT + CONSENT_BANNER))
    assert not meta.blocked
    assert meta.consent_clicked is None
    assert any("#onetrust-banner-sdk" in w for w in meta.warnings)


@pytest.mark.parametrize(
    ("banner", "selector"),
    [
        (CONSENT_BANNER, "#onetrust-reject-all-handler"),
        (CONSENT_IFRAME, "button[title='Reject all']"),  # inside the iframe
    ],
)
def test_consent_click_list_dismisses_the_banner(capturer, tmp_path, banner, selector):
    url = page(tmp_path, "c2", "News", CONTENT + banner)
    meta = capture(capturer, tmp_path, url, consent_clicks=["#not-on-this-page", selector])
    assert meta.consent_clicked == selector
    assert not any("consent" in w for w in meta.warnings)
