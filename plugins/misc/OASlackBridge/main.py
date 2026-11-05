from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import UTC, datetime
from urllib.parse import quote

from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.proxies.runner import PermissionDeniedError


def plain_text(chain) -> str:
    return "".join(part.text for part in chain if isinstance(part, message.Plain)).strip()


def slack_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def from_slack(text: str) -> str:
    def replace_reference(match: re.Match[str]) -> str:
        target, _, label = match.group(1).partition("|")
        if target.startswith(("http://", "https://")):
            return f"{label} {target}" if label else target
        if target.startswith("mailto:"):
            return label or target.removeprefix("mailto:")
        if target.startswith(("@", "#")):
            return target[0] + (label or target[1:])
        if target in ("!here", "!channel", "!everyone"):
            return "@" + target[1:]
        return match.group(0)

    text = re.sub(r"<([^<>]+)>", replace_reference, text)
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def send_error(error: Exception) -> str:
    if permission_denied(error):
        return permission_notice("bot.message.send")
    match = re.search(r"errcode=(\d+)", str(error))
    if not match:
        return "❌ 发送失败 / Send failed. 请检查 Bot 配置与连接 / Check bot configuration and connection."
    code = match.group(1)
    reason = {
        "45015": "48 小时回复窗口已过 / 48-hour reply window expired",
        "45047": "客服消息条数超限 / Customer-service message limit reached",
        "43004": "用户未关注公众号 / User is not following the Official Account",
        "48001": "接口无权限，请检查公众号认证 / API permission denied; check account verification",
    }.get(code, "微信拒绝发送 / WeChat rejected the message")
    return f"❌ {reason} (errcode={code})"


def permission_denied(error: Exception) -> bool:
    return (
        isinstance(error, PermissionDeniedError)
        or getattr(getattr(error, "error", error), "code", None) == "permission_denied"
        or getattr(error, "data", {}).get("error", {}).get("code") == "permission_denied"
        or "permission_denied" in str(error)
    )


def permission_notice(capability: str) -> str:
    return f"❌ 缺少权限 / Permission denied: {capability}. 请成员确认插件权限 / Ask a member to confirm plugin permissions."


class OASlackBridge(BasePlugin):
    def __init__(self):
        super().__init__()
        self._locks: dict[str, asyncio.Lock] = {}

    def scope(self, binding=None) -> str:
        if binding is None:
            binding = self.get_installation_binding()
        if binding is not None:
            return f"{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}"
        if os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared":
            raise RuntimeError("OASlackBridge requires an installation binding in shared runtime")
        return "dedicated"

    async def on_installation_revoked(self, binding):
        self._locks.pop(self.scope(binding), None)

    async def destroy(self):
        self._locks.clear()

    def key(self, kind: str, *parts: str) -> str:
        return "oasb:" + ":".join(quote(part, safe="") for part in (self.scope(), kind, *parts))

    async def load(self, key: str):
        if key not in await self.get_plugin_storage_keys():
            return None
        return json.loads(await self.get_plugin_storage(key))

    async def save(self, key: str, value):
        await self.set_plugin_storage(key, json.dumps(value).encode("utf-8"))

    def thread_key(self, session: dict) -> str:
        return self.key("thread", session["slack_bot"], session["channel"], session["thread"])

    async def close(self, key: str, session: dict):
        await self.delete_plugin_storage(self.thread_key(session))
        await self.delete_plugin_storage(key)

    async def to_slack(self, config: dict, text: str, thread: str = ""):
        parts = []
        if thread:
            parts.append(message.Quote(id=thread, origin=message.MessageChain([])))
        parts.append(message.Plain(text=text))
        return await self.send_message(
            bot_uuid=config["slack_bot"],
            target_type="group",
            target_id=config["slack_channel_id"],
            message_chain=message.MessageChain(parts),
        )

    async def handle_person(self, event_context):
        config = self.get_config()
        bot = await event_context.get_bot_uuid()
        if not bot or bot != config.get("oa_bot"):
            return
        if not config.get("slack_bot") or not config.get("slack_channel_id"):
            return
        scope = self.scope()
        async with self._locks.setdefault(scope, asyncio.Lock()):
            event = event_context.event
            openid = str(event.sender_id)
            key = self.key("session", bot, openid)
            session = await self.load(key)
            now = time.time()
            if session and (
                session["expires_at"] <= now
                or session["slack_bot"] != config["slack_bot"]
                or session["channel"] != config["slack_channel_id"]
            ):
                await self.close(key, session)
                session = None
            text = plain_text(event.message_chain)
            sensitive = config.get("case_sensitive", False)
            candidate = text if sensitive else text.casefold()
            matched = next(
                (word for word in config.get("keywords", [])
                 if word.strip() and (word if sensitive else word.casefold()) in candidate),
                "",
            )
            if not session and not matched:
                return
            event_context.prevent_default()
            event_context.prevent_postorder()
            new_session = session is None
            if new_session:
                timestamp = datetime.fromtimestamp(now, UTC).isoformat()
                display_id = openid[:6] + "…" + openid[-4:] if len(openid) > 12 else openid
                root = (
                    f"📩 公众号人工接管 / Official Account takeover\n"
                    f"用户 / User: {slack_text(display_id)}\n"
                    f"关键词 / Keyword: {slack_text(matched)}\nUTC: {timestamp}\n\n"
                    f"{slack_text(text)}\n\n"
                    "在 thread 中回复即可发送给用户；!close 结束接管。\n"
                    "Reply in this thread to send to the user; !close ends takeover."
                )
                result = await self.to_slack(config, root)
                thread = result.get("message_id") if isinstance(result, dict) else None
                if not thread:
                    raise RuntimeError("Slack send_message must return message_id; upgrade LangBot core")
                session = {
                    "oa_bot": bot, "openid": openid,
                    "slack_bot": config["slack_bot"], "channel": config["slack_channel_id"],
                    "thread": str(thread),
                }
            session["last_user_at"] = now
            session["expires_at"] = now + max(0, float(config.get("takeover_minutes", 60))) * 60
            await self.save(key, session)
            await self.save(self.thread_key(session), {"session_key": key})
            if not new_session and config.get("forward_followups", True):
                await self.to_slack(config, slack_text(text) or "[非文本消息 / Non-text message]", session["thread"])
