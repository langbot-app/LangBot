"""Business streams with the lifetime rules of Agent debug and Assistant runs."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from pydantic import Field

from .contracts import Input, Operation
from .service_operations import TurnInput
from ..authz import Permission
from ..context import PrincipalType


class AgentDebugInput(Input):
    agent_uuid: str = Field(min_length=1)
    payload: dict


async def agent_debug(ap, context, payload):
    async def frames():
        queue: asyncio.Queue[dict | Exception] = asyncio.Queue(maxsize=32)

        async def on_result(result):
            await queue.put({'kind': 'result', 'data': result})

        async def execute():
            try:
                # The callback producer is a different task and needs its own DB scope.
                async with ap.persistence_mgr.tenant_scope(context.workspace_uuid):
                    result = await ap.agent_service.debug_agent(
                        context, payload.agent_uuid, payload.payload, on_result=on_result
                    )
                await queue.put({'kind': 'completed', 'data': result})
            except Exception as exc:
                await queue.put(exc)

        task = asyncio.create_task(execute())
        try:
            while True:
                receive = asyncio.create_task(queue.get())
                try:
                    done, _ = await asyncio.wait({receive, task}, return_when=asyncio.FIRST_COMPLETED)
                    if receive not in done and queue.empty():
                        # A provider cancellation has no queued terminal frame.
                        await task
                    frame = await receive
                finally:
                    receive.cancel()
                    with suppress(asyncio.CancelledError):
                        await receive
                if isinstance(frame, Exception):
                    raise frame
                yield frame
                if frame['kind'] == 'completed':
                    return
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return frames()


async def assistant_turn(ap, context, payload):
    from .service_operations import _assistant_service, _validate_turn

    _validate_turn(payload)
    service = _assistant_service(ap)
    await service.get(context, payload.conversation_id)
    queue = service.start_run(context, payload.conversation_id, payload)

    async def frames():
        # start_run owns a bounded queue and the run survives a subscriber disconnect.
        while True:
            frame = await queue.get()
            yield frame
            if frame['kind'] in {'completed', 'error'}:
                return

    return frames()


def operations() -> list[Operation]:
    return [
        Operation(
            'agent.debug.stream',
            Permission.RUNTIME_OPERATE,
            agent_debug,
            AgentDebugInput,
            dict,
            side_effect=True,
            streaming=True,
        ),
        Operation(
            'assistant.stream',
            Permission.RUNTIME_OPERATE,
            assistant_turn,
            TurnInput,
            dict,
            side_effect=True,
            principals=frozenset({PrincipalType.ACCOUNT}),
            streaming=True,
        ),
    ]
