"""Previews must be served by URL, never by base64 in the list response.

``/list`` already returns a stable ``item.url``; shipping the bytes again as
base64 in every card doubled the transfer and made a 60-sticker page 60 extra
page-api round trips.
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "components" / "pages" / "hub" / "index.html"


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", PAGE.read_text(encoding="utf-8"), re.S))


def test_card_image_src_is_the_stable_url():
    body = script()
    assert 'src="' in body
    assert "item.url" in body
    assert "absoluteUrl(item.url)" in body


def test_thumbnails_lazy_load_and_decode_async():
    body = script()
    assert 'loading="lazy"' in body
    assert 'decoding="async"' in body


def test_image_builders_use_relative_paths_against_the_page_origin():
    body = script()
    assert "location.origin" in body, "relative asset paths need an absolute src"


def test_image_endpoint_is_only_a_fallback():
    body = script()
    # The single /image call sits inside the error handler, not in loadList.
    load_list = body[body.index("async function loadList"):body.index("function wireThumbs")]
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", load_list, flags=re.S)
    assert "/image" not in code, "loadList must not fetch previews"
    error_handler = body[body.index("img.addEventListener('error'"):]
    assert "'/image'" in error_handler[:600]


def test_failed_thumb_shows_a_placeholder():
    body = script()
    assert "classList.add('failed')" in body
    assert "imageFailed" in body


def test_page_never_reads_a_nested_data_wrapper():
    """langbot.api() resolves the unwrapped payload, so `.data` is always undefined."""
    body = script()
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S)
    assert "item.data" not in code
    assert "res.data" not in code
    assert "item && item.url" in code


def test_page_does_not_guard_on_the_never_set_error_property():
    """Failures reject the promise; the resolved value never carries `.error`."""
    body = script()
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S)
    assert "res.error" not in code
    assert code.count("catch (err)") >= 5, "every call should catch its own rejection"


def test_asset_urls_are_built_from_the_host_origin():
    """The iframe is a blob: document on an opaque origin, so relative URLs die."""
    body = script()
    assert "ancestorOrigins" in body
    absolute = body[body.index("function absoluteUrl"): body.index("function failText")]
    assert "hostOrigin()" in absolute
    assert "location.origin" not in absolute, "an opaque origin is the string 'null'"


def test_empty_url_is_reported_instead_of_silently_copying():
    body = script()
    assert "copyNoUrl" in body
    copy = body[body.index("async function copyText"): body.index("async function loadStats")]
    assert "if (!text)" in copy
