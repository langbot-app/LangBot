"""UI regressions behind the reported screenshot.

Each assertion pins one visible defect from the report: the reversed action
hierarchy, the name above the preview, the always-visible "load more" button,
the un-converted kilobyte header, the double count, the missing failure
placeholder and the unannounced toast.
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "components" / "pages" / "hub" / "index.html"


def html() -> str:
    return PAGE.read_text(encoding="utf-8")


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", html(), re.S))


def styles() -> str:
    return re.search(r"<style>(.*?)</style>", html(), re.S).group(1)


def card_markup() -> str:
    body = script()
    start = body.index("'<div class=\"card\"")
    return body[start: body.index("</div>');", start) + 12]


def test_copy_outranks_delete_on_a_card():
    card = card_markup()
    assert 'class="ghost copy"' in card, "copy should carry the primary variant"
    assert 'class="ghost danger"' in card
    # The search strings share the data-action=" prefix, so compare the
    # action names themselves.
    assert card.index('"copy"') < card.index('"delete"')


def test_delete_is_not_painted_solid_red():
    style = styles()
    danger = [ln for ln in style.splitlines() if "button.ghost.danger {" in ln]
    assert danger, "danger state must stay scoped to the ghost variant"
    assert "#ef4444" not in danger[0], "resting delete must not be solid red"
    assert "#dc2626" in "\n".join(
        ln for ln in style.splitlines() if "button.ghost.danger:hover" in ln
    ), "hover is what should turn it red"


def test_names_sit_below_the_preview():
    card = card_markup()
    assert card.index('class="thumb"') < card.index('class="name"')


def test_load_more_uses_one_toggle():
    body = script()
    assert "'more').hidden" in body, "the button should toggle the hidden attribute"
    assert "style.display" not in body, "display plus visibility used to fight each other"
    assert "style.visibility" not in body


def test_header_size_is_human_readable():
    body = script()
    assert "display_bytes" in body, "the stats endpoint already formats the size"
    assert "/ 1024).toFixed(1) + ' KB'" in body, "the header must not print raw KB"


def test_total_is_not_counted_twice():
    body = script()
    stats = body[body.index("async function loadStats"): body.index("async function loadList")]
    assert "'{n} 个表情包" not in stats, "the sticker count belongs to the footer only"
    assert "stats', '已用 {used}" in stats


def test_failed_image_falls_back_to_a_placeholder():
    body = script()
    assert "classList.add('failed')" in body
    assert "naturalWidth" in body, "a cached broken image only reports via naturalWidth"


def test_toast_is_announced():
    markup = html()
    assert re.search(r'id="toast"[^>]*aria-live="polite"', markup)
    assert re.search(r'id="toast"[^>]*role="status"', markup)
