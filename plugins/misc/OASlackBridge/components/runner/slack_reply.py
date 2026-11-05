import asyncio
import re
import time

from langbot_plugin.api.definition.components.runner import Runner, RunnerContext
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.entities.builtin.platform.events import MessageReceivedEvent

from main import from_slack, permission_denied, permission_notice, plain_text, send_error


class SlackReplyProcessor(Runner):
    async def initialize(self):
        await super().initialize()

        @self.handler(MessageReceivedEvent)
        async def on_message(ctx: RunnerContext):
            event = ctx.platform_event
            config = self.plugin.get_config()
            if (
                not event.bot_uuid
                or event.bot_uuid != config.get("slack_bot")
                or str(event.chat_id) != config.get("slack_channel_id")
            ):
                return
            thread = next((part.id for part in event.message_chain if isinstance(part, message.Quote)), "")
            if not thread:
                return
            try:
                async with self.plugin._locks.setdefault(self.plugin.scope(), asyncio.Lock()):
                    await self.handle_reply(ctx, config, thread)
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

    async def handle_reply(self, ctx: RunnerContext, config: dict, thread: str):
        event = ctx.platform_event
        mapping = await self.plugin.load(self.plugin.key("thread", event.bot_uuid, str(event.chat_id), thread))
        if not mapping:
            await ctx.log("Ignoring Slack thread without a takeover mapping.")
            return
        key = mapping["session_key"]
        session = await self.plugin.load(key)
        if not session or session["thread"] != thread or session["oa_bot"] != config.get("oa_bot"):
            await ctx.log("Ignoring Slack thread without a matching takeover session.")
            return
        text = plain_text(event.message_chain)
        if any(isinstance(part, message.At) for part in event.message_chain):
            text = re.sub(r"^<@[^>]+>\s*", "", text).strip()
        now = time.time()
        if text in ("/close", "!close"):
            await self.plugin.close(key, session)
            await self.acknowledge(ctx, "✅ 接管已结束，恢复 AI 回复 / Takeover closed; AI replies resumed.")
            return
        if now - session["last_user_at"] >= 48 * 3600:
            await self.plugin.close(key, session)
            await self.acknowledge(ctx, "❌ 48 小时回复窗口已过 / 48-hour reply window expired")
            return
        if session["expires_at"] <= now:
            await self.plugin.close(key, session)
            await self.acknowledge(ctx, "❌ 接管已到期，恢复 AI 回复 / Takeover expired; AI replies resumed.")
            return
        if not text:
            await self.acknowledge(ctx, "❌ 仅支持文本回复 / Only text replies are supported.")
            return
        try:
            await self.plugin.send_message(
                bot_uuid=session["oa_bot"], target_type="person", target_id=session["openid"],
                message_chain=message.MessageChain([message.Plain(text=from_slack(text))]),
            )
        except Exception as error:
            if permission_denied(error):
                await ctx.log(permission_notice("bot.message.send"), "warning")
            await self.acknowledge(ctx, send_error(error))
        else:
            await self.acknowledge(ctx, "✅ 已发送 / Sent")
