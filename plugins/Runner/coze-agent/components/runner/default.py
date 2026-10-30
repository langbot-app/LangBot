"""Coze Agent default runner implementation.

Real Coze API integration supporting streaming responses with multimodal input.
"""

from __future__ import annotations

import base64
import json
import logging
import typing
from urllib.parse import urlsplit

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from pkg.asset_gateway import register_assets
from pkg.coze_client import (
    AsyncCozeClient,
    CozeAPIError,
    CozeConfigError,
)
from pkg.reasoning import ResponseBudget, ThinkingFilter, positive_timeout, strict_bool
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


def _attachment_get(attachment: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(attachment, dict):
        return attachment.get(key, default)
    return getattr(attachment, key, default)


def _content_get(content: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(content, dict):
        return content.get(key, default)
    return getattr(content, key, default)


def _content_type_from_base64(value: typing.Any, default: str) -> str:
    if isinstance(value, str) and value.startswith("data:") and ";base64," in value:
        return value[5 : value.find(";base64,")] or default
    return default


def _decode_content(value: typing.Any) -> bytes | None:
    max_bytes = 10 * 1024 * 1024

    def check_size(size: int) -> None:
        if size > max_bytes:
            raise CozeAPIError("Input attachment exceeds the 10 MiB size limit", code="coze.input_error")

    if isinstance(value, (bytes, bytearray)):
        check_size(len(value))
        return bytes(value)
    if isinstance(value, str):
        start = value.find(",") + 1 if value.startswith("data:") else 0
        # Check before slicing or decoding: decoding itself allocates memory.
        if len(value) - start > 4 * ((max_bytes + 2) // 3) + 4:
            check_size(max_bytes + 1)
        payload = value[start:]
        try:
            decoded = base64.b64decode(payload, validate=True)
        except (ValueError, base64.binascii.Error):
            # Retain the existing plain-text attachment fallback, also bounded.
            check_size(len(value))
            decoded = value.encode("utf-8")
        check_size(len(decoded))
        return decoded
    return None


def _attachments_from_contents(contents: list[typing.Any]) -> list[dict[str, typing.Any]]:
    attachments: list[dict[str, typing.Any]] = []
    for item in contents or []:
        item_type = _content_get(item, "type")
        if item_type == "image_base64":
            content = _content_get(item, "image_base64")
            attachments.append(
                {
                    "type": "image",
                    "name": "image.png",
                    "content": content,
                    "content_type": _content_type_from_base64(content, "image/jpeg"),
                }
            )
        elif item_type == "file_base64":
            content = _content_get(item, "file_base64")
            attachments.append(
                {
                    "type": "file",
                    "name": _content_get(item, "file_name") or "file",
                    "content": content,
                    "content_type": _content_type_from_base64(content, "application/octet-stream"),
                }
            )
    return attachments


def _int_or_none(value: typing.Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(mapping: dict[str, typing.Any], *keys: str) -> int | None:
    for key in keys:
        value = _int_or_none(mapping.get(key))
        if value is not None:
            return value
    return None


def _usage_from_payload(payload: typing.Any) -> dict[str, typing.Any] | None:
    if not isinstance(payload, dict):
        return None

    usage = payload.get("usage")
    if not isinstance(usage, dict):
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            usage = metadata.get("usage")
    if not isinstance(usage, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            usage = data.get("usage")
    token_keys = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "input_count",
        "output_count",
        "token_count",
        "total_count",
    }
    if not isinstance(usage, dict) and token_keys.intersection(payload):
        usage = payload
    if not isinstance(usage, dict):
        return None

    normalized = dict(usage)
    prompt_tokens = _first_int(usage, "prompt_tokens", "input_tokens", "input_count", "inputTokenCount")
    completion_tokens = _first_int(
        usage,
        "completion_tokens",
        "output_tokens",
        "output_count",
        "outputTokenCount",
    )
    total_tokens = _first_int(usage, "total_tokens", "token_count", "total_count", "totalTokenCount")

    if prompt_tokens is not None:
        normalized["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        normalized["completion_tokens"] = completion_tokens
    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    if total_tokens is not None:
        normalized["total_tokens"] = total_tokens

    return normalized or None


class DefaultRunner(Runner):
    """Real Runner for Coze API.

    Supports:
    - Streaming chat responses
    - Multimodal input (text, image, file)
    - Thinking/reasoning content with 🤔...💬 tags
    - Stateful session via conversation_id

    Configuration (static, from ctx.config):
    - bot-id: Coze Bot ID
    - api-key: Coze API Key
    - api-base: Coze API base URL (default: https://api.coze.cn)
    - timeout: Request timeout in seconds
    - auto-save-history: Whether to save chat history

    Runtime state (from ctx.state):
    - external.conversation_id: Coze conversation ID for stateful sessions
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Validate and return static configuration.

        Raises CozeConfigError on missing required fields.
        """
        config = ctx.config or {}
        self._get_user_id(ctx)  # Validate identity before constructing any upstream client.
        try:
            remove_think = strict_bool(config, "remove-think")
            timeout = positive_timeout(config)
            auto_save_history = strict_bool(config, "auto-save-history", True)
        except ValueError as exc:
            raise CozeConfigError(str(exc), code="coze.config_invalid") from None

        api_base = config.get("api-base", "https://api.coze.cn")
        try:
            if not isinstance(api_base, str) or any(c.isspace() or ord(c) < 32 for c in api_base):
                raise ValueError
            parsed = urlsplit(api_base)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError
            _ = parsed.port  # Validate port without echoing the URL.
        except (ValueError, TypeError):
            raise CozeConfigError(
                "api-base must be an HTTP(S) URL without credentials, query or fragment", code="coze.config_invalid"
            ) from None

        api_key = config.get("api-key", "")
        if not api_key:
            raise CozeConfigError("api-key is required", code="coze.config_invalid")

        bot_id = config.get("bot-id", "")
        if not bot_id:
            raise CozeConfigError("bot-id is required", code="coze.config_invalid")

        return {
            "api_key": api_key,
            "bot_id": bot_id,
            "api_base": api_base,
            "timeout": timeout,
            "remove_think": remove_think,
            "auto_save_history": auto_save_history,
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

        The token is injected into Coze ``custom_variables`` so the bot prompt can
        reference it (``{{langbot_asset_run_token}}``) and pass it as the
        ``run_token`` argument on LangBot Asset Gateway MCP tool calls. The
        registration must be stopped when the run ends.
        """
        return await register_assets(self, self.get_run_api(ctx), ctx, config)

    def _get_user_id(self, ctx: RunnerContext) -> str:
        """Get user identifier for Coze API."""
        source = ctx.config.get("user-id-source", "sender")
        if source not in ("sender", "legacy-session"):
            raise CozeConfigError("user-id-source is invalid", code="coze.config_invalid")
        if source == "legacy-session":
            conversation = ctx.conversation
            if conversation and conversation.launcher_type in ("group", "person"):
                launcher_id = conversation.launcher_id
                if isinstance(launcher_id, str) and launcher_id:
                    return scoped_identity(self, ctx, f"{conversation.launcher_type}_{launcher_id}")
            raise CozeConfigError("user-id-source requires trusted Host identity", code="coze.identity_unavailable")
        actor = ctx.actor
        if actor and actor.actor_id:
            return scoped_identity(self, ctx, f"{actor.actor_type}_{actor.actor_id}")
        raise CozeConfigError(
            "user-id-source=sender requires a trusted Host actor identity",
            code="coze.identity_unavailable",
        )

    def _get_external_conversation_id(self, ctx: RunnerContext) -> str | None:
        """Get external conversation ID from state or context.

        Priority:
        1. ctx.state.conversation["external.conversation_id"]
        2. None (start new conversation)
        """
        # Priority 1: State (persistent external conversation ID)
        external_conv_id = ctx.state.conversation.get("external.conversation_id")
        if external_conv_id:
            return external_conv_id

        # Start a new Coze provider conversation. Do not send LangBot-local
        # conversation ids as provider conversation ids.
        return None

    async def _build_additional_messages(
        self,
        ctx: RunnerContext,
        client: AsyncCozeClient,
    ) -> list[dict[str, typing.Any]]:
        """Build Coze message format from input.

        Returns:
            List of Coze message objects with role, content, content_type
        """
        content_parts: list[dict[str, typing.Any]] = []

        # Process attachments first
        attachments = list(ctx.input.attachments or [])
        if not any(_attachment_get(attachment, "content") for attachment in attachments):
            attachments.extend(_attachments_from_contents(ctx.input.contents))

        for attachment in attachments:
            try:
                attachment_type = _attachment_get(attachment, "type") or _attachment_get(attachment, "artifact_type")
                content_type = (
                    _attachment_get(attachment, "content_type")
                    or _attachment_get(attachment, "mime_type")
                    or "application/octet-stream"
                )

                if attachment_type == "image_base64" or (
                    attachment_type == "image" and content_type.startswith("image/")
                ):
                    # Upload image to get file_id
                    file_bytes = _decode_content(_attachment_get(attachment, "content"))

                    if not file_bytes:
                        raise CozeAPIError(
                            f"Input image {_attachment_get(attachment, 'name', 'image.png')} has no uploadable content",
                            code="coze.input_error",
                        )

                    file_id = await client.upload_file(file_bytes, _attachment_get(attachment, "name") or "image.png")
                    content_parts.append({"type": "image", "file_id": file_id})

                # Handle file type
                elif attachment_type == "file":
                    file_bytes = _decode_content(_attachment_get(attachment, "content"))
                    if not file_bytes:
                        raise CozeAPIError(
                            f"Input file {_attachment_get(attachment, 'name', 'file')} has no uploadable content",
                            code="coze.input_error",
                        )
                    file_id = await client.upload_file(file_bytes, _attachment_get(attachment, "name") or "file")
                    content_parts.append({"type": "file", "file_id": file_id})

                # Handle image type (direct bytes)
                elif attachment_type == "image":
                    file_bytes = _decode_content(_attachment_get(attachment, "content"))
                    if not file_bytes:
                        raise CozeAPIError(
                            f"Input image {_attachment_get(attachment, 'name', 'image.png')} has no uploadable content",
                            code="coze.input_error",
                        )
                    file_id = await client.upload_file(file_bytes, _attachment_get(attachment, "name") or "image.png")
                    content_parts.append({"type": "image", "file_id": file_id})

            except CozeAPIError:
                raise
            except Exception as e:
                raise CozeAPIError(
                    f"Failed to upload input attachment {_attachment_get(attachment, 'name', 'attachment')}: {e}",
                    code="coze.input_error",
                ) from None

        # Add text content
        text = ctx.input.to_text()
        if text:
            content_parts.insert(0, {"type": "text", "text": text})

        if not content_parts:
            # Empty input, return empty messages list
            return []

        # Build message format
        if len(content_parts) == 1 and content_parts[0].get("type") == "text":
            # Simple text message
            return [
                {
                    "role": "user",
                    "content": content_parts[0].get("text", ""),
                    "content_type": "text",
                }
            ]
        else:
            # Multimodal message with object_string format
            return [
                {
                    "role": "user",
                    "content": json.dumps(content_parts),
                    "content_type": "object_string",
                }
            ]

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the Coze agent.

        Streams RunnerResult.message_delta chunks and final run_completed.
        """
        try:
            config = self._validate_config(ctx)
        except CozeConfigError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return

        client = AsyncCozeClient(
            api_key=config["api_key"],
            api_base=config["api_base"],
            timeout=config["timeout"],
        )

        user_id = self._get_user_id(ctx)
        conversation_id = self._get_external_conversation_id(ctx)
        auto_save_history = config["auto_save_history"]
        bot_id = config["bot_id"]

        # Build additional messages from input
        try:
            additional_messages = await self._build_additional_messages(ctx, client)
        except Exception as e:
            logger.exception(f"Failed to build Coze messages: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"Failed to prepare input: {e}",
                code="coze.input_error",
            )
            return

        final_conversation_id = conversation_id
        budget = ResponseBudget(CozeAPIError, "coze.response_limit")
        full_content = ""
        text_filter = ThinkingFilter(config["remove_think"], (("🤔", "💬"),))
        full_reasoning = ""
        has_response = False
        usage: dict[str, typing.Any] | None = None

        # Optionally register a run-scoped LangBot asset token and pass it to the
        # Coze bot through custom_variables. The bot prompt references it as
        # {{langbot_asset_run_token}} and passes it as the run_token argument on
        # LangBot Asset Gateway MCP tool calls. Stopped in finally when run ends.
        asset_registration = None
        custom_variables: dict[str, typing.Any] = {}
        if config["langbot_assets_enabled"]:
            asset_registration = await self._create_asset_gateway_registration(ctx, config)
            custom_variables[config["asset_gateway_input_name"]] = asset_registration.token

        try:
            async for chunk in client.chat_messages(
                bot_id=bot_id,
                user_id=user_id,
                additional_messages=additional_messages,
                conversation_id=conversation_id,
                auto_save_history=auto_save_history,
                custom_variables=custom_variables or None,
            ):
                event_type = chunk.get("event", "")
                data = chunk.get("data", {})
                logger.debug(f"Coze event: {event_type}")

                usage = _usage_from_payload(data) or usage

                if event_type == "conversation.message.delta":
                    budget.add(data.get("reasoning_content", ""), data.get("content", ""))
                    # Collect reasoning content
                    if "reasoning_content" in data:
                        reasoning = data.get("reasoning_content", "")
                        if reasoning:
                            has_response = True
                            if not config["remove_think"]:
                                full_reasoning += reasoning

                    # Collect main content
                    if "content" in data:
                        content_delta = data.get("content", "")
                        if content_delta:
                            full_content += text_filter.feed(content_delta)
                            has_response = True

                elif event_type.endswith(".done") or event_type == "conversation.chat.completed":
                    # Track conversation_id for stateful session
                    if data.get("conversation_id"):
                        final_conversation_id = data["conversation_id"]

                elif event_type == "error":
                    error_msg = data.get("message", "Unknown Coze API error")
                    yield RunnerResult.run_failed(
                        ctx.run_id,
                        error=f"Coze API error: {error_msg}",
                        code="coze.api_error",
                    )
                    return

            # Build final response content
            final_content = full_content + text_filter.feed("", final=True)

            # Add reasoning with think tags if present
            if full_reasoning:
                final_content = f"🤔\n{full_reasoning}\n💬\n{final_content}".strip()

            if not has_response:
                yield RunnerResult.run_failed(
                    ctx.run_id,
                    error="Coze API returned no response",
                    code="coze.empty_response",
                )
                return

            budget.check_rendered(final_content)

            # Yield final message
            yield RunnerResult.message_delta(
                ctx.run_id, MessageChunk(role="assistant", content=final_content, is_final=True)
            )

        except CozeAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return
        except Exception as e:
            logger.exception(f"Coze runner unexpected error: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"Coze runner error: {e}",
                code="coze.unexpected_error",
            )
            return
        finally:
            await client.close()
            if asset_registration is not None:
                await asset_registration.stop()

        # Update state with conversation_id for next run (scoped state)
        if final_conversation_id:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.conversation_id",
                final_conversation_id,
                scope="conversation",
            )

        yield RunnerResult.run_completed(ctx.run_id, usage=usage)
