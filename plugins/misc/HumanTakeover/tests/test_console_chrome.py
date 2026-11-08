"""Console chrome must follow the host's shadcn shapes.

Three regressions the user pointed at, each with a structural cause:

1. The tabs were three flat, equally weighted labels with rounded top corners -
   they read as a broken tab bar, not as the host's segmented control (a sunken
   track with a raised, shadowed active chip).
2. The sidebar and its inputs were the same white, so the two search fields
   looked like holes punched in the panel. The host's sidebar is a step darker
   than the content area, and controls get their own card surface.
3. Release-takeover was solid destructive red sitting next to the primary blue,
   and AI/human bubbles were solid slabs. Host chrome keeps destructive quiet
   until hover and tints bubbles instead of filling them.

Run from HumanTakeover: python -m pytest tests -q
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "components" / "pages" / "console" / "index.html"


def html() -> str:
    return PAGE.read_text(encoding="utf-8")


def style() -> str:
    match = re.search(r"<style>(.*?)</style>", html(), re.S)
    assert match is not None
    return match.group(1)


def rules(selector: str) -> list[str]:
    """Every rule for an exact selector.

    A selector can appear in more than one rule - `.composer textarea` is in the
    scrollbar list *and* in the layout block - so callers pick the one they mean.
    """
    found = re.findall(re.escape(selector) + r"\s*\{([^{}]*)\}", style())
    assert found, f"missing style rule for {selector}"
    return found


def rule(selector: str) -> str:
    return rules(selector)[0]


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", html(), re.S))


# --- segmented control -------------------------------------------------------

def test_tabs_are_a_segmented_control_not_bare_labels():
    track = rule(".tabs")
    assert "background:" in track, "the tab group needs its own sunken track"
    assert "border-radius" in track
    assert "padding:" in track, "the track needs inset so the active chip can float"

    chip = rule(".tab.active")
    assert "background: var(--langbot-bg" in chip, "the active chip must be raised"
    assert "box-shadow" in chip


def test_tab_corners_are_uniform():
    """`8px 8px 0 0` top-only corners were what made the tabs look half-built."""
    assert "border-radius: 8px 8px 0 0" not in rule(".tab")
    assert "border-radius: var(--r-sm)" in rule(".tab")


# --- surfaces ----------------------------------------------------------------

def test_sidebar_is_darker_than_the_content_area():
    assert "background: var(--muted)" in rule(".sidebar")


def test_search_inputs_paint_their_own_card_surface():
    body = rule(".search-box input")
    assert "background: var(--langbot-bg-card" in body
    assert "padding-left:" in body or "padding: " in body


def test_filters_live_in_one_stack():
    assert "flex-direction: column" in rule(".filters")


# --- destructive + bubbles ---------------------------------------------------

def test_release_takeover_is_quiet_until_hover():
    quiet = rule(".btn-quiet-danger")
    assert "background: var(--muted)" in quiet, "release must not sit on solid red"
    assert ":hover" in style().replace("\n", "") or True
    hover = re.search(r"\.btn-quiet-danger:hover[^{]*\{([^}]*)\}", style())
    assert hover is not None and "background: var(--muted-hover)" in hover.group(1)
    assert "btn btn-quiet-danger" in script(), "the toggle never applies the class"


def test_confirm_still_uses_true_destructive_red():
    """The confirm dialog *is* destructive, so it keeps the solid red."""
    assert "btn btn-danger" in html()


def test_bubbles_are_tinted_not_solid():
    ai = rule(".ai .bubble")
    assert "background: var(--muted)" in ai
    human = rule(".human .bubble")
    assert "color-mix" in human, "human replies should tint the accent, not fill it"


# --- composer ------------------------------------------------------------------

def test_composer_is_one_input_group():
    shell = rule(".composer-shell")
    assert "border: 1px solid" in shell
    assert "border-radius" in shell
    # the focus ring moves to the shell, so the bare textarea must not draw one
    assert "box-shadow: none" in rule(".composer textarea:focus")
    assert 'class="composer-shell"' in html()


def test_composer_keeps_the_wrapping_floor():
    """Still must not be crushable - tool buttons live inside the shell now."""
    layout = next((b for b in rules(".composer textarea") if "flex" in b), None)
    assert layout is not None, "no layout rule for the textarea"
    assert "min-width:" in layout and "min-width: 0" not in layout


# --- info card ---------------------------------------------------------------

def test_info_card_rows_are_an_aligned_grid():
    rows = rule(".card-rows")
    assert "grid-template-columns" in rows
    assert "<dl class=\"card-rows\">" in script()


def test_card_has_a_header_band_and_action_row():
    head = rule(".info-card .card-head")
    assert "border-bottom: 1px solid" in head, "the header needs a divider from the body"
    assert "padding-bottom:" in head
    assert "display: flex" in rule(".card-actions")
    # the old rows were flex pairs drifting against each other
    assert ".info-row " not in style()


def test_card_is_width_capped_to_the_viewport():
    assert "min(340px, calc(100vw - 32px))" in rule(".info-card")
