import io

import pytest
from PIL import Image, ImageDraw

from annotool.capture.walls import PageSignals, assess, uniformity


def signals(**overrides) -> PageSignals:
    """A healthy page by default."""
    base = {
        "http_status": 200,
        "title": "Home",
        "height": 6000,
        "viewport_height": 1080,
        "file_size": 2_000_000,
        "uniformity": 0.4,
        "bot_walls": [],
        "consent_banners": [],
        "text": "Welcome to our store",
    }
    return PageSignals(**{**base, **overrides})


def test_healthy_page_is_not_blocked():
    result = assess(signals())
    assert not result.blocked
    assert result.reasons == [] and result.warnings == []


# ── Strong signals: any one blocks ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"http_status": 403}, "HTTP 403"),
        ({"http_status": 503}, "HTTP 503"),
        ({"title": "Access Denied"}, "Access Denied"),
        ({"title": "Just a moment..."}, "Just a moment"),
        ({"title": "Robot Check"}, "Robot Check"),
        ({"title": "Pardon Our Interruption"}, "Pardon Our Interruption"),
        ({"bot_walls": ["#px-captcha"]}, "#px-captcha"),
        ({"uniformity": 0.999}, "one color"),
    ],
)
def test_strong_signal_blocks(overrides, reason):
    result = assess(signals(**overrides))
    assert result.blocked
    assert any(reason in r for r in result.reasons)


def test_ordinary_titles_are_not_block_titles():
    for title in ["Access to justice | Law Society", "Wait, what? Explained", "Captain Marvel"]:
        assert not assess(signals(title=title)).blocked, title


# ── Weak signals only warn ───────────────────────────────────────────────────


def test_weak_signals_only_warn():
    # Google's homepage was one viewport tall and 30 KB, and perfectly usable.
    result = assess(signals(height=1080, file_size=30_000))
    assert not result.blocked
    assert any("one viewport" in w for w in result.warnings)
    assert any("small file" in w for w in result.warnings)


# ── Block-page text: strong, but only on a short page ────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Pandora is unavailable in this country or region",
        "Hello! Choose a country. Canada United States",  # Best Buy's gate
        "To continue, please complete the verification test below.",  # trip.com slider
        "Checking your browser before accessing example.com",
        "Press & Hold to confirm you are a human (and not a bot).",
        "Please enable JavaScript and cookies to continue",
    ],
)
def test_block_text_on_a_short_page_blocks(text):
    result = assess(signals(height=1080, text=text))
    assert result.blocked
    assert any("block-page text" in r for r in result.reasons)


def test_block_text_on_a_long_page_is_ignored():
    # A news article can mention "unavailable in this country" in passing.
    text = "The service is unavailable in this country or region, the minister said..."
    assert not assess(signals(height=9000, text=text)).blocked


# ── Consent banners warn but don't block ─────────────────────────────────────


def test_visible_consent_banner_is_a_warning():
    result = assess(signals(consent_banners=["#onetrust-banner-sdk"]))
    assert not result.blocked
    assert any("#onetrust-banner-sdk" in w for w in result.warnings)


# ── Image uniformity ─────────────────────────────────────────────────────────


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_blank_image_is_fully_uniform():
    assert uniformity(png_bytes(Image.new("RGB", (1920, 1080), "white"))) == 1.0


def test_page_with_content_is_not_uniform():
    img = Image.new("RGB", (1920, 1080), "white")
    draw = ImageDraw.Draw(img)
    for i in range(12):  # a grid of "cards"
        x, y = 100 + (i % 4) * 450, 100 + (i // 4) * 320
        draw.rectangle([x, y, x + 400, y + 280], fill=(30 + i * 15, 90, 160))
    assert uniformity(png_bytes(img)) < 0.6


def test_access_denied_style_page_is_nearly_uniform():
    img = Image.new("RGB", (1920, 1080), "white")
    ImageDraw.Draw(img).rectangle([10, 10, 500, 40], fill="black")  # one line of text
    assert uniformity(png_bytes(img)) > 0.99
