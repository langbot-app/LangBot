from __future__ import annotations

import typing

from langbot_plugin.api.definition.components.agent_runner.runner import AgentRunner
from langbot_plugin.api.entities.builtin.agent_runner import AgentRunContext, AgentRunResult
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk


class DefaultAgentRunner(AgentRunner):
    async def run(
        self,
        ctx: AgentRunContext,
    ) -> typing.AsyncGenerator[AgentRunResult, None]:
        text = (ctx.input.to_text() or "").strip()
        if "fail" in text.lower():
            yield AgentRunResult.run_failed(
                ctx.run_id,
                error="QA_AGENT_RUNNER_CONTROLLED_FAILURE",
                code="qa.controlled_failure",
                retryable=False,
            )
            return

        content = f"QA_AGENT_RUNNER_OK:{text or 'empty'}"
        if "stream" in text.lower():
            for chunk in ("QA_", "AGENT_", f"RUNNER_OK:{text}"):
                yield AgentRunResult.message_delta(
                    ctx.run_id,
                    MessageChunk(role="assistant", content=chunk),
                )
            yield AgentRunResult.run_completed(ctx.run_id, finish_reason="stop")
            return

        yield AgentRunResult.run_completed(
            ctx.run_id,
            Message(role="assistant", content=content),
            finish_reason="stop",
        )
