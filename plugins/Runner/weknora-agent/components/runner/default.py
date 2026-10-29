"""WeKnora Agent default runner implementation.

Ported from LangBot's legacy weknora-api provider runner and adapted to
Runner protocol v1.
"""

from __future__ import annotations

import json
import logging
import typing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import FunctionCall, Message, MessageChunk, ToolCall
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from pkg.errors import WeKnoraAPIError, WeKnoraConfigError
from pkg.scoped_identity import scoped_identity
from pkg.weknora_client import AsyncWeKnoraClient

logger = logging.getLogger(__name__)


class DefaultRunner(Runner):
    """Real Runner for WeKnora API.

    Configuration is read from ctx.config using the legacy weknora-api field names
    so host-side migration can map old pipeline configs directly.

    Runtime state:
    - external.session_id: WeKnora session id for the current LangBot conversation.
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        config = ctx.config or {}

        app_type = config.get("app-type", "agent")
        valid_app_types = ["chat", "agent"]
        if app_type not in valid_app_types:
            raise WeKnoraConfigError(
                f"Invalid app-type: {app_type}. Must be one of {valid_app_types}",
                code="weknora.config_invalid",
            )

        api_key = str(config.get("api-key", "")).strip()
        if not api_key:
            raise WeKnoraConfigError("api-key is required", code="weknora.config_invalid")

        base_url = str(config.get("base-url", "")).strip()
        if not base_url:
            raise WeKnoraConfigError("base-url is required", code="weknora.config_invalid")

        knowledge_base_ids = config.get("knowledge-base-ids", [])
        if knowledge_base_ids is None:
            knowledge_base_ids = []
        if not isinstance(knowledge_base_ids, list):
            raise WeKnoraConfigError("knowledge-base-ids must be a list", code="weknora.config_invalid")

        if any(not isinstance(item, str) or not item.strip() for item in knowledge_base_ids):
            raise WeKnoraConfigError("knowledge-base-ids must contain nonblank strings", code="weknora.config_invalid")
        default_agent = "builtin-quick-answer" if app_type == "chat" else "builtin-smart-reasoning"
        agent_id = config.get("agent-id", default_agent)
        if agent_id is not None and not isinstance(agent_id, str):
            raise WeKnoraConfigError("agent-id must be a string or null", code="weknora.config_invalid")

        return {
            "base_url": base_url,
            "api_key": api_key,
            "app_type": app_type,
            "agent_id": agent_id,
            "knowledge_base_ids": list(knowledge_base_ids),
            "web_search_enabled": bool(config.get("web-search-enabled", False)),
            "timeout": float(config.get("timeout", 120)),
            "base_prompt": str(config.get("base-prompt", "")),
        }

    def _get_user_tag(self, ctx: RunnerContext) -> str:
        actor = ctx.actor
        if actor and actor.actor_id:
            return scoped_identity(self, ctx, f"{actor.actor_type}_{actor.actor_id}")
        raise WeKnoraConfigError(
            "vendor user identity requires a trusted Host actor identity",
            code="weknora.identity_unavailable",
        )

    def _get_input_text(self, ctx: RunnerContext, base_prompt: str) -> str:
        text = ctx.input.to_text()
        return text if text else base_prompt

    def _should_stream(self, ctx: RunnerContext) -> bool:
        configured = (ctx.config or {}).get("streaming")
        if configured is not None:
            return bool(configured)
        return bool(ctx.delivery.supports_streaming or ctx.runtime.metadata.get("streaming_supported", False))

    async def _ensure_session_id(
        self,
        ctx: RunnerContext,
        client: AsyncWeKnoraClient,
        timeout: float,
        user_tag: str,
    ) -> tuple[str, bool]:
        session_id = ctx.state.conversation.get("external.session_id")
        if session_id:
            return str(session_id), False

        session_id = await client.create_session(
            title=f"IM Chat - {user_tag}",
            timeout=min(30, timeout),
        )
        return session_id, True

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the WeKnora app."""
        try:
            user_tag = self._get_user_tag(ctx)  # Validate identity before constructing any upstream client.
            config = self._validate_config(ctx)
        except WeKnoraConfigError as e:
            yield RunnerResult.run_failed(ctx.run_id, error=e.message, code=e.code)
            return

        client = AsyncWeKnoraClient(
            api_key=config["api_key"],
            base_url=config["base_url"],
        )

        try:
            session_id, _created = await self._ensure_session_id(ctx, client, config["timeout"], user_tag)
            input_text = self._get_input_text(ctx, config["base_prompt"])

            if config["app_type"] == "agent":
                results = self._run_runner_chat(ctx, client, config, session_id, input_text, user_tag)
            else:
                results = self._run_knowledge_chat(ctx, client, config, session_id, input_text, user_tag)

            async for result in results:
                yield result

            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.session_id",
                session_id,
                scope="conversation",
            )
            yield RunnerResult.run_completed(ctx.run_id)
        except WeKnoraAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
                retryable=getattr(e, "retryable", False),
            )
            return
        except Exception as e:
            logger.exception(f"WeKnora runner unexpected error: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"WeKnora runner error: {e}",
                code="weknora.unexpected_error",
            )
            return

    async def _run_runner_chat(
        self,
        ctx: RunnerContext,
        client: AsyncWeKnoraClient,
        config: dict[str, typing.Any],
        session_id: str,
        input_text: str,
        user_tag: str,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        pending_answer = ""
        message_count = 0
        is_final = False
        saw_chunk = False
        should_stream = self._should_stream(ctx)

        async for chunk in client.agent_chat(
            session_id=session_id,
            query=input_text,
            user=user_tag,
            agent_id=config["agent_id"],
            knowledge_base_ids=config["knowledge_base_ids"],
            web_search_enabled=config["web_search_enabled"],
            timeout=config["timeout"],
        ):
            saw_chunk = True
            logger.debug(f"WeKnora agent chunk: {chunk}")

            response_type = chunk.get("response_type", "")
            content = chunk.get("content", "")
            done = bool(chunk.get("done", False))

            if response_type == "tool_call":
                tool_data = chunk.get("data", {})
                tool_name = tool_data.get("tool_name", "") if isinstance(tool_data, dict) else ""
                if tool_name:
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(
                            role="assistant",
                            tool_calls=[
                                ToolCall(
                                    id=str(chunk.get("id", "")),
                                    type="function",
                                    function=FunctionCall(
                                        name=str(tool_name),
                                        arguments=json.dumps(tool_data.get("arguments", {})),
                                    ),
                                )
                            ],
                        ),
                    )
                continue

            if response_type == "answer":
                message_count += 1
                if content:
                    if len(pending_answer) + len(str(content)) > 1024 * 1024:
                        raise WeKnoraAPIError("WeKnora response exceeds the runtime limit")
                    pending_answer += str(content)
                if done:
                    is_final = True
                if should_stream and pending_answer and (message_count % 8 == 0 or is_final):
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(role="assistant", content=pending_answer, is_final=is_final),
                    )
                continue

            if response_type == "error":
                raise WeKnoraAPIError(f"WeKnora service error: {content}", code="weknora.api_error")

        if not saw_chunk:
            raise WeKnoraAPIError("WeKnora API returned no response", code="weknora.empty_response")

        if not pending_answer:
            raise WeKnoraAPIError("WeKnora API returned an empty answer", code="weknora.empty_response")

        if pending_answer and (not should_stream or not is_final):
            if should_stream:
                yield RunnerResult.message_delta(
                    ctx.run_id,
                    MessageChunk(role="assistant", content=pending_answer, is_final=True),
                )
            else:
                yield RunnerResult.message_completed(
                    ctx.run_id,
                    Message(role="assistant", content=pending_answer),
                )

    async def _run_knowledge_chat(
        self,
        ctx: RunnerContext,
        client: AsyncWeKnoraClient,
        config: dict[str, typing.Any],
        session_id: str,
        input_text: str,
        user_tag: str,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        pending_answer = ""
        message_count = 0
        is_final = False
        saw_chunk = False
        should_stream = self._should_stream(ctx)

        async for chunk in client.knowledge_chat(
            session_id=session_id,
            query=input_text,
            user=user_tag,
            agent_id=config["agent_id"],
            knowledge_base_ids=config["knowledge_base_ids"],
            timeout=config["timeout"],
        ):
            saw_chunk = True
            logger.debug(f"WeKnora chat chunk: {chunk}")

            response_type = chunk.get("response_type", "")
            content = chunk.get("content", "")
            done = bool(chunk.get("done", False))

            if response_type == "answer":
                message_count += 1
                if content:
                    if len(pending_answer) + len(str(content)) > 1024 * 1024:
                        raise WeKnoraAPIError("WeKnora response exceeds the runtime limit")
                    pending_answer += str(content)
                if done:
                    is_final = True
                if should_stream and pending_answer and (message_count % 8 == 0 or is_final):
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(role="assistant", content=pending_answer, is_final=is_final),
                    )
                continue

            if response_type == "error":
                raise WeKnoraAPIError(f"WeKnora service error: {content}", code="weknora.api_error")

        if not saw_chunk:
            raise WeKnoraAPIError("WeKnora API returned no response", code="weknora.empty_response")

        if not pending_answer:
            raise WeKnoraAPIError("WeKnora API returned an empty answer", code="weknora.empty_response")

        if pending_answer and (not should_stream or not is_final):
            if should_stream:
                yield RunnerResult.message_delta(
                    ctx.run_id,
                    MessageChunk(role="assistant", content=pending_answer, is_final=True),
                )
            else:
                yield RunnerResult.message_completed(
                    ctx.run_id,
                    Message(role="assistant", content=pending_answer),
                )
