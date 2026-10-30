from __future__ import annotations

from typing import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext, CommandReturn


class Summary(Command):
    """Command to trigger group chat summary."""

    def __init__(self):
        super().__init__()

        @self.subcommand(
            name="",
            help="Summarize recent group chat messages",
            usage="summary [count]",
            aliases=["s"],
        )
        async def summarize(self, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            """Summarize recent N messages (default from config)."""
            if ctx.session.launcher_type.value != "group":
                yield CommandReturn(text="This command can only be used in group chats.")
                return

            # Shared placement loads this installation's buffers on demand.
            await self.plugin.ensure_loaded()

            # Parse optional count parameter
            count = None
            if ctx.crt_params:
                try:
                    count = int(ctx.crt_params[0])
                    if count <= 0:
                        yield CommandReturn(text="Message count must be positive.")
                        return
                    if count > 1000:
                        count = 1000
                except ValueError:
                    yield CommandReturn(
                        text="Invalid number. Usage: !summary [count]"
                    )
                    return

            # Show progress
            msg_count = self.plugin.get_message_count(
                ctx.session.launcher_type.value, ctx.session.launcher_id
            )
            actual_count = count or self.plugin._get_default_summary_count()
            actual_count = min(actual_count, msg_count)

            if msg_count == 0:
                yield CommandReturn(text=self.plugin._get_no_messages_text())
                return

            yield CommandReturn(
                text=f"⏳ Summarizing {actual_count} messages..."
            )

            summary = await self.plugin.generate_summary(
                launcher_type=ctx.session.launcher_type.value,
                launcher_id=ctx.session.launcher_id,
                count=count,
            )

            yield CommandReturn(text=f"📋 Group Chat Summary\n\n{summary}")

        @self.subcommand(
            name="hours",
            help="Summarize messages from last N hours",
            usage="summary hours <N>",
            aliases=["h"],
        )
        async def summarize_hours(self, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            """Summarize messages from the last N hours."""
            if ctx.session.launcher_type.value != "group":
                yield CommandReturn(text="This command can only be used in group chats.")
                return

            if not ctx.crt_params:
                yield CommandReturn(text="Please specify hours. Usage: !summary hours 3")
                return

            try:
                hours = float(ctx.crt_params[0])
                if hours <= 0:
                    yield CommandReturn(text="Hours must be positive.")
                    return
            except ValueError:
                yield CommandReturn(text="Invalid number. Usage: !summary hours 3")
                return

            yield CommandReturn(text=f"⏳ Summarizing messages from last {hours} hours...")

            summary = await self.plugin.generate_summary(
                launcher_type=ctx.session.launcher_type.value,
                launcher_id=ctx.session.launcher_id,
                hours=hours,
            )

            yield CommandReturn(text=f"📋 Group Chat Summary (Last {hours}h)\n\n{summary}")

        @self.subcommand(
            name="status",
            help="Show message buffer status",
            usage="summary status",
            aliases=["st"],
        )
        async def status(self, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            """Show how many messages are stored."""
            await self.plugin.ensure_loaded()
            count = self.plugin.get_message_count(
                ctx.session.launcher_type.value, ctx.session.launcher_id
            )
            max_msg = self.plugin._get_max_messages()

            text = f"📊 Message Buffer Status\n"
            text += f"  Stored: {count} / {max_msg}\n"

            if count > 0:
                key = self.plugin._group_key(
                    ctx.session.launcher_type.value, ctx.session.launcher_id
                )
                messages = self.plugin.message_buffer.get(key, [])
                if messages:
                    import time as _time
                    oldest = _time.strftime(
                        "%Y-%m-%d %H:%M", _time.localtime(messages[0]["time"])
                    )
                    newest = _time.strftime(
                        "%Y-%m-%d %H:%M", _time.localtime(messages[-1]["time"])
                    )
                    text += f"  Oldest: {oldest}\n"
                    text += f"  Newest: {newest}\n"

                    # Count unique senders
                    unique_senders = len(set(m["sender"] for m in messages))
                    text += f"  Participants: {unique_senders}"

            yield CommandReturn(text=text)

        @self.subcommand(
            name="clear",
            help="Clear stored messages for this group",
            usage="summary clear",
            aliases=["c"],
        )
        async def clear(self, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            """Clear the message buffer for this group."""
            await self.plugin.ensure_loaded()
            key = self.plugin._group_key(
                ctx.session.launcher_type.value, ctx.session.launcher_id
            )
            count = len(self.plugin.message_buffer.get(key, []))
            self.plugin.message_buffer[key] = []
            await self.plugin._persist_buffers()

            yield CommandReturn(text=f"✅ Cleared {count} stored messages.")
