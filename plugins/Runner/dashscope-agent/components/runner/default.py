"""DashScope Agent default runner implementation.

Real Aliyun DashScope (百炼) API integration supporting agent and workflow app types.
"""

from __future__ import annotations

import logging
import typing
from contextlib import aclosing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from pkg.asset_gateway import register_assets
from pkg.dashscope_client import (
    DashScopeAPIError,
    DashScopeClient,
    DashScopeConfigError,
    extract_references_from_chunk,
    replace_references,
)
from pkg.reasoning import ResponseBudget, ThinkingFilter, positive_timeout, strict_bool

logger = logging.getLogger(__name__)

# Thinking block markers (special Unicode characters used by DashScope)
THINK_START = "႑"
THINK_END = "႐"

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
    """Real Runner for DashScope (阿里云百炼) API.

    Supports two app types:
    - agent: Agent with thinking/reasoning capability
    - workflow: Workflow execution with message format streaming

    Configuration (static, from ctx.config):
    - app-type: Application type (agent/workflow)
    - api-key: DashScope API key
    - app-id: DashScope application ID
    - references_quote: Prefix for reference text (default: "参考资料来自:")

    Runtime state (from ctx.state):
    - external.conversation_id: DashScope session_id for stateful sessions
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Validate and return static configuration.

        Raises DashScopeConfigError on missing required fields.
        """
        config = ctx.config or {}
        try:
            remove_think = strict_bool(config, "remove-think")
            timeout = positive_timeout(config)
        except ValueError as exc:
            raise DashScopeConfigError(str(exc), code="dashscope.config_invalid") from None

        app_type = config.get("app-type", "agent")
        valid_types = ["agent", "workflow"]
        if app_type not in valid_types:
            raise DashScopeConfigError(
                f"Invalid app-type: {app_type}. Must be one of {valid_types}",
                code="dashscope.config_invalid",
            )

        api_key = config.get("api-key", "")
        if not api_key:
            raise DashScopeConfigError("api-key is required", code="dashscope.config_invalid")

        app_id = config.get("app-id", "")
        if not app_id:
            raise DashScopeConfigError("app-id is required", code="dashscope.config_invalid")

        return {
            "app_type": app_type,
            "api_key": api_key,
            "app_id": app_id,
            "references_quote": config.get("references_quote", "参考资料来自:"),
            "timeout": timeout,
            "remove_think": remove_think,
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

        The token is injected into DashScope ``biz_params`` so the 百炼 app can
        reference it and pass it as the ``run_token`` argument on LangBot Asset
        Gateway MCP tool calls. The registration must be stopped when the run ends.
        """
        return await register_assets(self, self.get_run_api(ctx), ctx, config)

    def _get_session_id(self, ctx: RunnerContext) -> str:
        """Get session ID from state for multi-turn conversation.

        Priority:
        1. ctx.state.conversation["external.conversation_id"]
        2. Empty string (start new session)
        """
        external_conv_id = ctx.state.conversation.get("external.conversation_id")
        if external_conv_id:
            return external_conv_id
        return ""

    def _get_input_text(self, ctx: RunnerContext) -> str:
        """Get text input from context."""
        return ctx.input.to_text()

    def _get_biz_params(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Get business parameters for workflow from adapter params."""
        return _get_adapter_params(ctx)

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the DashScope agent.

        Streams RunnerResult.message_delta chunks and final run_completed.
        """
        try:
            config = self._validate_config(ctx)
        except DashScopeConfigError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return

        client = DashScopeClient(
            api_key=config["api_key"],
            app_id=config["app_id"],
            app_type=config["app_type"],
            references_quote=config["references_quote"],
            timeout=config["timeout"],
        )

        input_text = self._get_input_text(ctx)
        session_id = self._get_session_id(ctx)
        app_type = config["app_type"]

        # Optionally register a run-scoped LangBot asset token and pass it to the
        # 百炼 app through biz_params. The app references it (e.g. ${biz_params.X})
        # and passes it as the run_token argument on LangBot Asset Gateway MCP
        # tool calls. The token is stopped in finally when the run ends.
        asset_registration = None
        asset_biz_params: dict[str, typing.Any] = {}
        if config["langbot_assets_enabled"]:
            asset_registration = await self._create_asset_gateway_registration(ctx, config)
            asset_biz_params[config["asset_gateway_input_name"]] = asset_registration.token

        try:
            run = self._run_workflow if app_type == "workflow" else self._run_runner
            # Own every delegated generator through downstream backpressure/close.
            async with aclosing(run(ctx, client, input_text, session_id, asset_biz_params)) as results:
                async for result in results:
                    yield result
        except DashScopeAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
                retryable=getattr(e, "retryable", False),
            )
            return
        except Exception as e:
            logger.exception(f"DashScope runner unexpected error: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"DashScope runner error: {e}",
                code="dashscope.unexpected_error",
            )
            return
        finally:
            if asset_registration is not None:
                await asset_registration.stop()

    async def _run_runner(
        self,
        ctx: RunnerContext,
        client: DashScopeClient,
        input_text: str,
        session_id: str,
        extra_biz_params: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run agent mode.

        Streams message_delta chunks with thinking content support.
        """
        budget = ResponseBudget(DashScopeAPIError, "dashscope.response_limit")
        pending_content = ""
        remove_think = strict_bool(ctx.config, "remove-think")
        text_filter = ThinkingFilter(remove_think, ((THINK_START, THINK_END),))
        saw_output = False
        last_final = False
        references_dict: dict[str, str] = {}
        final_session_id = session_id

        think_start = False
        think_end = False
        usage: dict[str, typing.Any] | None = None
        has_response = False

        # Match native request flags as well as filtering provider output.
        enable_thinking = not remove_think

        async with aclosing(
            client.iter_agent(
                prompt=input_text,
                session_id=session_id,
                enable_thinking=enable_thinking,
                biz_params=extra_biz_params or None,
            )
        ) as chunks:
            async for chunk in chunks:
                if not chunk:
                    continue
                # Check for API errors
                status_code = chunk.get("status_code")
                if status_code != 200:
                    raise DashScopeAPIError(
                        f"DashScope API error: status_code={status_code} "
                        f"message={chunk.get('message')} request_id={chunk.get('request_id')}",
                        code="dashscope.api_error",
                    )

                if not chunk:
                    continue

                stream_output = chunk.get("output", {})
                usage = _usage_from_payload(chunk, stream_output) or usage

                # Track session_id for stateful session
                if stream_output.get("session_id"):
                    final_session_id = stream_output["session_id"]

                # Handle thinking/reasoning content
                stream_think = stream_output.get("thoughts") or []
                budget.add(stream_output.get("text", ""), *(item.get("thought", "") for item in stream_think))
                if stream_think and stream_think[0].get("thought"):
                    saw_output = True
                if not remove_think and stream_think and stream_think[0].get("thought"):
                    if not think_start:
                        think_start = True
                        pending_content += f"{THINK_START}\n{stream_think[0].get('thought')}"
                    else:
                        # Continue outputting reasoning_content
                        pending_content += stream_think[0].get("thought")
                elif think_start and (not stream_think or stream_think[0].get("thought") == "") and not think_end:
                    think_end = True
                    pending_content += f"\n{THINK_END}\n"

                # Handle text content
                if stream_output.get("text"):
                    saw_output = True
                    pending_content += text_filter.feed(stream_output["text"])

                # Check if this is the final chunk
                finish_reason = stream_output.get("finish_reason")
                is_final = finish_reason != "null" if finish_reason else False
                if is_final:
                    pending_content += text_filter.feed("", final=True)

                # Extract and accumulate references
                chunk_refs = extract_references_from_chunk(stream_output)
                references_dict.update(chunk_refs)

                # Replace references in content
                if references_dict:
                    pending_content = replace_references(
                        pending_content,
                        references_dict,
                        client.references_quote,
                    )

                budget.check_rendered(pending_content)

                # Yield periodically or on final chunk
                if pending_content or (is_final and saw_output):
                    has_response = True
                    last_final = is_final
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(
                            role="assistant",
                            content=pending_content,
                            is_final=is_final,
                        ),
                    )
                    if is_final:
                        pending_content = ""

        # Providers may omit finish_reason; emit a final snapshot at EOF,
        # including an empty snapshot when only hidden reasoning was received.
        tail = text_filter.feed("", final=True)
        pending_content += tail
        budget.check_rendered(pending_content)
        if saw_output and (not last_final or tail):
            has_response = True
            yield RunnerResult.message_delta(
                ctx.run_id, MessageChunk(role="assistant", content=pending_content, is_final=True)
            )

        if not has_response:
            raise DashScopeAPIError(
                "DashScope API returned no response",
                code="dashscope.empty_response",
            )

        # Update state with session_id for next run
        if final_session_id:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.conversation_id",
                final_session_id,
                scope="conversation",
            )

        yield RunnerResult.run_completed(ctx.run_id, usage=usage)

    async def _run_workflow(
        self,
        ctx: RunnerContext,
        client: DashScopeClient,
        input_text: str,
        session_id: str,
        extra_biz_params: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run workflow mode.

        Streams message_delta chunks from workflow message format output.
        """
        budget = ResponseBudget(DashScopeAPIError, "dashscope.response_limit")
        pending_content = ""
        remove_think = strict_bool(ctx.config, "remove-think")
        text_filter = ThinkingFilter(remove_think, ((THINK_START, THINK_END),))
        saw_output = False
        last_final = False
        references_dict: dict[str, str] = {}
        final_session_id = session_id
        usage: dict[str, typing.Any] | None = None
        has_response = False

        # Get business parameters from context, merging the LangBot asset token.
        biz_params = self._get_biz_params(ctx)
        if extra_biz_params:
            biz_params = {**biz_params, **extra_biz_params}

        async with aclosing(
            client.iter_workflow(
                prompt=input_text,
                session_id=session_id,
                biz_params=biz_params,
            )
        ) as chunks:
            async for chunk in chunks:
                if not chunk:
                    continue
                # Check for API errors
                status_code = chunk.get("status_code")
                if status_code != 200:
                    raise DashScopeAPIError(
                        f"DashScope API error: status_code={status_code} "
                        f"message={chunk.get('message')} request_id={chunk.get('request_id')}",
                        code="dashscope.api_error",
                    )

                if not chunk:
                    continue

                stream_output = chunk.get("output", {})
                usage = _usage_from_payload(chunk, stream_output) or usage

                # Track session_id for stateful session
                if stream_output.get("session_id"):
                    final_session_id = stream_output["session_id"]

                # Handle workflow message format output
                workflow_message = stream_output.get("workflow_message")
                if workflow_message is not None:
                    content = (workflow_message.get("message") or {}).get("content", "")
                else:
                    # Native non-streaming workflows use output.text. Do not add
                    # both representations when a provider includes both.
                    content = stream_output.get("text", "")
                if content:
                    budget.add(content)
                    saw_output = True
                    pending_content += text_filter.feed(content)

                # Check if this is the final chunk
                finish_reason = stream_output.get("finish_reason")
                is_final = finish_reason != "null" if finish_reason else False
                if is_final:
                    pending_content += text_filter.feed("", final=True)

                # Extract and accumulate references
                chunk_refs = extract_references_from_chunk(stream_output)
                references_dict.update(chunk_refs)

                # Replace references in content
                if references_dict:
                    pending_content = replace_references(
                        pending_content,
                        references_dict,
                        client.references_quote,
                    )

                budget.check_rendered(pending_content)

                # Yield periodically or on final chunk
                if pending_content or (is_final and saw_output):
                    has_response = True
                    last_final = is_final
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(
                            role="assistant",
                            content=pending_content,
                            is_final=is_final,
                        ),
                    )
                    if is_final:
                        pending_content = ""

        # Providers may omit finish_reason; emit a final snapshot at EOF,
        # including an empty snapshot when only hidden reasoning was received.
        tail = text_filter.feed("", final=True)
        pending_content += tail
        budget.check_rendered(pending_content)
        if saw_output and (not last_final or tail):
            has_response = True
            yield RunnerResult.message_delta(
                ctx.run_id, MessageChunk(role="assistant", content=pending_content, is_final=True)
            )

        if not has_response:
            raise DashScopeAPIError(
                "DashScope workflow returned no response",
                code="dashscope.empty_response",
            )

        # Update state with session_id for next run
        if final_session_id:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.conversation_id",
                final_session_id,
                scope="conversation",
            )

        yield RunnerResult.run_completed(ctx.run_id, usage=usage)
