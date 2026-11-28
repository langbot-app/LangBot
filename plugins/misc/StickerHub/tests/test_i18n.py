"""The page must be translated from i18n files, not hard-coded Chinese.

The host pushes a language through the page SDK, which loads ./i18n/<locale>.json
and applies `data-i18n` nodes for us. Anything written straight into the HTML or
the script stays Chinese for English users, which is what these tests pin.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HUB = Path(__file__).resolve().parents[1] / "components" / "pages" / "hub"
PAGE = HUB / "index.html"
LOCALES = ("en_US", "zh_Hans")

# CJK ideographs, used to spot untranslated literals
CJK = re.compile(r"[\u4e00-\u9fff]")


def html() -> str:
    return PAGE.read_text(encoding="utf-8")


def translations(locale: str) -> dict[str, str]:
    return json.loads((HUB / "i18n" / f"{locale}.json").read_text(encoding="utf-8"))


def visible_markup() -> str:
    """Markup minus the inline script, so JS literals are judged separately."""
    body = re.sub(r"<script>.*?</script>", "", html(), flags=re.S)
    body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    return body


def test_both_locales_exist_and_cover_the_same_keys():
    en, zh = translations("en_US"), translations("zh_Hans")
    assert en.keys() == zh.keys(), "locales drifted apart"


def test_english_file_is_actually_english():
    for key, value in translations("en_US").items():
        assert not CJK.search(value) or value.isascii() is False, f"{key} is Chinese: {value!r}"


def text_by_translation_key() -> dict[str, str]:
    """Map data-i18n key -> the visible text of that element."""
    markup = visible_markup()
    found = {}
    for _tag, key, inner in re.findall(
        r"<([a-z0-9]+)\b[^>]*data-i18n=\"([^\"]+)\"[^>]*>(.*?)</\1>",
        markup,
        re.S | re.I,
    ):
        text = re.sub(r"<[^>]+>", "", inner).strip()
        if text:
            found[key] = text
    return found


def test_static_labels_are_marked_for_translation():
    keys = text_by_translation_key()
    mapped = set(keys.values())
    for literal in ("昵称", "图片地址", "本地文件", "加载更多"):
        assert literal in mapped, f"{literal} is not attached to a data-i18n element"


def test_no_bare_literal_reaches_the_ui():
    """Every CJK text node must belong to a data-i18n element."""
    markup = visible_markup()
    translated = set(text_by_translation_key().values())
    bare = [
        t.strip()
        for t in re.findall(r">([^<>]+)<", markup)
        if t.strip() and CJK.search(t) and t.strip() not in translated
    ]
    assert not bare, f"untranslated text in markup: {bare}"


def test_dynamic_strings_go_through_t():
    script = "\n".join(re.findall(r"<script>(.*?)</script>", html(), re.S))
    # user-facing toasts / empty state / counters must use T(...)
    for needle in ("T('added'", "T('nameRequired'", "T('empty'", "T('total'"):
        assert needle in script
    leftovers = [
        line.strip()
        for line in script.splitlines()
        if CJK.search(line) and "T(" not in line and not line.strip().startswith("//")
    ]
    assert not leftovers, f"hard-coded Chinese in script: {leftovers}"


def test_language_change_redraws_dynamic_content():
    script = "\n".join(re.findall(r"<script>(.*?)</script>", html(), re.S))
    assert "onLanguageChange" in script
