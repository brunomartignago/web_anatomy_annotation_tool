"""Detect captures that didn't get the real page: bot walls, error pages, blank pages,
and consent banners covering content.

`assess()` is a pure rule over signals the browser collects. Strong signals (HTTP error,
block-page title, bot-wall element, a blank first screen, block-page wording on a short
page) mark the page blocked. Weak signals (small PNG, one viewport tall) only warn: on the
90-site list every real block also had a strong signal, while Google's minimal homepage had
both weak ones. A visible consent banner is a warning too: the rest of the page is usable.

The tool only *detects* walls. It never tries to solve or evade them.
"""

import io
import re
from dataclasses import dataclass, field

from PIL import Image

SMALL_FILE_BYTES = 50_000  # legacy block pages were 7-45 KB; the smallest real page 125 KB
UNIFORM_SHARE = 0.995  # share of the first screen in a single color

BLOCK_TITLE = re.compile(
    r"access denied|just a moment|attention required|are you a (human|robot)|robot check"
    r"|pardon our interruption|request (blocked|rejected)|^\s*(403\s*)?forbidden\s*$"
    r"|verify (you are|you're) (a )?human|security check|unusual traffic|captcha",
    re.IGNORECASE,
)

# Wording of bot checks, region blocks and country gates. Only trusted on short pages,
# since an article can mention these words in passing.
BLOCK_TEXT = re.compile(
    r"(unavailable|not available) in (this|your) (country|region)"
    r"|choose (a|your) (country|region)|select (a|your) (country|region)"
    r"|complete the (verification|security check)|verify (that )?you are (a )?human"
    r"|checking (if the site connection is secure|your browser)|press (&|and) hold"
    r"|enable javascript and cookies to continue|problem providing the content"
    r"|you have been blocked|access to this page has been denied",
    re.IGNORECASE,
)
SHORT_PAGE_VIEWPORTS = 1.5

# Elements that only appear on bot-detection interstitials (must be visible to count).
BOT_WALL_SELECTORS = [
    "#challenge-form",  # Cloudflare
    "#challenge-running",
    "#cf-challenge-running",
    ".cf-turnstile",
    "iframe[src*='challenges.cloudflare.com']",
    "#px-captcha",  # PerimeterX / HUMAN
    "iframe[src*='captcha-delivery.com']",  # DataDome
    "iframe[src*='hcaptcha.com/captcha']",
    "form[action*='validateCaptcha']",  # Amazon
    "#sec-if-cpt-container",  # Akamai
]

# Consent-management banners (must be visible to count).
CONSENT_SELECTORS = [
    "#onetrust-banner-sdk",
    "#onetrust-consent-sdk .onetrust-pc-dark-filter",
    "#CybotCookiebotDialog",
    "#didomi-notice",
    "#qc-cmp2-container",
    "[id^='sp_message_container']",  # Sourcepoint (the Guardian)
    "#truste-consent-track",
    ".fc-consent-root",  # Google Funding Choices
    "#usercentrics-root",
    "#cookie-law-info-bar",
    "[aria-modal='true'][aria-label*='cookie' i]",
]


@dataclass(frozen=True)
class PageSignals:
    http_status: int | None
    title: str | None
    height: int
    viewport_height: int
    file_size: int
    uniformity: float  # share of the first screen in its most common color
    bot_walls: list[str] = field(default_factory=list)  # matched, visible selectors
    consent_banners: list[str] = field(default_factory=list)
    text: str = ""  # start of the page's visible text


@dataclass(frozen=True)
class Assessment:
    blocked: bool
    reasons: list[str]
    warnings: list[str]


def assess(s: PageSignals) -> Assessment:
    strong: list[str] = []
    if s.http_status is not None and s.http_status >= 400:
        strong.append(f"HTTP {s.http_status}")
    if s.title and BLOCK_TITLE.search(s.title):
        strong.append(f"block-page title {s.title.strip()!r}")
    strong += [f"bot wall element {sel}" for sel in s.bot_walls]
    if s.uniformity >= UNIFORM_SHARE:
        strong.append(f"first screen is {s.uniformity:.1%} one color")
    if s.height <= s.viewport_height * SHORT_PAGE_VIEWPORTS and (
        match := BLOCK_TEXT.search(s.text)
    ):
        strong.append(f"block-page text {match.group(0)!r}")

    weak: list[str] = []
    if s.file_size < SMALL_FILE_BYTES:
        weak.append(f"small file ({s.file_size / 1000:.0f} KB)")
    if s.height <= s.viewport_height:
        weak.append("only one viewport tall")

    warnings = [f"consent banner visible: {sel}" for sel in s.consent_banners]
    if strong:
        return Assessment(blocked=True, reasons=strong + weak, warnings=warnings)
    return Assessment(blocked=False, reasons=[], warnings=weak + warnings)


def uniformity(png: bytes) -> float:
    """Share of pixels in the most common (slightly quantized) color, 0-1."""
    with Image.open(io.BytesIO(png)) as img:
        # Nearest-neighbour keeps colors exact; 32 levels per channel absorbs JPEG-ish noise.
        small = img.convert("RGB").resize(
            (480, max(1, img.height * 480 // img.width)), Image.Resampling.NEAREST
        )
    quantized = small.point(lambda v: v // 8 * 8)
    counts = quantized.getcolors(maxcolors=small.width * small.height) or []
    total = small.width * small.height
    return max((n for n, _ in counts), default=0) / total
