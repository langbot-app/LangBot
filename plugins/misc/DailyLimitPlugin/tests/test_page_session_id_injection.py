"""Session identifiers must not be interpolated into the page's markup (review F2).

The page is rendered by ``tests/page_dom_probe.js`` (Node) against a recording
DOM, so these tests drive the real inline script of the management page instead
of matching its source. They check the rendered result: no markup string may
carry the session id, parsing those strings must not produce an event-handler
attribute, and the row's controls must still act on the exact id.

Pre-fix, ``esc(r.id)`` was HTML *text* escaped and then pasted into a
single-quoted JavaScript string inside a double-quoted attribute
(``onclick="resetOne('x');alert(1);//')"``): text escaping does not escape the
single quote, so the id escaped the string and the attribute carried executable
JavaScript.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PAGE = PLUGIN_ROOT / "components/pages/manage/index.html"
PROBE = Path(__file__).resolve().parent / "page_dom_probe.js"

SESSION_ID = "x');alert(1);//"
SESSION_LABEL = "group:1"
STATE = {
    "settings": {
        "default_limit": 50,
        "limit_message": "stop",
        "silent_mode": False,
        "tz_offset": 8,
        "reset_hour": 0,
    },
    "today": "2026-06-20",
    "sessions": [
        {
            "id": SESSION_ID,
            "label": SESSION_LABEL,
            "limit": None,
            "effective_limit": 50,
            "count": 3,
            "date": "2026-06-20",
            "last_active": "2026-06-20T11:20:00+0800",
        }
    ],
}


class _AttributeCollector(HTMLParser):
    """Collect every ``(tag, attribute, value)`` a markup string parses into."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.attributes: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag, attrs) -> None:
        for name, value in attrs:
            self.attributes.append((tag, name, value if value is not None else ""))

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)


def _render(drive: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("the page probe needs node to render the page against a recording DOM")

    # Every endpoint answers with the same installation state, so a page that
    # re-renders after a write keeps showing the row under test.
    config = {
        "responses": {
            "GET /state": STATE,
            "PUT /settings": STATE,
            "PUT /session": STATE,
            "POST /reset": STATE,
            "POST /reset-all": STATE,
            "DELETE /session": STATE,
        },
        "drive": drive,
    }
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "probe_config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        completed = subprocess.run(
            [node, str(PROBE), str(PAGE), str(config_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _rendered_attributes(report: dict) -> list[tuple[str, str, str]]:
    parser = _AttributeCollector()
    for write in report["markup_writes"]:
        parser.feed(write["markup"])
    parser.close()
    return parser.attributes


def test_session_id_never_reaches_markup_and_never_becomes_a_handler():
    report = _render("await refresh();")
    assert report["errors"] == []

    # 1. The id must not appear in any markup string at all: a value that never
    #    reaches markup cannot close an attribute or a JavaScript string literal.
    for write in report["markup_writes"]:
        assert SESSION_ID not in write["markup"]
        assert "alert(1)" not in write["markup"]

    # 2. Parsing those markup strings must not yield an executable attribute.
    handlers = [
        (tag, name, value)
        for tag, name, value in _rendered_attributes(report)
        if name.lower().startswith("on")
    ]
    assert handlers == [], handlers

    # 3. The row is still rendered, so the checks above are not vacuous.
    assert any(
        element["className"] == "session-label" and element["text"] == SESSION_LABEL
        for element in report["elements"]
    )
    assert any(
        element["className"] == "usage" and "3 / 50" in element["children"] + [element["text"]]
        for element in report["elements"]
    ) or any("3 / 50" in text for text in report["text_nodes"])


def test_reset_button_carries_the_exact_session_id():
    """The row's controls must act on the id that was rendered, not on a mangled one."""

    report = _render("await refresh(); await __probe.click('Reset');")
    assert report["errors"] == []

    resets = [call for call in report["api_calls"] if call["endpoint"] == "/reset"]
    assert resets, report["api_calls"]
    assert resets[0] == {"method": "POST", "endpoint": "/reset", "body": {"id": SESSION_ID}}


def test_remove_and_limit_controls_carry_the_exact_session_id():
    drive = (
        "await refresh();\n"
        "var inputs = __probe.elements().filter(function (n) { return n.className === 'lim-input'; });\n"
        "if (inputs.length) { inputs[0].value = '7'; await __probe.fire(inputs[0], 'change'); }\n"
        "await __probe.click('Remove');\n"
    )
    report = _render(drive)
    assert report["errors"] == []

    # The limit box exists as an element whose change listener is a real closure
    # and whose state lives in properties, not in attributes.
    inputs = [element for element in report["elements"] if element["className"] == "lim-input"]
    assert inputs and "change" in inputs[0]["listeners"]
    assert inputs[0]["attrs"] == {}

    limits = [call for call in report["api_calls"] if call["endpoint"] == "/session" and call["method"] == "PUT"]
    assert limits, report["api_calls"]
    assert limits[0]["body"] == {"id": SESSION_ID, "limit": 7}

    removals = [call for call in report["api_calls"] if call["endpoint"] == "/session" and call["method"] == "DELETE"]
    assert removals, report["api_calls"]
    assert removals[0]["body"] == {"id": SESSION_ID}
