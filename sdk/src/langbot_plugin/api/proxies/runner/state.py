"""Run-scoped state APIs for Runner components."""

from __future__ import annotations

from typing import Any

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class AgentRunStateAPIMixin:
    async def state_get(self, scope: str, key: str) -> dict[str, Any]:
        """Get a state value from host-owned state store.

        Args:
            scope: State scope ('conversation', 'actor', 'subject', 'runner').
            key: State key (should use namespace prefix like 'external.*').

        Returns:
            Dict with 'value' key containing the stored value, or 'value': None
            if key does not exist.

        Raises:
            PermissionDeniedError: If scope not enabled by state_policy.
        """
        self._require_context_api("state")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.STATE_GET,
            {
                "run_id": self.run_id,
                "scope": scope,
                "key": key,
            },
            timeout,
        )
        return resp

    async def state_set(self, scope: str, key: str, value: Any) -> dict[str, Any]:
        """Set a state value in host-owned state store.

        Args:
            scope: State scope ('conversation', 'actor', 'subject', 'runner').
            key: State key (should use namespace prefix like 'external.*').
            value: State value (must be JSON-serializable, size-limited).

        Returns:
            Dict with 'success' key.

        Raises:
            PermissionDeniedError: If scope not enabled by state_policy.
        """
        self._require_context_api("state")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.STATE_SET,
            {
                "run_id": self.run_id,
                "scope": scope,
                "key": key,
                "value": value,
            },
            timeout,
        )
        return resp

    async def state_delete(self, scope: str, key: str) -> dict[str, Any]:
        """Delete a state value from host-owned state store.

        Args:
            scope: State scope ('conversation', 'actor', 'subject', 'runner').
            key: State key to delete.

        Returns:
            Dict with 'success' key (True if deleted, False if not found).

        Raises:
            PermissionDeniedError: If scope not enabled by state_policy.
        """
        self._require_context_api("state")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.STATE_DELETE,
            {
                "run_id": self.run_id,
                "scope": scope,
                "key": key,
            },
            timeout,
        )
        return resp

    async def state_list(
        self,
        scope: str,
        prefix: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List state keys in a scope.

        Args:
            scope: State scope ('conversation', 'actor', 'subject', 'runner').
            prefix: Optional prefix to filter keys (e.g., 'external.').
            limit: Maximum number of keys to return (host-enforced cap of 100).

        Returns:
            Dict with 'keys' key containing list of key names, and 'has_more'
            boolean indicating if more keys are available.

        Raises:
            PermissionDeniedError: If scope not enabled by state_policy.
        """
        self._require_context_api("state")
        timeout = self._bounded_timeout(default=15.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.STATE_LIST,
            {
                "run_id": self.run_id,
                "scope": scope,
                "prefix": prefix,
                "limit": limit,
            },
            timeout,
        )
        return resp
