"""n8n Workflow Agent default runner implementation.

Real n8n webhook integration supporting streaming and non-streaming responses.
"""

from __future__ import annotations

import logging
import typing
import uuid

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from pkg.asset_gateway import register_assets
from pkg.n8n_client import (
    AsyncN8nClient,
    N8nAPIError,
    N8nConfigError,
)
from pkg.scoped_identity import scoped_identity

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


def _get_adapter_params(ctx: RunnerContext) -> dict[str, typing.Any]:
    """Read single-run business params from adapter.extra.params."""
    if ctx.adapter is None:
        return {}
    params = (ctx.adapter.extra or {}).get("params")
    return dict(params) if isinstance(params, dict) else {}


class DefaultRunner(Runner):
    """Real Runner for n8n Webhook.

    Supports:
    - Webhook calls with various authentication types (none, basic, jwt, header)
    - Streaming response (type: item/end format)
    - Non-streaming JSON response
    - Stateful session via conversation_id

    Configuration (static, from ctx.config):
    - webhook-url: n8n webhook URL (required)
    - auth-type: Authentication type (none/basic/jwt/header)
    - basic-username: Username for basic auth
    - basic-password: Password for basic auth
    - basic-encoding: Credential encoding (utf-8 default; latin1 for native migration)
    - jwt-secret: Secret key for JWT auth
    - jwt-algorithm: JWT algorithm (default: HS256)
    - header-name: Custom header name for header auth
    - header-value: Custom header value for header auth
    - timeout: Request timeout in seconds (default: 120)
    - output-key: Key to extract from non-streaming JSON response (default: response)
    - response-handling: Forward the response (reply, default) or ignore its body
    - langbot-assets-enabled: Register a run-scoped LangBot asset token and inject
      it into the webhook payload (default: false)
    - langbot-assets-gateway-host/port: Bind address of the local LangBot Asset Gateway
    - langbot-assets-gateway-request-timeout: Per gateway tool-call timeout (seconds)
    - langbot-assets-token-ttl: Lifetime of each run token (seconds)
    - langbot-assets-input-name: Payload field that receives the run token
      (default: langbot_asset_run_token)

    Runtime state (from ctx.state):
    - external.conversation_id: n8n conversation ID for stateful sessions
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Validate and return static configuration.

        Raises N8nConfigError on missing required fields.
        """
        config = ctx.config or {}
        self._get_user_tag(ctx)  # Validate identity before constructing any upstream client.

        webhook_url = config.get("webhook-url", "")
        if not webhook_url:
            raise N8nConfigError("webhook-url is required", code="n8n.config_invalid")

        auth_type = config.get("auth-type", "none")
        valid_auth_types = ["none", "basic", "jwt", "header"]
        if auth_type not in valid_auth_types:
            raise N8nConfigError(
                f"Invalid auth-type: {auth_type}. Must be one of {valid_auth_types}",
                code="n8n.config_invalid",
            )

        response_handling = config.get("response-handling", "reply")
        if response_handling not in ("reply", "ignore"):
            raise N8nConfigError("response-handling must be reply or ignore")
        if auth_type == "header" and not config.get("header-name"):
            raise N8nConfigError("header-name is required for header authentication")
        basic_encoding = config.get("basic-encoding", "utf-8")
        if auth_type == "basic" and basic_encoding not in ("utf-8", "latin1"):
            raise N8nConfigError("basic-encoding must be utf-8 or latin1")

        return {
            "webhook_url": webhook_url,
            "auth_type": auth_type,
            "auth_config": {
                "basic_username": config.get("basic-username", ""),
                "basic_password": config.get("basic-password", ""),
                "basic_encoding": basic_encoding,
                "jwt_secret": config.get("jwt-secret", ""),
                "jwt_algorithm": config.get("jwt-algorithm", "HS256"),
                "header_name": config.get("header-name", ""),
                "header_value": config.get("header-value", ""),
            },
            "timeout": float(config.get("timeout", 120)),
            "output_key": config.get("output-key", "response"),
            "response_handling": response_handling,
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

        The token is later injected into the webhook payload so the n8n workflow
        can pass it as the ``run_token`` argument on LangBot Asset Gateway MCP
        tool calls. The registration must be stopped when the run ends.
        """
        return await register_assets(self, self.get_run_api(ctx), ctx, config)

    def _get_user_tag(self, ctx: RunnerContext) -> str:
        """Get user identifier for n8n webhook."""
        source = ctx.config.get("user-id-source", "sender")
        if source not in ("sender", "legacy-session"):
            raise N8nConfigError("user-id-source is invalid", code="n8n.config_invalid")
        if source == "legacy-session":
            conversation = ctx.conversation
            if conversation and conversation.launcher_type in ("group", "person"):
                launcher_id = conversation.launcher_id
                if isinstance(launcher_id, str) and launcher_id:
                    return scoped_identity(self, ctx, f"{conversation.launcher_type}_{launcher_id}")
            raise N8nConfigError("user-id-source requires trusted Host identity", code="n8n.identity_unavailable")
        actor = ctx.actor
        if actor and actor.actor_id:
            return scoped_identity(self, ctx, f"{actor.actor_type}_{actor.actor_id}")
        raise N8nConfigError(
            "user-id-source=sender requires a trusted Host actor identity",
            code="n8n.identity_unavailable",
        )

    def _get_or_create_state_id(
        self,
        ctx: RunnerContext,
        key: str,
        prefix: str,
    ) -> tuple[str, bool]:
        """Get or create a runner-owned external identifier.

        Priority:
        1. ctx.state.conversation[key] (persistent)
        2. Generate new UUID

        Returns (identifier, created).
        """
        existing = ctx.state.conversation.get(key)
        if existing:
            return str(existing), False
        return f"{prefix}_{uuid.uuid4().hex}", True

    def _build_payload(
        self,
        ctx: RunnerContext,
        user_message: str,
        conversation_id: str,
        session_id: str,
    ) -> dict[str, typing.Any]:
        """Build webhook payload.

        Includes standard fields and merges adapter params.
        """
        user_tag = self._get_user_tag(ctx)
        params = _get_adapter_params(ctx)

        payload = {
            # Standard message fields (multiple keys for compatibility)
            "chatInput": user_message,
            "message": user_message,
            "user_message_text": user_message,
            # Session/conversation tracking
            "conversation_id": conversation_id,
            "session_id": session_id,
            "user_id": user_tag,
            "msg_create_time": params.get("msg_create_time", ""),
        }

        # Add optional fields from adapter params
        if params:
            # Merge other params (excluding reserved keys)
            reserved_keys = {"msg_create_time", "conversation_id", "session_id", "user_id"}
            for key, value in params.items():
                if key not in reserved_keys:
                    payload[key] = value

        return payload

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the n8n webhook.

        Streams RunnerResult.message_delta chunks and final run_completed.
        """
        try:
            config = self._validate_config(ctx)
        except N8nConfigError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return

        client = AsyncN8nClient(
            webhook_url=config["webhook_url"],
            timeout=config["timeout"],
            output_key=config["output_key"],
            response_handling=config["response_handling"],
        )

        # Get text input
        user_message = ctx.input.to_text()

        # Get or create runner-owned external IDs. Do not expose LangBot-local
        # conversation/session ids as workflow identifiers.
        conversation_id, conversation_created = self._get_or_create_state_id(
            ctx,
            "external.conversation_id",
            "n8n_conversation",
        )
        session_id, session_created = self._get_or_create_state_id(
            ctx,
            "external.session_id",
            "n8n_session",
        )

        # Build payload
        payload = self._build_payload(ctx, user_message, conversation_id, session_id)

        auth_type = config["auth_type"]
        auth_config = config["auth_config"]

        # Track accumulated content for final message
        full_content = ""
        has_response = False

        # Optionally register a run-scoped LangBot asset token and inject it into
        # the webhook payload. The n8n workflow reads this field and passes it as
        # the run_token argument on LangBot Asset Gateway MCP tool calls, so the
        # workflow can call back into LangBot history/knowledge/tools during the
        # webhook request. The token is stopped in finally when the run ends.
        asset_registration = None
        if config["langbot_assets_enabled"]:
            asset_registration = await self._create_asset_gateway_registration(ctx, config)
            payload[config["asset_gateway_input_name"]] = asset_registration.token

        try:
            async for event in client.call_webhook(
                payload=payload,
                auth_type=auth_type,
                auth_config=auth_config,
            ):
                event_type = event.get("type")

                if event_type == "item":
                    # Streaming chunk
                    content = event.get("content", "")
                    full_content += content
                    has_response = True

                    # Yield delta for each chunk
                    yield RunnerResult.message_delta(ctx.run_id, MessageChunk(role="assistant", content=full_content))

                elif event_type == "end":
                    # Streaming completed
                    if full_content:
                        yield RunnerResult.message_delta(
                            ctx.run_id, MessageChunk(role="assistant", content=full_content, is_final=True)
                        )

                elif event_type == "json":
                    # Non-streaming response
                    output_content = event.get("content", "")
                    if output_content:
                        has_response = True
                        yield RunnerResult.message_delta(
                            ctx.run_id, MessageChunk(role="assistant", content=output_content, is_final=True)
                        )

        except N8nAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return
        except Exception as e:
            # HTTP/auth/parser exceptions may include URLs, headers or response
            # values. Neither logs nor chat-facing failures may echo those.
            logger.error("n8n runner unexpected error (%s)", type(e).__name__)
            yield RunnerResult.run_failed(
                ctx.run_id,
                error="n8n runner encountered an unexpected error",
                code="n8n.unexpected_error",
            )
            return
        finally:
            if asset_registration is not None:
                await asset_registration.stop()

        if not has_response and config["response_handling"] != "ignore":
            yield RunnerResult.run_failed(
                ctx.run_id,
                error="n8n webhook returned no response",
                code="n8n.empty_response",
            )
            return

        if conversation_created:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.conversation_id",
                conversation_id,
                scope="conversation",
            )
        if session_created:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.session_id",
                session_id,
                scope="conversation",
            )

        yield RunnerResult.run_completed(ctx.run_id)
