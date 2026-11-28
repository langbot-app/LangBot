"""Host runtime bound to a single workflow execution.

Workflow protocol models are plain data. Live objects such as the Workspace
execution context and the platform adapter that received the event are
passed to the tree executor so nodes can reach them without
serializing them into the execution record.
"""

from __future__ import annotations

import dataclasses
import typing

import langbot_plugin.api.entities.builtin.platform.message as platform_message

if typing.TYPE_CHECKING:
    from ..api.http.context import ExecutionContext as WorkspaceExecutionContext

ReplySender = typing.Callable[[platform_message.MessageChain, bool], typing.Awaitable[str | None]]
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
    session_id: str = ''
    handoff: dict | None = None
    test: bool = False
    dispatch: typing.Callable[[dict], typing.Awaitable[None]] | None = None
    """Nesting depth of call_workflow invocations."""
    platform_session: dict | None = None
    """Host-frozen event context for platform and event actions, shaped like an Agent run session."""

    async def reply(self, chain: platform_message.MessageChain, quote_origin: bool = False) -> str | None:
        if self.reply_sender is not None:
            reason = await self.reply_sender(chain, quote_origin)
            if reason:
                return reason
        self.replies.append(chain)
        return None

    async def send(self, target_type: str, target_id: str, chain: platform_message.MessageChain) -> None:
        if self.target_sender is None:
            raise RuntimeError('This workflow execution has no bot to send messages through')
        await self.target_sender(target_type, target_id, chain)
