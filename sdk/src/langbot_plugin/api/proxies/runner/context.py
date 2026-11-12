"""Context pull APIs for Runner components."""

from __future__ import annotations

import base64
from typing import Any

from langbot_plugin.api.entities.builtin.runner.errors import (
    AgentAPIError,
    AgentAPIException,
)
from langbot_plugin.api.entities.builtin.runner.page_results import (
    AgentEventRecord,
    EventPage,
    HistoryPage,
    HistorySearchResult,
)
from langbot_plugin.api.entities.builtin.runner.input import InputAttachmentData
from langbot_plugin.api.entities.builtin.runner.steering import (
    SteeringAckResult,
    SteeringPullResult,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class RunnerContextAPIMixin:
    async def get_prompt(self) -> list[dict[str, Any]]:
        """Get the Host effective prompt for the current run.

        The returned prompt reflects host-side PromptPreProcessing output for
        query-backed runs. Runners should fall back to ctx.config.prompt when
        this API is unavailable or returns an empty list.
        """
        self._require_context_api("prompt_get")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.GET_PROMPT,
            {
                "run_id": self.run_id,
            },
            timeout,
        )
        prompt = self._expect_key(resp, "prompt", PluginToRuntimeAction.GET_PROMPT)
        if not isinstance(prompt, list):
            raise AgentAPIException(
                AgentAPIError(
                    code="host.malformed_response",
                    message=f"{PluginToRuntimeAction.GET_PROMPT.value} response field prompt must be a list",
                    retryable=False,
                    details={
                        "action": PluginToRuntimeAction.GET_PROMPT.value,
                        "field": "prompt",
                    },
                )
            )
        return prompt

    async def history_page(
        self,
        conversation_id: str | None = None,
        before_cursor: str | None = None,
        after_cursor: str | None = None,
        limit: int = 50,
        direction: str = "backward",
        include_attachments: bool = False,
    ) -> dict[str, Any]:
        """Page through transcript history for a conversation.

        Args:
            conversation_id: Conversation ID to query. Must match current run's
                conversation. If None, uses current run's conversation.
            before_cursor: Get items before this cursor (backward direction).
            after_cursor: Get items after this cursor (forward direction).
            limit: Maximum items to return. Has a hard cap on host side.
            direction: 'backward' (older items) or 'forward' (newer items).
            include_attachments: Whether to include attachment refs in items.

        Returns:
            HistoryPage with items, next_cursor, prev_cursor, has_more.

        Raises:
            PermissionDeniedError: If not authorized for this conversation.
        """
        self._require_context_api("history_page")
        timeout = self._bounded_timeout(default=30.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.HISTORY_PAGE,
            {
                "run_id": self.run_id,
                "conversation_id": conversation_id,
                "before_cursor": before_cursor,
                "after_cursor": after_cursor,
                "limit": limit,
                "direction": direction,
                "include_attachments": include_attachments,
            },
            timeout,
        )
        return HistoryPage.model_validate(resp)

    async def history_search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> HistorySearchResult:
        """Search transcript history for matching items.

        This is a basic search capability. Host implementation may use
        simple LIKE filtering initially.

        Args:
            query: Search query string.
            filters: Optional filters (conversation_id, event_types, etc.).
            top_k: Maximum results to return.

        Returns:
            HistorySearchResult with items, total_count, query.

        Note:
            Basic implementation may return unsupported error or limited results.
        """
        self._require_context_api("history_search")
        timeout = self._bounded_timeout(default=30.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.HISTORY_SEARCH,
            {
                "run_id": self.run_id,
                "query": query,
                "filters": filters or {},
                "top_k": top_k,
            },
            timeout,
        )
        return HistorySearchResult.model_validate(resp)

    # ================= Event APIs (run-scoped) ==========

    async def event_get(self, event_id: str) -> AgentEventRecord:
        """Get a single event record by ID.

        Args:
            event_id: The event ID to retrieve.

        Returns:
            AgentEventRecord.

        Raises:
            PermissionDeniedError: If event not accessible by current run.
        """
        self._require_context_api("event_get")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.EVENT_GET,
            {
                "run_id": self.run_id,
                "event_id": event_id,
            },
            timeout,
        )
        return AgentEventRecord.model_validate(resp)

    async def event_page(
        self,
        conversation_id: str | None = None,
        event_types: list[str] | None = None,
        before_cursor: str | None = None,
        limit: int = 50,
    ) -> EventPage:
        """Page through event records.

        Args:
            conversation_id: Conversation ID to query. Must match current run.
            event_types: Filter by event types if specified.
            before_cursor: Get items before this cursor.
            limit: Maximum items to return. Has a hard cap on host side.

        Returns:
            EventPage with items, next_cursor, prev_cursor, has_more.

        Raises:
            PermissionDeniedError: If not authorized for this conversation.
        """
        self._require_context_api("event_page")
        timeout = self._bounded_timeout(default=30.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.EVENT_PAGE,
            {
                "run_id": self.run_id,
                "conversation_id": conversation_id,
                "event_types": event_types,
                "before_cursor": before_cursor,
                "limit": limit,
            },
            timeout,
        )
        return EventPage.model_validate(resp)

    # ================= Run Ledger APIs (run-scoped) ==========

    async def steering_pull(
        self,
        mode: str = "all",
        limit: int | None = None,
        claim: bool = False,
    ) -> SteeringPullResult:
        """Pull pending run-scoped steering/follow-up input.

        Args:
            mode: "all" to pull all currently queued items in Host claim order,
                or "one"/"one-at-a-time" to pull one item. Host does not merge
                multiple user messages.
            limit: Optional maximum number of items to pull. Host applies a
                hard cap.
            claim: Opt in to leased delivery. Requires steering_ack after the
                input is accepted. False preserves legacy consume-on-pull.

        Returns:
            SteeringPullResult with items containing event/input/context
            projections for messages claimed by the active run.

        Raises:
            PermissionDeniedError: If steering_pull is not available.
        """
        self._require_context_api("steering_pull")
        timeout = self._bounded_timeout(default=10.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.STEERING_PULL,
            {
                "run_id": self.run_id,
                "mode": mode,
                "limit": limit,
                "claim": claim,
            },
            timeout,
        )
        return SteeringPullResult.model_validate(resp)

    async def read_input_attachment(self, ref: str) -> InputAttachmentData:
        """Read the bytes of one current-event attachment by its ref.

        Args:
            ref: ``InputAttachment.ref`` of an attachment in ``ctx.input``.

        Returns:
            InputAttachmentData with the bytes, file name and MIME type.

        Raises:
            PermissionDeniedError: If the Host does not offer this API.
            AgentAPIException: If the ref is unknown, the media cannot be
                resolved, or a size limit is exceeded.
        """
        self._require_context_api("input_attachments")
        timeout = self._bounded_timeout(default=120.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.READ_INPUT_ATTACHMENT,
            {"run_id": self.run_id, "ref": ref},
            timeout,
        )
        content = self._expect_key(
            resp, "content", PluginToRuntimeAction.READ_INPUT_ATTACHMENT
        )
        try:
            data = base64.b64decode(content, validate=True)
        except (TypeError, ValueError) as exc:
            raise AgentAPIException(
                AgentAPIError(
                    code="host.malformed_response",
                    message=f"{PluginToRuntimeAction.READ_INPUT_ATTACHMENT.value} response content is not base64",
                    retryable=False,
                    details={
                        "action": PluginToRuntimeAction.READ_INPUT_ATTACHMENT.value,
                        "field": "content",
                    },
                )
            ) from exc
        return InputAttachmentData(
            ref=str(resp.get("ref") or ref),
            name=resp.get("name"),
            mime_type=resp.get("mime_type"),
            data=data,
        )

    async def steering_ack(self, delivery_ids: list[str]) -> SteeringAckResult:
        """Acknowledge claimed steering inputs after applying them."""
        self._require_context_api("steering_ack")
        timeout = 10.0
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.STEERING_ACK,
            {"run_id": self.run_id, "delivery_ids": delivery_ids},
            timeout,
        )
        return SteeringAckResult.model_validate(resp)
