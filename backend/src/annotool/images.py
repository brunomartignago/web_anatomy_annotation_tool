"""Image helpers. Screenshots are local, trusted files, and full pages can be
very tall (91,086 px for Unsplash), so Pillow's decompression-bomb guard is off.
"""

from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def image_size(path: Path) -> tuple[int, int]:
    """Width and height in pixels. Reads only the header, not the pixels."""
    with Image.open(path) as img:
        return img.size
