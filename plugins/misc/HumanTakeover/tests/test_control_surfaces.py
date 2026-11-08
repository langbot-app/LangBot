"""Every form control must paint its own themed surface.

A control that only sets border/text keeps the browser's default white
background, which turns into a white slab on the dark theme. The search box
shipped like that, so these tests guard every control rule.
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "components" / "pages" / "console" / "index.html"


def style() -> str:
    match = re.search(r"<style>(.*?)</style>", PAGE.read_text(encoding="utf-8"), re.S)
    assert match is not None
    return match.group(1)


def control_rules():
    """(selector, body) for rules that style a text input."""
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style()):
        selector = selector.strip().splitlines()[-1].strip()
        # :focus / :disabled variants inherit the base rule's surface
        if "input" in selector and "hidden" not in body and not re.search(r":\w", selector):
            yield selector, body


def test_every_text_input_declares_a_background():
    missing = [
        selector
        for selector, body in control_rules()
        if "background" not in body and "border" in body  # a real visual box
    ]
    assert not missing, f"controls fall back to the UA white: {missing}"


def test_text_inputs_use_theme_tokens_not_literals():
    for selector, body in control_rules():
        if "background" in body:
            assert "var(--langbot-" in body, f"{selector} paints a literal colour"


def test_composer_textarea_cannot_be_crushed():
    """Icon buttons must not squeeze the input to a sliver.

    A bare `flex: 1` leaves min-width:auto, so on a narrow pane the textarea
    collapsed to ~43px and showed "输…". It needs a real floor plus a wrapping row.
    """
    style_text = style()
    rules = re.findall(r"(?:^|\n)\s*\.composer textarea \{(.*?)\}", style_text, re.S)
    assert rules, "no standalone .composer textarea rule"
    rule = None
    body = next((b for b in rules if "flex" in b), rules[0])
    assert "min-width:" in body and "min-width: 0" not in body, (
        "textarea needs a positive min-width, not 0"
    )
    row = re.search(r"\.composer-row \{(.*?)\}", style_text, re.S)
    assert row is not None and "flex-wrap: wrap" in row.group(1), (
        "the composer row must wrap instead of crushing the input"
    )
