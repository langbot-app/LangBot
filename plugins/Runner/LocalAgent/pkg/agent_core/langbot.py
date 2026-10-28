"""LangBot Host adapters used by the local-agent loop."""

from __future__ import annotations

import json
import logging
import re
import typing

from langbot_plugin.api.entities.builtin.provider.message import ContentElement, Message, MessageChunk
from langbot_plugin.api.entities.builtin.resource.tool import LLMTool
from langbot_plugin.api.proxies.runner import PermissionDeniedError, RunnerAPIProxy

from pkg.config import DEFAULT_MAX_TOOL_RESULT_CHARS
from pkg.context_pipeline import (
    ContextBudget,
    ContextCompactor,
    ContextSummarizer,
    ContextTokenCounter,
    ContextUsageAnchor,
    usage_total_tokens,
)
from pkg.messages import build_user_message
from pkg.model_calling import (
    ModelCallError,
    StreamingModelCaller,
    build_tool_call_message,
    build_tool_reference_message,
    extract_tool_result_references,
    invoke_with_fallback_result,
    is_deadline_exceeded_error,
    model_call_error_from_exception,
    normalize_llm_call_result,
    serialize_tool_result_content,
)

from .types import (
    AgentLoopHooks,
    ModelTurnEvent,
    ModelTurnResult,
    NonRetryableToolError,
    PreparedToolCall,
    ToolCallRequest,
    ToolExecutionOutcome,
)

THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
logger = logging.getLogger(__name__)


def _strip_thinking_blocks(content: str) -> str:
    return THINK_BLOCK_RE.sub("", content).lstrip()


def build_assistant_message(content: str, tool_calls: list[ToolCallRequest]) -> Message:
    """Build an assistant message that preserves provider tool call IDs."""
    return Message(
        role="assistant",
        content=_strip_thinking_blocks(content) if tool_calls else content,
        tool_calls=[tool_call.to_tool_call() for tool_call in tool_calls] if tool_calls else None,
    )


def _context_message_for_tool_follow_up(message: Message, tool_calls: list[ToolCallRequest]) -> Message:
    if not tool_calls or not isinstance(message.content, str):
        return message

    copied = message.model_copy(deep=True)
    copied.content = _strip_thinking_blocks(message.content)
    return copied


def _prefix_chunk_content(chunk: MessageChunk, prefix: str) -> MessageChunk:
    if not prefix:
        return chunk

    copied = chunk.model_copy(deep=True)
    if isinstance(copied.content, str):
        copied.content = prefix + copied.content
    elif isinstance(copied.content, list):
        for content in copied.content:
            if content.type == "text" and isinstance(content.text, str):
                content.text = prefix + content.text
                break
    return copied


class LangBotModelAdapter:
    """Model invocation adapter that keeps all model access behind Host APIs."""

    def __init__(
        self, api: RunnerAPIProxy, *, remove_think: bool = False, reasoning_levels: dict[str, str] | None = None
    ):
        self.api = api
        self.remove_think = remove_think
        self.reasoning_levels = dict(reasoning_levels or {})

    async def stream_turn(
        self,
        *,
        model_ids: list[str],
        messages: list[Message],
        tools: list[LLMTool],
        visible_prefix: str = "",
    ) -> typing.AsyncGenerator[ModelTurnEvent, None]:
        caller = StreamingModelCaller(
            api=self.api,
            model_ids=model_ids,
            messages=messages,
            tools=tools,
            remove_think=self.remove_think,
            reasoning_levels=self.reasoning_levels,
        )

        from contextlib import aclosing

        last_display = None
        async with aclosing(caller.stream()) as stream:
            async for chunk, _is_delta in stream:
                display = (chunk.content, (chunk.provider_specific_fields or {}).get("reasoning_content"))
                if display != last_display and (chunk.content or display[1]):
                    last_display = display
                    yield ModelTurnEvent.message_delta(_prefix_chunk_content(chunk, visible_prefix))

        tool_calls = [ToolCallRequest.from_raw(tool_call) for tool_call in caller.get_tool_calls()]
        content = caller.get_accumulated_content()
        message = build_assistant_message(content, tool_calls)
        message.provider_specific_fields = caller.get_provider_specific_fields()
        yield ModelTurnEvent.message_end(
            ModelTurnResult(
                message=message,
                tool_calls=tool_calls,
                committed_model_id=caller.get_committed_model_id(),
                visible_content=content,
                usage=caller.get_usage(),
            )
        )

    async def invoke_turn(
        self,
        *,
        model_ids: list[str],
        messages: list[Message],
        tools: list[LLMTool],
    ) -> ModelTurnResult:
        call_result, committed_model_id = await invoke_with_fallback_result(
            api=self.api,
            model_ids=model_ids,
            messages=messages,
            tools=tools,
            remove_think=self.remove_think,
            reasoning_levels=self.reasoning_levels,
        )
        response = call_result.message
        tool_calls = [ToolCallRequest.from_raw(tool_call) for tool_call in response.tool_calls or []]
        return ModelTurnResult(
            message=_context_message_for_tool_follow_up(response, tool_calls),
            tool_calls=tool_calls,
            committed_model_id=committed_model_id,
            visible_content=response.content if isinstance(response.content, str) else "",
            usage=call_result.usage,
        )

    async def invoke_committed_turn(
        self,
        *,
        committed_model_id: str,
        messages: list[Message],
        tools: list[LLMTool],
    ) -> ModelTurnResult:
        try:
            invoke = getattr(self.api, "invoke_llm_with_usage", None)
            if not callable(invoke):
                invoke = self.api.invoke_llm
            raw_response = await invoke(
                llm_model_uuid=committed_model_id,
                messages=messages,
                funcs=tools,
                remove_think=self.remove_think,
                reasoning_level=self.reasoning_levels.get(committed_model_id, "provider_default"),
            )
        except Exception as e:
            if is_deadline_exceeded_error(e):
                raise model_call_error_from_exception(e, prefix="LLM call in tool loop failed") from e
            raise ModelCallError(f"LLM call in tool loop failed: {e}", retryable=True) from e

        call_result = normalize_llm_call_result(raw_response)
        response = call_result.message
        usage = call_result.usage
        tool_calls = [ToolCallRequest.from_raw(tool_call) for tool_call in response.tool_calls or []]
        return ModelTurnResult(
            message=_context_message_for_tool_follow_up(response, tool_calls),
            tool_calls=tool_calls,
            committed_model_id=committed_model_id,
            visible_content=response.content if isinstance(response.content, str) else "",
            usage=usage,
        )


class LangBotToolExecutor:
    """Tool preflight, execution, and model-result adaptation."""

    def __init__(
        self,
        api: RunnerAPIProxy,
        allowed_tools: set[str],
        max_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS,
    ):
        self.api = api
        self.allowed_tools = allowed_tools
        self.max_result_chars = max_result_chars
        self.local_tools = {}

    def prepare(self, request: ToolCallRequest) -> PreparedToolCall:
        parameters: dict[str, typing.Any] = {}
        if request.arguments:
            try:
                parsed = json.loads(request.arguments)
                if isinstance(parsed, dict):
                    parameters = parsed
                else:
                    return PreparedToolCall(
                        request=request,
                        parameters={},
                        error=f"Invalid JSON arguments for tool '{request.name}': expected object",
                    )
            except json.JSONDecodeError as e:
                return PreparedToolCall(
                    request=request,
                    parameters={},
                    error=f"Invalid JSON arguments for tool '{request.name}': {e}",
                )

        if request.name not in self.allowed_tools:
            return PreparedToolCall(
                request=request,
                parameters=parameters,
                error=f"Tool '{request.name}' is not authorized. Allowed tools: {list(self.allowed_tools)}",
            )

        return PreparedToolCall(request=request, parameters=parameters)

    async def execute(self, prepared: PreparedToolCall) -> ToolExecutionOutcome:
        if prepared.error is not None:
            return self.finalize(prepared, result=None, error=prepared.error)

        try:
            if prepared.request.name in self.local_tools:
                result = await self.local_tools[prepared.request.name](**prepared.parameters)
                return self.finalize(prepared, result=result, error=None)
            result = await self.api.call_tool(
                tool_name=prepared.request.name,
                parameters=prepared.parameters,
            )
            return self.finalize(prepared, result=result, error=None)
        except NonRetryableToolError:
            raise
        except PermissionDeniedError as e:
            return self.finalize(prepared, result=None, error=str(e))
        except Exception as e:
            if is_deadline_exceeded_error(e):
                raise
            return self.finalize(prepared, result=None, error=f"Tool execution failed: {e}")

    def finalize(
        self,
        prepared: PreparedToolCall,
        *,
        result: typing.Any,
        error: str | None,
    ) -> ToolExecutionOutcome:
        event_result: typing.Any = None
        terminate = error is None and _tool_result_terminates(result)
        model_result = _strip_tool_runtime_hints(result) if error is None else result
        if error is None:
            references = extract_tool_result_references(model_result)
            if references["file_refs"]:
                message, event_result = build_tool_reference_message(
                    prepared.request.id,
                    result=model_result,
                    references=references,
                    max_result_chars=self.max_result_chars,
                )
                return ToolExecutionOutcome(
                    request=prepared.request,
                    parameters=prepared.parameters,
                    result=result,
                    event_result=event_result,
                    error=None,
                    message=message,
                    terminate=terminate,
                )

            content = serialize_tool_result_content(model_result, is_error=False)
            if len(content) > self.max_result_chars:
                preview = content[: self.max_result_chars]
                message = build_tool_call_message(
                    prepared.request.id,
                    prepared.request.name,
                    model_result,
                    is_error=False,
                    max_result_chars=self.max_result_chars,
                )
                event_result = {
                    "type": "langbot_tool_result_preview",
                    "truncated": True,
                    "reason": "tool_result_truncated",
                    "original_chars": len(content),
                    "original_bytes": len(content.encode("utf-8")),
                    "kept_preview_chars": len(preview),
                    "preview": preview,
                }
                return ToolExecutionOutcome(
                    request=prepared.request,
                    parameters=prepared.parameters,
                    result=result,
                    event_result=event_result,
                    error=None,
                    message=message,
                    terminate=terminate,
                )

        message = build_tool_call_message(
            prepared.request.id,
            prepared.request.name,
            error if error is not None else model_result,
            is_error=error is not None,
            max_result_chars=self.max_result_chars,
        )
        return ToolExecutionOutcome(
            request=prepared.request,
            parameters=prepared.parameters,
            result=result,
            event_result=event_result,
            error=error,
            message=message,
            terminate=terminate,
        )


class LangBotContextHooks(AgentLoopHooks):
    """LangBot-specific loop hooks for Pi-style per-turn context management."""

    def __init__(
        self,
        budget: ContextBudget,
        summarizer: ContextSummarizer | None = None,
        token_counter: ContextTokenCounter | None = None,
        steering_puller: "LangBotSteeringPuller | None" = None,
    ):
        self.budget = budget
        self.summarizer = summarizer
        self.token_counter = token_counter
        self.steering_puller = steering_puller
        self._usage_anchor: ContextUsageAnchor | None = None

    async def prepare_model_turn(self, messages: list[Message]) -> list[Message]:
        usage_anchor = self._usage_anchor
        self._usage_anchor = None
        assembly = await ContextCompactor(
            self.budget,
            summarizer=self.summarizer,
            usage_anchor=usage_anchor,
            token_counter=self.token_counter,
        ).compact_messages_async(messages)
        return assembly.messages

    async def should_stop_after_turn(self, result: ModelTurnResult, messages: list[Message]) -> bool:
        return False

    async def after_model_turn(self, result: ModelTurnResult, messages: list[Message]) -> list[Message]:
        next_messages = [message.model_copy(deep=True) for message in messages]
        if result.tool_calls:
            return next_messages
        steering_messages = await self._pull_steering_messages(mode="all")
        if steering_messages:
            next_messages.extend(steering_messages)
            self._usage_anchor = self._usage_anchor_from_result(result, len(messages))
        return next_messages

    async def prepare_next_turn(
        self,
        messages: list[Message],
        result: ModelTurnResult,
        tool_results: list[Message],
    ) -> list[Message]:
        next_messages = [message.model_copy(deep=True) for message in messages]
        usage_anchor = self._usage_anchor_from_result(result, max(0, len(messages) - len(tool_results)))
        next_messages.extend(await self._pull_steering_messages(mode="all"))
        assembly = await ContextCompactor(
            self.budget,
            summarizer=self.summarizer,
            usage_anchor=usage_anchor,
            token_counter=self.token_counter,
        ).compact_messages_async(next_messages)
        self._usage_anchor = None
        return assembly.messages

    async def recover_context_overflow(self, messages: list[Message], error: Exception) -> list[Message] | None:
        is_overflow = error.is_context_overflow if isinstance(error, ModelCallError) else False
        if not is_overflow or not self.budget.enabled:
            return None

        assembly = await ContextCompactor(
            self._overflow_retry_budget(),
            summarizer=self.summarizer,
            token_counter=self.token_counter,
        ).compact_messages_async(messages)
        if not assembly.compacted or assembly.tokens_after >= assembly.tokens_before:
            return None
        return assembly.messages

    def _overflow_retry_budget(self) -> ContextBudget:
        retry_input_tokens = max(1, (self.budget.input_tokens * 3) // 4)
        return ContextBudget(
            window_tokens=retry_input_tokens,
            reserve_tokens=0,
            keep_recent_tokens=min(self.budget.keep_recent_tokens, max(1, retry_input_tokens // 2)),
            summary_tokens=min(self.budget.summary_tokens, max(0, retry_input_tokens // 4)),
            history_fetch_limit=self.budget.history_fetch_limit,
        )

    async def _pull_steering_messages(self, *, mode: str) -> list[Message]:
        if self.steering_puller is None:
            return []
        return await self.steering_puller.pull_messages(mode=mode)

    def _usage_anchor_from_result(self, result: ModelTurnResult, message_count: int) -> ContextUsageAnchor | None:
        total_tokens = usage_total_tokens(result.usage)
        if total_tokens is None:
            return None
        return ContextUsageAnchor(
            message_count=message_count,
            total_tokens=total_tokens,
            model_id=result.committed_model_id,
        )


class LangBotSteeringPuller:
    """Pull and adapt Host-claimed steering inputs into user messages."""

    def __init__(self, api: RunnerAPIProxy):
        self.api = api

    async def pull_messages(self, *, mode: str = "all") -> list[Message]:
        steering_pull = getattr(self.api, "steering_pull", None)
        if not callable(steering_pull):
            return []

        try:
            response = await steering_pull(mode=mode)
        except PermissionDeniedError:
            return []
        except Exception:
            logger.debug("Failed to pull steering inputs", exc_info=True)
            return []

        items = _model_or_mapping_get(response, "items", [])
        if not isinstance(items, list):
            return []

        messages: list[Message] = []
        for item in items:
            message = self._message_from_item(item)
            if message is not None:
                messages.append(message)
        return messages

    def _message_from_item(self, item: typing.Any) -> Message | None:
        if not isinstance(item, dict) and not hasattr(item, "input"):
            return None

        input_data = _model_or_mapping_get(item, "input")
        if not isinstance(input_data, dict) and not hasattr(input_data, "text"):
            return None

        text = _model_or_mapping_get(input_data, "text")
        contents = self._content_elements(_model_or_mapping_get(input_data, "contents"))
        attachments = _model_or_mapping_get(input_data, "attachments")
        return build_user_message(
            user_text=text if isinstance(text, str) else "",
            input_contents=contents,
            input_attachments=attachments if isinstance(attachments, list) else [],
        )

    def _content_elements(self, raw_contents: typing.Any) -> list[ContentElement]:
        if not isinstance(raw_contents, list):
            return []

        contents: list[ContentElement] = []
        for raw_content in raw_contents:
            try:
                if isinstance(raw_content, ContentElement):
                    contents.append(raw_content.model_copy(deep=True))
                elif isinstance(raw_content, dict):
                    contents.append(ContentElement.model_validate(raw_content))
            except Exception:
                logger.debug("Ignoring invalid steering content element", exc_info=True)
        return contents


def _model_or_mapping_get(value: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _tool_result_terminates(result: typing.Any) -> bool:
    return isinstance(result, dict) and result.get("terminate") is True


def _strip_tool_runtime_hints(result: typing.Any) -> typing.Any:
    if not isinstance(result, dict) or "terminate" not in result:
        return result
    stripped = dict(result)
    stripped.pop("terminate", None)
    return stripped
