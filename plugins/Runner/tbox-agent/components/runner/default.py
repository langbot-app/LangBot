"""Tbox Agent default runner implementation.

Real Tbox (蚂蚁百宝箱) API integration supporting chat with multimodal input and stateful sessions.
"""

from __future__ import annotations

import base64
import json
import logging
import typing
from contextlib import aclosing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from pkg.reasoning import ResponseBudget, ThinkingFilter, positive_timeout, strict_bool
from pkg.scoped_identity import scoped_identity
from pkg.tbox_client import (
    AsyncTboxClient,
    TboxAPIError,
    TboxConfigError,
)

logger = logging.getLogger(__name__)


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
            raise TboxAPIError("Input attachment exceeds the 10 MiB size limit", code="tbox.input_error")

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


def _usage_from_payload(*payloads: typing.Any) -> dict[str, typing.Any] | None:
    for payload in payloads:
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                continue
        if not isinstance(payload, dict):
            continue

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
            continue

        normalized = dict(usage)
        prompt_tokens = _first_int(usage, "prompt_tokens", "input_tokens", "input_count")
        completion_tokens = _first_int(usage, "completion_tokens", "output_tokens", "output_count")
        total_tokens = _first_int(usage, "total_tokens", "token_count", "total_count")

        if prompt_tokens is not None:
            normalized["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            normalized["completion_tokens"] = completion_tokens
        if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
        if total_tokens is not None:
            normalized["total_tokens"] = total_tokens

        return normalized or None
    return None


class DefaultRunner(Runner):
    """Real Runner for Tbox (蚂蚁百宝箱) API.

    Features:
    - Streaming and non-streaming responses
    - Multimodal input (image uploads)
    - Stateful session via conversation_id
    - Thinking content with ࿏...viewport tags

    Configuration (from ctx.config):
    - app-id: Tbox application ID
    - api-key: Tbox authorization token

    Runtime state (from ctx.state):
    - external.conversation_id: Tbox conversation ID for stateful sessions
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Validate and return static configuration.

        Raises TboxConfigError on missing required fields.
        """
        config = ctx.config or {}
        self._get_user_id(ctx)  # Validate identity before constructing any upstream client.
        try:
            remove_think = strict_bool(config, "remove-think")
            timeout = positive_timeout(config)
            if "streaming" in config:
                strict_bool(config, "streaming")
        except ValueError as exc:
            raise TboxConfigError(str(exc), code="tbox.config_invalid") from None

        app_id = config.get("app-id", "")
        if not app_id:
            raise TboxConfigError("app-id is required", code="tbox.config_invalid")

        api_key = config.get("api-key", "")
        if not api_key:
            raise TboxConfigError("api-key is required", code="tbox.config_invalid")

        return {
            "app_id": app_id,
            "api_key": api_key,
            "timeout": timeout,
            "remove_think": remove_think,
        }

    def _get_user_id(self, ctx: RunnerContext) -> str:
        """Get user identifier for Tbox API."""
        source = ctx.config.get("user-id-source", "sender")
        if source not in ("sender", "legacy-bot"):
            raise TboxConfigError("user-id-source is invalid", code="tbox.config_invalid")
        if source == "legacy-bot":
            conversation = ctx.conversation
            bot_id = conversation.bot_id if conversation else ctx.runtime.metadata.get("bot_id")
            if isinstance(bot_id, str) and bot_id:
                return scoped_identity(self, ctx, bot_id)
            raise TboxConfigError("user-id-source requires trusted Host identity", code="tbox.identity_unavailable")
        actor = ctx.actor
        if actor and actor.actor_id:
            return scoped_identity(self, ctx, f"{actor.actor_type}_{actor.actor_id}")
        raise TboxConfigError(
            "user-id-source=sender requires a trusted Host actor identity",
            code="tbox.identity_unavailable",
        )

    def _get_external_conversation_id(self, ctx: RunnerContext) -> str | None:
        """Get external conversation ID from state.

        Priority:
        1. ctx.state.conversation["external.conversation_id"]
        2. None (start new conversation)
        """
        # State (persistent external conversation ID)
        external_conv_id = ctx.state.conversation.get("external.conversation_id")
        if external_conv_id:
            return external_conv_id

        # Start new Tbox conversation
        return None

    async def _upload_input_files(
        self,
        ctx: RunnerContext,
        client: AsyncTboxClient,
    ) -> list[dict[str, typing.Any]]:
        """Upload files from input attachments to Tbox.

        Returns list of Tbox file references.
        """
        uploaded_files: list[dict[str, typing.Any]] = []

        attachments = list(ctx.input.attachments or [])
        if not any(_attachment_get(attachment, "content") for attachment in attachments):
            attachments.extend(_attachments_from_contents(ctx.input.contents))

        for attachment in attachments:
            try:
                file_bytes = _decode_content(_attachment_get(attachment, "content"))
                if not file_bytes:
                    raise TboxAPIError(
                        f"Input attachment {_attachment_get(attachment, 'name', 'file')} has no uploadable content",
                        code="tbox.input_error",
                    )

                file_name = _attachment_get(attachment, "name") or "file"
                content_type = (
                    _attachment_get(attachment, "content_type")
                    or _attachment_get(attachment, "mime_type")
                    or "application/octet-stream"
                )

                # Tbox primarily supports images
                if content_type.startswith("image/"):
                    file_id = await client.upload_file(file_bytes, file_name)
                    if file_id:
                        uploaded_files.append(
                            {
                                "file_id": file_id,
                                "type": "image",
                            }
                        )
                    else:
                        raise TboxAPIError(
                            f"Tbox file upload response missing file id for {file_name}",
                            code="tbox.input_error",
                        )
                elif content_type:
                    raise TboxAPIError(
                        f"Tbox only supports image attachments, got {content_type}",
                        code="tbox.input_error",
                    )
            except TboxAPIError as e:
                if e.code in {"tbox.input_error", "tbox.timeout"}:
                    raise
                raise TboxAPIError(
                    f"Failed to upload input attachment {_attachment_get(attachment, 'name', 'file')}: {e.message}",
                    code="tbox.input_error",
                ) from None
            except Exception as e:
                raise TboxAPIError(
                    f"Failed to upload input attachment {_attachment_get(attachment, 'name', 'file')}: {e}",
                    code="tbox.input_error",
                ) from None

        return uploaded_files

    def _get_input_text(self, ctx: RunnerContext) -> str:
        """Get text input from context."""
        return ctx.input.to_text()

    def _should_stream(self, ctx: RunnerContext) -> bool:
        """Decide whether to request streaming from Tbox."""
        if "streaming" in ctx.config:
            return strict_bool(ctx.config, "streaming")
        return bool(ctx.runtime.metadata.get("streaming_supported", ctx.delivery.supports_streaming))

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the Tbox agent.

        Streams RunnerResult.message_delta chunks and final run_completed.
        """
        try:
            config = self._validate_config(ctx)
        except TboxConfigError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return

        client = AsyncTboxClient(api_key=config["api_key"], timeout=config["timeout"])

        user_id = self._get_user_id(ctx)
        input_text = self._get_input_text(ctx)
        app_id = config["app_id"]

        # Get conversation_id from state (not from config!)
        conversation_id = self._get_external_conversation_id(ctx)

        is_stream = self._should_stream(ctx)

        try:
            # Upload files if present. Multimodal inputs must not silently
            # degrade to text-only when provider upload fails.
            files = await self._upload_input_files(ctx, client)

            # Own every delegated generator through downstream backpressure/close.
            async with aclosing(
                self._run_chat(ctx, client, app_id, user_id, input_text, conversation_id, files, is_stream)
            ) as results:
                async for result in results:
                    yield result
        except TboxAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
                retryable=getattr(e, "retryable", False),
            )
            return
        except Exception as e:
            logger.exception(f"Tbox runner unexpected error: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"Tbox runner error: {e}",
                code="tbox.unexpected_error",
            )
            return

    async def _run_chat(
        self,
        ctx: RunnerContext,
        client: AsyncTboxClient,
        app_id: str,
        user_id: str,
        input_text: str,
        conversation_id: str | None,
        files: list[dict[str, typing.Any]],
        is_stream: bool,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run chat with Tbox.

        Streams message_delta chunks and handles streaming/non-streaming responses.
        """
        budget = ResponseBudget(TboxAPIError, "tbox.response_limit")
        pending_content = ""
        remove_think = strict_bool(ctx.config, "remove-think")
        text_filter = ThinkingFilter(remove_think)
        final_conversation_id = conversation_id
        has_response = False
        idx_msg = 0
        think_start = False
        think_end = False
        usage: dict[str, typing.Any] | None = None

        async with aclosing(
            client.chat(
                app_id=app_id,
                user_id=user_id,
                query=input_text,
                stream=is_stream,
                conversation_id=conversation_id,
                files=files if files else None,
            )
        ) as chunks:
            async for chunk in chunks:
                chunk_type = chunk.get("type", "")
                usage = _usage_from_payload(chunk, chunk.get("payload"), chunk.get("data")) or usage

                if is_stream:
                    # Handle streaming chunks
                    if chunk_type == "chunk":
                        """
                        Tbox chunk structure:
                        {'lane': 'default', 'payload': {'conversationId': '...', 'messageId': '...', 'text': '...'}, 'type': 'chunk'}
                        """
                        # If thinking started but not ended, add closing tag
                        if think_start and not think_end:
                            pending_content += "\n viewport\n"
                            think_end = True

                        payload = chunk.get("payload", {})
                        if not final_conversation_id:
                            final_conversation_id = payload.get("conversationId")

                        budget.add(payload.get("text", ""))
                        if payload.get("text"):
                            idx_msg += 1
                            has_response = True
                            pending_content += text_filter.feed(payload.get("text"))

                    elif chunk_type == "thinking":
                        """
                        Tbox thinking chunk structure:
                        {'payload': '{"ext_data":{"text":"..."},"event":"flow.node.llm.thinking",...}', 'type': 'thinking'}
                        """
                        try:
                            payload = json.loads(chunk.get("payload", "{}"))
                            budget.add(payload.get("ext_data", {}).get("text", ""))
                            if payload.get("ext_data", {}).get("text"):
                                has_response = True
                                if remove_think:
                                    continue
                                idx_msg += 1
                                content = payload.get("ext_data", {}).get("text")
                                if not think_start:
                                    think_start = True
                                    pending_content += f"<tool_call>\n{content}"
                                else:
                                    pending_content += content
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse Tbox thinking payload: {chunk}")

                    elif chunk_type == "error":
                        raise TboxAPIError(
                            f"Tbox API error: status_code={chunk.get('status_code')} "
                            f"message={chunk.get('message')} request_id={chunk.get('request_id')}",
                            code="tbox.api_error",
                        )

                    budget.check_rendered(pending_content)

                    # Yield periodic updates (every 8 chunks)
                    if idx_msg > 0 and idx_msg % 8 == 0:
                        has_response = True
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(
                                role="assistant",
                                content=pending_content,
                                is_final=False,
                            ),
                        )

                else:
                    # Handle non-streaming response
                    """
                    Tbox non-stream response:
                    {'errorCode': '0', 'data': {'conversationId': '...', 'reasoningContent': [...], 'result': [...]}}
                    """
                    if chunk.get("errorCode") != "0":
                        raise TboxAPIError(
                            f"Tbox API request failed: {chunk.get('errorMsg', '')}",
                            code="tbox.api_error",
                        )

                    payload = chunk.get("data", {})
                    final_conversation_id = payload.get("conversationId", "")

                    budget.add(
                        *(item.get("text", "") for item in payload.get("reasoningContent", [])),
                        *(item.get("chunk", "") for item in payload.get("result", [])),
                    )
                    result = ""
                    thinking_content = payload.get("reasoningContent", [])
                    if thinking_content and not remove_think:
                        result += f"<tool_call>\n{thinking_content[0].get('text', '')}\n viewport\n"

                    content = payload.get("result", [])
                    if content:
                        result += text_filter.feed(content[0].get("chunk", ""), final=True)

                    budget.check_rendered(result)
                    has_response = True
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(
                            role="assistant",
                            content=result,
                            is_final=True,
                        ),
                    )

        # Flush literal partial delimiters only at EOF. Hidden-only responses
        # still complete successfully with an empty final chunk.
        pending_content += text_filter.feed("", final=True)
        budget.check_rendered(pending_content)
        if is_stream and (pending_content or has_response):
            has_response = True
            yield RunnerResult.message_delta(
                ctx.run_id,
                MessageChunk(
                    role="assistant",
                    content=pending_content,
                    is_final=True,
                ),
            )

        if not has_response:
            raise TboxAPIError(
                "Tbox API returned no response",
                code="tbox.api_error",
            )

        # Update state with conversation_id for next run (scoped state)
        if final_conversation_id:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.conversation_id",
                final_conversation_id,
                scope="conversation",
            )

        yield RunnerResult.run_completed(ctx.run_id, usage=usage)
