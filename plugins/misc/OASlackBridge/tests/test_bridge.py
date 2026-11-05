from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from langbot_plugin.api.entities import events
from langbot_plugin.api.definition.components.runner import RunnerContext
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.errors import ActionCallError
from langbot_plugin.api.proxies.runner import PermissionDeniedError

ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load_module(ROOT / "main.py", "oa_slack_bridge")
sys.modules["main"] = bridge
listener_module = load_module(ROOT / "components/event_listener/bridge.py", "oa_slack_listener")
runner_module = load_module(ROOT / "components/runner/slack_reply.py", "oa_slack_runner")
CONFIG = {
    "oa_bot": "oa-1", "slack_bot": "slack-1", "slack_channel_id": "C-1",
    "keywords": ["help", "人工"], "case_sensitive": False,
    "takeover_minutes": 60, "forward_followups": True,
}
OPENID = "openid-complete-value-12345"


class Host:
    def __init__(self):
        self.storage = {}
        self.sent = []
        self.failure = None
        self.root_result = {"message_id": "1234.000001"}

    async def call_action(self, action, data, *args, **kwargs):
        if action == getattr(self, "denied_action", None):
            raise self.denial
        if action == Action.CALL_TOOL:
            return {"result": await self.reply(data["tool_name"], data["parameters"])}
        if action == Action.CALL_PLATFORM_API:
            assert data["action"] == "send_message"
            data = {"bot_uuid": data["bot_uuid"], "target_type": data["params"]["target_type"],
                    "target_id": data["params"]["target_id"], "message_chain": data["params"]["message"]}
            action = Action.SEND_MESSAGE
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {"keys": list(self.storage)}
        if action == Action.GET_PLUGIN_STORAGE:
            return {"value_base64": base64.b64encode(self.storage[data["key"]]).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            self.storage[data["key"]] = base64.b64decode(data["value_base64"])
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            self.storage.pop(data["key"], None)
            return {}
        if action == Action.SEND_MESSAGE:
            if data["target_type"] == "person" and self.failure:
                raise self.failure
            self.sent.append(data)
            return {"result": self.root_result}
        raise AssertionError(f"Unexpected API action: {action}")


def binding(installation="first", workspace="workspace-1", revision=1):
    return InstallationBinding(
        instance_uuid="instance-1", workspace_uuid=workspace,
        installation_uuid=installation, placement_generation=1,
        runtime_revision=revision, artifact_digest="a" * 64,
    )


def context(text="help", *, bot="oa-1", channel="C-1", user=OPENID, thread="", mention=False):
    parts = [message.Plain(text=text)]
    if mention:
        parts.insert(0, message.At(target="SlackBot"))
    if thread:
        parts.append(message.Quote(id=thread, origin=message.MessageChain([message.Plain(text="not user input")])))
    return SimpleNamespace(
        event=SimpleNamespace(sender_id=user, launcher_id=channel, message_chain=message.MessageChain(parts)),
        get_bot_uuid=AsyncMock(return_value=bot), prevent_default=Mock(), prevent_postorder=Mock(),
    )


async def graph(host=None):
    host = host or Host()
    plugin = bridge.OASlackBridge()
    plugin.plugin_runtime_handler = host
    listener = listener_module.BridgeListener()
    listener.plugin = plugin
    await listener.initialize()
    assert events.GroupMessageReceived not in listener.registered_handlers
    runner = runner_module.SlackReplyProcessor()
    runner.plugin = plugin
    runner.bind_runtime(plugin_runtime_handler=host)
    await runner.initialize()
    return plugin, host, (listener.registered_handlers, runner, host)


async def receive(handlers, ctx, *, group=False):
    listeners, runner, host = handlers
    if not group:
        await listeners[events.PersonMessageReceived][0](ctx)
        return
    bot = await ctx.get_bot_uuid()
    data = {
        "type": "message.received", "bot_uuid": bot, "chat_id": ctx.event.launcher_id,
        "message_chain": ctx.event.message_chain.model_dump(mode="json"),
    }
    run_ctx = RunnerContext.model_validate({
        "run_id": "test", "trigger": {"type": "message.received"},
        "event": {"event_id": "test", "event_type": "message.received", "source": "test", "data": data},
        "input": {}, "delivery": {"surface": "test"},
        "resources": {"storage": {"plugin_storage": True},
                      "tools": [{"tool_name": "event_reply", "tool_type": "platform", "operations": ["call"]}]},
        "runtime": {}, "config": {"oa_bot": "ignored-processor-setting"},
    })

    async def call_tool(name, parameters):
        assert name == "event_reply"
        if getattr(host, "reply_failure", None):
            raise host.reply_failure
        chain = message.MessageChain([
            *(part for part in ctx.event.message_chain if isinstance(part, message.Quote)),
            message.Plain(text=parameters["text"]),
        ])
        host.sent.append({"bot_uuid": bot, "target_type": "group", "target_id": ctx.event.launcher_id,
                          "message_chain": chain.model_dump(mode="json")})
        return {"ok": True}

    host.reply = AsyncMock(side_effect=call_tool)
    ctx.results = [result async for result in runner.invoke(run_ctx)]
    ctx.reply_api = host.reply


def contents(payload):
    return message.MessageChain.model_validate(payload["message_chain"])


def text(payload):
    return bridge.plain_text(contents(payload))


def thread_id(payload):
    return next((part.id for part in contents(payload) if isinstance(part, message.Quote)), "")


@pytest.mark.asyncio
async def test_keyword_creates_root_and_persistent_mapping(monkeypatch):
    monkeypatch.setattr(bridge.time, "time", lambda: 1000)
    plugin, host, handlers = await graph()
    ctx = context("HELP <!channel>")
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, ctx)
        session = await plugin.load(plugin.key("session", "oa-1", OPENID))
        mapping = await plugin.load(plugin.thread_key(session))
        assert mapping["session_key"] == plugin.key("session", "oa-1", OPENID)
    ctx.prevent_default.assert_called_once()
    ctx.prevent_postorder.assert_called_once()
    assert session["openid"] == OPENID
    assert session["last_user_at"] == 1000
    assert session["expires_at"] == 4600
    assert len(host.storage) == 2
    assert len(host.sent) == 1
    assert not thread_id(host.sent[0])
    assert "HELP &lt;!channel&gt;" in text(host.sent[0])
    assert OPENID not in text(host.sent[0])
    assert "1970-01-01" in text(host.sent[0])
    assert host.sent[0]["target_id"] == "C-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("forward", [True, False])
async def test_followups_refresh_both_timers_and_reuse_thread(monkeypatch, forward):
    now = [1000]
    monkeypatch.setattr(bridge.time, "time", lambda: now[0])
    plugin, host, handlers = await graph()
    with bind_invocation(host, config={**CONFIG, "forward_followups": forward}, binding=binding()):
        await receive(handlers, context())
        now[0] = 2000
        followup = context("another question")
        await receive(handlers, followup)
        session = await plugin.load(plugin.key("session", "oa-1", OPENID))
    assert session["last_user_at"] == 2000
    assert session["expires_at"] == 5600
    followup.prevent_default.assert_called_once()
    assert len(host.sent) == (2 if forward else 1)
    if forward:
        assert thread_id(host.sent[-1]) == "1234.000001"
        assert text(host.sent[-1]) == "another question"


@pytest.mark.asyncio
@pytest.mark.parametrize("mention", [False, True])
async def test_staff_reply_uses_plain_components_and_acknowledges(mention):
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, context())
        reply = context("<@B123> Answer" if mention else "Answer", bot="slack-1", thread="1234.000001", mention=mention)
        await receive(handlers, reply, group=True)
    assert len(host.sent) == 3
    assert host.sent[1]["bot_uuid"] == "oa-1"
    assert host.sent[1]["target_type"] == "person"
    assert host.sent[1]["target_id"] == OPENID
    assert text(host.sent[1]) == "Answer"
    assert thread_id(host.sent[2]) == "1234.000001"
    assert "✅" in text(host.sent[2])
    reply.prevent_default.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mention", [False, True])
@pytest.mark.parametrize("encoded,expected", [
    (
        "价格 &lt; 100 &amp; 包邮，详见 <https://example.com>",
        "价格 < 100 & 包邮，详见 https://example.com",
    ),
    (
        "<https://example.com?a=1&amp;b=2|购买 &amp; 详情>",
        "购买 & 详情 https://example.com?a=1&b=2",
    ),
    (
        "<mailto:help@example.com|客服邮箱> <mailto:help@example.com>",
        "客服邮箱 help@example.com",
    ),
    (
        "<@U123> <@U456|Alice> <#C123|support> <#C456>",
        "@U123 @Alice #support #C456",
    ),
    ("<!here> <!channel> <!everyone>", "@here @channel @everyone"),
    ("&amp;lt; &amp;gt; &amp;amp; &lt; &gt; &amp;", "&lt; &gt; &amp; < > &"),
    ("&lt;@U123&gt; &lt;https://example.com&gt;", "<@U123> <https://example.com>"),
    ("&lt;!close&gt;", "<!close>"),
    ("&amp;!close&amp;", "&!close&"),
    ("!close &amp;", "!close &"),
    ("&amp; !close", "& !close"),
    ("<!close>", "<!close>"),
    ("<mailto:help@example.com|!close>", "!close"),
])
async def test_staff_reply_normalizes_slack_without_interpreting_commands(mention, encoded, expected):
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, context())
        reply = context(
            f"<@B123> {encoded}" if mention else encoded,
            bot="slack-1", thread="1234.000001", mention=mention,
        )
        await receive(handlers, reply, group=True)
    assert len(host.sent) == 3
    assert host.sent[1]["target_type"] == "person"
    assert text(host.sent[1]) == expected
    assert text(host.sent[2]) == "✅ 已发送 / Sent"
    assert thread_id(host.sent[2]) == "1234.000001"
    assert len(host.storage) == 2
    reply.prevent_default.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("code,reason", [(45015, "48-hour"), (45047, "limit"), (43004, "following"), (48001, "permission"), (99999, "rejected")])
async def test_provider_errcode_is_readable_without_raw_secrets(code, reason):
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, context())
        host.failure = RuntimeError(f"OfficialAccountSendError: OfficialAccount send_message failed: errcode={code} (secret-token)")
        await receive(handlers, context("answer", bot="slack-1", thread="1234.000001"), group=True)
    assert len(host.sent) == 2
    assert f"errcode={code}" in text(host.sent[-1])
    assert reason in text(host.sent[-1])
    assert "secret-token" not in text(host.sent[-1])
    assert thread_id(host.sent[-1]) == "1234.000001"


def test_unknown_error_never_discloses_raw_diagnostics():
    assert "secret-token" not in bridge.send_error(RuntimeError("secret-token"))


@pytest.mark.asyncio
@pytest.mark.parametrize("bot,channel,thread,group", [
    ("other-oa", "C-1", "", False), ("", "C-1", "", False),
    ("other-slack", "C-1", "1234.000001", True),
    ("slack-1", "C-other", "1234.000001", True),
    ("slack-1", "C-1", "unknown", True), ("slack-1", "C-1", "", True),
])
async def test_unrelated_events_are_ignored(bot, channel, thread, group):
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, context())
        ctx = context(bot=bot, channel=channel, thread=thread)
        await receive(handlers, ctx, group=group)
    assert len(host.sent) == 1
    ctx.prevent_default.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["/close", "!close"])
@pytest.mark.parametrize("mention", [False, True])
async def test_close_releases_takeover(command, mention):
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, context())
        await receive(handlers, context(
            f"<@B123> {command}" if mention else command,
            bot="slack-1", thread="1234.000001", mention=mention,
        ), group=True)
        followup = context("ordinary text")
        await receive(handlers, followup)
    assert host.storage == {}
    assert len(host.sent) == 2
    assert "closed" in text(host.sent[-1])
    followup.prevent_default.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("from_staff", [False, True])
async def test_timeout_releases_takeover(monkeypatch, from_staff):
    now = [1000]
    monkeypatch.setattr(bridge.time, "time", lambda: now[0])
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, context())
        now[0] = 4600
        ctx = context("normal", bot="slack-1", thread="1234.000001") if from_staff else context("normal")
        await receive(handlers, ctx, group=from_staff)
    assert host.storage == {}
    if from_staff:
        assert "expired" in text(host.sent[-1])
        ctx.prevent_default.assert_not_called()
        assert all(payload["target_type"] == "group" for payload in host.sent)
    else:
        ctx.prevent_default.assert_not_called()
        assert len(host.sent) == 1


@pytest.mark.asyncio
async def test_window_expires_even_with_long_takeover(monkeypatch):
    now = [1000]
    monkeypatch.setattr(bridge.time, "time", lambda: now[0])
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config={**CONFIG, "takeover_minutes": 4000}, binding=binding()):
        await receive(handlers, context())
        now[0] += 48 * 3600
        await receive(handlers, context("answer", bot="slack-1", thread="1234.000001"), group=True)
    assert len(host.sent) == 2
    assert "48-hour" in text(host.sent[-1])
    assert host.storage == {}


@pytest.mark.asyncio
async def test_mapping_survives_restart_and_runtime_revision():
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await receive(handlers, context())
    _restarted, host, handlers = await graph(host)
    with bind_invocation(host, config=CONFIG, binding=binding(revision=2)):
        await receive(handlers, context("after restart", bot="slack-1", thread="1234.000001"), group=True)
    assert host.sent[1]["target_id"] == OPENID
    assert text(host.sent[1]) == "after restart"


@pytest.mark.asyncio
async def test_installations_and_workspaces_do_not_share_rows_or_locks():
    plugin, host, handlers = await graph()
    first, second, third = binding(), binding("second"), binding(workspace="workspace-2")
    for active in (first, second, third):
        with bind_invocation(host, config=CONFIG, binding=active):
            reply = context("answer", bot="slack-1", thread="1234.000001")
            await receive(handlers, reply, group=True)
            reply.prevent_default.assert_not_called()
            await receive(handlers, context())
    assert len(host.sent) == 3
    assert len(host.storage) == 6
    await plugin.on_installation_revoked(first)
    assert set(plugin._locks) == {plugin.scope(second), plugin.scope(third)}
    assert len(host.storage) == 6
    await plugin.destroy()
    assert plugin._locks == {}


@pytest.mark.asyncio
async def test_bot_and_user_keys_are_independent():
    _plugin, host, handlers = await graph()
    for bot, user in (("oa-1", OPENID), ("oa-2", OPENID), ("oa-1", "another-user")):
        host.root_result = {"message_id": f"{len(host.sent)}.000001"}
        with bind_invocation(host, config={**CONFIG, "oa_bot": bot}, binding=binding()):
            await receive(handlers, context(bot=bot, user=user))
    rows = [json.loads(value) for value in host.storage.values() if "openid" in json.loads(value)]
    assert len(rows) == 3
    assert {(row["oa_bot"], row["openid"]) for row in rows} == {("oa-1", OPENID), ("oa-2", OPENID), ("oa-1", "another-user")}


@pytest.mark.asyncio
async def test_shared_runtime_without_binding_refuses_storage(monkeypatch):
    monkeypatch.setenv("LANGBOT_PLUGIN_RUNTIME_PROFILE", "shared")
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG):
        with pytest.raises(RuntimeError, match="installation binding"):
            await receive(handlers, context())
    assert host.storage == {}
    assert host.sent == []


@pytest.mark.asyncio
async def test_concurrent_messages_create_one_root():
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await asyncio.gather(receive(handlers, context()), receive(handlers, context()))
    assert len(host.sent) == 2
    assert [thread_id(payload) for payload in host.sent] == ["", "1234.000001"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case_sensitive,expected", [(False, 1), (True, 0)])
async def test_case_sensitive_matching(case_sensitive, expected):
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config={**CONFIG, "case_sensitive": case_sensitive, "keywords": ["", " ", "help"]}):
        await receive(handlers, context("HELP"))
    assert len(host.sent) == expected


@pytest.mark.asyncio
async def test_missing_root_id_does_not_persist_unroutable_session():
    _plugin, host, handlers = await graph()
    host.root_result = None
    with bind_invocation(host, config=CONFIG):
        with pytest.raises(RuntimeError, match="message_id"):
            await receive(handlers, context())
    assert not host.storage


@pytest.mark.asyncio
async def test_empty_staff_reply_does_not_send_quoted_origin():
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG):
        await receive(handlers, context())
        await receive(handlers, context("", bot="slack-1", thread="1234.000001"), group=True)
    assert len(host.sent) == 2
    assert "Only text" in text(host.sent[-1])


@pytest.mark.asyncio
async def test_channel_change_creates_new_thread():
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG):
        await receive(handlers, context())
    host.root_result = {"message_id": "2222.000001"}
    with bind_invocation(host, config={**CONFIG, "slack_channel_id": "C-2"}):
        await receive(handlers, context())
    assert len(host.storage) == 2
    assert host.sent[-1]["target_id"] == "C-2"
    assert not thread_id(host.sent[-1])


def denied():
    return ActionCallError("Host rejected the operation", {
        "error": {"code": "permission_denied", "message": "Host rejected the operation"},
    })


@pytest.mark.asyncio
async def test_version_010_rows_work_without_rewriting_keys(monkeypatch):
    monkeypatch.setattr(bridge.time, "time", lambda: 2000)
    _plugin, host, handlers = await graph()
    key = "oasb:instance-1%3Aworkspace-1%3Afirst:session:oa-1:openid-sensitive-123456789"
    mapping_key = "oasb:instance-1%3Aworkspace-1%3Afirst:thread:slack-1:C-1:1234.000001"
    session = {"oa_bot": "oa-1", "openid": "openid-sensitive-123456789", "slack_bot": "slack-1",
               "channel": "C-1", "thread": "1234.000001", "last_user_at": 1000, "expires_at": 4600}
    host.storage = {key: json.dumps(session).encode(), mapping_key: json.dumps({"session_key": key}).encode()}
    previous = dict(host.storage)
    with bind_invocation(host, config=CONFIG, binding=binding(revision=2)):
        reply = context("old session reply", bot="slack-1", thread="1234.000001")
        await receive(handlers, reply, group=True)
    assert host.storage == previous
    assert text(host.sent[0]) == "old session reply"
    assert host.sent[0]["target_id"] == session["openid"]
    reply.reply_api.assert_awaited_once_with("event_reply", {"text": "✅ 已发送 / Sent"})
    assert reply.results[-1].type == "run.completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_session", [False, True])
async def test_unmapped_threads_log_without_reply(missing_session):
    plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG):
        if missing_session:
            await plugin.save(plugin.key("thread", "slack-1", "C-1", "1234.000001"), {"session_key": "missing"})
        reply = context("answer", bot="slack-1", thread="1234.000001")
        await receive(handlers, reply, group=True)
    assert not host.sent
    reply.reply_api.assert_not_called()
    assert any("Ignoring Slack" in result.data.get("text", "") for result in reply.results)


@pytest.mark.asyncio
@pytest.mark.parametrize("action,command,capability", [
    (Action.GET_PLUGIN_STORAGE_KEYS, "answer", "storage.plugin"),
    (Action.GET_PLUGIN_STORAGE, "answer", "storage.plugin"),
    (Action.DELETE_PLUGIN_STORAGE, "!close", "storage.plugin"),
    (Action.CALL_PLATFORM_API, "answer", "bot.message.send"),
])
async def test_runner_permission_denial_logs_and_acknowledges(action, command, capability):
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG):
        await receive(handlers, context())
        host.denied_action, host.denial = action, denied()
        reply = context(command, bot="slack-1", thread="1234.000001")
        await receive(handlers, reply, group=True)
    assert len(host.sent) == 2
    assert capability in text(host.sent[-1])
    assert any(capability in result.data.get("text", "") for result in reply.results)
    assert reply.results[-1].type == "run.completed"


@pytest.mark.asyncio
async def test_denied_receipt_does_not_retry_customer_send():
    _plugin, host, handlers = await graph()
    with bind_invocation(host, config=CONFIG):
        await receive(handlers, context())
        host.reply_failure = denied()
        reply = context("answer", bot="slack-1", thread="1234.000001")
        await receive(handlers, reply, group=True)
    assert len(host.sent) == 2
    assert host.sent[-1]["target_type"] == "person"
    assert any("event_reply" in result.data.get("text", "") for result in reply.results)
    assert reply.results[-1].type == "run.completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [Action.GET_PLUGIN_STORAGE_KEYS, Action.SET_PLUGIN_STORAGE, Action.SEND_MESSAGE])
async def test_listener_permission_denial_stops_pipeline_without_crashing(action, caplog):
    _plugin, host, handlers = await graph()
    host.denied_action, host.denial = action, denied()
    with bind_invocation(host, config=CONFIG):
        incoming = context()
        await receive(handlers, incoming)
    incoming.prevent_default.assert_called()
    assert "Permission denied" in caplog.text
    assert "Host rejected" not in caplog.text


def test_sdk_local_permission_denial_is_recognized():
    assert bridge.permission_denied(PermissionDeniedError("Plugin storage is not authorized."))
    assert not bridge.permission_denied(RuntimeError("network failed"))


def test_component_and_permission_manifest():
    plugin = yaml.safe_load((ROOT / "manifest.yaml").read_text())
    runner = yaml.safe_load((ROOT / "components/runner/slack_reply.yaml").read_text())
    assert plugin["metadata"]["version"] == "0.2.0"
    assert plugin["spec"]["permissions"] == {
        "capabilities": ["bot.message.send", "storage.plugin"], "workspace_operations": [],
    }
    assert runner["spec"]["usages"] == ["event"]
    assert runner["spec"]["events"] == ["message.received"]
    assert runner["spec"]["permissions"] == {"tools": ["call"], "storage": ["plugin"]}
    assert runner["spec"]["config"] == []
    locales = {"en_US", "zh_Hans", "zh_Hant", "ja_JP", "es_ES", "ru_RU", "th_TH", "vi_VN"}
    for manifest in (plugin, runner):
        for field in ("label", "description"):
            assert set(manifest["metadata"][field]) == locales
