"""Being a polite crawler: a per-host delay, a user agent that says who we are, and
robots.txt checks (warn by default, `--obey-robots` to skip).

Everything here is honest by design: the browser's real user agent is kept and the project
is appended to it, never hidden or faked.
"""

import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlsplit

BOT_NAME = "annotool"
PROJECT_URL = "https://github.com/brunomartignago/web_anatomy_annotation_tool"
ROBOTS_TIMEOUT_S = 10


def identifying_user_agent(browser_user_agent: str, version: str) -> str:
    """The browser's own user agent plus `annotool/<version> (+<repo URL>)`."""
    return f"{browser_user_agent} {BOT_NAME}/{version} (+{PROJECT_URL})"


def _host(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        return None
    return (parts.hostname or "").lower() or None


class HostThrottle:
    """Keeps requests to the same host at least `delay_s` seconds apart."""

    def __init__(
        self,
        delay_s: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.delay_s = delay_s
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> float:
        """Sleep if this URL's host was visited less than `delay_s` ago. Returns the wait."""
        host = _host(url)
        if host is None:
            return 0.0
        waited = 0.0
        last = self._last.get(host)
        if last is not None:
            waited = max(0.0, self.delay_s - (self._clock() - last))
            if waited > 0:
                self._sleep(waited)
        self._last[host] = self._clock()
        return waited


def _robots_groups(robots_txt: str) -> list[tuple[set[str], list[tuple[bool, str]]]]:
    """[(user agents, [(is_allow, path pattern)])], one entry per group in file order."""
    groups: list[tuple[set[str], list[tuple[bool, str]]]] = []
    in_agent_lines = False
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not in_agent_lines:  # consecutive user-agent lines share one group
                groups.append((set(), []))
            groups[-1][0].add(value.split("/", 1)[0].strip().lower())
            in_agent_lines = True
        elif key in {"allow", "disallow"}:
            in_agent_lines = False
            if groups and value:  # an empty Disallow means "nothing disallowed"
                groups[-1][1].append((key == "allow", value))
    return groups


def _pattern_matches(pattern: str, path: str) -> bool:
    """RFC 9309 path matching: `*` matches any run of characters, a final `$` anchors."""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(piece) for piece in body.split("*"))
    return re.match(regex + ("$" if anchored else ""), path) is not None


def robots_allows(robots_txt: str | None, url: str, agent: str = BOT_NAME) -> bool:
    """Whether robots.txt lets `agent` fetch `url`, following RFC 9309. No robots.txt = yes.

    Our own group(s) apply if present, otherwise the `*` group(s). The longest matching rule
    wins and Allow wins ties. (Python's urllib.robotparser gets real files wrong: it ignores
    `$` and `*` and turns `Disallow: /?` into `Disallow: /`.)
    """
    if robots_txt is None:
        return True
    groups = _robots_groups(robots_txt)
    ours = [rules for agents, rules in groups if agent.lower() in agents]
    rules = [r for group in (ours or [r for a, r in groups if "*" in a]) for r in group]

    parts = urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    best: tuple[int, bool] | None = None  # (pattern length, is_allow)
    for is_allow, pattern in rules:
        if _pattern_matches(pattern, path):
            candidate = (len(pattern), is_allow)
            if best is None or candidate > best:  # longer wins; on a tie True > False
                best = candidate
    return True if best is None else best[1]


def fetch_robots(robots_url: str, user_agent: str) -> str | None:
    """robots.txt text, or None when there is none (404, network error, timeout)."""
    request = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=ROBOTS_TIMEOUT_S) as response:
            return response.read(500_000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


class RobotsChecker:
    """Checks URLs against their host's robots.txt, fetching each robots.txt once."""

    def __init__(self, fetch: Callable[[str], str | None]):
        self._fetch = fetch
        self._cache: dict[str, str | None] = {}

    def allows(self, url: str) -> bool | None:
        """True/False for web pages; None for URLs robots.txt doesn't cover (file://)."""
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            return None
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        if robots_url not in self._cache:
            self._cache[robots_url] = self._fetch(robots_url)
        return robots_allows(self._cache[robots_url], url)
