"""Workspace Application API proxy for listing and executing authorized operations."""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.errors import ActionCallError
from .workspace_domains import WorkspaceDomains

logger = logging.getLogger(__name__)


class WorkspaceOperationsProxy(WorkspaceDomains):
    """Proxy for interacting with authorized LangBot workspace operations."""

    def __init__(self, handler: Any, run_id: str | None = None):
        if hasattr(handler, "call_action"):
            self._handler = handler
        elif hasattr(handler, "plugin_runtime_handler"):
            self._handler = handler.plugin_runtime_handler
        else:
            self._handler = handler
        self._run_id = run_id
        super().__init__(self)

    async def list(self) -> dict[str, Any]:
        """List authorized Application API operations and domains for the current run.

        Returns structured result with 'operations' and 'domains'.
        Does not raise business exceptions on failure.
        """
        payload: dict[str, Any] = {}
        if self._run_id is not None:
            payload["run_id"] = self._run_id

        try:
            result = await self._handler.call_action(
                PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS,
                payload,
                timeout=180.0,
            )
            if isinstance(result, dict):
                return result
            return {"operations": [], "domains": []}
        except ActionCallError as exc:
            logger.warning("Failed to list workspace operations: %s", exc)
            data = getattr(exc, "data", None)
            error_code = "action_error"
            if isinstance(data, dict) and "code" in data:
                error_code = data["code"]
            return {
                "operations": [],
                "domains": [],
                "error": {
                    "code": error_code,
                    "message": str(exc),
                    "details": data,
                },
            }
        except Exception as exc:
            logger.warning("Unexpected error listing workspace operations: %s", exc)
            return {
                "operations": [],
                "domains": [],
                "error": {"code": "execution_error", "message": str(exc)},
            }

    async def call(
        self,
        operation_id: str,
        _timeout: float | None = None,
        **arguments: Any,
    ) -> dict[str, Any]:
        """Directly call an authorized Application API operation.

        Returns structured result from Core without raising business exceptions.
        """
        payload: dict[str, Any] = {
            "operation_id": operation_id,
            "arguments": dict(arguments),
        }
        if self._run_id is not None:
            payload["run_id"] = self._run_id

        timeout = _timeout if _timeout is not None else 180.0

        try:
            result = await self._handler.call_action(
                PluginToRuntimeAction.CALL_APPLICATION_OPERATION,
                payload,
                timeout=timeout,
            )
            if isinstance(result, dict):
                return result
            return {
                "ok": True,
                "result": result,
                "operation": {"id": operation_id},
            }
        except ActionCallError as exc:
            logger.warning("Workspace operation %s failed: %s", operation_id, exc)
            data = getattr(exc, "data", None)
            error_code = "action_error"
            if isinstance(data, dict) and "code" in data:
                error_code = data["code"]
            return {
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": str(exc),
                    "details": data,
                },
            }
        except Exception as exc:
            logger.warning(
                "Unexpected error calling workspace operation %s: %s", operation_id, exc
            )
            return {
                "ok": False,
                "error": {
                    "code": "execution_failed",
                    "message": str(exc),
                },
            }
