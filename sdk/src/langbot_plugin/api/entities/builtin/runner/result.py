"""RunnerResult as defined in Protocol v1."""

from __future__ import annotations

import typing
import pydantic
import enum

from langbot_plugin.api.entities.builtin.provider.message import (
    LLMTokenUsage,
    Message,
    MessageChunk,
)
from langbot_plugin.api.entities.builtin.runner.state import (
    VALID_STATE_SCOPES,
    STATE_SCOPE_LITERAL,
)


class RunnerResultType(str, enum.Enum):
    """Type of RunnerResult event."""

    MESSAGE_DELTA = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    TOOL_CALL_STARTED = "tool.call.started"
    TOOL_CALL_COMPLETED = "tool.call.completed"
    STATE_UPDATED = "state.updated"
    ACTION_REQUESTED = "action.requested"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    PROCESSOR_LOG = "processor.log"


class ProcessorLogPayload(pydantic.BaseModel):
    """A processor log entry; never a platform message."""

    text: str = pydantic.Field(max_length=65536)
    level: typing.Literal["debug", "info", "warning", "error"] = "info"

    model_config = pydantic.ConfigDict(extra="forbid")


class MessageDeltaPayload(pydantic.BaseModel):
    """Payload for message.delta."""

    chunk: MessageChunk

    model_config = pydantic.ConfigDict(extra="forbid")


class MessageCompletedPayload(pydantic.BaseModel):
    """Payload for message.completed."""

    message: Message
    file_ids: list[str] = pydantic.Field(default_factory=list, max_length=100)

    model_config = pydantic.ConfigDict(extra="forbid")


class ToolCallStartedPayload(pydantic.BaseModel):
    """Payload for tool.call.started."""

    tool_call_id: str
    tool_name: str
    parameters: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    model_config = pydantic.ConfigDict(extra="forbid")


class ToolCallCompletedPayload(pydantic.BaseModel):
    """Payload for tool.call.completed."""

    tool_call_id: str
    tool_name: str
    result: dict[str, typing.Any] | None = None
    error: str | None = None

    model_config = pydantic.ConfigDict(extra="forbid")


class StateUpdatedPayload(pydantic.BaseModel):
    """Payload for state.updated."""

    scope: STATE_SCOPE_LITERAL
    key: str
    value: typing.Any

    model_config = pydantic.ConfigDict(extra="forbid")


class RunCompletedPayload(pydantic.BaseModel):
    """Payload for run.completed."""

    finish_reason: str = "stop"
    message: Message | None = None

    model_config = pydantic.ConfigDict(extra="forbid")


class RunFailedPayload(pydantic.BaseModel):
    """Payload for run.failed."""

    error: str
    code: str = "runner.error"
    retryable: bool = False

    model_config = pydantic.ConfigDict(extra="forbid")


class ActionRequestedPayload(pydantic.BaseModel):
    """Payload for action.requested."""

    action: str
    target: dict[str, typing.Any] | None = None
    payload: dict[str, typing.Any] | None = None

    model_config = pydantic.ConfigDict(extra="forbid")


class RunnerResult(pydantic.BaseModel):
    """Result event from Runner.run().

    Protocol v1 result structure:
    - run_id: Links result to the run
    - type: Result type
    - data: Type-specific payload
    - usage: Optional token usage observed for this result/run
    - sequence: Optional sequence number for ordering
    - timestamp: Optional timestamp

    Each yield from the runner's run() method produces one RunnerResult.
    LangBot maps these to appropriate host delivery events.

    Token usage is optional because not every upstream runtime reports it. When
    a runner can observe provider/runtime usage, it should attach the final
    aggregate usage to the terminal run.completed result. For failed runs,
    run.failed may include partial usage collected before the failure. Missing
    usage means "unknown", not zero. Billing cost is intentionally not
    standardized here; Host should derive authoritative cost from usage,
    model identity, and its pricing table.
    """

    run_id: str
    """Run identifier linking this result to the run."""

    type: RunnerResultType | str
    """Result type. Unknown strings are accepted for forward compatibility."""

    data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Result data."""

    usage: LLMTokenUsage | None = None
    """Optional token usage for this result or final aggregate run usage."""

    sequence: int | None = None
    """Optional sequence number for ordering."""

    timestamp: int | None = None
    """Optional timestamp (epoch seconds)."""

    @classmethod
    def message_delta(
        cls,
        run_id: str,
        chunk: MessageChunk,
        *,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create a message.delta result.

        LangBot maps this to MessageChunk for streaming output.
        """
        payload = MessageDeltaPayload(chunk=chunk)
        return cls(
            run_id=run_id,
            type=RunnerResultType.MESSAGE_DELTA,
            data=payload.model_dump(mode="json"),
            sequence=sequence,
            timestamp=timestamp,
        )

    @classmethod
    def message_completed(
        cls,
        run_id: str,
        message: Message,
        *,
        file_ids: list[str] | None = None,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create a message.completed result.

        LangBot maps this to a complete Message.
        """
        payload = MessageCompletedPayload(message=message, file_ids=file_ids or [])
        return cls(
            run_id=run_id,
            type=RunnerResultType.MESSAGE_COMPLETED,
            data=payload.model_dump(mode="json"),
            sequence=sequence,
            timestamp=timestamp,
        )

    @classmethod
    def tool_call_started(
        cls,
        run_id: str,
        tool_call_id: str,
        tool_name: str,
        parameters: dict[str, typing.Any],
        *,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create a tool.call.started result.

        LangBot records this for telemetry/debug.
        """
        payload = ToolCallStartedPayload(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            parameters=parameters,
        )
        return cls(
            run_id=run_id,
            type=RunnerResultType.TOOL_CALL_STARTED,
            data=payload.model_dump(mode="json"),
            sequence=sequence,
            timestamp=timestamp,
        )

    @classmethod
    def tool_call_completed(
        cls,
        run_id: str,
        tool_call_id: str,
        tool_name: str,
        result: dict[str, typing.Any] | None = None,
        error: str | None = None,
        *,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create a tool.call.completed result.

        LangBot records this for telemetry/debug.
        """
        payload = ToolCallCompletedPayload(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            result=result,
            error=error,
        )
        return cls(
            run_id=run_id,
            type=RunnerResultType.TOOL_CALL_COMPLETED,
            data=payload.model_dump(mode="json"),
            sequence=sequence,
            timestamp=timestamp,
        )

    @classmethod
    def state_updated(
        cls,
        run_id: str,
        key: str,
        value: typing.Any,
        scope: STATE_SCOPE_LITERAL,
        *,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create a state.updated result.

        Runner requests host to persist a state change.
        SDK defines the protocol; LangBot host handles actual persistence.

        Args:
            run_id: Run identifier
            key: State key, should use namespace prefix (e.g., external.conversation_id)
            value: State value, must be JSON-serializable
            scope: State scope - one of: conversation, actor, subject, runner.

        Returns:
            RunnerResult with type="state.updated" and data containing scope/key/value.

        Raises:
            ValueError: If scope is not one of the valid scopes.

        Example:
            # Store external platform conversation ID
            yield RunnerResult.state_updated(
                run_id,
                "external.conversation_id",
                "abc123",
                scope="conversation"
            )

            # Store user preference
            yield RunnerResult.state_updated(
                run_id,
                "preferred_language",
                "en",
                scope="actor",
            )
        """
        if scope not in VALID_STATE_SCOPES:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of: {', '.join(VALID_STATE_SCOPES)}"
            )

        payload = StateUpdatedPayload(scope=scope, key=key, value=value)

        return cls(
            run_id=run_id,
            type=RunnerResultType.STATE_UPDATED,
            data=payload.model_dump(mode="json"),
            sequence=sequence,
            timestamp=timestamp,
        )

    @classmethod
    def run_completed(
        cls,
        run_id: str,
        message: Message | None = None,
        finish_reason: str = "stop",
        *,
        usage: LLMTokenUsage | dict[str, typing.Any] | None = None,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create a run.completed result.

        If message is provided, LangBot can map it to final Message.
        If message.completed was already output, message can be None.
        If provider/runtime token usage is available, pass final aggregate usage.
        """
        payload = RunCompletedPayload(finish_reason=finish_reason, message=message)
        return cls(
            run_id=run_id,
            type=RunnerResultType.RUN_COMPLETED,
            data=payload.model_dump(mode="json", exclude_none=True),
            usage=_coerce_usage(usage),
            sequence=sequence,
            timestamp=timestamp,
        )

    @classmethod
    def run_failed(
        cls,
        run_id: str,
        error: str,
        code: str | None = None,
        retryable: bool = False,
        *,
        usage: LLMTokenUsage | dict[str, typing.Any] | None = None,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create a run.failed result.

        LangBot returns a user-friendly error message per host delivery strategy.
        If the runner collected usage before the failure, pass partial usage.
        """
        payload = RunFailedPayload(
            error=error,
            code=code or "runner.error",
            retryable=retryable,
        )
        return cls(
            run_id=run_id,
            type=RunnerResultType.RUN_FAILED,
            data=payload.model_dump(mode="json"),
            usage=_coerce_usage(usage),
            sequence=sequence,
            timestamp=timestamp,
        )

    @classmethod
    def action_requested(
        cls,
        run_id: str,
        action: str,
        target: dict[str, typing.Any] | None = None,
        payload: dict[str, typing.Any] | None = None,
        *,
        sequence: int | None = None,
        timestamp: int | None = None,
    ) -> "RunnerResult":
        """Create an action.requested result.

        This phase only logs to telemetry, actual execution waits for EBA.
        """
        result_payload = ActionRequestedPayload(
            action=action,
            target=target,
            payload=payload,
        )
        return cls(
            run_id=run_id,
            type=RunnerResultType.ACTION_REQUESTED,
            data=result_payload.model_dump(mode="json"),
            sequence=sequence,
            timestamp=timestamp,
        )


def _coerce_usage(
    usage: LLMTokenUsage | dict[str, typing.Any] | None,
) -> LLMTokenUsage | None:
    if usage is None or isinstance(usage, LLMTokenUsage):
        return usage
    return LLMTokenUsage.model_validate(usage)
