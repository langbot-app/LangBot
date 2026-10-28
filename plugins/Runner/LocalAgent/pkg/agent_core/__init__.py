"""LangBot-native agent runtime primitives for local-agent."""

from .langbot import LangBotContextHooks, LangBotModelAdapter, LangBotToolExecutor
from .loop import AgentLoop
from .types import (
    AgentLoopEvent,
    AgentLoopEventType,
    AgentLoopHooks,
    ModelTurnEvent,
    ModelTurnEventType,
    ModelTurnResult,
    PreparedToolCall,
    ToolCallRequest,
    ToolExecutionMode,
    ToolExecutionOutcome,
)

__all__ = [
    "AgentLoop",
    "AgentLoopEvent",
    "AgentLoopEventType",
    "AgentLoopHooks",
    "LangBotContextHooks",
    "LangBotModelAdapter",
    "LangBotToolExecutor",
    "ModelTurnEvent",
    "ModelTurnEventType",
    "ModelTurnResult",
    "PreparedToolCall",
    "ToolCallRequest",
    "ToolExecutionMode",
    "ToolExecutionOutcome",
]
