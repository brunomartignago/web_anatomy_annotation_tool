"""Screenshot → cached vertical WebP strips, so the browser never loads a full page.

Pages are 1920 px wide and up to ~91,000 px tall (AUDIT #11). A strip
is the full width and `STRIP_HEIGHT` rows; the last one is shorter. Strips live in the page's
`.cache/strips/` next to a `source.json` stamp (size + mtime of page.png), so a recapture
regenerates them.

PNG can't be decoded from the middle, so the first request for a page cuts *all* its strips
in one pass. That decodes the screenshot once (about 525 MB for the Unsplash page in RGB);
every later request is a plain file read.
"""

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path

from PIL import Image

from annotool.images import image_size

STRIP_HEIGHT = 2048
STRIP_QUALITY = 85  # lossy WebP; small text stays readable at this quality
STRIP_DIR = Path(".cache") / "strips"
_STAMP = "source.json"

_locks: dict[Path, threading.Lock] = {}
_locks_guard = threading.Lock()


def strip_count(height: int, strip_height: int = STRIP_HEIGHT) -> int:
    return -(-height // strip_height)


def strip_bounds(n: int, height: int, strip_height: int = STRIP_HEIGHT) -> tuple[int, int]:
    """Top (inclusive) and bottom (exclusive) image rows of strip `n`."""
    if not 0 <= n < strip_count(height, strip_height):
        raise IndexError(f"strip {n} is out of range for a {height}-px image")
    top = n * strip_height
    return top, min(top + strip_height, height)


def _lock_for(folder: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(folder.resolve(), threading.Lock())


class StripCache:
    """The strips of one page folder's screenshot."""

    def __init__(
        self,
        page_folder: Path,
        image_name: str = "page.png",
        strip_height: int = STRIP_HEIGHT,
        quality: int = STRIP_QUALITY,
    ):
        self.image = Path(page_folder) / image_name
        self.folder = Path(page_folder) / STRIP_DIR
        self.strip_height = strip_height
        self.quality = quality

    def _source(self) -> dict:
        stat = self.image.stat()  # FileNotFoundError when there's no screenshot
        return {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "strip_height": self.strip_height,
            "quality": self.quality,
        }

    def version(self) -> str:
        """Changes whenever the strips would change; used for HTTP ETags."""
        s = self._source()
        return f"{s['size']:x}-{s['mtime_ns']:x}-{s['strip_height']}-{s['quality']}"

    def count(self) -> int:
        return strip_count(image_size(self.image)[1], self.strip_height)

    def path(self, n: int) -> Path:
        """The WebP file for strip `n`, cutting all strips first if the cache is stale."""
        with _lock_for(self.folder):
            source = self._source()
            count = self._fresh_count(source)
            if count is None:
                count = self._generate(source)
            if not 0 <= n < count:
                raise IndexError(f"strip {n} is out of range for {self.image}")
            return self.folder / f"{n}.webp"

    def _fresh_count(self, source: dict) -> int | None:
        """Number of cached strips, or None if the cache doesn't match the screenshot."""
        try:
            stamp = json.loads((self.folder / _STAMP).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        count = stamp.pop("count", None)
        return count if stamp == source and isinstance(count, int) else None

    def _generate(self, source: dict) -> int:
        # ignore_errors: on Windows a strip still being sent to the browser can't be deleted.
        # It is overwritten below or, if the new page is shorter, left unused.
        shutil.rmtree(self.folder, ignore_errors=True)
        self.folder.mkdir(parents=True, exist_ok=True)
        with Image.open(self.image) as img:
            width, height = img.size
            img.load()
            count = strip_count(height, self.strip_height)
            for n in range(count):
                top, bottom = strip_bounds(n, height, self.strip_height)
                strip = img.crop((0, top, width, bottom))
                if strip.mode not in ("RGB", "RGBA"):
                    strip = strip.convert("RGBA" if "transparency" in img.info else "RGB")
                self._save_atomic(strip, self.folder / f"{n}.webp")
        # Written last: an interrupted run leaves no stamp and is redone next time.
        stamp = {**source, "count": count}
        (self.folder / _STAMP).write_text(json.dumps(stamp), encoding="utf-8")
        return count

    def _save_atomic(self, strip: Image.Image, path: Path) -> None:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        os.close(fd)
        try:
            strip.save(tmp, format="WEBP", quality=self.quality)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
