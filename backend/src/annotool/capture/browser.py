"""Full-page capture with Playwright Chromium.

One screenshot with `full_page=True` (no stitching), so fixed and sticky headers appear
once (AUDIT #17). The viewport is 1920x1080 at a device scale factor of 1, so image pixels
equal CSS pixels and DOM boxes captured later (roadmap 1.3) line up with the PNG.
"""

import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType

from playwright.sync_api import Browser, Page, Playwright, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AwareDatetime, BaseModel

from annotool import __version__
from annotool.capture.urls import UrlEntry
from annotool.capture.walls import (
    BOT_WALL_SELECTORS,
    CONSENT_SELECTORS,
    PageSignals,
    assess,
    uniformity,
)
from annotool.images import image_size
from annotool.models import Viewport
from annotool.project import write_json_atomic

IMAGE_NAME = "page.png"
META_NAME = "meta.json"

# Scrolls down one step at a time so lazy-loaded content renders, then returns to the top.
# Capped so infinite-scroll pages terminate. `behavior: 'instant'` overrides pages that set
# `scroll-behavior: smooth` (e.g. MDN): otherwise the jump back to the top animates, and a
# screenshot taken mid-animation draws sticky headers far down the page.
_SCROLL_JS = """
async ({ step, delayMs, maxSteps }) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const root = document.scrollingElement || document.documentElement;
  const scrollTo = top => window.scrollTo({ top, left: 0, behavior: 'instant' });
  let steps = 0;
  for (let y = 0; steps < maxSteps; y += step) {
    scrollTo(y);
    steps++;
    await sleep(delayMs);
    if (window.scrollY + window.innerHeight >= root.scrollHeight) break;
  }
  const reachedEnd = window.scrollY + window.innerHeight >= root.scrollHeight;
  scrollTo(0);
  return { steps, scrollHeight: root.scrollHeight, reachedEnd };
}
"""

# Which of the given selectors match an element that is actually rendered.
_VISIBLE_JS = """
selectors => selectors.filter(sel => {
  let els;
  try { els = document.querySelectorAll(sel); } catch { return false; }
  return [...els].some(el => {
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && style.visibility !== 'hidden';
  });
})
"""


@dataclass(frozen=True)
class CaptureSettings:
    viewport_width: int = 1920
    viewport_height: int = 1080
    locale: str = "en-US"
    timeout_s: float = 60
    network_idle_s: float = 10
    scroll_delay_ms: int = 250
    max_scroll_steps: int = 60  # 60 x 1080 px ≈ 65,000 px of page
    settle_ms: int = 1000


class ScrollInfo(BaseModel):
    steps: int
    scroll_height: int
    reached_end: bool  # False when max_scroll_steps ran out (e.g. infinite scroll)
    returned_to_top: bool  # False when the page kept scrolling itself; sticky parts may be off


class CaptureMeta(BaseModel):
    """Contents of `meta.json`, written next to `page.png`."""

    page_id: str
    url: str
    final_url: str
    title: str | None = None
    category: str | None = None
    page_type: str | None = None
    http_status: int | None = None
    locale: str | None = None
    image: str = IMAGE_NAME
    width: int
    height: int
    file_size: int
    viewport: Viewport
    captured_at: AwareDatetime
    duration_s: float
    scroll: ScrollInfo
    # Bot wall, error page or blank capture: not the real page (see capture/walls.py).
    blocked: bool = False
    blocked_reasons: list[str] = []
    warnings: list[str] = []  # usable, but check it (consent banner, short page...)
    consent_clicked: str | None = None  # selector from project.yaml › consent_clicks
    user_agent: str
    tool: str = f"annotool {__version__}"


class Capturer:
    """Keeps one Chromium open across pages; each page gets a fresh browser context."""

    def __init__(self, settings: CaptureSettings | None = None):
        self.settings = settings or CaptureSettings()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def __enter__(self) -> "Capturer":
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch()
        except BaseException:
            self._playwright.stop()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def capture(
        self, entry: UrlEntry, out_dir: Path, consent_clicks: Sequence[str] = ()
    ) -> CaptureMeta:
        """Capture one page into `out_dir/page.png` and `out_dir/meta.json`.

        `consent_clicks`: CSS selectors to try, in order, to dismiss a consent banner before
        scrolling (searched in every frame; the first visible match is clicked).
        """
        if self._browser is None:
            raise RuntimeError("use Capturer as a context manager")
        s = self.settings
        out_dir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        context = self._browser.new_context(
            viewport={"width": s.viewport_width, "height": s.viewport_height},
            device_scale_factor=1,
            locale=s.locale,
        )
        try:
            page = context.new_page()
            response = page.goto(
                entry.url, wait_until="domcontentloaded", timeout=s.timeout_s * 1000
            )
            try:
                page.wait_for_load_state("networkidle", timeout=s.network_idle_s * 1000)
            except PlaywrightTimeoutError:
                pass  # busy pages (ads, analytics) never go idle; scrolling still helps

            consent_clicked = _click_first(page, consent_clicks)
            scroll = page.evaluate(
                _SCROLL_JS,
                {
                    "step": s.viewport_height,
                    "delayMs": s.scroll_delay_ms,
                    "maxSteps": s.max_scroll_steps,
                },
            )
            # Some pages scroll themselves (restored positions, scripted animations).
            try:
                page.wait_for_function("window.scrollY === 0", timeout=5000)
                returned_to_top = True
            except PlaywrightTimeoutError:
                returned_to_top = False  # capture anyway; meta.json records it
            page.wait_for_timeout(s.settle_ms)

            bot_walls = page.evaluate(_VISIBLE_JS, BOT_WALL_SELECTORS)
            consent_banners = page.evaluate(_VISIBLE_JS, CONSENT_SELECTORS)
            text = page.evaluate("(document.body?.innerText || '').slice(0, 3000)")
            first_screen = page.screenshot(type="png", animations="disabled")

            # Write to a temp name first so an interrupted capture never leaves a half PNG.
            tmp = out_dir / f".{IMAGE_NAME}.tmp"
            page.screenshot(
                path=tmp,
                type="png",
                full_page=True,
                animations="disabled",
                timeout=s.timeout_s * 2000,
            )
            os.replace(tmp, out_dir / IMAGE_NAME)
            width, height = image_size(out_dir / IMAGE_NAME)
            file_size = (out_dir / IMAGE_NAME).stat().st_size

            title = page.title() or None
            http_status = response.status if response else None
            verdict = assess(
                PageSignals(
                    http_status=http_status,
                    title=title,
                    height=height,
                    viewport_height=s.viewport_height,
                    file_size=file_size,
                    uniformity=uniformity(first_screen),
                    bot_walls=bot_walls,
                    consent_banners=consent_banners,
                    text=text,
                )
            )
            warnings = list(verdict.warnings)
            if not scroll["reachedEnd"]:
                warnings.append(f"stopped scrolling after {s.max_scroll_steps} steps")
            if not returned_to_top:
                warnings.append("page did not return to the top; sticky parts may be misplaced")

            meta = CaptureMeta(
                page_id=entry.page_id,
                url=entry.url,
                final_url=page.url,
                title=title,
                category=entry.category,
                page_type=entry.page_type,
                http_status=http_status,
                locale=page.evaluate("document.documentElement.lang") or None,
                width=width,
                height=height,
                file_size=file_size,
                viewport=Viewport(width=s.viewport_width, height=s.viewport_height),
                captured_at=datetime.now().astimezone(),
                duration_s=round(time.monotonic() - started, 2),
                scroll=ScrollInfo(
                    steps=scroll["steps"],
                    scroll_height=scroll["scrollHeight"],
                    reached_end=scroll["reachedEnd"],
                    returned_to_top=returned_to_top,
                ),
                blocked=verdict.blocked,
                blocked_reasons=verdict.reasons,
                warnings=warnings,
                consent_clicked=consent_clicked,
                user_agent=page.evaluate("navigator.userAgent"),
            )
        finally:
            context.close()

        write_json_atomic(out_dir / META_NAME, meta.model_dump(mode="json", exclude_none=True))
        return meta


def _click_first(page: Page, selectors: Sequence[str]) -> str | None:
    """Click the first selector that is visible in any frame. Returns it, or None."""
    for selector in selectors:
        for frame in page.frames:
            try:
                target = frame.locator(selector).first
                if not target.is_visible():
                    continue
                target.click(timeout=3000)
            except PlaywrightError:
                continue  # invalid selector, detached frame, covered button...
            page.wait_for_timeout(1500)  # let the banner animate away
            return selector
    return None
