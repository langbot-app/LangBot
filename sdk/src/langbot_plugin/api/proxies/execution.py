"""ExecutionAPI facade proxy for plugins and runners."""

from __future__ import annotations

from typing import Any, AsyncIterator

from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction,
    RuntimeToLangBotAction,
)
from langbot_plugin.runtime.io.handler import Handler


_ACTION_ENUM_BY_NAME: dict[str, Any] = {e.value: e for e in PluginToRuntimeAction}
_ACTION_ENUM_BY_NAME.update({e.value: e for e in RuntimeToLangBotAction})


class ExecutionProxy:
    """Generic ExecutionAPI entry point for invoking Core operations."""

    def __init__(self, handler: Handler, run_id: str | None = None):
        self._handler = handler
        self._run_id = run_id

    @staticmethod
    def _normalize_operation(operation_id: str) -> str:
        if operation_id.startswith("execution."):
            return operation_id[len("execution.") :]
        return operation_id

    async def invoke(self, operation_id: str, **arguments: Any) -> Any:
        """Invoke a unary ExecutionAPI operation."""
        action_name = self._normalize_operation(operation_id)
        action = _ACTION_ENUM_BY_NAME.get(action_name, action_name)
        payload = dict(arguments)
        if self._run_id is not None and "run_id" not in payload:
            payload["run_id"] = self._run_id

        timeout = 180.0
        if "timeout" in payload and action_name not in (
            "invoke_llm",
            "invoke_llm_stream",
            "count_tokens",
        ):
            timeout = float(payload.pop("timeout")) or 180.0
        elif "timeout" in payload:
            timeout = float(payload["timeout"]) or 180.0

        return await self._handler.call_action(action, payload, timeout=timeout)

    async def stream(self, operation_id: str, **arguments: Any) -> AsyncIterator[Any]:
        """Invoke a streaming ExecutionAPI operation."""
        action_name = self._normalize_operation(operation_id)
        action = _ACTION_ENUM_BY_NAME.get(action_name, action_name)
        payload = dict(arguments)
        if self._run_id is not None and "run_id" not in payload:
            payload["run_id"] = self._run_id

        timeout = 180.0
        if "timeout" in payload and action_name not in (
            "invoke_llm",
            "invoke_llm_stream",
            "count_tokens",
        ):
            timeout = float(payload.pop("timeout")) or 180.0
        elif "timeout" in payload:
            timeout = float(payload["timeout"]) or 180.0

        async for chunk in self._handler.call_action_generator(
            action, payload, timeout=timeout
        ):
            yield chunk
