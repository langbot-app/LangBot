import re
import time

from langbot_plugin.api.definition.components.runner import Runner, RunnerContext
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.entities.builtin.platform.events import MessageReceivedEvent

from main import from_slack, is_slack, permission_denied, permission_notice, plain_text, send_error


class StaffReplyProcessor(Runner):
    async def initialize(self):
        await super().initialize()

        @self.handler(MessageReceivedEvent)
        async def on_message(ctx: RunnerContext):
            event = ctx.platform_event
            config = self.plugin.get_config()
            staff_bot, staff_type, staff_target = self.plugin.staff_destination(config)
            if not event.bot_uuid or event.bot_uuid != staff_bot or not staff_target:
                return
            chat_type = str(getattr(event.chat_type, "value", event.chat_type))
            expected = "group" if staff_type == "group" else "private"
            if chat_type != expected or str(event.chat_id) != staff_target:
                return
            reply_to = next((part.id for part in event.message_chain if isinstance(part, message.Quote)), "")
            if not reply_to:
                return
            try:
                async with self.plugin.lock():
                    await self.handle_reply(ctx, config, (staff_bot, staff_type, staff_target), str(reply_to))
            except Exception as error:
                if not permission_denied(error):
                    raise
                await ctx.log(permission_notice("storage.plugin"), "warning")
                await self.acknowledge(ctx, permission_notice("storage.plugin"))

    async def acknowledge(self, ctx: RunnerContext, text: str):
        try:
            await ctx.reply(text)
        except Exception as error:
            if not permission_denied(error):
                raise
            await ctx.log("Permission denied: event_reply; check processor tools.call authorization.", "warning")

    async def notify_end(self, ctx: RunnerContext, config: dict, session: dict):
        warning = await self.plugin.notify_user(config, session, "end")
        if warning:
            await self.acknowledge(ctx, warning)

    async def handle_reply(self, ctx: RunnerContext, config: dict, destination: tuple[str, str, str], reply_to: str):
        event = ctx.platform_event
        staff_bot, staff_type, staff_target = destination
        mapping = await self.plugin.load(self.plugin.key("ref", staff_bot, staff_type, staff_target, reply_to))
        if not mapping:
            await ctx.log("Ignoring a staff reply that is not linked to a handoff.")
            return
        key = mapping["session_key"]
        session = await self.plugin.load(key)
        if (
            not session
            or reply_to not in session.get("refs", [])
            or session["source_bot"] != config.get("source_bot")
        ):
            await ctx.log("Ignoring a staff reply without a matching handoff session.")
            return
        text = plain_text(event.message_chain)
        slack = is_slack(session.get("staff_adapter", ""))
        if slack and any(isinstance(part, message.At) for part in event.message_chain):
            text = re.sub(r"^<@[^>]+>\s*", "", text).strip()
        now = time.time()
        if text in ("/close", "!close"):
            await self.plugin.close(key, session)
            await self.acknowledge(ctx, "✅ 接管已结束，恢复 AI 回复 / Takeover closed; AI replies resumed.")
            await self.notify_end(ctx, config, session)
            return
        try:
            window = float(config.get("reply_window_hours", 0) or 0)
        except (TypeError, ValueError):
            window = 0
        if window > 0 and now - session["last_user_at"] >= window * 3600:
            await self.plugin.close(key, session)
            await self.acknowledge(
                ctx, f"❌ 已超过 {window:g} 小时回复窗口 / {window:g}-hour reply window expired",
            )
            return
        if session["expires_at"] <= now:
            await self.plugin.close(key, session)
            await self.acknowledge(ctx, "❌ 接管已到期，恢复 AI 回复 / Takeover expired; AI replies resumed.")
            await self.notify_end(ctx, config, session)
            return
        if not text:
            await self.acknowledge(ctx, "❌ 仅支持文本回复 / Only text replies are supported.")
            return
        try:
            await self.plugin.send_message(
                bot_uuid=session["source_bot"], target_type="person", target_id=session["user"],
                message_chain=message.MessageChain([message.Plain(text=from_slack(text) if slack else text)]),
            )
        except Exception as error:
            if permission_denied(error):
                await ctx.log(permission_notice("bot.message.send"), "warning")
            await self.acknowledge(ctx, send_error(error))
        else:
            await self.acknowledge(ctx, "✅ 已发送 / Sent")
