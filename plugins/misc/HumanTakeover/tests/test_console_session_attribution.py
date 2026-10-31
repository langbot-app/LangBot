"""Console responses must stay attributed to the session that requested them.

Review finding F1: `openSession()` switched the shared page state immediately
while `/messages` was still in flight, so an out-of-order response could paint
session A's history, title and member card while `state.current` (the reply
target) was already B. The same attribution gap existed for the takeover
response and for the polling writeback, and a switch did not clear the previous
conversation or block sending.

Round-4 findings, also covered here: an attachment read started in A could
complete after the switch and be posted with B's reply (`late_attachment_writeback`),
the shared text box leaked A's draft into B (`draft_typed_in_a_is_not_sent_from_b`),
and a `/reply` response for A could mark B as taken over and delete B's draft
(`reply_result_binds_to_sending_session`).

The console is a browser page, so these tests run its real inline script inside
a fake DOM (tests/js/console_attribution_harness.mjs) with API responses and
FileReader reads that are completed manually, which makes "the older response
lands last" and "the attachment read finishes after the switch" deterministic.
Skipped when no `node` binary is available.

Run from HumanTakeover: python -m pytest tests
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HARNESS = Path(__file__).parent / "js" / "console_attribution_harness.mjs"
PAGE = PLUGIN_ROOT / "components" / "pages" / "console" / "index.html"


@pytest.fixture(scope="module")
def obs() -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the console page script")
    assert PAGE.is_file(), f"missing console page: {PAGE}"
    proc = subprocess.run(
        [node, str(HARNESS), str(PAGE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    marker = "__RESULT__"
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith(marker)),
        None,
    )
    if line is None:
        pytest.fail(
            f"harness produced no result (exit {proc.returncode})\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    data = json.loads(line[len(marker) :])
    broken = {name: value for name, value in data.items() if isinstance(value, dict) and "error" in value}
    assert not broken, f"harness scenarios crashed: {broken}"
    return data


def test_interleaved_loads_attribute_to_current_session(obs):
    """Opening A then B: B's response wins even though A's arrives last."""
    scenario = obs["interleaved_loads_and_reply"]
    after = scenario["afterLoads"]
    assert after["current"] == "B"
    assert after["displayedKey"] == "B", "the late A response overwrote B's conversation"
    assert after["currentKey"] == "B", "displayed data is not attributed to its session"
    assert after["titleKey"] == "name-B"


def test_reply_goes_to_the_displayed_session(obs):
    """The reply body's session_key must equal the displayed conversation's key."""
    scenario = obs["interleaved_loads_and_reply"]
    assert scenario["replySent"] is True
    assert scenario["replyKeyMatchesDisplayed"] is True, (
        "reply was sent to a different session than the one on screen "
        f"(displayed={scenario['displayedAtTyping']!r}, sent={scenario['replyKey']!r})"
    )
    assert scenario["replyKey"] == "B"
    assert scenario["displayedAtTyping"] == "B"


def test_switch_clears_previous_conversation_and_blocks_send(obs):
    """Switching to a still-loading session must clear A's state and block sending."""
    scenario = obs["switch_while_loading"]
    assert scenario["loaded"]["displayedKey"] == "A"

    while_loading = scenario["whileLoading"]
    assert while_loading["current"] == "B"
    assert while_loading["displayedKey"] is None, "A's data was still displayed after switching to B"
    assert while_loading["currentKey"] is None
    assert while_loading["titleKey"] == ""
    assert while_loading["messagesHtml"] == ""
    assert while_loading["infoHtml"] == ""
    assert while_loading["sendDisabled"] is True, "sending was allowed before B finished loading"
    assert while_loading["replySentWhileLoading"] is False, (
        "a reply typed against A was posted while B was not loaded yet"
    )

    after = scenario["afterLoad"]
    assert after["displayedKey"] == "B"
    assert after["sendDisabled"] is False


def test_poll_writeback_ignores_stale_snapshot(obs):
    """A poll snapshot for A must not repaint B when it lands after the switch."""
    scenario = obs["poll_stale_writeback"]
    assert scenario["polledKey"] == "A"
    after = scenario["after"]
    assert after["current"] == "B"
    assert after["displayedKey"] == "B"
    assert after["takeoverActive"] is False, "A's takeover snapshot was applied to B"
    assert after["buttonText"] == "接管"
    assert after["countdownShown"] is False


def test_takeover_response_ignores_stale_session(obs):
    """A takeover response for A must not repaint B's takeover UI."""
    scenario = obs["takeover_stale_response"]
    assert scenario["requestKey"] == "A"
    after = scenario["after"]
    assert after["current"] == "B"
    assert after["displayedKey"] == "B"
    assert after["takeoverActive"] is False, "A's takeover response was applied to B"
    assert after["buttonText"] == "接管"
    assert after["countdownShown"] is False


def test_current_session_still_applies_its_own_responses(obs):
    """Guard against over-blocking: the selected session's own responses still apply."""
    scenario = obs["current_session_still_works"]
    after_load = scenario["afterLoad"]
    assert after_load["displayedKey"] == "Z"
    assert after_load["takeoverActive"] is True
    assert after_load["buttonText"] == "取消接管"
    assert after_load["countdownShown"] is True

    assert scenario["replyKey"] == "Z"
    after_send = scenario["afterSend"]
    assert after_send["displayedKey"] == "Z"
    assert after_send["takeoverActive"] is False
    assert after_send["buttonText"] == "接管"


def test_late_attachment_read_stays_out_of_the_other_session(obs):
    """An attachment read started in A must not be written into B (F1)."""
    scenario = obs["late_attachment_writeback"]
    assert scenario["readStarted"] == 1, "the attachment read never started"
    assert scenario["beforeLate"]["displayedKey"] == "B"
    assert scenario["beforeLate"]["pendingImage"] is None

    after_late = scenario["afterLate"]
    assert after_late["current"] == "B"
    assert after_late["pendingImage"] is None, "A's attachment was staged in B's composer"
    assert after_late["pendingFileName"] is None
    assert after_late["previewChildren"] == 0, "A's attachment preview was rendered while B was on screen"

    assert scenario["replySent"] is True
    assert scenario["replyKey"] == "B"
    assert scenario["replyText"] == "hello from B"
    assert scenario["replyImage"] == "", "A's attachment was posted with B's reply"
    assert scenario["leakedImage"] is False


def test_attachment_committed_in_one_session_stays_with_it(obs):
    """A's staged attachment must not travel with B's reply, and must come back to A."""
    scenario = obs["attachment_stays_with_its_session"]
    in_a = scenario["inA"]
    assert in_a["pendingFileName"] == "A-doc.txt"
    assert in_a["previewChildren"] == 1

    in_b = scenario["inB"]
    assert in_b["displayedKey"] == "B"
    assert in_b["pendingFileName"] is None, "A's attachment was still staged while B was on screen"
    assert in_b["pendingFileBase64"] is None
    assert in_b["previewChildren"] == 0

    assert scenario["replyKey"] == "B"
    assert scenario["attachmentLeakedToB"] is False
    assert scenario["replyImage"] == ""
    assert scenario["replyFile"] == ""
    assert scenario["replyFileName"] == ""

    back_in_a = scenario["backInA"]
    assert back_in_a["current"] == "A"
    assert back_in_a["pendingFileName"] == "A-doc.txt", "A's attachment was lost instead of kept per session"
    assert back_in_a["pendingFileBase64"] == "data:text/plain;base64,QS1ET0M="
    assert back_in_a["previewChildren"] == 1


def test_draft_typed_in_one_session_is_not_sent_from_another(obs):
    """The shared text box must not carry A's draft into B (F1)."""
    scenario = obs["draft_typed_in_a_is_not_sent_from_b"]
    assert scenario["inB"]["current"] == "B"
    assert scenario["inB"]["inputValue"] == "", "A's text draft was left in the box after switching to B"
    assert scenario["replies"] == [], "a reply was posted from B carrying A's draft"
    assert scenario["leakedDraft"] is False

    back_in_a = scenario["backInA"]
    assert back_in_a["current"] == "A"
    assert back_in_a["inputValue"] == "private draft for A", "the draft was not restored for its own session"


def test_reply_result_does_not_bind_to_another_session(obs):
    """A's reply result must not repaint B, nor clean up B's draft/attachment (F2)."""
    scenario = obs["reply_result_binds_to_sending_session"]
    assert scenario["replyKey"] == "A"
    assert scenario["replyText"] == "answer for A"

    before = scenario["beforeResponse"]
    assert before["current"] == "B"
    assert before["takeoverActive"] is False
    assert before["inputValue"] == "B draft typed while A replied"
    assert before["pendingFileName"] == "B-doc.txt"

    after = scenario["afterResponse"]
    assert after["displayedKey"] == "B"
    assert after["takeoverActive"] is False, "A's reply result marked B as taken over"
    assert after["buttonText"] == "接管"
    assert after["countdownShown"] is False, "A's reply result started B's countdown"
    assert after["inputValue"] == "B draft typed while A replied", "A's reply cleanup deleted B's draft"
    assert after["pendingFileName"] == "B-doc.txt", "A's reply cleanup deleted B's attachment"


def test_send_only_carries_attachments_owned_by_the_target_session(obs):
    """Defence in depth: an attachment sourced from another session is never posted."""
    scenario = obs["foreign_attachment_is_never_posted"]
    assert scenario["replySent"] is True
    assert scenario["replyKey"] == "B"
    assert scenario["replyText"] == "text for B"
    assert scenario["replyImage"] == "", "an attachment owned by A was posted with B's reply"
    assert scenario["replyFile"] == ""
    assert scenario["replyFileName"] == ""


def test_reply_cleanup_keeps_content_added_while_sending(obs):
    """The reply cleanup may only consume the draft that was actually sent."""
    scenario = obs["composer_typed_during_send_is_kept"]
    assert scenario["replyText"] == "first message"
    after = scenario["afterReply"]
    assert after["current"] == "C"
    assert after["inputValue"] == "second message typed while sending", (
        "the reply cleanup deleted text typed after the send"
    )
    assert after["pendingFileName"] == "late.txt", "the reply cleanup deleted an attachment picked after the send"
    refreshed = scenario["afterRefresh"]
    assert refreshed["displayedKey"] == "C"
    assert refreshed["inputValue"] == "second message typed while sending"
