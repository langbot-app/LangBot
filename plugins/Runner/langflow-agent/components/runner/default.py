"""Langflow Agent default runner implementation.

Real Langflow API integration supporting flow execution with streaming and non-streaming modes.
"""

from __future__ import annotations

import json
import logging
import typing
import uuid

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from pkg.asset_gateway import register_assets
from pkg.langflow_client import (
    AsyncLangflowClient,
    LangflowAPIError,
    LangflowConfigError,
    extract_message_from_response,
)

logger = logging.getLogger(__name__)

DEFAULT_LANGBOT_ASSET_TOKEN_INPUT = "langbot_asset_run_token"


def _to_bool(value: typing.Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _to_int(value: typing.Any, default: int) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: typing.Any, default: float) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class DefaultRunner(Runner):
    """Real Runner for Langflow API.

    Supports running Langflow flows via the /api/v1/run/{flow_id} endpoint.

    Configuration (static, from ctx.config):
    - base-url: Langflow API base URL (default: http://localhost:7860)
    - api-key: Langflow API key
    - flow-id: The flow ID to run
    - input-type: Input type for the flow (default: chat)
    - output-type: Output type for the flow (default: chat)
    - tweaks: JSON tweaks configuration (default: {})

    Runtime state (from ctx.state):
    - external.session_id: Langflow session ID for stateful sessions
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Validate and return static configuration.

        Raises LangflowConfigError on missing required fields.
        """
        config = ctx.config or {}

        base_url = config.get("base-url", "http://localhost:7860")
        if not base_url:
            raise LangflowConfigError("base-url is required", code="langflow.config_invalid")

        api_key = config.get("api-key", "")
        if not api_key:
            raise LangflowConfigError("api-key is required", code="langflow.config_invalid")

        flow_id = config.get("flow-id", "")
        if not flow_id:
            raise LangflowConfigError("flow-id is required", code="langflow.config_invalid")

        # Parse tweaks from JSON string if needed
        tweaks_raw = config.get("tweaks", "{}")
        if isinstance(tweaks_raw, str):
            try:
                tweaks = json.loads(tweaks_raw) if tweaks_raw.strip() else {}
            except json.JSONDecodeError:
                # Tweaks may contain credentials; never echo the value or parser context.
                raise LangflowConfigError("tweaks must be a JSON object", code="langflow.config_invalid") from None
        else:
            tweaks = tweaks_raw
        # Missing/null/blank remain an empty override. Whitespace-only strings
        # are a plugin convenience, not a claim that native json.loads accepted them.
        if tweaks is None:
            tweaks = {}
        if not isinstance(tweaks, dict):
            raise LangflowConfigError("tweaks must be a JSON object", code="langflow.config_invalid")

        return {
            "base_url": base_url,
            "api_key": api_key,
            "flow_id": flow_id,
            "input_type": config.get("input-type", "chat"),
            "output_type": config.get("output-type", "chat"),
            "tweaks": tweaks,
            "timeout": float(config.get("timeout", 120)),
            "langbot_assets_enabled": _to_bool(config.get("langbot-assets-enabled"), False),
            "asset_gateway_host": str(config.get("langbot-assets-gateway-host") or "0.0.0.0"),
            "asset_gateway_port": _to_int(config.get("langbot-assets-gateway-port"), 8765),
            "asset_gateway_request_timeout": _to_float(config.get("langbot-assets-gateway-request-timeout"), 60.0),
            "asset_gateway_token_ttl": _to_float(config.get("langbot-assets-token-ttl"), 3600.0),
            "asset_gateway_input_name": str(
                config.get("langbot-assets-input-name") or DEFAULT_LANGBOT_ASSET_TOKEN_INPUT
            ),
        }

    async def _create_asset_gateway_registration(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
    ):
        """Register a run-scoped LangBot asset token in the shared MCP gateway.

        The token is injected into the flow via a ``tweaks`` override that sets
        the ``input_value`` of the component named by ``langbot-assets-input-name``.
        The flow wires that component into the Agent so it passes the token as the
        ``run_token`` argument on LangBot Asset Gateway MCP tool calls. The
        registration must be stopped when the run ends.
        """
        return await register_assets(self, self.get_run_api(ctx), ctx, config)

    def _get_session_id(self, ctx: RunnerContext) -> str:
        """Get or generate session ID for Langflow.

        Priority:
        1. ctx.state.conversation["external.session_id"]
        2. Generate new UUID

        Returns:
            Session ID string
        """
        # Check for existing session in state
        session_id = ctx.state.conversation.get("external.session_id")
        if session_id:
            return session_id

        # Generate new session ID
        return str(uuid.uuid4())

    def _should_stream(self, ctx: RunnerContext) -> bool:
        """Decide whether to request streaming from Langflow."""
        configured = ctx.config.get("streaming")
        if configured is not None:
            return bool(configured)
        return bool(ctx.runtime.metadata.get("streaming_supported", True))

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the Langflow flow.

        Streams RunnerResult.message_delta chunks for streaming,
        or yields message_completed for non-streaming.
        """
        try:
            config = self._validate_config(ctx)
        except LangflowConfigError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return

        client = AsyncLangflowClient(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=config["timeout"],
        )

        input_text = ctx.input.to_text()
        session_id = self._get_session_id(ctx)

        is_stream = self._should_stream(ctx)

        # Optionally register a run-scoped LangBot asset token and inject it into
        # the flow via a tweak that sets the target component's input_value. The
        # flow wires that component into the Agent so it passes the token as the
        # run_token argument on LangBot Asset Gateway MCP tool calls. The token is
        # stopped in finally when the run ends.
        tweaks = config["tweaks"]
        asset_registration = None
        if config["langbot_assets_enabled"]:
            asset_registration = await self._create_asset_gateway_registration(ctx, config)
            tweaks = {
                **tweaks,
                config["asset_gateway_input_name"]: {"input_value": asset_registration.token},
            }

        try:
            accumulated_content = ""
            message_count = 0
            has_response = False
            final_session_id = session_id

            async for data in client.run_flow(
                flow_id=config["flow_id"],
                input_value=input_text,
                input_type=config["input_type"],
                output_type=config["output_type"],
                tweaks=tweaks,
                session_id=session_id,
                stream=is_stream,
            ):
                # Extract message content from response
                message_text = extract_message_from_response(data)
                if not message_text and not is_stream:
                    # Native non-streaming flows also expose structured outputs.
                    message_text = json.dumps(data, ensure_ascii=False, indent=2)

                if message_text:
                    if is_stream:
                        # For streaming, accumulate and yield chunks
                        accumulated_content = message_text
                        message_count += 1

                        # Yield chunks periodically (every 8 events or when content changes significantly)
                        if message_count % 8 == 0 or len(message_text) > 0:
                            yield RunnerResult.message_delta(
                                ctx.run_id,
                                MessageChunk(
                                    role="assistant",
                                    content=accumulated_content,
                                    is_final=False,
                                ),
                            )
                            has_response = True
                    else:
                        # For non-streaming, just accumulate
                        accumulated_content = message_text

                # Track session_id from response if present
                if "session_id" in data:
                    final_session_id = data["session_id"]

            # Final output
            if accumulated_content:
                if is_stream:
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(
                            role="assistant",
                            content=accumulated_content,
                            is_final=True,
                        ),
                    )
                else:
                    # Non-streaming: return complete message
                    message = Message(
                        role="assistant",
                        content=accumulated_content,
                    )
                    yield RunnerResult.message_completed(ctx.run_id, message)
                has_response = True

            if not has_response:
                raise LangflowAPIError(
                    "Langflow API returned no response",
                    code="langflow.api_error",
                )

            # Update state with session_id for next run
            if final_session_id:
                yield RunnerResult.state_updated(
                    ctx.run_id,
                    "external.session_id",
                    final_session_id,
                    scope="conversation",
                )

            yield RunnerResult.run_completed(ctx.run_id)

        except LangflowAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return
        except Exception as e:
            logger.exception(f"Langflow runner unexpected error: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"Langflow runner error: {e}",
                code="langflow.unexpected_error",
            )
            return
        finally:
            if asset_registration is not None:
                await asset_registration.stop()
