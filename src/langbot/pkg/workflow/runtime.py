"""Host runtime bound to a single workflow execution.

Workflow protocol models are plain data. Live objects such as the Workspace
execution context and the platform adapter that received the event are
carried here through a context variable so nodes can reach them without
serializing them into the execution record.
"""

from __future__ import annotations

import contextlib
import contextvars
import dataclasses
import typing

import langbot_plugin.api.entities.builtin.platform.message as platform_message

if typing.TYPE_CHECKING:
    from ..api.http.context import ExecutionContext as WorkspaceExecutionContext

ReplySender = typing.Callable[[platform_message.MessageChain, bool], typing.Awaitable[None]]
TargetSender = typing.Callable[[str, str, platform_message.MessageChain], typing.Awaitable[None]]


@dataclasses.dataclass
class WorkflowRuntime:
    """Live dependencies of one workflow execution."""

    execution_context: WorkspaceExecutionContext
    """Workspace scope used for every resource lookup made by nodes."""

    reply_sender: ReplySender | None = None
    """Reply to the event that triggered the workflow, when there is one."""

    target_sender: TargetSender | None = None
    """Send a message to an explicit person/group target through the same bot."""

    replies: list[platform_message.MessageChain] = dataclasses.field(default_factory=list)
    """Every message chain replied during the execution, for manual runs and tests."""

    depth: int = 0
    """Nesting depth of call_workflow invocations."""

    async def reply(self, chain: platform_message.MessageChain, quote_origin: bool = False) -> None:
        self.replies.append(chain)
        if self.reply_sender is not None:
            await self.reply_sender(chain, quote_origin)

    async def send(self, target_type: str, target_id: str, chain: platform_message.MessageChain) -> None:
        if self.target_sender is None:
            raise RuntimeError('This workflow execution has no bot to send messages through')
        await self.target_sender(target_type, target_id, chain)


_current_runtime: contextvars.ContextVar[WorkflowRuntime | None] = contextvars.ContextVar(
    'langbot_workflow_runtime', default=None
)


def current_runtime() -> WorkflowRuntime:
    runtime = _current_runtime.get()
    if runtime is None:
        raise RuntimeError('Workflow node executed outside a workflow runtime')
    return runtime


@contextlib.contextmanager
def use_runtime(runtime: WorkflowRuntime) -> typing.Iterator[WorkflowRuntime]:
    token = _current_runtime.set(runtime)
    try:
        yield runtime
    finally:
        _current_runtime.reset(token)
