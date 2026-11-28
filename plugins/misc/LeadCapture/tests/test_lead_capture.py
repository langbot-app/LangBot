from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml
from langbot_plugin.api.entities import events
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import InstallationBinding

ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lead_main = load_module(ROOT / "main.py", "lead_capture_main")
sys.modules["main"] = lead_main
listener_module = load_module(ROOT / "components/event_listener/lead.py", "lead_capture_listener")

CONFIG = {
    "model": "model-1", "intent_prompt": "asks for a quote", "history_messages": 20,
    "ask_text": "ASK-CONTACT", "thanks_text": "THANKS",
    "resend_api_key": "re_secret_key", "from_email": "Leads <leads@example.com>",
    "to_emails": ["sales@example.com", " ", "boss@example.com"],
}
USER = "openid-user-1"


class Host:
    def __init__(self):
        self.storage = {}
        self.history = []  # oldest first
        self.llm_answers = []
        self.llm_calls = []
        self.operations = []

    async def call_action(self, action, data, *args, **kwargs):
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {"keys": list(self.storage)}
        if action == Action.GET_PLUGIN_STORAGE:
            return {"value_base64": base64.b64encode(self.storage[data["key"]]).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            self.storage[data["key"]] = base64.b64decode(data["value_base64"])
            return {}
        if action == Action.CALL_APPLICATION_OPERATION:
            self.operations.append(data)
            args = data["arguments"]
            newest_first = list(reversed(self.history))
            rows = newest_first[args["offset"]:args["offset"] + args["limit"]]
            return {"ok": True, "result": [rows, len(self.history)]}
        if action == Action.INVOKE_LLM:
            self.llm_calls.append(data)
            answer = self.llm_answers.pop(0) if self.llm_answers else "{}"
            return {"message": {"role": "assistant", "content": answer}}
        raise AssertionError(f"Unexpected action: {action}")


def binding():
    return InstallationBinding(
        instance_uuid="instance-1", workspace_uuid="workspace-1", installation_uuid="install-1",
        placement_generation=1, runtime_revision=1, artifact_digest="a" * 64,
    )


def row(role, text, ts="2026-11-06T07:00:00"):
    return {"role": role, "bot_name": "微信公众号", "timestamp": ts,
            "message_content": json.dumps([{"type": "Plain", "text": text}])}


def received(text, user=USER):
    return SimpleNamespace(
        event=SimpleNamespace(
            launcher_type="person", launcher_id=user, sender_id=user,
            message_chain=message.MessageChain([message.Plain(text=text)]),
        ),
        get_bot_uuid=AsyncMock(return_value="bot-1"),
    )


def responded(text="AI answer", user=USER):
    event = SimpleNamespace(
        launcher_type="person", launcher_id=user, sender_id=user,
        response_text=text, reply_message_chain=None,
    )
    return SimpleNamespace(event=event, get_bot_uuid=AsyncMock(return_value="bot-1"))


def reply_text(ctx):
    chain = ctx.event.reply_message_chain
    return None if chain is None else "".join(part.text for part in chain if isinstance(part, message.Plain))


class Resend:
    def __init__(self, status=200, body=None):
        self.requests = []
        self.status = status
        self.body = body or {"id": "email-1"}

    def install(self, monkeypatch):
        transport = httpx.MockTransport(self.handle)
        original = httpx.AsyncClient

        def client(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        monkeypatch.setattr(lead_main.httpx, "AsyncClient", client)
        return self

    def handle(self, request):
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


async def graph():
    host = Host()
    plugin = lead_main.LeadCapture()
    plugin.plugin_runtime_handler = host
    listener = listener_module.LeadListener()
    listener.plugin = plugin
    await listener.initialize()
    handlers = listener.registered_handlers
    return plugin, host, handlers


async def fire(handlers, event_type, ctx):
    await handlers[event_type][0](ctx)


@pytest.mark.asyncio
async def test_no_intent_leaves_reply_untouched():
    _plugin, host, handlers = await graph()
    host.history = [row("user", "what does it do?")]
    host.llm_answers = ['{"strong_intent": false, "reason": "just browsing"}']
    ctx = responded()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, ctx)
    assert reply_text(ctx) is None
    state = json.loads(next(iter(host.storage.values())))
    assert state["status"] == "idle"
    assert [(e["kind"], e["strong"], e["reason"], e["message"], e["reply"]) for e in state["events"]] == [
        ("judge", False, "just browsing", "what does it do?", "AI answer"),
    ]
    prompt = host.llm_calls[0]["messages"]
    assert "asks for a quote" in json.dumps(prompt, ensure_ascii=False)
    assert "AI: AI answer" in json.dumps(prompt, ensure_ascii=False)
    assert host.operations[0]["arguments"]["session_ids"] == [f"person_{USER}"]


@pytest.mark.asyncio
async def test_strong_intent_appends_ask_once():
    _plugin, host, handlers = await graph()
    host.history = [row("user", "how much is the annual plan?")]
    host.llm_answers = ['```json\n{"strong_intent": true, "reason": "asked price"}\n```']
    first = responded("The annual plan is $99.")
    second = responded("Anything else?")
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, first)
        await fire(handlers, events.NormalMessageResponded, second)
    assert reply_text(first) == "The annual plan is $99.\n\nASK-CONTACT"
    assert reply_text(second) is None
    assert len(host.llm_calls) == 1  # never re-evaluated after asking
    state = json.loads(next(iter(host.storage.values())))
    assert state["status"] == "asked" and state["reason"] == "asked price"


@pytest.mark.asyncio
async def test_existing_plugin_reply_is_preserved_when_appending():
    _plugin, host, handlers = await graph()
    host.llm_answers = ['{"strong_intent": "true"}']
    ctx = responded("original")
    ctx.event.reply_message_chain = message.MessageChain([message.Plain(text="rewritten by another plugin")])
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, ctx)
    assert reply_text(ctx) == "rewritten by another plugin\n\nASK-CONTACT"


@pytest.mark.asyncio
async def test_contact_capture_emails_full_history_and_thanks_once(monkeypatch):
    resend = Resend().install(monkeypatch)
    _plugin, host, handlers = await graph()
    host.history = [row("user", f"msg {i}", f"2026-11-0{1 + i // 200}T00:00:{i % 60:02d}") for i in range(230)]
    host.llm_answers = ['{"strong_intent": true, "reason": "wants to buy"}']
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, responded())
        await fire(handlers, events.PersonMessageReceived, received("我的手机 138 0013 8000，微信 abc_12345"))
        after = responded("Noted.")
        await fire(handlers, events.NormalMessageResponded, after)
        later = responded("Bye.")
        await fire(handlers, events.NormalMessageResponded, later)
    # One judgment, then field extraction; the contact came from patterns, so no contact-extraction call.
    assert len(host.llm_calls) == 2
    assert len(resend.requests) == 1
    request = resend.requests[0]
    assert request.headers["Authorization"] == "Bearer re_secret_key"
    payload = json.loads(request.content)
    assert payload["from"] == "Leads <leads@example.com>"
    assert payload["to"] == ["sales@example.com", "boss@example.com"]
    assert "138 0013 8000" in payload["subject"] and "微信: abc_12345" in payload["subject"]
    assert "wants to buy" in payload["text"] and "消息总数：230" in payload["text"]
    transcript = base64.b64decode(payload["attachments"][0]["content"]).decode()
    assert transcript.count("\n") == 229 and transcript.startswith("[2026-11-01 00:00:00 UTC] 用户: msg 0")
    assert "re_secret_key" not in payload["text"] + payload["html"]
    assert reply_text(after) == "Noted.\n\nTHANKS"
    assert reply_text(later) is None
    state = json.loads(next(iter(host.storage.values())))
    assert state["status"] == "captured" and state["email_status"] == "sent"


@pytest.mark.asyncio
async def test_llm_extracts_contact_when_patterns_miss(monkeypatch):
    resend = Resend().install(monkeypatch)
    _plugin, host, handlers = await graph()
    host.llm_answers = ['{"strong_intent": true}', '{"contact": "QQ 123456789"}']
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, responded())
        await fire(handlers, events.PersonMessageReceived, received("加我扣扣一二三四五六七八九吧 就是 123456789"))
    assert len(resend.requests) == 1
    assert "QQ 123456789" in json.loads(resend.requests[0].content)["subject"]


@pytest.mark.asyncio
async def test_messages_without_contact_keep_waiting(monkeypatch):
    resend = Resend().install(monkeypatch)
    _plugin, host, handlers = await graph()
    host.llm_answers = ['{"strong_intent": true}', '{"contact": ""}']
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, responded())
        await fire(handlers, events.PersonMessageReceived, received("我再考虑一下"))
    assert resend.requests == []
    assert json.loads(next(iter(host.storage.values())))["status"] == "asked"


@pytest.mark.asyncio
async def test_email_failure_is_retried_on_later_replies(monkeypatch):
    resend = Resend(status=403, body={"name": "validation_error", "message": "domain not verified"}).install(monkeypatch)
    _plugin, host, handlers = await graph()
    host.llm_answers = ['{"strong_intent": true}']
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, responded())
        await fire(handlers, events.PersonMessageReceived, received("my email is a@b.co"))
        for _ in range(4):
            await fire(handlers, events.NormalMessageResponded, responded())
    state = json.loads(next(iter(host.storage.values())))
    assert state["email_status"] == "http_403:validation_error"
    assert state["email_attempts"] == lead_main.MAX_EMAIL_ATTEMPTS
    assert len(resend.requests) == lead_main.MAX_EMAIL_ATTEMPTS


@pytest.mark.asyncio
async def test_unconfigured_or_group_events_do_nothing():
    _plugin, host, handlers = await graph()
    group = responded()
    group.event.launcher_type = "group"
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, group)
    with bind_invocation(host, config={**CONFIG, "model": ""}, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, responded())
    assert host.llm_calls == [] and host.storage == {}


@pytest.mark.asyncio
async def test_llm_failure_never_breaks_the_reply():
    _plugin, host, handlers = await graph()

    async def boom(*args, **kwargs):
        raise RuntimeError("provider down")

    host.call_action, original = boom, host.call_action
    ctx = responded()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, ctx)
    host.call_action = original
    assert reply_text(ctx) is None


@pytest.mark.parametrize("text,expected", [
    ("电话13800138000", "13800138000"),
    ("+86 138-0013-8000", "+86 138-0013-8000"),
    ("座机 010-12345678", "010-12345678"),
    ("mail me: Foo.Bar@example.co.uk", "Foo.Bar@example.co.uk"),
    ("我的微信号是 wxid_abc123", "微信: wxid_abc123"),
    ("VX：Hello-2024", "微信: Hello-2024"),
    ("订单号 123456789012345", ""),
    ("我再想想", ""),
])
def test_find_contact(text, expected):
    assert lead_main.find_contact(text) == expected


def test_send_email_reports_missing_configuration():
    import asyncio

    plugin = lead_main.LeadCapture()
    result = asyncio.run(plugin.send_email({"resend_api_key": ""}, {"from": "a@b.co", "to": ["c@d.co"]}))
    assert result == "not_configured"


def test_manifest():
    manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text())
    assert manifest["metadata"]["name"] == "LeadCapture"
    assert manifest["spec"]["permissions"] == {
        "capabilities": ["models.invoke", "storage.plugin"], "workspace_operations": ["monitoring.messages"],
    }
    assert manifest["metadata"]["version"] == "0.3.0"
    assert manifest["spec"]["components"]["Page"]["fromDirs"][0]["path"] == "components/pages/"
    names = [item["name"] for item in manifest["spec"]["config"]]
    assert names == ["model", "intent_prompt", "high_score", "ask_score", "risk_prompt", "history_messages",
                     "ask_text", "thanks_text", "lead_fields", "resend_api_key", "from_email", "to_emails"]
    defaults = {item["name"]: item.get("default") for item in manifest["spec"]["config"]}
    assert defaults["risk_prompt"] == lead_main.DEFAULT_RISK_PROMPT
    assert defaults["lead_fields"] == lead_main.DEFAULT_LEAD_FIELDS
    assert (defaults["high_score"], defaults["ask_score"]) == (60, 30)
    assert defaults["intent_prompt"] == lead_main.DEFAULT_INTENT_PROMPT
    assert defaults["ask_text"] == lead_main.DEFAULT_ASK_TEXT
    assert defaults["thanks_text"] == lead_main.DEFAULT_THANKS_TEXT
    locales = {"en_US", "zh_Hans", "zh_Hant", "ja_JP", "es_ES", "ru_RU", "th_TH", "vi_VN"}
    assert set(manifest["metadata"]["label"]) == locales
    assert set(manifest["metadata"]["description"]) == locales


page_module = load_module(ROOT / "components/pages/console/console.py", "lead_capture_console")


async def page_for(plugin):
    page = page_module.ConsolePage()
    page.plugin = plugin
    return page


async def call_page(page, endpoint, body=None, method="GET"):
    from langbot_plugin.api.definition.components.page import PageRequest

    return await page.handle_api(PageRequest(endpoint=endpoint, method=method, body=body))


@pytest.mark.asyncio
async def test_page_lists_sessions_and_shows_timeline(monkeypatch):
    resend = Resend().install(monkeypatch)
    plugin, host, handlers = await graph()
    host.history = [row("user", "年付多少钱？", "2026-11-06T07:00:00"), row("assistant", "99 元", "2026-11-06T07:00:05")]
    host.llm_answers = [
        '{"strong_intent": false, "reason": "only asking"}',
        '{"strong_intent": true, "reason": "asked about invoices"}',
        '{"公司名称": "Acme"}',
        '{"score": 10, "reason": "browsing"}',
    ]
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, responded("first answer"))
        await fire(handlers, events.NormalMessageResponded, responded("second answer"))
        await fire(handlers, events.PersonMessageReceived, received("13800138000"))
        await fire(handlers, events.NormalMessageResponded, responded("noted", user="other-user"))
        page = await page_for(plugin)
        listing = await call_page(page, "/sessions")
        assert listing.error is None
        totals, sessions = listing.data["totals"], listing.data["sessions"]
        assert totals == {"sessions": 2, "asked": 0, "risk": 0, "captured": 1, "emailed": 1, "judgments": 3}
        captured = next(item for item in sessions if item["user"] == USER)
        assert captured["status"] == "captured" and captured["contact"] == "13800138000"
        assert captured["judgments"] == 2 and captured["strong_judgments"] == 1
        assert captured["last_reason"] == "asked about invoices" and captured["email_status"] == "sent"
        detail = await call_page(page, "/session", {"key": captured["key"]}, "POST")
    assert detail.error is None
    kinds = [event["kind"] for event in detail.data["session"]["events"]]
    assert kinds == ["judge", "judge", "asked", "contact", "fields", "email"]
    assert detail.data["session"]["fields"]["公司名称"] == "Acme"
    assert detail.data["session"]["events"][0]["message"] == "年付多少钱？"
    assert [m["text"] for m in detail.data["conversation"]] == ["年付多少钱？", "99 元"]
    assert len(resend.requests) == 1


@pytest.mark.asyncio
async def test_page_rejects_foreign_keys_and_unknown_endpoints():
    plugin, host, _handlers = await graph()
    host.storage["lead:other-install:bot-1:x"] = json.dumps({"status": "captured"}).encode()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        page = await page_for(plugin)
        foreign = await call_page(page, "/session", {"key": "lead:other-install:bot-1:x"}, "POST")
        missing = await call_page(page, "/session", {"key": plugin.key("bot-1", "nobody")}, "POST")
        listing = await call_page(page, "/sessions")
        unknown = await call_page(page, "/nope")
    assert foreign.error == "Unknown session" and missing.error == "Unknown session"
    assert listing.data["sessions"] == []
    assert unknown.error.startswith("Unknown endpoint")


@pytest.mark.asyncio
async def test_judgment_errors_are_recorded():
    _plugin, host, handlers = await graph()
    host.llm_answers = []

    async def failing(action, data, *args, **kwargs):
        if action == Action.INVOKE_LLM:
            raise RuntimeError("provider down")
        return await Host.call_action(host, action, data, *args, **kwargs)

    host.call_action = failing
    ctx = responded()
    with bind_invocation(host, config=CONFIG, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, ctx)
    assert reply_text(ctx) is None
    state = json.loads(next(iter(host.storage.values())))
    assert state["status"] == "idle"
    assert state["events"][0]["kind"] == "error" and state["events"][0]["stage"] == "judge"


def test_page_i18n_keys_match_and_cover_html():
    import re

    folder = ROOT / "components/pages/console"
    en = json.loads((folder / "i18n/en_US.json").read_text())
    zh = json.loads((folder / "i18n/zh_Hans.json").read_text())
    assert set(en) == set(zh)
    html = (folder / "index.html").read_text()
    used = set(re.findall(r'data-i18n="([^"]+)"', html)) | set(re.findall(r"t\('([^']+)'", html))
    assert used <= set(en), used - set(en)



SCORING = {**CONFIG, "high_score": 60, "ask_score": 30}


@pytest.mark.asyncio
@pytest.mark.parametrize("score,level,asks", [(82, "high", True), (45, "medium", True), (29, "low", False)])
async def test_score_tiers_decide_the_single_ask(score, level, asks):
    _plugin, host, handlers = await graph()
    host.llm_answers = [json.dumps({"score": score, "signals": ["询价", "发票"], "risk": False, "reason": "r"})]
    first, second = responded("a1"), responded("a2")
    with bind_invocation(host, config=SCORING, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, first)
        await fire(handlers, events.NormalMessageResponded, second)
    state = json.loads(next(iter(host.storage.values())))
    judge = state["events"][0]
    assert (judge["score"], judge["level"], judge["signals"]) == (score, level, ["询价", "发票"])
    assert state["score"] == score and state["level"] == level
    assert (reply_text(first) == "a1\n\nASK-CONTACT") is asks
    assert state["status"] == ("asked" if asks else "idle")
    assert reply_text(second) is None
    assert len(host.llm_calls) == (1 if asks else 2)  # asked users are never re-judged


@pytest.mark.asyncio
async def test_thresholds_are_configurable():
    _plugin, host, handlers = await graph()
    host.llm_answers = ['{"score": 45}']
    ctx = responded()
    with bind_invocation(host, config={**SCORING, "ask_score": 60}, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, ctx)
    assert reply_text(ctx) is None
    # Raising the ask threshold to the high-intent line means only high intent is asked; 45 is then low.
    assert json.loads(next(iter(host.storage.values())))["level"] == "low"


@pytest.mark.asyncio
async def test_compliance_risk_never_asks_or_emails(monkeypatch):
    resend = Resend().install(monkeypatch)
    _plugin, host, handlers = await graph()
    host.llm_answers = ['{"score": 90, "risk": true, "risk_reason": "抢票", "reason": "wants bulk tickets"}']
    first, later = responded("a1"), responded("a2")
    with bind_invocation(host, config=SCORING, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, first)
        await fire(handlers, events.PersonMessageReceived, received("13800138000"))
        await fire(handlers, events.NormalMessageResponded, later)
    state = json.loads(next(iter(host.storage.values())))
    assert state["status"] == "risk" and state["reason"] == "抢票"
    assert [event["kind"] for event in state["events"]] == ["judge", "risk"]
    assert reply_text(first) is None and reply_text(later) is None
    assert resend.requests == [] and len(host.llm_calls) == 1


@pytest.mark.asyncio
async def test_email_has_score_and_extracted_fields(monkeypatch):
    resend = Resend().install(monkeypatch)
    _plugin, host, handlers = await graph()
    host.history = [row("user", "我们公司 Acme 做跨境电商，每月 500 万次请求，下周上线")]
    host.llm_answers = [
        '{"score": 75, "signals": ["大规模请求", "时间紧迫"], "reason": "规模大且着急"}',
        json.dumps({"公司名称": "Acme", "行业": "跨境电商", "预估月请求量或数据量": "500 万次", "上线时间": "下周",
                    "预算范围": "", "made_up": "x"}, ensure_ascii=False),
    ]
    config = {**SCORING, "lead_fields": ["公司名称", "行业", "预估月请求量或数据量", "预算范围", "上线时间"]}
    with bind_invocation(host, config=config, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, responded())
        await fire(handlers, events.PersonMessageReceived, received("微信 acme_boss1"))
    payload = json.loads(resend.requests[0].content)
    assert payload["subject"].startswith("【购买意向·高意向 75分】微信: acme_boss1")
    assert "意向评分：75 分（高意向）" in payload["text"]
    assert "命中信号：大规模请求、时间紧迫" in payload["text"]
    assert "公司名称：Acme" in payload["text"] and "预算范围：未提及" in payload["text"]
    assert "made_up" not in payload["text"]
    state = json.loads(next(iter(host.storage.values())))
    assert state["fields"] == {"公司名称": "Acme", "行业": "跨境电商", "预估月请求量或数据量": "500 万次", "预算范围": "", "上线时间": "下周"}


@pytest.mark.asyncio
async def test_unparseable_judgment_is_recorded_as_error():
    _plugin, host, handlers = await graph()
    host.llm_answers = ["I think the user wants to buy"]
    ctx = responded()
    with bind_invocation(host, config=SCORING, binding=binding()):
        await fire(handlers, events.NormalMessageResponded, ctx)
    state = json.loads(next(iter(host.storage.values())))
    assert reply_text(ctx) is None and state["events"][0]["kind"] == "error"


def test_score_parsing_is_clamped():
    assert lead_main.to_score("87.6") == 88
    assert lead_main.to_score(150) == 100 and lead_main.to_score(-5) == 0 and lead_main.to_score("x") == 0
