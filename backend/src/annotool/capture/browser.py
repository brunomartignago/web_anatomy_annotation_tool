"""Full-page capture with Playwright Chromium.

One screenshot with `full_page=True` (no stitching), so fixed and sticky headers appear
once (AUDIT #17). The viewport is 1920x1080 at a device scale factor of 1, so image pixels
equal CSS pixels and DOM boxes captured later (roadmap 1.3) line up with the PNG.
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType

from playwright.sync_api import Browser, Playwright, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AwareDatetime, BaseModel

from annotool import __version__
from annotool.capture.urls import UrlEntry
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
    viewport: Viewport
    captured_at: AwareDatetime
    duration_s: float
    scroll: ScrollInfo
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

    def capture(self, entry: UrlEntry, out_dir: Path) -> CaptureMeta:
        """Capture one page into `out_dir/page.png` and `out_dir/meta.json`."""
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

            meta = CaptureMeta(
                page_id=entry.page_id,
                url=entry.url,
                final_url=page.url,
                title=page.title() or None,
                category=entry.category,
                page_type=entry.page_type,
                http_status=response.status if response else None,
                locale=page.evaluate("document.documentElement.lang") or None,
                width=width,
                height=height,
                viewport=Viewport(width=s.viewport_width, height=s.viewport_height),
                captured_at=datetime.now().astimezone(),
                duration_s=round(time.monotonic() - started, 2),
                scroll=ScrollInfo(
                    steps=scroll["steps"],
                    scroll_height=scroll["scrollHeight"],
                    reached_end=scroll["reachedEnd"],
                    returned_to_top=returned_to_top,
                ),
                user_agent=page.evaluate("navigator.userAgent"),
            )
        finally:
            context.close()

        write_json_atomic(out_dir / META_NAME, meta.model_dump(mode="json", exclude_none=True))
        return meta
