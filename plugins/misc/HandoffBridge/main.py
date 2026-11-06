from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from urllib.parse import quote

from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.proxies.runner import PermissionDeniedError

DEFAULT_START_NOTICE = "已为您转接人工客服，请稍候，客服会在这里回复您。"
DEFAULT_END_NOTICE = "人工客服已结束本次服务，后续将由 AI 助手继续为您解答。"
COMPONENT_LABELS = {
    "Image": "[图片 / Image]", "Voice": "[语音 / Voice]", "File": "[文件 / File]",
    "Face": "[表情 / Sticker]", "Forward": "[转发 / Forward]",
}
MAX_HISTORY_MESSAGES = 50
MAX_HISTORY_CHARS = 300
MAX_REFS = 200


def plain_text(chain) -> str:
    return "".join(part.text for part in chain if isinstance(part, message.Plain)).strip()


def is_slack(adapter: str) -> bool:
    return str(adapter or "").split("-")[0] == "slack"


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
    }.get(code, "平台拒绝发送 / The platform rejected the message")
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


def stored_text(content) -> str:
    """Render a monitoring message_content (JSON message chain) as one line of plain text."""
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
    text = " ".join("".join(rendered).split())
    return text if len(text) <= MAX_HISTORY_CHARS else text[:MAX_HISTORY_CHARS] + "…"


def utc_label(timestamp) -> str:
    try:
        moment = datetime.fromisoformat(str(timestamp))
    except ValueError:
        return str(timestamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


class HandoffBridge(BasePlugin):
    """Hand customers of one bot over to human staff reachable through another bot."""

    def __init__(self):
        super().__init__()
        self._locks: dict[str, asyncio.Lock] = {}

    def scope(self, binding=None) -> str:
        if binding is None:
            binding = self.get_installation_binding()
        if binding is not None:
            return f"{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}"
        if os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared":
            raise RuntimeError("HandoffBridge requires an installation binding in shared runtime")
        return "dedicated"

    async def on_installation_revoked(self, binding):
        self._locks.pop(self.scope(binding), None)

    async def destroy(self):
        self._locks.clear()

    def lock(self) -> asyncio.Lock:
        return self._locks.setdefault(self.scope(), asyncio.Lock())

    # ---- storage -------------------------------------------------------------

    def key(self, kind: str, *parts: str) -> str:
        return "hob:" + ":".join(quote(str(part), safe="") for part in (self.scope(), kind, *parts))

    async def load(self, key: str):
        if key not in await self.get_plugin_storage_keys():
            return None
        return json.loads(await self.get_plugin_storage(key))

    async def save(self, key: str, value):
        await self.set_plugin_storage(key, json.dumps(value).encode("utf-8"))

    def ref_key(self, session: dict, message_id: str) -> str:
        return self.key("ref", session["staff_bot"], session["staff_type"], session["staff_target"], message_id)

    async def remember_ref(self, session: dict, session_key: str, message_id: str):
        """Map one staff-side message to the session so staff can reply to (quote) it."""
        message_id = str(message_id or "")
        if not message_id:
            return
        refs = session.setdefault("refs", [])
        if message_id not in refs:
            refs.append(message_id)
            if len(refs) > MAX_REFS:
                await self.delete_plugin_storage(self.ref_key(session, refs.pop(1)))
        await self.save(self.ref_key(session, message_id), {"session_key": session_key})

    async def close(self, key: str, session: dict):
        for message_id in session.get("refs", [session.get("root", "")]):
            if message_id:
                await self.delete_plugin_storage(self.ref_key(session, message_id))
        await self.delete_plugin_storage(key)

    # ---- configuration ---------------------------------------------------------

    @staticmethod
    def staff_destination(config: dict) -> tuple[str, str, str]:
        target_type = "person" if config.get("staff_target_type") == "person" else "group"
        return str(config.get("staff_bot") or ""), target_type, str(config.get("staff_target_id") or "").strip()

    async def bot_info(self, bot_uuid: str) -> dict:
        """Return bot name/adapter; empty on failure so formatting falls back to plain text."""
        try:
            info = await self.get_bot_info(bot_uuid)
        except Exception as error:
            if not permission_denied(error):
                logging.getLogger(__name__).warning("HandoffBridge get_bot_info failed: %s", type(error).__name__)
            return {}
        return info if isinstance(info, dict) else {}

    # ---- sending ---------------------------------------------------------------

    async def to_staff(self, session_or_config: dict, text: str, reply_to: str = ""):
        """Send text to the staff destination, as a reply to ``reply_to`` when given."""
        bot = session_or_config.get("staff_bot")
        target_type = session_or_config.get("staff_type") or self.staff_destination(session_or_config)[1]
        target = session_or_config.get("staff_target") or self.staff_destination(session_or_config)[2]
        slack = is_slack(session_or_config.get("staff_adapter", ""))
        parts = []
        if reply_to:
            parts.append(message.Quote(id=reply_to, origin=message.MessageChain([])))
        parts.append(message.Plain(text=slack_text(text) if slack else text))
        return await self.send_message(
            bot_uuid=bot, target_type=target_type, target_id=target,
            message_chain=message.MessageChain(parts),
        )

    async def to_staff_thread(self, session: dict, session_key: str, text: str) -> None:
        """Post into the session's staff thread and make that message repliable too."""
        result = await self.to_staff(session, text, session["root"])
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if message_id:
            await self.remember_ref(session, session_key, str(message_id))
            await self.save(session_key, session)

    async def warn_staff(self, session: dict, session_key: str, warning: str):
        if not warning:
            return
        try:
            await self.to_staff_thread(session, session_key, warning)
        except Exception as error:
            if not permission_denied(error):
                raise
            logging.getLogger(__name__).warning(warning)

    async def notify_user(self, config: dict, session: dict, kind: str) -> str:
        """Send the configured start/end notice to the customer.

        Returns an empty string on success or when the notice is disabled, otherwise a
        readable error for staff. Never raises, so a failed notice cannot undo or block
        the takeover state change that triggered it.
        """
        default = DEFAULT_START_NOTICE if kind == "start" else DEFAULT_END_NOTICE
        notice = str(config.get(f"{kind}_notice", default) or "").strip()
        if not notice:
            return ""
        try:
            await self.send_message(
                bot_uuid=session["source_bot"], target_type="person", target_id=session["user"],
                message_chain=message.MessageChain([message.Plain(text=notice)]),
            )
        except Exception as error:
            label = "开始" if kind == "start" else "结束"
            return f"⚠️ 未能向用户发送接管{label}提示 / Failed to send the {kind} notice: {send_error(error)}"
        return ""

    # ---- user details ----------------------------------------------------------

    async def query_messages(self, bot: str, session_id: str, limit: int, offset: int = 0):
        """Read the user's processed messages (newest first); returns (rows, total) or an error string."""
        try:
            response = await self.workspace.monitoring.messages(
                bot_ids=[bot], session_ids=[session_id], limit=limit, offset=offset,
            )
        except Exception as error:
            return None, "permission_denied" if permission_denied(error) else type(error).__name__
        if not isinstance(response, dict) or not response.get("ok"):
            if "permission_denied" in str(response):
                return None, "permission_denied"
            code = (response.get("error") or {}).get("code", "error") if isinstance(response, dict) else "error"
            return None, str(code)
        rows, total = (list(response.get("result") or []) + [[], 0])[:2]
        return (rows if isinstance(rows, list) else [], int(total or 0)), ""

    async def user_details(self, config: dict, session: dict, matched: str) -> str:
        user = session["user"]
        session_id = f"person_{user}"
        expires = datetime.fromtimestamp(session["expires_at"], UTC).strftime("%Y-%m-%d %H:%M")
        lines = [
            "👤 用户详情 / User details",
            f"• 用户 ID / User ID: `{user}`",
            f"• 会话 / Session: `{session_id}`",
            f"• 触发关键词 / Keyword: {matched}",
            f"• 接管至 / Takeover until (UTC): {expires}",
        ]
        if session.get("source_name"):
            lines.insert(1, f"• 来源 Bot / Source bot: {session['source_name']}")
        try:
            history = min(MAX_HISTORY_MESSAGES, max(0, int(config.get("history_messages", 10))))
        except (TypeError, ValueError):
            history = 10
        page, error = await self.query_messages(session["source_bot"], session_id, max(history, 1))
        if error:
            reason = (
                "需在插件详情页确认 monitoring.messages 权限 / confirm the monitoring.messages permission"
                if error == "permission_denied" else f"查询失败 / query failed ({error})"
            )
            lines.append(f"• 历史记录不可用 / History unavailable: {reason}")
            return "\n".join(lines)
        rows, total = page
        first_seen = rows[-1].get("timestamp") if rows else None
        if total > len(rows):
            oldest, _ = await self.query_messages(session["source_bot"], session_id, 1, total - 1)
            if oldest and oldest[0]:
                first_seen = oldest[0][0].get("timestamp")
        lines.append(f"• 历史消息数 / Messages so far: {total}")
        if first_seen:
            lines.append(f"• 首次联系 / First contact (UTC): {utc_label(first_seen)}")
        if history and rows:
            lines.append("")
            lines.append(f"最近 {min(history, len(rows))} 条对话 / Recent conversation (UTC):")
            for row in reversed(rows[:history]):
                who = "用户 / User" if row.get("role") == "user" else "AI / Bot"
                body = stored_text(row.get("message_content")) or "[空 / empty]"
                lines.append(f"[{utc_label(row.get('timestamp'))}] {who}: {body}")
        return "\n".join(lines)

    async def post_user_details(self, config: dict, session: dict, session_key: str, matched: str):
        if not config.get("send_user_details", True):
            return
        try:
            details = await self.user_details(config, session, matched)
        except Exception as error:
            logging.getLogger(__name__).warning("HandoffBridge user details failed: %s", type(error).__name__)
            return
        await self.warn_staff(session, session_key, details)

    # ---- customer side -----------------------------------------------------------

    async def handle_person(self, event_context):
        config = self.get_config()
        bot = await event_context.get_bot_uuid()
        if not bot or bot != config.get("source_bot"):
            return
        staff_bot, staff_type, staff_target = self.staff_destination(config)
        if not staff_bot or not staff_target:
            return
        async with self.lock():
            event = event_context.event
            user = str(event.sender_id)
            key = self.key("session", bot, user)
            session = await self.load(key)
            now = time.time()
            ended = None
            if session and (
                session["expires_at"] <= now
                or (session["staff_bot"], session["staff_type"], session["staff_target"])
                != (staff_bot, staff_type, staff_target)
            ):
                await self.close(key, session)
                ended, session = session, None
            text = plain_text(event.message_chain)
            sensitive = config.get("case_sensitive", False)
            candidate = text if sensitive else text.casefold()
            matched = next(
                (word for word in config.get("keywords", [])
                 if word.strip() and (word if sensitive else word.casefold()) in candidate),
                "",
            )
            if ended and not matched:
                # The user is back with the AI; tell them before its reply arrives.
                warning = await self.notify_user(config, ended, "end")
                if warning:
                    logging.getLogger(__name__).warning(warning)
            if not session and not matched:
                return
            new_session = session is None
            if new_session:
                source = await self.bot_info(bot)
                staff = await self.bot_info(staff_bot)
                session = {
                    "source_bot": bot, "source_name": str(source.get("name") or ""), "user": user,
                    "staff_bot": staff_bot, "staff_type": staff_type, "staff_target": staff_target,
                    "staff_adapter": str(staff.get("adapter") or ""), "refs": [],
                }
                timestamp = datetime.fromtimestamp(now, UTC).isoformat()
                display_id = user[:6] + "…" + user[-4:] if len(user) > 12 else user
                source_line = f"来源 / Source: {session['source_name']}\n" if session["source_name"] else ""
                root = (
                    f"📩 人工客服请求 / Human handoff request\n{source_line}"
                    f"用户 / User: {display_id}\n"
                    f"关键词 / Keyword: {matched}\nUTC: {timestamp}\n\n{text}\n\n"
                    "回复（引用）这条消息即可发送给用户；发送 !close 结束接管。\n"
                    "Reply to (quote) this message to answer the user; send !close to end the takeover."
                )
                result = await self.to_staff(session, root)
                root_id = result.get("message_id") if isinstance(result, dict) else None
                if not root_id:
                    raise RuntimeError("Staff bot send_message must return message_id to route replies")
                session["root"] = str(root_id)
                await self.remember_ref(session, key, session["root"])
            session["last_user_at"] = now
            session["expires_at"] = now + max(0, float(config.get("takeover_minutes", 60))) * 60
            await self.save(key, session)
            if new_session:
                await self.post_user_details(config, session, key, matched)
                await self.warn_staff(session, key, await self.notify_user(config, session, "start"))
            elif config.get("forward_followups", True):
                await self.to_staff_thread(session, key, text or "[非文本消息 / Non-text message]")
            event_context.prevent_default()
            event_context.prevent_postorder()
