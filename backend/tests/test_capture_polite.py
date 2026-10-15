"""Politeness helpers: per-host delay, identifying user agent, robots.txt (no browser)."""

import pytest

from annotool.capture.polite import (
    BOT_NAME,
    HostThrottle,
    RobotsChecker,
    identifying_user_agent,
    robots_allows,
)

# ── Per-host delay ───────────────────────────────────────────────────────────


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_same_host_waits_for_the_delay():
    clock = FakeClock()
    throttle = HostThrottle(delay_s=5, clock=clock.time, sleep=clock.sleep)
    throttle.wait("https://www.example.com/a")
    clock.now += 2  # the first capture took 2 s
    throttle.wait("https://www.example.com/b")
    assert clock.slept == [pytest.approx(3)]


def test_different_hosts_do_not_wait():
    clock = FakeClock()
    throttle = HostThrottle(delay_s=5, clock=clock.time, sleep=clock.sleep)
    throttle.wait("https://www.example.com/")
    throttle.wait("https://www.other.org/")
    assert clock.slept == []


def test_no_wait_once_the_delay_has_passed():
    clock = FakeClock()
    throttle = HostThrottle(delay_s=5, clock=clock.time, sleep=clock.sleep)
    throttle.wait("https://www.example.com/a")
    clock.now += 10
    throttle.wait("https://www.example.com/b")
    assert clock.slept == []


def test_host_comparison_ignores_case_and_port():
    clock = FakeClock()
    throttle = HostThrottle(delay_s=5, clock=clock.time, sleep=clock.sleep)
    throttle.wait("https://Example.com:443/a")
    throttle.wait("https://example.com/b")
    assert clock.slept == [pytest.approx(5)]


# ── User agent ───────────────────────────────────────────────────────────────


def test_identifying_user_agent_keeps_the_browser_string_and_adds_the_project():
    browser_ua = "Mozilla/5.0 (Windows NT 10.0) HeadlessChrome/156.0 Safari/537.36"
    ua = identifying_user_agent(browser_ua, version="0.1.0")
    assert ua.startswith(browser_ua)  # nothing hidden or faked
    assert f"{BOT_NAME}/0.1.0" in ua
    assert "github.com/brunomartignago/web_anatomy_annotation_tool" in ua


# ── robots.txt ───────────────────────────────────────────────────────────────

ROBOTS = """
User-agent: annotool
Disallow: /private

User-agent: *
Disallow: /admin
"""


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://example.com/", True),
        ("https://example.com/private/page", False),  # rule for us by name
        ("https://example.com/admin", True),  # our own group overrides the * group
    ],
)
def test_robots_rules(url, allowed):
    assert robots_allows(ROBOTS, url) is allowed


def test_wildcard_rules_apply_when_we_are_not_named():
    robots = "User-agent: *\nDisallow: /\n"
    assert robots_allows(robots, "https://example.com/") is False


# Real-world cases where Python's urllib.robotparser gets it wrong (RFC 9309 semantics).


def test_query_rule_does_not_block_the_homepage():
    # google.com: Python's parser turns "Disallow: /?" into "Disallow: /".
    robots = "User-agent: *\nDisallow: /search\nDisallow: /?\nAllow: /search/about\n"
    assert robots_allows(robots, "https://www.google.com/") is True
    assert robots_allows(robots, "https://www.google.com/?q=x") is False
    assert robots_allows(robots, "https://www.google.com/search?q=x") is False
    assert robots_allows(robots, "https://www.google.com/search/about") is True


def test_end_anchor_allows_exactly_the_homepage():
    # quora.com: "Allow: /$" before "Disallow: /".
    robots = "User-agent: *\nAllow: /$\nAllow: /about$\nDisallow: /\n"
    assert robots_allows(robots, "https://www.quora.com/") is True
    assert robots_allows(robots, "https://www.quora.com") is True
    assert robots_allows(robots, "https://www.quora.com/about") is True
    assert robots_allows(robots, "https://www.quora.com/about/team") is False
    assert robots_allows(robots, "https://www.quora.com/What-is-x") is False


def test_longest_match_wins_and_allow_wins_ties():
    robots = "User-agent: *\nDisallow: /shop\nAllow: /shop/public\nDisallow: /a\nAllow: /a\n"
    assert robots_allows(robots, "https://x.com/shop/cart") is False
    assert robots_allows(robots, "https://x.com/shop/public/item") is True
    assert robots_allows(robots, "https://x.com/a") is True  # equal length: allow


def test_wildcards_in_paths():
    robots = "User-agent: *\nDisallow: /*.pdf$\nDisallow: /*/private/\n"
    assert robots_allows(robots, "https://x.com/docs/file.pdf") is False
    assert robots_allows(robots, "https://x.com/docs/file.pdf?v=2") is True  # $ anchors
    assert robots_allows(robots, "https://x.com/team/private/notes") is False
    assert robots_allows(robots, "https://x.com/private") is True


def test_groups_for_the_same_agent_are_merged_and_names_match_case_insensitively():
    robots = (
        "User-agent: AnnoTool\nDisallow: /a\n\n"
        "User-agent: googlebot\nDisallow: /\n\n"
        "User-agent: annotool\nDisallow: /b\n"
    )
    assert robots_allows(robots, "https://x.com/a") is False
    assert robots_allows(robots, "https://x.com/b") is False
    assert robots_allows(robots, "https://x.com/c") is True  # googlebot's group isn't ours


def test_empty_disallow_and_comments():
    robots = "# hello\nUser-agent: * # everyone\nDisallow:\n"
    assert robots_allows(robots, "https://x.com/anything") is True


def test_several_agents_share_one_group():
    robots = "User-agent: foo\nUser-agent: annotool\nDisallow: /x\n"
    assert robots_allows(robots, "https://x.com/x") is False


def test_missing_robots_allows_everything():
    assert robots_allows(None, "https://example.com/anything") is True


def test_robots_checker_fetches_once_per_host():
    fetched: list[str] = []

    def fetch(url: str) -> str | None:
        fetched.append(url)
        return ROBOTS

    checker = RobotsChecker(fetch=fetch)
    assert checker.allows("https://example.com/") is True
    assert checker.allows("https://example.com/private/x") is False
    assert fetched == ["https://example.com/robots.txt"]


def test_robots_checker_skips_file_urls():
    checker = RobotsChecker(fetch=lambda url: pytest.fail("should not fetch"))
    assert checker.allows("file:///C:/tmp/page.html") is None
