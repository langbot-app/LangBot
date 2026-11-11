"""Host control-plane/admin APIs for authorized plugins."""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.runner.errors import (
    AgentAPIError,
    AgentAPIException,
)
from langbot_plugin.api.entities.builtin.runner.run_ledger import (
    AgentRun,
    AgentRunEvent,
    RunEventPage,
    RunPage,
)
from langbot_plugin.api.entities.builtin.runner.runtime_registry import (
    AgentRuntime,
    RuntimePage,
)
from langbot_plugin.api.entities.builtin.runner.stats import (
    RunnerStatsPage,
    RunStats,
    RuntimeStats,
)
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.proxies.runner.common import (
    _build_agent_api_exception,
    _build_transport_api_exception,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.errors import (
    ActionCallError,
    ActionCallTimeoutError,
    ConnectionClosedError,
)
from langbot_plugin.runtime.io.handler import Handler


class RunnerAdminAPIProxy:
    """Admin API proxy for Host-authorized control plugins.

    This proxy is intended for plugin Page backends or runtime daemons that are
    explicitly granted Host-level permissions such as ``agent_run:admin`` or
    ``runtime:admin`` in LangBot config. It does not carry a RunnerContext or
    run_id; Host action handlers remain the source of truth for authorization.
    """

    plugin_runtime_handler: Handler

    def __init__(self, plugin_runtime_handler: Handler):
        self.plugin_runtime_handler = plugin_runtime_handler

    async def _call_action(
        self,
        action: PluginToRuntimeAction,
        data: dict[str, Any],
        timeout: float,
    ) -> Any:
        try:
            return await self.plugin_runtime_handler.call_action(action, data, timeout)
        except ActionCallError as error:
            raise _build_agent_api_exception(action, error) from error
        except (ActionCallTimeoutError, ConnectionClosedError) as error:
            raise _build_transport_api_exception(action, error) from error

    async def run_get(self, run_id: str) -> AgentRun:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_GET,
            {"target_run_id": run_id},
            15.0,
        )
        return AgentRun.model_validate(resp)

    async def run_list(
        self,
        conversation_id: str | None = None,
        statuses: list[str] | None = None,
        before_cursor: str | None = None,
        limit: int = 50,
    ) -> RunPage:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_LIST,
            {
                "conversation_id": conversation_id,
                "statuses": statuses,
                "before_cursor": before_cursor,
                "limit": limit,
            },
            30.0,
        )
        return RunPage.model_validate(resp)

    async def run_events_page(
        self,
        run_id: str,
        before_cursor: str | None = None,
        after_cursor: str | None = None,
        limit: int = 50,
        direction: str = "forward",
    ) -> RunEventPage:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_EVENTS_PAGE,
            {
                "target_run_id": run_id,
                "before_cursor": before_cursor,
                "after_cursor": after_cursor,
                "limit": limit,
                "direction": direction,
            },
            30.0,
        )
        return RunEventPage.model_validate(resp)

    async def run_cancel(
        self,
        run_id: str,
        reason: str | None = None,
    ) -> AgentRun:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_CANCEL,
            {
                "target_run_id": run_id,
                "reason": reason,
            },
            15.0,
        )
        return AgentRun.model_validate(resp)

    async def run_append_result(
        self,
        result: RunnerResult,
    ) -> AgentRunEvent:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_APPEND_RESULT,
            {
                "target_run_id": result.run_id,
                "result": result.model_dump(mode="json"),
            },
            15.0,
        )
        return AgentRunEvent.model_validate(resp)

    async def run_finalize(
        self,
        run_id: str,
        status: str,
        reason: str | None = None,
        usage: dict[str, Any] | None = None,
        cost: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRun:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_FINALIZE,
            {
                "target_run_id": run_id,
                "status": status,
                "reason": reason,
                "usage": usage,
                "cost": cost,
                "metadata": metadata,
            },
            15.0,
        )
        return AgentRun.model_validate(resp)

    async def runtime_register(
        self,
        runtime_id: str,
        status: str = "online",
        display_name: str | None = None,
        endpoint: str | None = None,
        version: str | None = None,
        capabilities: dict[str, Any] | None = None,
        labels: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        heartbeat_deadline_at: int | float | None = None,
    ) -> AgentRuntime:
        resp = await self._call_action(
            PluginToRuntimeAction.RUNTIME_REGISTER,
            {
                "runtime_id": runtime_id,
                "status": status,
                "display_name": display_name,
                "endpoint": endpoint,
                "version": version,
                "capabilities": capabilities or {},
                "labels": labels or {},
                "metadata": metadata or {},
                "heartbeat_deadline_at": heartbeat_deadline_at,
            },
            15.0,
        )
        return AgentRuntime.model_validate(resp)

    async def runtime_heartbeat(
        self,
        runtime_id: str,
        status: str = "online",
        capabilities: dict[str, Any] | None = None,
        labels: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        heartbeat_deadline_at: int | float | None = None,
    ) -> AgentRuntime:
        resp = await self._call_action(
            PluginToRuntimeAction.RUNTIME_HEARTBEAT,
            {
                "runtime_id": runtime_id,
                "status": status,
                "capabilities": capabilities,
                "labels": labels,
                "metadata": metadata,
                "heartbeat_deadline_at": heartbeat_deadline_at,
            },
            10.0,
        )
        return AgentRuntime.model_validate(resp)

    async def runtime_list(
        self,
        statuses: list[str] | None = None,
        labels: dict[str, str] | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> RuntimePage:
        resp = await self._call_action(
            PluginToRuntimeAction.RUNTIME_LIST,
            {
                "statuses": statuses,
                "labels": labels or {},
                "cursor": cursor,
                "limit": limit,
            },
            15.0,
        )
        return RuntimePage.model_validate(resp)

    async def runner_list(
        self,
        include_plugins: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        resp = await self._call_action(
            PluginToRuntimeAction.RUNNER_LIST,
            {
                "include_plugins": include_plugins,
            },
            15.0,
        )
        if isinstance(resp, list):
            return resp
        if isinstance(resp, dict) and isinstance(resp.get("items"), list):
            return resp["items"]
        raise AgentAPIException(
            AgentAPIError(
                code="host.malformed_response",
                message=(
                    f"{PluginToRuntimeAction.RUNNER_LIST.value} response must be "
                    "a list or contain an items list"
                ),
                retryable=False,
                details={"action": PluginToRuntimeAction.RUNNER_LIST.value},
            )
        )

    async def runtime_reconcile(
        self,
        stale_after_seconds: float | None = None,
    ) -> dict[str, Any]:
        resp = await self._call_action(
            PluginToRuntimeAction.RUNTIME_RECONCILE,
            {
                "stale_after_seconds": stale_after_seconds,
            },
            30.0,
        )
        if isinstance(resp, dict):
            return resp
        raise AgentAPIException(
            AgentAPIError(
                code="host.malformed_response",
                message=(
                    f"{PluginToRuntimeAction.RUNTIME_RECONCILE.value} response "
                    "must be a dict"
                ),
                retryable=False,
                details={"action": PluginToRuntimeAction.RUNTIME_RECONCILE.value},
            )
        )

    async def run_claim(
        self,
        runtime_id: str,
        queue_name: str | None = None,
        lease_seconds: int = 60,
        runner_ids: list[str] | None = None,
    ) -> AgentRun:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_CLAIM,
            {
                "runtime_id": runtime_id,
                "queue_name": queue_name,
                "lease_seconds": lease_seconds,
                "runner_ids": runner_ids,
            },
            15.0,
        )
        return AgentRun.model_validate(resp)

    async def run_renew_claim(
        self,
        run_id: str,
        runtime_id: str,
        claim_token: str,
        lease_seconds: int = 60,
    ) -> AgentRun:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_RENEW_CLAIM,
            {
                "target_run_id": run_id,
                "runtime_id": runtime_id,
                "claim_token": claim_token,
                "lease_seconds": lease_seconds,
            },
            15.0,
        )
        return AgentRun.model_validate(resp)

    async def run_release_claim(
        self,
        run_id: str,
        runtime_id: str,
        claim_token: str,
        reason: str | None = None,
    ) -> AgentRun:
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_RELEASE_CLAIM,
            {
                "target_run_id": run_id,
                "runtime_id": runtime_id,
                "claim_token": claim_token,
                "reason": reason,
            },
            15.0,
        )
        return AgentRun.model_validate(resp)

    async def run_stats(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
        runner_id: str | None = None,
    ) -> RunStats:
        """Get run statistics within a time window.

        Args:
            start_time: Unix timestamp for start of window (optional, defaults to 1 hour ago)
            end_time: Unix timestamp for end of window (optional, defaults to now)
            runner_id: Filter by runner ID (optional)

        Returns:
            RunStats with counts, rates, and duration percentiles.
        """
        resp = await self._call_action(
            PluginToRuntimeAction.RUN_STATS,
            {
                "start_time": start_time,
                "end_time": end_time,
                "runner_id": runner_id,
            },
            30.0,
        )
        return RunStats.model_validate(resp)

    async def runtime_stats(self) -> RuntimeStats:
        """Get runtime registry statistics.

        Returns:
            RuntimeStats with counts, heartbeat health, and capacity.
        """
        resp = await self._call_action(
            PluginToRuntimeAction.RUNTIME_STATS,
            {},
            15.0,
        )
        return RuntimeStats.model_validate(resp)

    async def runner_stats(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 50,
    ) -> RunnerStatsPage:
        """Get runner-aggregated statistics.

        Args:
            start_time: Unix timestamp for start of window (optional, defaults to 1 hour ago)
            end_time: Unix timestamp for end of window (optional, defaults to now)
            limit: Maximum number of runners to return (default 50, max 100)

        Returns:
            RunnerStatsPage with per-runner statistics.
        """
        resp = await self._call_action(
            PluginToRuntimeAction.RUNNER_STATS,
            {
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            },
            30.0,
        )
        return RunnerStatsPage.model_validate(resp)
