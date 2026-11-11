"""Run ledger APIs for Runner components."""

from __future__ import annotations

from langbot_plugin.api.entities.builtin.runner.run_ledger import (
    AgentRun,
    AgentRunEvent,
    RunEventPage,
    RunPage,
)
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class AgentRunLedgerAPIMixin:
    async def run_get(self, run_id: str | None = None) -> AgentRun:
        """Get one Host-owned run record.

        Args:
            run_id: Run ID to retrieve. Defaults to the current run.

        Returns:
            AgentRun record.

        Raises:
            PermissionDeniedError: If run_get is not available.
        """
        self._require_context_api("run_get")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.RUN_GET,
            {
                "run_id": self.run_id,
                "target_run_id": run_id or self.run_id,
            },
            timeout,
        )
        return AgentRun.model_validate(resp)

    async def run_list(
        self,
        conversation_id: str | None = None,
        statuses: list[str] | None = None,
        before_cursor: str | None = None,
        limit: int = 50,
    ) -> RunPage:
        """List Host-owned run records visible to the current run scope.

        Args:
            conversation_id: Conversation ID to query. Must match current run
                scope if supplied.
            statuses: Optional run status filter.
            before_cursor: Cursor returned by a previous page.
            limit: Maximum items to return. Host applies a hard cap.
        """
        self._require_context_api("run_list")
        timeout = self._bounded_timeout(default=30.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.RUN_LIST,
            {
                "run_id": self.run_id,
                "conversation_id": conversation_id,
                "statuses": statuses,
                "before_cursor": before_cursor,
                "limit": limit,
            },
            timeout,
        )
        return RunPage.model_validate(resp)

    async def run_events_page(
        self,
        run_id: str | None = None,
        before_cursor: str | None = None,
        after_cursor: str | None = None,
        limit: int = 50,
        direction: str = "forward",
    ) -> RunEventPage:
        """Page through result events for one Host-owned run.

        Args:
            run_id: Run ID to inspect. Defaults to the current run.
            before_cursor: Get events before this sequence.
            after_cursor: Get events after this sequence.
            limit: Maximum items to return. Host applies a hard cap.
            direction: "forward" or "backward".
        """
        self._require_context_api("run_events_page")
        timeout = self._bounded_timeout(default=30.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.RUN_EVENTS_PAGE,
            {
                "run_id": self.run_id,
                "target_run_id": run_id or self.run_id,
                "before_cursor": before_cursor,
                "after_cursor": after_cursor,
                "limit": limit,
                "direction": direction,
            },
            timeout,
        )
        return RunEventPage.model_validate(resp)

    async def run_cancel(
        self,
        run_id: str | None = None,
        reason: str | None = None,
    ) -> AgentRun:
        """Request cancellation for one Host-owned run.

        Args:
            run_id: Run ID to cancel. Defaults to the current run.
            reason: Optional cancellation reason for Host audit/debug output.
        """
        self._require_context_api("run_cancel")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.RUN_CANCEL,
            {
                "run_id": self.run_id,
                "target_run_id": run_id or self.run_id,
                "reason": reason,
            },
            timeout,
        )
        return AgentRun.model_validate(resp)

    async def run_append_result(
        self,
        result: RunnerResult,
    ) -> AgentRunEvent:
        """Append one result event to a Host-owned run ledger.

        Args:
            result: Existing RunnerResult DTO to persist.
        """
        self._require_context_api("run_append_result")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.RUN_APPEND_RESULT,
            {
                "run_id": self.run_id,
                "target_run_id": result.run_id,
                "result": result.model_dump(mode="json"),
            },
            timeout,
        )
        return AgentRunEvent.model_validate(resp)

    async def run_finalize(
        self,
        run_id: str | None = None,
        status: str | None = None,
        reason: str | None = None,
    ) -> AgentRun:
        """Finalize one Host-owned run ledger record.

        Args:
            run_id: Run ID to finalize. Defaults to the current run.
            status: Optional terminal status supplied by the caller.
            reason: Optional terminal status reason for Host audit/debug output.
        """
        self._require_context_api("run_finalize")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.RUN_FINALIZE,
            {
                "run_id": self.run_id,
                "target_run_id": run_id or self.run_id,
                "status": status,
                "reason": reason,
            },
            timeout,
        )
        return AgentRun.model_validate(resp)
