from __future__ import annotations

import asyncio
import base64
import html
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from urllib.parse import quote

import httpx

from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.entities.builtin.provider.message import ContentElement, Message
from langbot_plugin.api.proxies.runner import PermissionDeniedError

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_INTENT_PROMPT = (
    "用户明确表达了购买、下单、试用、报价、签约、采购或与销售沟通的意愿，"
    "或在询问价格、套餐、付款方式、发票、合同、交付时间等成交相关细节，视为强烈购买意愿。"
    "只是了解产品功能、闲聊或技术咨询，不算强烈购买意愿。"
)
DEFAULT_ASK_TEXT = "为了更好地为您服务，方便留下您的手机号或微信号吗？我们的顾问会尽快与您联系。"
DEFAULT_THANKS_TEXT = "已收到您的联系方式，我们的顾问会尽快与您联系，感谢您的信任！"
MAX_EMAIL_ATTEMPTS = 3
PAGE_SIZE = 100
MAX_TRANSCRIPT_MESSAGES = 5000
COMPONENT_LABELS = {
    "Image": "[图片]", "Voice": "[语音]", "File": "[文件]", "Face": "[表情]", "Forward": "[转发]",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
MOBILE_RE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d(?:[-\s]?\d{4}){2}(?!\d)")
LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}-\d{7,8}(?!\d)")
WECHAT_RE = re.compile(
    r"(?:微信号?|weixin|wechat|vx|wx|v信|威信)\s*(?:号|id)?\s*[:：是为]?\s*([A-Za-z][-_A-Za-z0-9]{5,19})",
    re.IGNORECASE,
)


def permission_denied(error: Exception) -> bool:
    return (
        isinstance(error, PermissionDeniedError)
        or getattr(getattr(error, "error", error), "code", None) == "permission_denied"
        or "permission_denied" in str(error)
    )


def plain_text(chain) -> str:
    return "".join(part.text for part in chain if isinstance(part, message.Plain)).strip()


def find_contact(text: str) -> str:
    """Return contact details found by pattern, or an empty string."""
    found = []
    for pattern in (MOBILE_RE, LANDLINE_RE, EMAIL_RE):
        found.extend(match.group(0).strip() for match in pattern.finditer(text))
    found.extend(f"微信: {match.group(1)}" for match in WECHAT_RE.finditer(text))
    unique = list(dict.fromkeys(found))
    return "；".join(unique)


def stored_text(content) -> str:
    """Render a monitoring message_content (JSON message chain) as plain text."""
    try:
        parts = json.loads(content) if isinstance(content, str) else content
    except ValueError:
        return str(content)
    if not isinstance(parts, list):
        return str(parts)
    rendered = []
    for part in parts:
        if not isinstance(part, dict) or part.get("type") in ("Source", "Quote", "At"):
            continue
        if part.get("type") == "Plain":
            rendered.append(str(part.get("text", "")))
        else:
            rendered.append(COMPONENT_LABELS.get(part.get("type"), f"[{part.get('type')}]"))
    return "".join(rendered).strip()


def utc_label(timestamp, seconds: bool = True) -> str:
    try:
        moment = datetime.fromisoformat(str(timestamp))
    except ValueError:
        return str(timestamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M")


def parse_json_object(text: str) -> dict:
    """Extract the first JSON object from an LLM response (tolerates code fences and prose)."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def response_text(response) -> str:
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(getattr(part, "text", "") or "" for part in content).strip()
    return ""


def role_label(role: str) -> str:
    return "用户" if role == "user" else "AI"


class LeadCapture(BasePlugin):
    """Detect strong purchase intent with an LLM, ask once for contact details, email the lead."""

    def __init__(self):
        super().__init__()
        self._locks: dict[str, asyncio.Lock] = {}

    def scope(self, binding=None) -> str:
        if binding is None:
            binding = self.get_installation_binding()
        if binding is not None:
            return f"{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}"
        if os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared":
            raise RuntimeError("LeadCapture requires an installation binding in shared runtime")
        return "dedicated"

    async def on_installation_revoked(self, binding):
        self._locks.pop(self.scope(binding), None)

    async def destroy(self):
        self._locks.clear()

    def lock(self) -> asyncio.Lock:
        return self._locks.setdefault(self.scope(), asyncio.Lock())

    def key(self, bot: str, user: str) -> str:
        return "lead:" + ":".join(quote(str(part), safe="") for part in (self.scope(), bot, user))

    async def load(self, key: str):
        if key not in await self.get_plugin_storage_keys():
            return None
        return json.loads(await self.get_plugin_storage(key))

    async def save(self, key: str, value):
        await self.set_plugin_storage(key, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    # ---- conversation history --------------------------------------------------

    async def messages_page(self, bot: str, user: str, limit: int, offset: int = 0):
        """Return (rows newest first, total) for the user's private session."""
        response = await self.workspace.monitoring.messages(
            bot_ids=[bot], session_ids=[f"person_{user}"], limit=limit, offset=offset,
        )
        if not isinstance(response, dict) or not response.get("ok"):
            error = (response or {}).get("error", {}) if isinstance(response, dict) else {}
            raise RuntimeError(f"monitoring.messages failed: {error.get('code', 'error')}")
        rows, total = (list(response.get("result") or []) + [[], 0])[:2]
        return (rows if isinstance(rows, list) else []), int(total or 0)

    async def recent_dialogue(self, bot: str, user: str, limit: int) -> list[str]:
        rows, _ = await self.messages_page(bot, user, limit)
        return [f"{role_label(row.get('role'))}: {stored_text(row.get('message_content'))}" for row in reversed(rows)]

    async def full_history(self, bot: str, user: str) -> list[dict]:
        rows, total = await self.messages_page(bot, user, PAGE_SIZE)
        collected = list(rows)
        offset = len(rows)
        while offset < min(total, MAX_TRANSCRIPT_MESSAGES) and rows:
            rows, _ = await self.messages_page(bot, user, PAGE_SIZE, offset)
            collected.extend(rows)
            offset += len(rows)
        return list(reversed(collected))

    # ---- LLM -----------------------------------------------------------------

    async def ask_llm(self, model: str, system: str, user_text: str) -> dict:
        response = await self.invoke_llm(
            llm_model_uuid=model,
            messages=[
                Message(role="system", content=[ContentElement.from_text(system)]),
                Message(role="user", content=[ContentElement.from_text(user_text)]),
            ],
        )
        return parse_json_object(response_text(response))

    async def evaluate_intent(self, config: dict, dialogue: list[str]) -> tuple[bool, str]:
        criteria = str(config.get("intent_prompt") or DEFAULT_INTENT_PROMPT).strip()
        system = (
            "你是销售线索分析助手。请根据「判断标准」阅读客户与 AI 客服的对话，判断客户当前是否有强烈购买意愿。\n"
            "只输出一个 JSON 对象，不要输出其他内容：{\"strong_intent\": true 或 false, \"reason\": \"一句话理由\"}\n\n"
            f"判断标准：\n{criteria}"
        )
        result = await self.ask_llm(str(config["model"]), system, "对话记录（从旧到新）：\n" + "\n".join(dialogue))
        strong = result.get("strong_intent")
        if isinstance(strong, str):
            strong = strong.strip().lower() in ("true", "yes", "1", "是")
        return bool(strong), str(result.get("reason") or "").strip()

    async def extract_contact(self, config: dict, text: str) -> str:
        contact = find_contact(text)
        if contact or not text.strip():
            return contact
        system = (
            "从客户的这条消息中提取联系方式（手机号、电话、微信号、邮箱、QQ 号等）。"
            "只输出 JSON：{\"contact\": \"联系方式，多个用；分隔，没有则为空字符串\"}。"
            "不要编造，消息里没有明确的联系方式时返回空字符串。"
        )
        try:
            result = await self.ask_llm(str(config["model"]), system, text)
        except Exception as error:
            logger.warning("LeadCapture contact extraction failed: %s", type(error).__name__)
            return ""
        return str(result.get("contact") or "").strip()

    # ---- email -----------------------------------------------------------------

    def build_email(self, config: dict, lead: dict, history: list[dict]) -> dict:
        bot_name = next((row.get("bot_name") for row in history if row.get("bot_name")), "") or lead["bot"]
        first = utc_label(history[0].get("timestamp")) if history else "-"
        lines = [
            f"[{utc_label(row.get('timestamp'))} UTC] {role_label(row.get('role'))}: {stored_text(row.get('message_content'))}"
            for row in history
        ]
        summary = [
            ("联系方式", lead["contact"]),
            ("用户 ID", lead["user"]),
            ("来源 Bot", bot_name),
            ("意向判断理由", lead.get("reason") or "-"),
            ("留资时间 (UTC)", utc_label(datetime.fromtimestamp(lead["captured_at"], UTC).isoformat())),
            ("首次联系 (UTC)", first),
            ("消息总数", str(len(history))),
        ]
        text_body = "\n".join(f"{name}：{value}" for name, value in summary)
        text_body += "\n\n完整对话记录见附件；以下为全文：\n\n" + "\n".join(lines)
        html_rows = "".join(
            f"<tr><td style='padding:4px 12px 4px 0;color:#666'>{html.escape(name)}</td>"
            f"<td style='padding:4px 0'>{html.escape(value)}</td></tr>"
            for name, value in summary
        )
        html_lines = "".join(f"<div style='margin:2px 0'>{html.escape(line)}</div>" for line in lines)
        html_body = (
            "<h2 style='margin:0 0 12px'>新的购买意向线索</h2>"
            f"<table style='border-collapse:collapse'>{html_rows}</table>"
            "<h3 style='margin:20px 0 8px'>对话记录</h3>"
            f"<div style='font-family:monospace;font-size:13px;white-space:pre-wrap'>{html_lines}</div>"
        )
        transcript = "\n".join(lines).encode("utf-8")
        stamp = datetime.fromtimestamp(lead["captured_at"], UTC).strftime("%Y%m%d-%H%M%S")
        return {
            "from": str(config.get("from_email") or "").strip(),
            "to": [address.strip() for address in config.get("to_emails", []) if str(address).strip()],
            "subject": f"【购买意向】{lead['contact']} · {bot_name}",
            "text": text_body,
            "html": html_body,
            "attachments": [{
                "filename": f"conversation-{stamp}.txt",
                "content": base64.b64encode(transcript).decode("ascii"),
            }],
        }

    async def send_email(self, config: dict, payload: dict) -> str:
        """Send through Resend; returns '' on success or a short error code (never the API key)."""
        api_key = str(config.get("resend_api_key") or "").strip()
        if not api_key or not payload["from"] or not payload["to"]:
            return "not_configured"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    RESEND_URL, json=payload, headers={"Authorization": f"Bearer {api_key}"},
                )
        except httpx.HTTPError as error:
            return f"network:{type(error).__name__}"
        if response.status_code >= 300:
            try:
                name = str(response.json().get("name") or "")
            except ValueError:
                name = ""
            return f"http_{response.status_code}" + (f":{name}" if name else "")
        return ""

    async def deliver(self, config: dict, lead: dict) -> None:
        """Email the lead; record the outcome on the lead row."""
        lead["email_attempts"] = int(lead.get("email_attempts", 0)) + 1
        try:
            history = await self.full_history(lead["bot"], lead["user"])
        except Exception as error:
            lead["email_status"] = f"history:{'permission_denied' if permission_denied(error) else type(error).__name__}"
            logger.warning("LeadCapture could not read the conversation: %s", lead["email_status"])
            return
        error = await self.send_email(config, self.build_email(config, lead, history))
        lead["email_status"] = error or "sent"
        if error:
            logger.warning("LeadCapture email failed (%s), attempt %s", error, lead["email_attempts"])

    # ---- events --------------------------------------------------------------------

    @staticmethod
    def configured(config: dict) -> bool:
        return bool(config.get("model"))

    async def on_person_message(self, event_context) -> None:
        """While waiting for contact details, look for them in each user message."""
        config = self.get_config()
        if not self.configured(config):
            return
        bot = str(await event_context.get_bot_uuid() or "")
        if not bot:
            return
        event = event_context.event
        user = str(event.sender_id)
        async with self.lock():
            key = self.key(bot, user)
            lead = await self.load(key)
            if not lead or lead.get("status") != "asked":
                return
            contact = await self.extract_contact(config, plain_text(event.message_chain))
            if not contact:
                return
            lead.update(status="captured", contact=contact, captured_at=time.time(), thanks_pending=True)
            await self.save(key, lead)
            await self.deliver(config, lead)
            await self.save(key, lead)

    async def on_responded(self, event_context) -> None:
        """After each AI reply: judge intent and ask once, or append the thank-you."""
        config = self.get_config()
        event = event_context.event
        if not self.configured(config) or str(event.launcher_type) != "person":
            return
        bot = str(await event_context.get_bot_uuid() or "")
        if not bot:
            return
        user = str(event.sender_id)
        async with self.lock():
            key = self.key(bot, user)
            lead = await self.load(key)
            if lead and lead.get("status") == "captured":
                if lead.get("email_status") != "sent" and int(lead.get("email_attempts", 0)) < MAX_EMAIL_ATTEMPTS:
                    await self.deliver(config, lead)
                if lead.pop("thanks_pending", False):
                    self.append_to_reply(event_context, str(config.get("thanks_text", DEFAULT_THANKS_TEXT) or ""))
                await self.save(key, lead)
                return
            if lead:
                return  # Already asked once; never ask again.
            try:
                history = int(config.get("history_messages", 20))
            except (TypeError, ValueError):
                history = 20
            try:
                dialogue = await self.recent_dialogue(bot, user, max(1, min(history, 100)))
            except Exception as error:
                logger.warning("LeadCapture could not read recent messages: %s", type(error).__name__)
                return
            dialogue.append(f"AI: {event.response_text}")
            try:
                strong, reason = await self.evaluate_intent(config, dialogue)
            except Exception as error:
                logger.warning("LeadCapture intent evaluation failed: %s", type(error).__name__)
                return
            if not strong:
                return
            await self.save(key, {"status": "asked", "bot": bot, "user": user, "reason": reason, "asked_at": time.time()})
            self.append_to_reply(event_context, str(config.get("ask_text") or DEFAULT_ASK_TEXT))

    @staticmethod
    def append_to_reply(event_context, text: str) -> None:
        text = text.strip()
        if not text:
            return
        event = event_context.event
        base = list(event.reply_message_chain) if event.reply_message_chain is not None else [
            message.Plain(text=event.response_text)
        ]
        event.reply_message_chain = message.MessageChain([*base, message.Plain(text=f"\n\n{text}")])
