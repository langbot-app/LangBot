"""The console's empty states must look like the host's, not like a bare hint.

The first ship of this page put a 35%-opacity outline glyph and one line of
grey text in the middle of a 500 px pane - it read as "broken", and the user
said so. The host (shadcn) always gives an empty state an icon on a tinted
badge, a real title, and a line of direction; the sidebar additionally frames
it with a dashed box. These tests pin that shape so a later restyle cannot
quietly drop back to a floating icon.

They also pin the two states being *distinct*: "no sessions at all" tells you
how sessions appear, "nothing matched the filter" tells you to clear it. One
shared string for both is the regression.

Run from HumanTakeover: python -m pytest tests -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "components" / "pages" / "console" / "index.html"
I18N = PAGE.parent / "i18n"
LOCALES = ("en_US", "zh_Hans")


def html() -> str:
    return PAGE.read_text(encoding="utf-8")


def style() -> str:
    match = re.search(r"<style>(.*?)</style>", html(), re.S)
    assert match is not None
    return match.group(1)


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", html(), re.S))


def rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", style())
    assert match is not None, f"missing style rule for {selector}"
    return match.group(1)


def translations(locale: str) -> dict[str, str]:
    return json.loads((I18N / f"{locale}.json").read_text(encoding="utf-8"))


# --- the empty state is built from parts, not one grey line ------------------

def test_chat_empty_state_has_badge_title_and_direction():
    body = re.search(r'<div class="empty" id="chatEmpty">(.*?)\n      </div>', html(), re.S)
    assert body is not None, "chatEmpty block is missing"
    markup = body.group(1)
    assert 'class="empty-badge"' in markup, "the icon needs a tinted badge behind it"
    assert 'class="empty-title"' in markup, "an empty state needs a real title"
    assert 'class="empty-sub"' in markup, "an empty state needs a line of direction"
    # all three copy slots must be translatable
    for key in ("selectSessionTitle", "selectSession", "selectSessionHint"):
        assert f'data-i18n="{key}"' in markup, f"{key} is not translatable"


def test_badge_is_a_tinted_circle_not_a_faint_outline():
    badge = rule(".empty-badge")
    assert "border-radius: 999px" in badge.replace("border-radius:999px", "border-radius: 999px")
    assert "background: var(--muted)" in badge, "badge needs a surface, not just an outline"
    assert "color: var(--langbot-text-muted" in badge
    # the old implementation faded the whole glyph to 35% instead
    assert 'class="empty-icon"' not in html()
    assert "opacity: .35" not in style()


def test_sidebar_empty_state_is_framed():
    """Sidebar emptiness is boxed so it cannot read as a stray label."""
    framed = rule(".list-empty")
    assert "border: 1px dashed" in framed
    assert "border-radius" in framed
    assert 'class="list-empty"' in script(), "the list must render the framed state"


# --- "no sessions" and "filter matched nothing" are different states ---------

def test_list_empty_distinguishes_filtered_from_empty():
    body = script()
    assert "noMatch" in body, "a filtered-out list needs its own copy"
    assert "noSessionsTitle" in body
    # the old page printed one string for both cases
    assert "t('noSessions','暂无会话')" not in body


def test_empty_states_are_fully_translated():
    for locale in LOCALES:
        strings = translations(locale)
        for key in (
            "selectSessionTitle",
            "selectSession",
            "selectSessionHint",
            "noSessionsTitle",
            "noSessions",
            "noMatch",
            "noMatchHint",
        ):
            assert strings.get(key), f"{locale} is missing {key}"


def test_locales_have_not_drifted():
    en, zh = translations("en_US"), translations("zh_Hans")
    assert en.keys() == zh.keys(), "one locale gained a key the other did not"


def test_no_chinese_leaks_into_the_english_file():
    cjk = re.compile(r"[\u4e00-\u9fff]")
    for key, value in translations("en_US").items():
        assert not cjk.search(value), f"en_US.{key} is still Chinese: {value!r}"
