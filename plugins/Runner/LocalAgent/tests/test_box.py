from types import SimpleNamespace as SimpleContext
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.runner.box import BoxBinding, BoxFile, BoxSession, BoxStatus
from langbot_plugin.api.entities.builtin.runner.input import AgentInput, InputAttachment

from pkg.box import LocalAgentBox, resolve_reuse_key


def context():
    return SimpleContext(
        run_id="run-1",
        variables={"project": "demo"},
        config={},
        conversation=SimpleContext(
            launcher_type="group", launcher_id="room", sender_id="alice", bot_id="bot", conversation_id="conversation-1"
        ),
        actor=None,
        event=SimpleContext(event_id="event", event_type="message.received", data={}),
        delivery=SimpleContext(reply_target={}, automatic_reply=True),
        context=SimpleContext(available_apis=SimpleContext(box=True)),
        input=AgentInput(),
        bind_box=AsyncMock(return_value=BoxBinding(box_id="box", inbox="/in/run-1", outbox="/out/run-1")),
        import_box_attachments=AsyncMock(return_value=[]),
        export_box_files=AsyncMock(return_value=[]),
        reply_files=AsyncMock(),
    )


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{global}", "global"),
        ("{launcher_type}_{launcher_id}", "group_room"),
        ("{sender_id}", "alice"),
        ("{bot_id}_{project}", "bot_demo"),
        ("{run_id}", "run-1"),
        ("{launcher_type}_{launcher_id}_{sender_id}", "group_room_alice"),
        ("{launcher_type}_{launcher_id}_{conversation_id}", "group_room_conversation-1"),
        ("{query_id}", "run-1"),
    ],
)
def test_reuse_template(template, expected):
    assert resolve_reuse_key(context(), template) == expected


@pytest.mark.parametrize("template", ["{missing}", "{sender_id.__class__}", "{sender_id!r}", "", "{"])
def test_invalid_template_is_not_silently_shared(template):
    with pytest.raises(ValueError):
        resolve_reuse_key(context(), template)


@pytest.mark.asyncio
async def test_zero_remaining_still_attempts_reuse_and_imports_explicitly():
    ctx = context()
    ctx.input.attachments = [InputAttachment(ref="attachment-0", name="input.txt")]
    ctx.import_box_attachments.return_value = [
        BoxFile(
            id="attachment-0",
            name="input.txt",
            type="File",
            size=3,
            path="/in/run-1/input.txt",
        )
    ]
    api = SimpleContext(
        get_allowed_tools=lambda: [SimpleContext(tool_name="exec")],
        get_box_status=AsyncMock(return_value=BoxStatus(enabled=True, available=True, remaining=0)),
        acquire_box=AsyncMock(return_value=BoxSession(id="box", status="ready")),
    )
    box = LocalAgentBox(ctx, api)
    assert box.needed()
    await box.prepare()
    api.acquire_box.assert_awaited_once_with("group_room")
    ctx.bind_box.assert_awaited_once_with("box")
    assert ctx.input.attachments[0].path == "/in/run-1/input.txt"
    assert "/out/run-1/" in ctx.input.contents[-1].text
    ctx.reply_files.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("automatic_reply", [True, False])
async def test_completion_returns_files_for_pipeline_or_explicitly_replies(automatic_reply):
    ctx = context()
    ctx.delivery.automatic_reply = automatic_reply
    ctx.export_box_files.return_value = [BoxFile(id="file", name="a.txt", type="File", size=1)]
    box = LocalAgentBox(ctx, None)
    box.prepare = AsyncMock()
    box.binding = ctx.bind_box.return_value
    assert (await box.export_files(["/workspace/a.txt"]))["status"] == "accepted"
    assert box.file_ids == (["file"] if automatic_reply else [])
    ctx.export_box_files.assert_awaited_once_with(["/workspace/a.txt"])
    if automatic_reply:
        ctx.reply_files.assert_not_called()
    else:
        ctx.reply_files.assert_awaited_once_with(["file"])


def test_disabled_box_never_prepares():
    ctx = context()
    ctx.config["box-enabled"] = False
    box = LocalAgentBox(ctx, SimpleContext(get_allowed_tools=lambda: [SimpleContext(tool_name="exec")]))
    assert not box.needed()
