"""DeerFlow Agent default runner implementation.

Ported from LangBot's legacy deerflow-api provider runner and adapted to
Runner protocol v1.
"""

from __future__ import annotations

import hashlib
import json
import logging
import typing
from collections import deque

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from pkg import stream_utils
from pkg.deerflow_client import AsyncDeerFlowClient
from pkg.errors import DeerFlowAPIError, DeerFlowConfigError

logger = logging.getLogger(__name__)

_MAX_VALUES_HISTORY = 200


class _StreamState:
    """State used while consuming a DeerFlow stream."""

    def __init__(self) -> None:
        self.latest_text = ""
        self.clarification_text = ""
        self.task_failures: list[str] = []
        self.seen_message_ids: set[str] = set()
        self.seen_message_order: deque[str] = deque()
        self.no_id_message_fingerprints: dict[int, str] = {}
        self.baseline_initialized = False
        self.has_values_text = False
        self.run_values_messages: list[dict[str, typing.Any]] = []


def _content_get(content: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(content, dict):
        return content.get(key, default)
    return getattr(content, key, default)


def _attachment_get(attachment: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(attachment, dict):
        return attachment.get(key, default)
    return getattr(attachment, key, default)


def _image_url_value(value: typing.Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("url", ""))
    return str(getattr(value, "url", "") or "")


class DefaultRunner(Runner):
    """Real Runner for DeerFlow LangGraph HTTP API.

    Configuration is read from ctx.config using the legacy deerflow-api field
    names so host-side migration can map old pipeline configs directly.

    Runtime state:
    - external.thread_id: DeerFlow LangGraph thread id for this conversation.
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        config = ctx.config or {}

        api_base = self._as_string(config, "api-base", "").strip()
        if not api_base or not api_base.startswith(("http://", "https://")):
            raise DeerFlowConfigError("api-base must start with http:// or https://")

        return {
            "api_base": api_base,
            "api_key": self._as_string(config, "api-key", ""),
            "auth_header": self._as_string(config, "auth-header", ""),
            "assistant_id": self._as_string(config, "assistant-id", "lead_agent"),
            "model_name": self._as_string(config, "model-name", ""),
            "thinking_enabled": self._as_bool(config, "thinking-enabled", False),
            "plan_mode": self._as_bool(config, "plan-mode", False),
            "subagent_enabled": self._as_bool(config, "subagent-enabled", False),
            "max_concurrent_subagents": self._as_int(config, "max-concurrent-subagents", 3),
            "timeout": self._as_int(config, "timeout", 300),
            "recursion_limit": self._as_int(config, "recursion-limit", 1000),
        }

    def _as_string(self, config: dict[str, typing.Any], name: str, default: str) -> str:
        value = config.get(name, default)
        if not isinstance(value, str):
            raise DeerFlowConfigError(f"{name} must be a string")
        # Credentials and provider identifiers are opaque, including whitespace.
        return value

    def _as_bool(self, config: dict[str, typing.Any], name: str, default: bool) -> bool:
        value = config.get(name, default)
        if not isinstance(value, bool):
            raise DeerFlowConfigError(f"{name} must be a boolean")
        return value

    def _as_int(self, config: dict[str, typing.Any], name: str, default: int) -> int:
        raw_value = config.get(name, default)
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, str)):
            raise DeerFlowConfigError(f"{name} must be an integer")
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            raise DeerFlowConfigError(f"{name} must be an integer") from None

    def _should_stream(self, ctx: RunnerContext) -> bool:
        configured = (ctx.config or {}).get("streaming")
        if configured is not None:
            return bool(configured)
        return bool(ctx.delivery.supports_streaming or ctx.runtime.metadata.get("streaming_supported", False))

    def _fingerprint_message(self, message: dict[str, typing.Any]) -> str:
        try:
            raw = json.dumps(message, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            raw = repr(message)
        return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()

    def _remember_seen_message_id(self, state: _StreamState, msg_id: str) -> None:
        if not msg_id or msg_id in state.seen_message_ids:
            return
        state.seen_message_ids.add(msg_id)
        state.seen_message_order.append(msg_id)
        while len(state.seen_message_order) > _MAX_VALUES_HISTORY:
            dropped = state.seen_message_order.popleft()
            state.seen_message_ids.discard(dropped)

    def _extract_new_messages_from_values(
        self,
        values_messages: list[typing.Any],
        state: _StreamState,
    ) -> list[dict[str, typing.Any]]:
        new_messages: list[dict[str, typing.Any]] = []
        no_id_indexes_seen: set[int] = set()
        for idx, msg in enumerate(values_messages):
            if not isinstance(msg, dict):
                continue
            msg_id = stream_utils.get_message_id(msg)
            if msg_id:
                if msg_id in state.seen_message_ids:
                    continue
                self._remember_seen_message_id(state, msg_id)
                new_messages.append(msg)
                continue

            no_id_indexes_seen.add(idx)
            fingerprint = self._fingerprint_message(msg)
            if state.no_id_message_fingerprints.get(idx) == fingerprint:
                continue
            state.no_id_message_fingerprints[idx] = fingerprint
            new_messages.append(msg)

        for idx in list(state.no_id_message_fingerprints.keys()):
            if idx not in no_id_indexes_seen:
                state.no_id_message_fingerprints.pop(idx, None)
        return new_messages

    def _build_user_content(
        self,
        prompt: str,
        image_urls: list[str],
    ) -> typing.Any:
        if not image_urls:
            return prompt

        content: list[dict[str, typing.Any]] = []
        if prompt:
            content.append({"type": "text", "text": prompt})
        for url in image_urls:
            url = url.strip()
            if not url:
                continue
            if url.startswith(("http://", "https://", "data:")):
                content.append({"type": "image_url", "image_url": {"url": url}})
        return content if content else prompt

    def _extract_image_urls(self, ctx: RunnerContext) -> list[str]:
        image_urls: list[str] = []

        for item in ctx.input.contents or []:
            item_type = _content_get(item, "type")
            if item_type == "image_base64":
                value = _content_get(item, "image_base64")
                if isinstance(value, str) and value:
                    if not value.startswith("data:"):
                        value = f"data:image/png;base64,{value}"
                    image_urls.append(value)
            elif item_type == "image_url":
                value = _image_url_value(_content_get(item, "image_url"))
                if value:
                    image_urls.append(value)

        for attachment in ctx.input.attachments or []:
            url = _attachment_get(attachment, "url")
            if isinstance(url, str) and url:
                image_urls.append(url)
                continue

            content = _attachment_get(attachment, "content")
            mime_type = _attachment_get(attachment, "mime_type") or "image/png"
            artifact_type = str(_attachment_get(attachment, "artifact_type") or "").lower()
            if (
                isinstance(content, str)
                and content
                and (artifact_type == "image" or str(mime_type).startswith("image/"))
            ):
                if not content.startswith("data:"):
                    content = f"data:{mime_type};base64,{content}"
                image_urls.append(content)

        return image_urls

    def _build_messages(
        self,
        prompt: str,
        image_urls: list[str],
        system_prompt: str = "",
    ) -> list[dict[str, typing.Any]]:
        messages: list[dict[str, typing.Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append(
            {
                "role": "user",
                "content": self._build_user_content(prompt, image_urls),
            }
        )
        return messages

    def _build_runtime_configurable(self, config: dict[str, typing.Any], thread_id: str) -> dict[str, typing.Any]:
        runtime_configurable: dict[str, typing.Any] = {
            "thread_id": thread_id,
            "thinking_enabled": config["thinking_enabled"],
            "is_plan_mode": config["plan_mode"],
            "subagent_enabled": config["subagent_enabled"],
        }
        if config["subagent_enabled"]:
            runtime_configurable["max_concurrent_subagents"] = config["max_concurrent_subagents"]
        if config["model_name"]:
            runtime_configurable["model_name"] = config["model_name"]
        return runtime_configurable

    def _build_payload(
        self,
        config: dict[str, typing.Any],
        thread_id: str,
        prompt: str,
        image_urls: list[str],
        system_prompt: str = "",
    ) -> dict[str, typing.Any]:
        runtime_configurable = self._build_runtime_configurable(config, thread_id)
        return {
            "assistant_id": config["assistant_id"],
            "input": {
                "messages": self._build_messages(prompt, image_urls, system_prompt),
            },
            "stream_mode": ["values", "messages-tuple", "custom"],
            "context": dict(runtime_configurable),
            "config": {
                "recursion_limit": config["recursion_limit"],
                "configurable": runtime_configurable,
            },
        }

    async def _ensure_thread_id(
        self,
        ctx: RunnerContext,
        client: AsyncDeerFlowClient,
        timeout: int,
    ) -> tuple[str, bool]:
        thread_id = ctx.state.conversation.get("external.thread_id")
        if thread_id:
            return str(thread_id), False

        thread = await client.create_thread(timeout=min(30, timeout))
        thread_id = thread.get("thread_id", "")
        if not thread_id:
            raise DeerFlowAPIError(
                f"DeerFlow create thread response missing thread_id: {thread}",
                code="deerflow.api_error",
            )
        return str(thread_id), True

    def _handle_values_event(
        self,
        data: typing.Any,
        state: _StreamState,
    ) -> str | None:
        values_messages = stream_utils.extract_messages_from_values_data(data)
        if not values_messages:
            return None

        if not state.baseline_initialized:
            state.baseline_initialized = True
            new_messages: list[dict[str, typing.Any]] = []
            for idx, msg in enumerate(values_messages):
                if not isinstance(msg, dict):
                    continue
                new_messages.append(msg)
                msg_id = stream_utils.get_message_id(msg)
                if msg_id:
                    self._remember_seen_message_id(state, msg_id)
                    continue
                state.no_id_message_fingerprints[idx] = self._fingerprint_message(msg)
        else:
            new_messages = self._extract_new_messages_from_values(values_messages, state)

        latest_text = ""
        if new_messages:
            state.run_values_messages.extend(new_messages)
            if len(state.run_values_messages) > _MAX_VALUES_HISTORY:
                state.run_values_messages = state.run_values_messages[-_MAX_VALUES_HISTORY:]
            latest_text = stream_utils.extract_latest_ai_text(state.run_values_messages)
            if latest_text:
                state.has_values_text = True
            latest_clarification = stream_utils.extract_latest_clarification_text(state.run_values_messages)
            if latest_clarification:
                state.clarification_text = latest_clarification

        return latest_text or None

    def _handle_message_event(
        self,
        data: typing.Any,
        state: _StreamState,
    ) -> str | None:
        delta = stream_utils.extract_ai_delta_from_event_data(data)
        if delta and not state.has_values_text:
            state.latest_text += delta
            return delta

        maybe_clarification = stream_utils.extract_clarification_from_event_data(data)
        if maybe_clarification:
            state.clarification_text = maybe_clarification
        return None

    def _build_final_text(self, state: _StreamState) -> str:
        if state.clarification_text:
            return state.clarification_text

        latest_ai = stream_utils.extract_latest_ai_message(state.run_values_messages)
        if latest_ai:
            text = stream_utils.extract_text(latest_ai.get("content"))
            if text:
                return text

        if state.latest_text:
            return state.latest_text

        failure_text = stream_utils.build_task_failure_summary(state.task_failures)
        if failure_text:
            return failure_text

        return "DeerFlow returned an empty response"

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the DeerFlow LangGraph agent."""
        try:
            config = self._validate_config(ctx)
        except DeerFlowConfigError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
                retryable=getattr(e, "retryable", False),
            )
            return

        client = AsyncDeerFlowClient(
            api_base=config["api_base"],
            api_key=config["api_key"],
            auth_header=config["auth_header"],
        )

        try:
            thread_id, _created = await self._ensure_thread_id(ctx, client, config["timeout"])
            prompt = ctx.input.to_text() or "continue"
            image_urls = self._extract_image_urls(ctx)
            payload = self._build_payload(
                config=config,
                thread_id=thread_id,
                prompt=prompt,
                image_urls=image_urls,
            )

            if self._should_stream(ctx):
                async for result in self._stream_run(ctx, client, config, thread_id, payload):
                    yield result
            else:
                message = await self._complete_run(client, config, thread_id, payload)
                yield RunnerResult.message_completed(ctx.run_id, message)

            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.thread_id",
                thread_id,
                scope="conversation",
            )
            yield RunnerResult.run_completed(ctx.run_id)
        except DeerFlowAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
                retryable=getattr(e, "retryable", False),
            )
            return
        except Exception as e:
            logger.exception(f"DeerFlow runner unexpected error: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"DeerFlow runner error: {e}",
                code="deerflow.unexpected_error",
            )
            return

    async def _stream_run(
        self,
        ctx: RunnerContext,
        client: AsyncDeerFlowClient,
        config: dict[str, typing.Any],
        thread_id: str,
        payload: dict[str, typing.Any],
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        state = _StreamState()
        prev_text = ""

        try:
            async for event in client.stream_run(
                thread_id=thread_id,
                payload=payload,
                timeout=config["timeout"],
            ):
                event_type = event.get("event")
                data = event.get("data")

                if event_type == "values":
                    new_full = self._handle_values_event(data, state)
                    if new_full and new_full != prev_text:
                        changed_text = new_full[len(prev_text) :] if new_full.startswith(prev_text) else new_full
                        prev_text = new_full
                        if changed_text:
                            yield RunnerResult.message_delta(
                                ctx.run_id,
                                MessageChunk(role="assistant", content=new_full, is_final=False),
                            )
                    continue

                if event_type in {"messages-tuple", "messages", "message"}:
                    delta = self._handle_message_event(data, state)
                    if delta:
                        prev_text = state.latest_text
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(role="assistant", content=prev_text, is_final=False),
                        )
                    continue

                if event_type == "custom":
                    state.task_failures.extend(stream_utils.extract_task_failures_from_custom_event(data))
                    continue

                if event_type == "error":
                    raise DeerFlowAPIError(f"DeerFlow stream error event: {data}", code="deerflow.api_error")

                if event_type == "end":
                    break
        except TimeoutError:
            logger.warning(f"DeerFlow stream timed out after {config['timeout']}s for thread_id={thread_id}")
            raise DeerFlowAPIError(
                f"DeerFlow stream timed out after {config['timeout']}s",
                code="deerflow.timeout",
                retryable=True,
            ) from None

        final_text = self._build_final_text(state)
        yield RunnerResult.message_delta(
            ctx.run_id,
            MessageChunk(role="assistant", content=final_text, is_final=True),
        )

    async def _complete_run(
        self,
        client: AsyncDeerFlowClient,
        config: dict[str, typing.Any],
        thread_id: str,
        payload: dict[str, typing.Any],
    ) -> Message:
        state = _StreamState()

        try:
            async for event in client.stream_run(
                thread_id=thread_id,
                payload=payload,
                timeout=config["timeout"],
            ):
                event_type = event.get("event")
                data = event.get("data")

                if event_type == "values":
                    self._handle_values_event(data, state)
                    continue

                if event_type in {"messages-tuple", "messages", "message"}:
                    self._handle_message_event(data, state)
                    continue

                if event_type == "custom":
                    state.task_failures.extend(stream_utils.extract_task_failures_from_custom_event(data))
                    continue

                if event_type == "error":
                    raise DeerFlowAPIError(f"DeerFlow stream error event: {data}", code="deerflow.api_error")

                if event_type == "end":
                    break
        except TimeoutError:
            logger.warning(f"DeerFlow stream timed out after {config['timeout']}s for thread_id={thread_id}")
            raise DeerFlowAPIError(
                f"DeerFlow stream timed out after {config['timeout']}s",
                code="deerflow.timeout",
                retryable=True,
            ) from None

        final_text = self._build_final_text(state)
        return Message(role="assistant", content=final_text)
