from __future__ import annotations

import typing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.runner import RunnerContext, RunnerResult
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk


class DefaultRunner(Runner):
    async def run(
        self,
        ctx: RunnerContext,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        text = (ctx.input.to_text() or '').strip()
        if 'fail' in text.lower():
            yield RunnerResult.run_failed(
                ctx.run_id,
                error='QA_RUNNER_CONTROLLED_FAILURE',
                code='qa.controlled_failure',
                retryable=False,
            )
            return

        content = f'QA_RUNNER_OK:{text or "empty"}'
        if 'stream' in text.lower():
            for chunk in ('QA_', 'AGENT_', f'RUNNER_OK:{text}'):
                yield RunnerResult.message_delta(
                    ctx.run_id,
                    MessageChunk(role='assistant', content=chunk),
                )
            yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
            return

        yield RunnerResult.run_completed(
            ctx.run_id,
            Message(role='assistant', content=content),
            finish_reason='stop',
        )
