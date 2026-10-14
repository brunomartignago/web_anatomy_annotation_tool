"""Shared fixtures.

Browser tests need Playwright's Chromium (`uv run playwright install chromium`). Without it
they are skipped, unless ANNOTOOL_REQUIRE_BROWSER=1 (set in CI), where they fail instead.
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from annotool.capture.browser import Capturer

_COLORFUL = "".join(
    f'<div style="height:300px;margin:20px;background:hsl({i * 37},60%,50%)"></div>'
    for i in range(12)
)


class _WallHandler(BaseHTTPRequestHandler):
    """`/` is a 403 bot wall; `/home` is the real page a human reaches after the check."""

    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path == "/home":
            status, title, body = 200, "Real home page", _COLORFUL
        else:
            status, title, body = 403, "Just a moment...", "<p>Checking your browser</p>"
        html = f"<!doctype html><html lang='en'><title>{title}</title><body>{body}</body>"
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, *args):  # keep test output quiet
        pass


@pytest.fixture(scope="module")
def site():
    """A local site with a bot wall at `/` and the real page at `/home`."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _WallHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _skip_without_browser(exc: Exception) -> None:
    if os.environ.get("ANNOTOOL_REQUIRE_BROWSER") == "1":
        raise exc
    pytest.skip(f"Playwright Chromium not available: {exc}")


@pytest.fixture(scope="module")
def capturer():
    """One Chromium shared by a module's tests.

    Playwright's sync API allows one instance per thread, so a module that runs the CLI
    (which starts its own) must use `chromium_available` instead.
    """
    try:
        with Capturer() as cap:
            yield cap
    except Exception as exc:
        _skip_without_browser(exc)


@pytest.fixture(scope="module")
def chromium_available() -> None:
    try:
        with Capturer():
            pass
    except Exception as exc:
        _skip_without_browser(exc)
