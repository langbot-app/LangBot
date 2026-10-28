"""An explicitly selected, read-only wildcard event processor."""

from __future__ import annotations

import json

from langbot_plugin.api.definition.components.runner import (
    Runner,
    RunnerContext,
)
from langbot_plugin.api.entities.builtin.platform.events import EBAEvent


class ObserverProcessor(Runner):
    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(EBAEvent)
        async def observe(ctx: RunnerContext):
            event = ctx.platform_event
            chinese = ctx.config.get("language", "zh_Hans") == "zh_Hans"
            await ctx.log(f"{'接收事件' if chinese else 'Received event'}: {event.type}")
            fields = event.model_dump(mode="json", exclude={"source_platform_object", "legacy_event"})
            summary = {
                "type": event.type,
                "adapter": event.adapter_name,
                "bot_uuid": event.bot_uuid,
                "fields": sorted(key for key, value in fields.items() if value not in (None, "", [])),
            }
            await ctx.log(json.dumps(summary, ensure_ascii=False), "debug")
            if ctx.config.get("include_payload", False):
                await ctx.log(json.dumps(fields, ensure_ascii=False, indent=2))
            await ctx.log(
                "观察完成：未调用工具，未发送消息。"
                if chinese
                else "Observation complete: no tools called and no messages sent."
            )
