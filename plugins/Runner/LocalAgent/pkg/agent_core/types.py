"""Typed events and normalized tool calls for the local-agent loop."""

from __future__ import annotations

import copy
import typing
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from langbot_plugin.api.entities.builtin.provider.message import (
    FunctionCall,
    Message,
    MessageChunk,
    ToolCall,
)


class NonRetryableToolError(RuntimeError):
    """A tool failed after a side effect that must not be automatically repeated."""


class AgentLoopEventType(StrEnum):
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    MESSAGE_START = "message_start"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_END = "message_end"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"
    RUN_FAILED = "run_failed"


class ModelTurnEventType(StrEnum):
    MESSAGE_DELTA = "message_delta"
    MESSAGE_END = "message_end"


class ToolExecutionMode(StrEnum):
    PARALLEL = "parallel"
    SERIAL = "serial"


@dataclass(frozen=True)
class ToolCallRequest:
    """Provider-neutral tool call shape used by the agent loop."""

    id: str
    name: str
    arguments: str
    type: str = "function"
    provider_specific_fields: dict[str, typing.Any] | None = None

    @classmethod
    def from_raw(cls, raw: typing.Any) -> "ToolCallRequest":
        if isinstance(raw, ToolCall):
            return cls(
                id=raw.id,
                type=raw.type,
                name=raw.function.name if raw.function else "",
                arguments=raw.function.arguments if raw.function else "",
                provider_specific_fields=copy.deepcopy(raw.provider_specific_fields),
            )

        if isinstance(raw, dict):
            function = raw.get("function")
            if isinstance(function, dict):
                name = function.get("name", "")
                arguments = function.get("arguments", "")
            else:
                name = raw.get("function_name", "")
                arguments = raw.get("function_arguments", "")

            return cls(
                id=str(raw.get("id") or _new_tool_call_id()),
                type=str(raw.get("type") or "function"),
                name=str(name or ""),
                arguments=str(arguments or ""),
                provider_specific_fields=copy.deepcopy(raw.get("provider_specific_fields")),
            )

        return cls(id=_new_tool_call_id(), name="", arguments="")

    def to_tool_call(self) -> ToolCall:
        return ToolCall(
            id=self.id,
            type=self.type,
            function=FunctionCall(name=self.name, arguments=self.arguments),
            provider_specific_fields=copy.deepcopy(self.provider_specific_fields),
        )


def _new_tool_call_id() -> str:
    return f"call_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class PreparedToolCall:
    request: ToolCallRequest
    parameters: dict[str, typing.Any]
    error: str | None = None


@dataclass(frozen=True)
class ToolExecutionOutcome:
    request: ToolCallRequest
    parameters: dict[str, typing.Any]
    result: typing.Any = None
    event_result: typing.Any = None
    error: str | None = None
    message: Message | None = None
    terminate: bool = False

    @property
    def is_error(self) -> bool:
        return self.error is not None


@dataclass(frozen=True)
class ModelTurnResult:
    message: Message
    tool_calls: list[ToolCallRequest]
    committed_model_id: str | None
    visible_content: str = ""
    usage: dict[str, typing.Any] | None = None


@dataclass(frozen=True)
class ModelTurnEvent:
    type: ModelTurnEventType
    chunk: MessageChunk | None = None
    result: ModelTurnResult | None = None

    @classmethod
    def message_delta(cls, chunk: MessageChunk) -> "ModelTurnEvent":
        return cls(type=ModelTurnEventType.MESSAGE_DELTA, chunk=chunk)

    @classmethod
    def message_end(cls, result: ModelTurnResult) -> "ModelTurnEvent":
        return cls(type=ModelTurnEventType.MESSAGE_END, result=result)


class AgentLoopHooks:
    """Async extension points for Pi-style loop lifecycle customization."""

    async def prepare_model_turn(self, messages: list[Message]) -> list[Message]:
        return [message.model_copy(deep=True) for message in messages]

    async def recover_context_overflow(self, messages: list[Message], error: Exception) -> list[Message] | None:
        return None

    async def before_tool_call(self, prepared: PreparedToolCall) -> PreparedToolCall:
        return prepared

    async def after_tool_call(self, outcome: ToolExecutionOutcome) -> ToolExecutionOutcome:
        return outcome

    async def should_stop_after_turn(self, result: ModelTurnResult, messages: list[Message]) -> bool:
        return False

    async def after_model_turn(self, result: ModelTurnResult, messages: list[Message]) -> list[Message]:
        return [message.model_copy(deep=True) for message in messages]

    async def prepare_next_turn(
        self,
        messages: list[Message],
        result: ModelTurnResult,
        tool_results: list[Message],
    ) -> list[Message]:
        return [message.model_copy(deep=True) for message in messages]


@dataclass(frozen=True)
class AgentLoopEvent:
    type: AgentLoopEventType
    message: Message | None = None
    chunk: MessageChunk | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    parameters: dict[str, typing.Any] = field(default_factory=dict)
    result: typing.Any = None
    error: str | None = None
    code: str | None = None
    retryable: bool = False
    tool_results: list[Message] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    usage: dict[str, typing.Any] | None = None

    @classmethod
    def agent_start(cls) -> "AgentLoopEvent":
        return cls(type=AgentLoopEventType.AGENT_START)

    @classmethod
    def agent_end(
        cls,
        messages: list[Message],
        usage: dict[str, typing.Any] | None = None,
    ) -> "AgentLoopEvent":
        return cls(type=AgentLoopEventType.AGENT_END, messages=list(messages), usage=usage)

    @classmethod
    def turn_start(cls) -> "AgentLoopEvent":
        return cls(type=AgentLoopEventType.TURN_START)

    @classmethod
    def turn_end(
        cls,
        message: Message,
        tool_results: list[Message],
        usage: dict[str, typing.Any] | None = None,
    ) -> "AgentLoopEvent":
        return cls(
            type=AgentLoopEventType.TURN_END,
            message=message,
            tool_results=list(tool_results),
            usage=usage,
        )

    @classmethod
    def message_start(cls, message: Message) -> "AgentLoopEvent":
        return cls(type=AgentLoopEventType.MESSAGE_START, message=message)

    @classmethod
    def message_update(cls, chunk: MessageChunk) -> "AgentLoopEvent":
        return cls(type=AgentLoopEventType.MESSAGE_UPDATE, chunk=chunk)

    @classmethod
    def message_end(cls, message: Message) -> "AgentLoopEvent":
        return cls(type=AgentLoopEventType.MESSAGE_END, message=message)

    @classmethod
    def tool_execution_start(
        cls,
        request: ToolCallRequest,
        parameters: dict[str, typing.Any],
    ) -> "AgentLoopEvent":
        return cls(
            type=AgentLoopEventType.TOOL_EXECUTION_START,
            tool_call_id=request.id,
            tool_name=request.name,
            parameters=dict(parameters),
        )

    @classmethod
    def tool_execution_end(cls, outcome: ToolExecutionOutcome) -> "AgentLoopEvent":
        return cls(
            type=AgentLoopEventType.TOOL_EXECUTION_END,
            tool_call_id=outcome.request.id,
            tool_name=outcome.request.name,
            parameters=dict(outcome.parameters),
            result=outcome.event_result if outcome.event_result is not None else outcome.result,
            error=outcome.error,
        )

    @classmethod
    def run_failed(
        cls,
        error: str,
        code: str = "runner.error",
        retryable: bool = False,
        usage: dict[str, typing.Any] | None = None,
    ) -> "AgentLoopEvent":
        return cls(
            type=AgentLoopEventType.RUN_FAILED,
            error=error,
            code=code,
            retryable=retryable,
            usage=usage,
        )
