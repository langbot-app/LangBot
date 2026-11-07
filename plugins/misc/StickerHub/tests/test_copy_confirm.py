"""The page must survive a sandboxed iframe without ``allow-modals``.

The host renders plugin pages in ``sandbox="allow-scripts allow-forms"``. In
that frame ``window.prompt`` / ``window.confirm`` are silently ignored and
``navigator.clipboard`` usually rejects on the opaque origin, so the page has
to carry its own copy fallbacks and its own confirmation sheet.
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "components" / "pages" / "hub" / "index.html"


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", PAGE.read_text(encoding="utf-8"), re.S))


def test_copy_never_depends_on_a_modal_dialog():
    body = script()
    # Strip comments: they mention the ignored APIs by name.
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S)
    assert "window.prompt" not in code
    assert not re.search(r"(?<![\w.])confirm\(", code)


def test_copy_tries_clipboard_then_execcommand_then_sheet():
    body = script()
    copy = body[body.index("async function copyText"):]
    copy = copy[: copy.index("async function loadStats")]
    clipboard = copy.find("navigator.clipboard.writeText")
    legacy = copy.find("legacyCopy(")
    sheet = copy.find("openSheet(T('copyPrompt'")
    assert -1 not in (clipboard, legacy, sheet), "all three copy tiers must exist"
    assert clipboard < legacy < sheet, "the copy tiers must run in fallback order"
    # The execCommand tier itself must be the real thing, not a stub.
    assert "document.execCommand('copy')" in body


def test_every_copy_tier_that_succeeds_toasts():
    body = script()
    matches = list(re.finditer(r"toast\(T\('copied'", body))
    assert len(matches) >= 2, "each successful copy tier should confirm with a toast"


def test_clear_confirms_in_an_in_page_sheet():
    body = script()
    clear = body[body.index("getElementById('clear')"):]
    clear = clear[: clear.index("addEventListener('click', async", 0) + 400]
    assert "openSheet(" in clear, "clear must ask through the page's own sheet"
    assert "'/clear'" in clear


def test_clear_aborts_when_the_sheet_is_dismissed():
    body = script()
    assert re.search(r"if \(!ok\) \{ return; \}", body), "a declined sheet must abort"
