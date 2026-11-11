"""Agent run context as defined in Protocol v1."""

from __future__ import annotations

import typing
from langbot_plugin.api.entities.builtin.runner.box import BoxBinding, BoxFile
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.entities.builtin.runner.run_ledger import (
    AgentRun,
    RunPage,
    RunEventPage,
    AgentRunEvent,
)
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from typing import Any
from langbot_plugin.api.entities.builtin.runner.page_results import (
    HistoryPage,
    HistorySearchResult,
    AgentEventRecord,
    EventPage,
)
from langbot_plugin.api.entities.builtin.runner.steering import SteeringPullResult

import pydantic
from langbot_plugin.api.entities.builtin.runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.runner.input import (
    AgentInput,
    InputAttachment,
    InputAttachmentData,
)
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources
from langbot_plugin.api.entities.builtin.runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.runner.state import AgentRunState
from langbot_plugin.api.entities.builtin.runner.event import (
    ConversationContext,
    AgentEventContext,
    ActorContext,
    SubjectContext,
)
from langbot_plugin.api.entities.builtin.runner.context_access import (
    ContextAccess,
)
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionRequest,
    InteractionResult,
)


class AdapterContext(pydantic.BaseModel):
    """Context for host entry-adapter metadata.

    This context holds adapter-specific fields that are not part of the stable
    event/input/resource contract.
    """

    extra: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Other adapter-specific fields."""


class RunnerContext(pydantic.BaseModel):
    """Agent run context passed to Runner.run().

    Protocol v1 context structure. This is event-first:
    - event is REQUIRED (not optional)
    - input is REQUIRED (current event input, not history)
    - messages is not part of the context; runners pull history through APIs
    - adapter holds non-core Host entry-adapter metadata

    Field boundaries:
    - config: Current agent/runner configuration from Host.
    - adapter.extra: Adapter-specific fields such as entry params.
    - state: Host-managed runner-scoped persistent state snapshot.
    - runtime.metadata: Host/runtime observability info, not a business input contract.
    """

    run_id: str
    """Unique identifier for this run."""

    trigger: AgentTrigger
    """Trigger information."""

    event: AgentEventContext
    """Event context (REQUIRED for Protocol v1)."""

    conversation: ConversationContext | None = None
    """Conversation context."""

    actor: ActorContext | None = None
    """Actor context."""

    subject: SubjectContext | None = None
    """Subject context."""

    input: AgentInput
    """User input (current event input, not history)."""

    delivery: DeliveryContext
    """Delivery context (output surface capabilities)."""

    resources: AgentResources
    """Authorized resources."""

    context: ContextAccess = pydantic.Field(default_factory=ContextAccess)
    """Context access descriptor (what's inlined, what APIs are available)."""

    state: AgentRunState = pydantic.Field(default_factory=AgentRunState)
    """Host-managed scoped state snapshot.

    Semantics:
    - Scoped (conversation/actor/subject/runner)
    - Durable (host persists and reloads next run)
    - Runner can read and request updates via state.updated result

    Scopes:
    - conversation: Current conversation + current runner state
    - actor: Current user long-term state or preferences
    - subject: Current group/channel/object state
    - runner: Runner instance-level state (use sparingly)
    """

    runtime: AgentRuntimeContext
    """Runtime context."""

    variables: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Public invocation variables. Host-private state is never included."""

    config: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Current agent/runner configuration from Host."""

    adapter: AdapterContext | None = None
    """Adapter context for host entry-adapter metadata.

    Runners should prefer stable protocol fields and pull APIs when possible.
    """

    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Additional metadata."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    _api: typing.Any = pydantic.PrivateAttr(default=None)
    _results: typing.Any = pydantic.PrivateAttr(default=None)

    @property
    def api(self):
        """Host APIs bound to this invocation and its granted resources."""
        if self._api is None:
            raise RuntimeError("Runner context is not active")
        return self._api

    @property
    def platform_event(self):
        """Typed platform event for handlers; the event envelope stays unchanged."""
        from langbot_plugin.api.entities.builtin.platform.events import parse_eba_event

        return parse_eba_event(self.event.data)

    async def reply(
        self, message_chain: MessageChain | str, quote_origin: bool = False
    ) -> typing.Any:
        """Reply to the current event using its authorized target and optional quote."""
        if isinstance(message_chain, str) and not quote_origin:
            return await self.api.call_tool("event_reply", {"text": message_chain})
        if isinstance(message_chain, str):
            message_chain = MessageChain([Plain(text=message_chain)])
        return await self.api.reply_message(message_chain, quote_origin=quote_origin)

    def reply_stream(self):
        """Update one explicit reply with full text snapshots."""
        return self.api.reply_stream()

    async def bind_box(self, box_id: str) -> "BoxBinding":
        """Bind one authorized Box to this run; cannot switch after binding."""
        return await self.api.bind_box(box_id)

    async def read_input_attachment(
        self, attachment: InputAttachment | str
    ) -> InputAttachmentData | None:
        """Read the bytes of an input attachment by ref.

        Returns None when the attachment has no ref or the Host does not offer
        this API, so Runners can fall back to older attachment handling.
        """
        ref = attachment if isinstance(attachment, str) else attachment.ref
        if not ref or not self.context.available_apis.input_attachments:
            return None
        return await self.api.read_input_attachment(ref)

    async def import_box_attachments(
        self, attachment_ids: list[str] | None = None
    ) -> list["BoxFile"]:
        """Import selected input refs, or all inputs, into run-specific paths."""
        return await self.api.import_box_attachments(attachment_ids)

    async def export_box_files(self, paths: list[str]) -> list["BoxFile"]:
        """Export explicitly selected absolute sandbox paths; does not send them."""
        return await self.api.export_box_files(paths)

    async def reply_files(self, file_ids: list[str]) -> typing.Any:
        """Explicitly reply with exported handles, subject to tool authorization."""
        return await self.api.reply_files(file_ids)

    async def get_available_tools(self) -> list[dict[str, typing.Any]]:
        """List tools callable in this invocation, with names and JSON parameter schemas."""
        return await self.api.list_tools()

    async def call_tool(
        self, tool_name: str, parameters: dict[str, typing.Any] | None = None
    ) -> dict[str, typing.Any]:
        """Call an authorized event, platform, or plugin tool in the current context."""
        return await self.api.call_tool(tool_name, parameters or {})

    async def request_interaction(
        self,
        request: InteractionRequest,
        *,
        timeout: float = 600,
        on_unsupported: str = "error",
        responders: str | list[str] = "actor",
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> InteractionResult:
        """Wait for a user submission in this run."""
        return await self.api.request_interaction(
            request,
            timeout=timeout,
            on_unsupported=on_unsupported,
            responders=responders,
            target_type=target_type,
            target_id=target_id,
        )

    async def get_bot_uuid(self) -> str:
        """Get the source bot UUID, or fail when this event has no platform bot."""
        bot_uuid = (self.conversation.bot_id if self.conversation else None) or (
            self.event.data or {}
        ).get("bot_uuid")
        if not bot_uuid:
            raise ValueError("This event is not associated with a platform bot")
        return str(bot_uuid)

    async def get_prompt(self) -> list[dict[str, Any]]:
        """Get the Host effective prompt for the current run."""
        return await self.api.get_prompt()

    async def history_page(
        self,
        conversation_id: str | None = None,
        before_cursor: str | None = None,
        after_cursor: str | None = None,
        limit: int = 50,
        direction: str = "backward",
        include_attachments: bool = False,
    ) -> HistoryPage:
        """Page through transcript history for a conversation."""
        return await self.api.history_page(
            conversation_id=conversation_id,
            before_cursor=before_cursor,
            after_cursor=after_cursor,
            limit=limit,
            direction=direction,
            include_attachments=include_attachments,
        )

    async def history_search(
        self, query: str, filters: dict[str, Any] | None = None, top_k: int = 10
    ) -> HistorySearchResult:
        """Search transcript history for matching items."""
        return await self.api.history_search(query=query, filters=filters, top_k=top_k)

    async def event_get(self, event_id: str) -> AgentEventRecord:
        """Get a single event record by ID."""
        return await self.api.event_get(event_id=event_id)

    async def event_page(
        self,
        conversation_id: str | None = None,
        event_types: list[str] | None = None,
        before_cursor: str | None = None,
        limit: int = 50,
    ) -> EventPage:
        """Page through event records."""
        return await self.api.event_page(
            conversation_id=conversation_id,
            event_types=event_types,
            before_cursor=before_cursor,
            limit=limit,
        )

    async def steering_pull(
        self, mode: str = "all", limit: int | None = None
    ) -> SteeringPullResult:
        """Pull pending run-scoped steering/follow-up input."""
        return await self.api.steering_pull(mode=mode, limit=limit)

    async def state_get(self, scope: str, key: str) -> dict[str, Any]:
        """Get a state value from host-owned state store."""
        return await self.api.state_get(scope=scope, key=key)

    async def state_set(self, scope: str, key: str, value: Any) -> dict[str, Any]:
        """Set a state value in host-owned state store."""
        return await self.api.state_set(scope=scope, key=key, value=value)

    async def state_delete(self, scope: str, key: str) -> dict[str, Any]:
        """Delete a state value from host-owned state store."""
        return await self.api.state_delete(scope=scope, key=key)

    async def state_list(
        self, scope: str, prefix: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """List state keys in a scope."""
        return await self.api.state_list(scope=scope, prefix=prefix, limit=limit)

    async def run_get(self, run_id: str | None = None) -> AgentRun:
        """Get one Host-owned run record."""
        return await self.api.run_get(run_id=run_id)

    async def run_list(
        self,
        conversation_id: str | None = None,
        statuses: list[str] | None = None,
        before_cursor: str | None = None,
        limit: int = 50,
    ) -> RunPage:
        """List Host-owned run records visible to the current run scope."""
        return await self.api.run_list(
            conversation_id=conversation_id,
            statuses=statuses,
            before_cursor=before_cursor,
            limit=limit,
        )

    async def run_events_page(
        self,
        run_id: str | None = None,
        before_cursor: str | None = None,
        after_cursor: str | None = None,
        limit: int = 50,
        direction: str = "forward",
    ) -> RunEventPage:
        """Page through result events for one Host-owned run."""
        return await self.api.run_events_page(
            run_id=run_id,
            before_cursor=before_cursor,
            after_cursor=after_cursor,
            limit=limit,
            direction=direction,
        )

    async def run_cancel(
        self, run_id: str | None = None, reason: str | None = None
    ) -> AgentRun:
        """Request cancellation for one Host-owned run."""
        return await self.api.run_cancel(run_id=run_id, reason=reason)

    async def run_append_result(self, result: RunnerResult) -> AgentRunEvent:
        """Append one result event to a Host-owned run ledger."""
        return await self.api.run_append_result(result=result)

    async def run_finalize(
        self,
        run_id: str | None = None,
        status: str | None = None,
        reason: str | None = None,
    ) -> AgentRun:
        """Finalize one Host-owned run ledger record."""
        return await self.api.run_finalize(run_id=run_id, status=status, reason=reason)

    async def log(self, text: str, level: str = "info") -> None:
        """Record a log for this invocation without sending a platform message."""
        from langbot_plugin.api.entities.builtin.runner.result import (
            ProcessorLogPayload,
        )

        if self._results is None:
            raise RuntimeError("Runner context is not active")
        if level not in {"debug", "info", "warning", "error"}:
            raise ValueError("Invalid log level")
        log_level = typing.cast(
            typing.Literal["debug", "info", "warning", "error"], level
        )
        await self._results.put(
            RunnerResult(
                run_id=self.run_id,
                type="processor.log",
                data=ProcessorLogPayload(text=str(text), level=log_level).model_dump(),
            )
        )
