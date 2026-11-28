"""Platform APIs with the same signatures as the shared plugin API."""

import time
from typing import Any
from langbot_plugin.api.entities.builtin.platform.message import MessageChain
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionRequest,
    InteractionResult,
    InteractionNotSupportedError,
)


class RunnerPlatformAPIMixin:
    async def request_interaction(
        self,
        request: InteractionRequest,
        *,
        timeout: float = 600,
        on_unsupported: str = "error",
        responders: str | list[str] = "actor",
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> InteractionResult:
        if not 0 < timeout <= 86400:
            raise ValueError("Interaction timeout must be between 0 and 86400 seconds")
        if on_unsupported not in {"error", "degrade"}:
            raise ValueError("on_unsupported must be 'error' or 'degrade'")
        if (target_type is None) != (target_id is None):
            raise ValueError("target_type and target_id must be provided together")
        original_deadline = self.ctx.runtime.deadline_at
        started_at = time.time()
        if original_deadline is not None:
            self.ctx.runtime.deadline_at = float(original_deadline) + timeout + 30
        try:
            response = await self._api.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.REQUEST_INTERACTION,
                {
                    "run_id": self.run_id,
                    "request": request.model_dump(mode="json"),
                    "timeout": timeout,
                    "on_unsupported": on_unsupported,
                    "responders": responders,
                    "target_type": target_type,
                    "target_id": target_id,
                },
                timeout + 30,
                cancel_peer_on_cancel=True,
            )
            if response.get("unsupported"):
                raise InteractionNotSupportedError(response["unsupported"])
            result = InteractionResult.model_validate(response)
        except BaseException:
            if original_deadline is not None:
                self.ctx.runtime.deadline_at = float(original_deadline) + (
                    time.time() - started_at
                )
            raise
        if result.deadline_at is not None:
            self.ctx.runtime.deadline_at = result.deadline_at
        elif original_deadline is not None:
            self.ctx.runtime.deadline_at = float(original_deadline) + (
                time.time() - started_at
            )
        return result

    async def call_platform_api(
        self, bot_uuid: str, action: str, params: dict[str, Any] | None = None
    ) -> Any:
        response = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.CALL_PLATFORM_API,
            {
                "run_id": self.run_id,
                "bot_uuid": bot_uuid,
                "action": action,
                "params": params or {},
            },
            self._bounded_timeout(default=180.0),
        )
        return self._expect_key(
            response, "result", PluginToRuntimeAction.CALL_PLATFORM_API
        )

    async def send_message(
        self,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        message_chain: MessageChain,
    ) -> Any:
        return await self.call_platform_api(
            bot_uuid,
            "send_message",
            {
                "target_type": target_type,
                "target_id": target_id,
                "message": message_chain.model_dump(mode="json"),
            },
        )

    async def reply_message(
        self, message_chain: MessageChain, quote_origin: bool = False
    ) -> Any:
        response = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.CALL_PLATFORM_API,
            {
                "run_id": self.run_id,
                "action": "send_message",
                "context_tool": "event_reply",
                "params": {
                    "message": message_chain.model_dump(mode="json"),
                    "quote_origin": quote_origin,
                },
            },
            self._bounded_timeout(default=180.0),
        )
        return self._expect_key(
            response, "result", PluginToRuntimeAction.CALL_PLATFORM_API
        )
