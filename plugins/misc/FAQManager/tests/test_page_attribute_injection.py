"""The manager page must not build markup out of tenant text (review F-01).

The page is rendered by ``tests/page_dom_probe.js`` (Node) against a recording
DOM, so these tests drive the real inline script instead of matching its source.
The property under test is the rendered result: no markup string may carry the
entry text, and parsing every markup string the page writes must not yield an
event-handler attribute.

Pre-fix (``esc(e.question)`` concatenated into ``value="..."`` and, for the list
view, straight into element content): a question of
``" onfocus="alert(1)" data-x="`` closed the ``value`` attribute and produced an
``onfocus`` handler, and an answer containing ``</textarea><img src=x
onerror=...>`` produced an element with an ``onerror`` handler.
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
PAGE = PLUGIN_ROOT / "components/pages/manager/index.html"
PROBE = Path(__file__).resolve().parent / "page_dom_probe.js"

QUESTION = '" onfocus="alert(1)" data-x="'
ANSWER = 'line1</textarea><img src=x onerror="alert(2)">'
ENTRY = {"id": "e1", "question": QUESTION, "answer": ANSWER}


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

    config = {"responses": {"GET /entries": {"entries": [ENTRY]}}, "drive": drive}
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


def test_entry_text_never_reaches_markup_and_never_becomes_a_handler():
    report = _render("await loadEntries();")
    assert report["errors"] == []

    # 1. Entry text must not appear in any markup string at all: a value that
    #    never reaches markup cannot open an attribute or a script context.
    for write in report["markup_writes"]:
        assert QUESTION not in write["markup"]
        assert "<img" not in write["markup"]

    # 2. Parsing those markup strings with a real HTML parser must not yield an
    #    executable attribute.
    handlers = [
        (tag, name, value)
        for tag, name, value in _rendered_attributes(report)
        if name.lower().startswith("on")
    ]
    assert handlers == [], handlers

    # 3. The entry is still rendered as data, so the checks above are not vacuous.
    assert any(
        element["className"] == "entry-q" and element["text"] == "Q: " + QUESTION
        for element in report["elements"]
    )
    assert any(
        element["className"] == "entry-a" and element["text"] == ANSWER
        for element in report["elements"]
    )


def test_edit_form_carries_the_question_as_a_property_not_markup():
    report = _render("await loadEntries(); startEdit('e1');")
    assert report["errors"] == []

    for write in report["markup_writes"]:
        assert QUESTION not in write["markup"]
        assert ANSWER not in write["markup"]

    handlers = [
        (tag, name, value)
        for tag, name, value in _rendered_attributes(report)
        if name.lower().startswith("on")
    ]
    assert handlers == [], handlers

    # The edit form still holds the entry text, and it holds it as a property.
    edited_question = [element for element in report["elements"] if element["id"] == "editQ"]
    edited_answer = [element for element in report["elements"] if element["id"] == "editA"]
    assert len(edited_question) == 1 and len(edited_answer) == 1
    assert edited_question[0]["props"]["value"] == QUESTION
    assert edited_answer[0]["props"]["value"] == ANSWER
    assert edited_question[0]["attrs"] == {}
    assert edited_answer[0]["attrs"] == {}


def test_edit_actions_still_target_the_entry_id():
    """The save button must reach the API with the entry that was being edited."""

    report = _render("await loadEntries(); startEdit('e1'); await __probe.click('Save');")
    assert report["errors"] == []

    puts = [call for call in report["api_calls"] if call["method"] == "PUT"]
    assert puts, report["api_calls"]
    assert puts[0]["body"] == {"id": "e1", "question": QUESTION, "answer": ANSWER}
