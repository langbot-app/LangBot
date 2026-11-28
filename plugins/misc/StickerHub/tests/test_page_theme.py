"""The management page must follow the host theme (light *and* dark).

The surrounding WebUI renders plugin pages in an iframe and pushes the theme
through ``{type: 'langbot:context', theme}``; the page SDK turns that into the
``--langbot-*`` custom properties below. Any colour that is painted with a
hard-coded light value, or with a property the SDK never defines, stays light
in dark mode - which is exactly the bug these tests pin down.
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "components" / "pages" / "hub" / "index.html"

# Every custom property the bundled page SDK actually sets (see
# langbot_plugin/assets/langbot-page-sdk.js -> applyTheme).
SDK_PROPERTIES = {
    "--langbot-bg",
    "--langbot-bg-card",
    "--langbot-text",
    "--langbot-text-muted",
    "--langbot-border",
    "--langbot-accent",
}

# Surfaces that must be painted from the theme, never from a fixed colour.
THEMED_SURFACES = ("body", "header", ".toolbar", ".card", "input", ".toast")


def page_html() -> str:
    return PAGE.read_text(encoding="utf-8")


def style_block() -> str:
    match = re.search(r"<style>(.*?)</style>", page_html(), re.S)
    assert match is not None, "page must keep an inline <style> block"
    return match.group(1)


def test_page_references_the_sdk_bootstrap():
    """Theme sync only exists if the page loads the SDK that receives it."""
    assert "/api/v1/plugins/_sdk/page-sdk.js" in page_html()


def test_every_custom_property_is_one_the_sdk_defines():
    used = set(re.findall(r"var\((--langbot-[a-z-]+)", style_block()))
    assert used, "the page should theme itself through --langbot-* properties"
    undefined = used - SDK_PROPERTIES
    assert not undefined, (
        "these properties are never set by the page SDK, so their hard-coded "
        f"fallback would always win: {sorted(undefined)}"
    )


def rules_by_selector(style: str) -> dict[str, str]:
    """Map every individual selector to its declaration block."""
    rules: dict[str, str] = {}
    for selector_list, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style):
        for selector in selector_list.split(","):
            selector = selector.strip()
            if selector:
                rules.setdefault(selector, "")
                rules[selector] += body
    return rules


def test_surface_backgrounds_are_themed():
    rules = rules_by_selector(style_block())
    for selector in THEMED_SURFACES:
        assert selector in rules, f"missing style block for {selector}"
        assert "var(--langbot-" in rules[selector], (
            f"{selector} paints a fixed colour and will not follow dark mode"
        )


def test_no_hardcoded_white_background_survives():
    style = style_block()
    offenders = [
        line.strip()
        for line in style.splitlines()
        if "background" in line and re.search(r"#[fF]{3,6}\b|white", line)
        and "var(--langbot-" not in line
    ]
    # Destructive red is deliberately theme-independent: it must stay red on both.
    offenders = [o for o in offenders if "#dc2626" not in o and "#ef4444" not in o]
    assert not offenders, f"hard-coded light backgrounds remain: {offenders}"


# --- response contract -------------------------------------------------------
# langbot.api() resolves the already-unwrapped payload (page SDK: resolve(data.data)),
# so reading `res.data.xxx` always yields undefined.
def script_block() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", page_html(), re.S))


def test_page_does_not_double_unwrap_api_payload():
    script = script_block()
    # Ignore comments: the shape is documented by name in a comment.
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", script, flags=re.S)
    offenders = re.findall(r"res\.data", code)
    assert not offenders, f"res.data is always undefined, found {len(offenders)} uses"


def test_stats_never_prints_undefined_capacity():
    script = script_block()
    stats = re.search(r"async function loadStats\(\)\s*\{(.*?)\n    \}", script, re.S)
    assert stats is not None
    assert "max_sticker_bytes" in stats.group(1)
    assert "typeof capBytes" in stats.group(1), (
        "capacity must be guarded so the header never reads 'undefined'"
    )


def test_empty_state_is_rendered_not_just_text():
    script = script_block()
    assert "还没有表情包" in script
    assert "status.innerHTML" in script, "empty state should carry an icon + hint"
