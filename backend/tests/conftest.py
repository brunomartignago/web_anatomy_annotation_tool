"""Shared fixtures.

Browser tests need Playwright's Chromium (`uv run playwright install chromium`). Without it
they are skipped, unless ANNOTOOL_REQUIRE_BROWSER=1 (set in CI), where they fail instead.
"""

import os

import pytest

from annotool.capture.browser import Capturer


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
