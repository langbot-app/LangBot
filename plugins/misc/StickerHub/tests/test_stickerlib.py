"""Pure-helper behaviour of StickerHub's storage layer."""

from __future__ import annotations

from stickerlib import (
    build_media_url,
    filename_for,
    guess_ext,
    media_path,
    normalize_mime,
    parse_data_url,
    sniff_mime,
    slugify,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 8
GIF_BYTES = b"GIF89a" + b"\x00" * 8
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 8


def test_slugify_preserves_unicode_and_collapses_separators():
    assert slugify("Hello World") == "hello-world"
    assert slugify("  Hello   World  ") == "hello-world"
    assert slugify("表情包 😀") == "表情包"
    assert slugify("a__b---c") == "a-b-c"
    assert slugify("") == "sticker"
    assert slugify("...") == "sticker"


def test_slugify_is_stable_and_bounded():
    assert slugify("Cat") == slugify("  cat  ")
    assert len(slugify("x" * 500)) <= 120


def test_sniff_mime_recognises_supported_formats():
    assert sniff_mime(PNG_BYTES) == "image/png"
    assert sniff_mime(JPEG_BYTES) == "image/jpeg"
    assert sniff_mime(GIF_BYTES) == "image/gif"
    assert sniff_mime(WEBP_BYTES) == "image/webp"
    assert sniff_mime(b"BM" + b"\x00" * 8) == "image/bmp"
    assert sniff_mime(b"not an image") is None


def test_guess_ext_maps_mime_and_honours_hint():
    assert guess_ext("image/png") == ".png"
    assert guess_ext("image/jpeg") == ".jpg"
    assert guess_ext("image/gif") == ".gif"
    assert guess_ext("image/webp") == ".webp"
    assert guess_ext(None) == ".jpg"
    assert guess_ext(None, hint="PNG") == ".png"


def test_normalize_mime_prefers_supported_then_sniffed():
    assert normalize_mime(PNG_BYTES, "image/jpeg") == "image/png"
    assert normalize_mime(PNG_BYTES, "image/png") == "image/png"
    assert normalize_mime(PNG_BYTES, None) == "image/png"
    assert normalize_mime(PNG_BYTES, "image/svg+xml") == "image/png"
    assert normalize_mime(b"whatever", "image/png; charset=utf-8") == "image/png"
    assert normalize_mime(b"whatever", None) is None
    assert normalize_mime(b"whatever", "text/plain") == "text/plain"


def test_filename_is_ascii_and_content_derived():
    first = filename_for("表情包", "a" * 64, ".png")
    second = filename_for("表情包", "a" * 64, ".png")
    third = filename_for("表情包", "b" * 64, ".png")
    assert first == second
    assert first != third
    assert first.endswith(".png")
    assert "表情包" not in first
    assert first.isascii()
    assert len(first) <= 64


def test_media_path_is_plugin_relative():
    assert media_path("cat-abc.png") == "assets/stickers/cat-abc.png"


def test_build_media_url_absolute_and_relative():
    base = "https://bot.example.com"
    url = build_media_url(
        public_base_url=base,
        author="langbot-team",
        plugin_name="StickerHub",
        filename="cat.png",
    )
    assert url == "https://bot.example.com/api/v1/plugins/langbot-team/StickerHub/assets/stickers/cat.png"
    relative = build_media_url(
        public_base_url="",
        author="langbot-team",
        plugin_name="StickerHub",
        filename="cat.png",
    )
    assert relative == "/api/v1/plugins/langbot-team/StickerHub/assets/stickers/cat.png"


def test_parse_data_url_extracts_bytes_and_mime():
    data, mime = parse_data_url("data:image/png;base64," + "AAAA")
    assert mime == "image/png"
    assert data == bytes.fromhex("000000")
    assert parse_data_url("not a data url") == (b"", None)
