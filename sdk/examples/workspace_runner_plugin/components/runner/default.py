from __future__ import annotations

import json
from typing import AsyncGenerator

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.entities.builtin.provider.message import Message


class DefaultWorkspaceRunner(Runner):
    """Minimal runner plugin demonstrating workspace operations listing and execution."""

    async def run(self, ctx: RunnerContext) -> AsyncGenerator[RunnerResult, None]:
        # 1. Call api.workspace.list()
        list_res = await ctx.api.workspace.list()

        # 2. Call api.workspace.call(...)
        call_res = await ctx.api.workspace.call("bot.list")

        reply_content = json.dumps(
            {
                "operations": list_res.get("operations", []),
                "domains": list_res.get("domains", []),
                "call_result": call_res,
            },
            ensure_ascii=False,
            indent=2,
        )

        yield RunnerResult.run_completed(
            ctx.run_id,
            Message(role="assistant", content=reply_content),
        )
