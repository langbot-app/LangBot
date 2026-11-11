"""Shared helpers for Runner run-scoped API proxies."""

from __future__ import annotations

from contextlib import aclosing

from typing import Any
from copy import deepcopy

from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.errors import (
    AgentAPIError,
    AgentAPIException,
)
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.errors import (
    ActionCallError,
    ActionCallTimeoutError,
    ConnectionClosedError,
)
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.utils.deadline import remaining_deadline_seconds


DEFAULT_RESOURCE_OPERATIONS: dict[str, frozenset[str]] = {
    "model": frozenset({"invoke", "stream", "rerank", "count_tokens"}),
    "tool": frozenset({"detail", "call"}),
    "knowledge_base": frozenset({"list", "retrieve"}),
}


class PermissionDeniedError(Exception):
    """Raised when an API call is not authorized by ctx.resources."""

    pass


def _build_agent_api_exception(
    action: PluginToRuntimeAction,
    error: ActionCallError,
) -> AgentAPIException:
    data = error.data or {}
    parse_error: str | None = None
    raw_error = data.get("error") if isinstance(data, dict) else None
    if isinstance(raw_error, dict):
        try:
            return AgentAPIException(AgentAPIError.model_validate(raw_error))
        except Exception as exc:
            parse_error = str(exc)
    if isinstance(data, dict) and {"code", "message"}.issubset(data.keys()):
        try:
            return AgentAPIException(AgentAPIError.model_validate(data))
        except Exception as exc:
            parse_error = str(exc)
    details = {"action": action.value, "response_data": data}
    if parse_error:
        details["parse_error"] = parse_error
    return AgentAPIException(
        AgentAPIError(
            code="host.action_error",
            message=str(error),
            retryable=False,
            details=details,
        )
    )


def _build_transport_api_exception(
    action: PluginToRuntimeAction,
    error: ActionCallTimeoutError | ConnectionClosedError,
) -> AgentAPIException:
    if isinstance(error, ActionCallTimeoutError):
        return AgentAPIException(
            AgentAPIError(
                code="deadline_exceeded",
                message=str(error),
                retryable=True,
                details={"action": action.value},
            )
        )
    return AgentAPIException(
        AgentAPIError(
            code="runtime_error",
            message=str(error),
            retryable=True,
            details={"action": action.value},
        )
    )


def _build_deadline_exceeded_exception() -> AgentAPIException:
    return AgentAPIException(
        AgentAPIError(
            code="deadline_exceeded",
            message="Agent run deadline has expired",
            retryable=True,
        )
    )


class _AgentRunHandlerAdapter:
    """Wrap Handler errors in AgentAPIException for runner-facing APIs."""

    def __init__(self, handler: Handler):
        self._handler = handler

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handler, name)

    async def call_action(
        self,
        action: PluginToRuntimeAction,
        data: dict[str, Any],
        timeout: float = 15.0,
        *,
        cancel_peer_on_cancel: bool = False,
    ) -> dict[str, Any]:
        try:
            return await self._handler.call_action(
                action, data, timeout, cancel_peer_on_cancel=cancel_peer_on_cancel
            )
        except ActionCallError as error:
            raise _build_agent_api_exception(action, error) from error
        except (ActionCallTimeoutError, ConnectionClosedError) as error:
            raise _build_transport_api_exception(action, error) from error

    async def call_action_generator(
        self,
        action: PluginToRuntimeAction,
        data: dict[str, Any],
        timeout: float = 15.0,
    ):
        try:
            async with aclosing(
                self._handler.call_action_generator(action, data, timeout)
            ) as owned_stream:
                async for item in owned_stream:
                    yield item
        except ActionCallError as error:
            raise _build_agent_api_exception(action, error) from error
        except (ActionCallTimeoutError, ConnectionClosedError) as error:
            raise _build_transport_api_exception(action, error) from error


class AgentRunProxyBase:
    """Common state, deadline handling, and authorization helpers."""

    ctx: RunnerContext
    _api: LangBotAPIProxy
    _allowed_model_ids: frozenset[str]
    _allowed_tool_names: frozenset[str]
    _allowed_kb_ids: frozenset[str]
    _allowed_model_operations: dict[str, frozenset[str]]
    _allowed_tool_operations: dict[str, frozenset[str]]
    _allowed_kb_operations: dict[str, frozenset[str]]

    def __init__(self, ctx: RunnerContext, plugin_runtime_handler: Handler):
        self.ctx = ctx
        self._granted_resources = deepcopy(ctx.resources)
        self._api = LangBotAPIProxy(_AgentRunHandlerAdapter(plugin_runtime_handler))
        # Pre-compute allowed IDs for efficient validation
        self._allowed_model_ids = frozenset(m.model_id for m in ctx.resources.models)
        self._allowed_tool_names = frozenset(t.tool_name for t in ctx.resources.tools)
        self._allowed_kb_ids = frozenset(k.kb_id for k in ctx.resources.knowledge_bases)
        self._allowed_model_operations = {
            m.model_id: self._normalize_operations("model", m.operations)
            for m in ctx.resources.models
        }
        self._allowed_tool_operations = {
            t.tool_name: self._normalize_operations("tool", t.operations)
            for t in ctx.resources.tools
        }
        self._allowed_kb_operations = {
            k.kb_id: self._normalize_operations("knowledge_base", k.operations)
            for k in ctx.resources.knowledge_bases
        }

    @property
    def run_id(self) -> str:
        """Unique identifier for this agent run."""
        return self.ctx.run_id

    @property
    def execution(self):
        """Generic ExecutionAPI entry point bound to this agent run."""
        if not hasattr(self, "_execution_proxy"):
            from langbot_plugin.api.proxies.execution import ExecutionProxy

            self._execution_proxy = ExecutionProxy(
                self._api.plugin_runtime_handler, run_id=self.run_id
            )
        return self._execution_proxy

    @property
    def workspace(self):
        """Workspace operations proxy bound to this agent run."""
        if not hasattr(self, "_workspace_proxy"):
            from langbot_plugin.api.proxies.workspace import WorkspaceOperationsProxy

            self._workspace_proxy = WorkspaceOperationsProxy(
                self._api.plugin_runtime_handler, run_id=self.run_id
            )
        return self._workspace_proxy

    def _remaining_deadline_seconds(self) -> float | None:
        return remaining_deadline_seconds(self.ctx.runtime.deadline_at)

    def _bounded_timeout(
        self,
        default: float,
        requested: float | None = None,
    ) -> float:
        base_timeout = default if requested is None else requested
        if not isinstance(base_timeout, (int, float)) or base_timeout <= 0:
            base_timeout = default

        remaining = self._remaining_deadline_seconds()
        if remaining is None:
            return float(base_timeout)
        if remaining <= 0:
            raise _build_deadline_exceeded_exception()
        return max(min(float(base_timeout), remaining), 0.001)

    def _context_api_enabled(self, name: str) -> bool:
        context = getattr(self.ctx, "context", None)
        if isinstance(context, dict):
            available_apis = context.get("available_apis")
        else:
            available_apis = getattr(context, "available_apis", None)

        if isinstance(available_apis, dict):
            return bool(available_apis.get(name, False))
        return bool(getattr(available_apis, name, False))

    def _require_context_api(self, name: str) -> None:
        if not self._context_api_enabled(name):
            raise PermissionDeniedError(f"{name} is not available for this run")

    def _expect_key(
        self,
        resp: dict[str, Any],
        key: str,
        action: PluginToRuntimeAction,
    ) -> Any:
        if key in resp:
            return resp[key]
        raise AgentAPIException(
            AgentAPIError(
                code="host.malformed_response",
                message=f"{action.value} response missing required field: {key}",
                retryable=False,
                details={"action": action.value, "missing_key": key},
            )
        )

    # ================= Resource Helper Methods =================
    @staticmethod
    def _normalize_operations(
        resource_type: str, operations: list[str] | None
    ) -> frozenset[str]:
        if operations:
            return frozenset(str(operation) for operation in operations)
        return DEFAULT_RESOURCE_OPERATIONS[resource_type]

    @staticmethod
    def _validate_operation(
        resource_type: str,
        resource_id: str,
        operation: str,
        allowed_operations: frozenset[str] | None,
    ) -> None:
        effective_operations = (
            allowed_operations or DEFAULT_RESOURCE_OPERATIONS[resource_type]
        )
        if operation not in effective_operations:
            raise PermissionDeniedError(
                f"{resource_type} '{resource_id}' is not authorized for operation '{operation}'. "
                f"Allowed operations: {sorted(effective_operations)}"
            )

    def _validate_model_access(self, llm_model_uuid: str, operation: str) -> None:
        if llm_model_uuid not in self._allowed_model_ids:
            raise PermissionDeniedError(
                f"Model '{llm_model_uuid}' is not authorized. "
                f"Allowed models: {list(self._allowed_model_ids)}"
            )
        self._validate_operation(
            "model",
            llm_model_uuid,
            operation,
            self._allowed_model_operations.get(llm_model_uuid),
        )

    def _validate_tool_access(self, tool_name: str, operation: str) -> None:
        if tool_name not in self._allowed_tool_names:
            raise PermissionDeniedError(
                f"Tool '{tool_name}' is not authorized. "
                f"Allowed tools: {list(self._allowed_tool_names)}"
            )
        self._validate_operation(
            "tool",
            tool_name,
            operation,
            self._allowed_tool_operations.get(tool_name),
        )

    def _validate_knowledge_base_access(self, kb_id: str, operation: str) -> None:
        if kb_id not in self._allowed_kb_ids:
            raise PermissionDeniedError(
                f"Knowledge base '{kb_id}' is not authorized. "
                f"Allowed knowledge bases: {list(self._allowed_kb_ids)}"
            )
        self._validate_operation(
            "knowledge_base",
            kb_id,
            operation,
            self._allowed_kb_operations.get(kb_id),
        )

    def _validate_plugin_storage_access(self) -> None:
        if not self._granted_resources.storage.plugin_storage:
            raise PermissionDeniedError("Plugin storage is not authorized.")

    def _validate_workspace_storage_access(self) -> None:
        if not self._granted_resources.storage.workspace_storage:
            raise PermissionDeniedError("Workspace storage is not authorized.")

    # ================= LLM APIs (delegated with validation) =================
