"""Context assembly, budgeting, and deterministic compaction for local-agent."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import typing
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

from langbot_plugin.api.entities.builtin.provider.message import ContentElement, Message
from langbot_plugin.api.entities.builtin.runner import RunnerContext

from pkg.config import get_knowledge_base_ids, get_rerank_config, get_retrieval_top_k
from pkg.messages import (
    build_event_context_message,
    build_platform_tools_system_message,
    build_prompt_messages,
    build_rag_context_message,
    build_skills_system_message,
    build_user_message,
    get_effective_prompt_config,
)
from pkg.rag import RagChunk, format_rag_chunks, retrieve_rag_chunks

DEFAULT_HISTORY_FETCH_LIMIT = 50
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000
DEFAULT_CONTEXT_RESERVE_TOKENS = 16_384
DEFAULT_CONTEXT_KEEP_RECENT_TOKENS = 20_000
DEFAULT_CONTEXT_SUMMARY_TOKENS = 8_000
RAG_CONTEXT_MAX_INPUT_FRACTION = 4

ESTIMATED_ATTACHMENT_CHARS = 4800
ESTIMATED_ATTACHMENT_TOKENS = 1600
ESTIMATED_CHARS_PER_TOKEN = 4
SUMMARY_REFERENCE_LIMIT = 40
SUMMARY_OPEN_TAG = "<conversation_summary>"
SUMMARY_CLOSE_TAG = "</conversation_summary>"
SUMMARY_SCHEMA_VERSION = "langbot.conversation_summary.v1"
CHECKPOINT_STATE_KEY = "runner.compaction.checkpoint"
CHECKPOINT_SCHEMA_VERSION = "langbot.local_agent.compaction_checkpoint.v1"
SUMMARY_ENTRY_RE = re.compile(r"^\s*\d+\.\s+([A-Za-z_][A-Za-z0-9_-]*):\s?(.*)$", re.DOTALL)
SUMMARY_COUNT_RE = re.compile(r"\bcount=(\d+)\b")
CRITICAL_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_./:-])"
    r"(?:[A-Za-z][A-Za-z0-9]*[_.:/-]){2,}[A-Za-z0-9][A-Za-z0-9_.:/-]*"
)
CRITICAL_REF_GUIDANCE = (
    "Instruction: exact opaque values from omitted messages; when asked for a remembered "
    "passcode, secret, sentinel, or identifier, reply with the full matching value verbatim."
)
SUMMARIZATION_SYSTEM_PROMPT = """You are a context summarization assistant. Your task is to read a conversation between a user and an AI assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary."""
SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages."""
UPDATE_SUMMARIZATION_PROMPT = """The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. RULES:
- PRESERVE all existing information from the previous summary
- ADD new progress, decisions, and context from the new messages
- UPDATE the Progress section: move items from "In Progress" to "Done" when completed
- UPDATE "Next Steps" based on what was accomplished
- PRESERVE exact file paths, function names, and error messages
- If something is no longer relevant, you may remove it

Use this EXACT format:

## Goal
[Preserve existing goals, add new ones if the task expanded]

## Constraints & Preferences
- [Preserve existing, add new ones discovered]

## Progress
### Done
- [x] [Include previously done items AND newly completed items]

### In Progress
- [ ] [Current work - update based on progress]

### Blocked
- [Current blockers - remove if resolved]

## Key Decisions
- **[Decision]**: [Brief rationale] (preserve all previous, add new)

## Next Steps
1. [Update based on current state]

## Critical Context
- [Preserve important context, add new if needed]

Keep each section concise. Preserve exact file paths, function names, and error messages."""

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContextBudget:
    """Token-style context budget resolved from runner config and Host metadata."""

    window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    reserve_tokens: int = DEFAULT_CONTEXT_RESERVE_TOKENS
    keep_recent_tokens: int = DEFAULT_CONTEXT_KEEP_RECENT_TOKENS
    summary_tokens: int = DEFAULT_CONTEXT_SUMMARY_TOKENS
    history_fetch_limit: int = DEFAULT_HISTORY_FETCH_LIMIT

    @classmethod
    def from_context(cls, ctx: RunnerContext) -> "ContextBudget":
        config = ctx.config if isinstance(ctx.config, dict) else {}
        runtime = getattr(ctx, "runtime", None)
        metadata = getattr(runtime, "metadata", {}) if runtime is not None else {}
        if not isinstance(metadata, dict):
            metadata = {}

        host_window_tokens = _runtime_context_window_tokens(metadata)
        host_max_output_tokens = _runtime_max_output_tokens(metadata)
        config_window_tokens = _config_token_value(
            config,
            "context-window-tokens",
            DEFAULT_CONTEXT_WINDOW_TOKENS,
            minimum=0,
        )
        window_tokens = config_window_tokens
        if host_window_tokens is not None:
            window_tokens = min(host_window_tokens, config_window_tokens)

        return cls.from_config(
            config,
            window_tokens=window_tokens,
            max_output_tokens=host_max_output_tokens,
        )

    @classmethod
    def from_config(
        cls,
        config: dict[str, typing.Any],
        *,
        window_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> "ContextBudget":
        resolved_window_tokens = (
            window_tokens
            if window_tokens is not None
            else _config_token_value(
                config,
                "context-window-tokens",
                DEFAULT_CONTEXT_WINDOW_TOKENS,
                minimum=0,
            )
        )
        reserve_tokens = _clamp_reserve_tokens(
            resolved_window_tokens,
            _config_token_value(
                config,
                "context-reserve-tokens",
                DEFAULT_CONTEXT_RESERVE_TOKENS,
                minimum=0,
            ),
        )
        summary_tokens = _config_token_value(
            config,
            "context-summary-tokens",
            DEFAULT_CONTEXT_SUMMARY_TOKENS,
            minimum=0,
        )
        if max_output_tokens is not None and max_output_tokens > 0:
            summary_tokens = min(summary_tokens, max_output_tokens, max(1, (reserve_tokens * 4) // 5))

        return cls(
            window_tokens=resolved_window_tokens,
            reserve_tokens=reserve_tokens,
            keep_recent_tokens=_config_token_value(
                config,
                "context-keep-recent-tokens",
                DEFAULT_CONTEXT_KEEP_RECENT_TOKENS,
                minimum=0,
            ),
            summary_tokens=summary_tokens,
            history_fetch_limit=_config_int(
                config,
                "context-history-fetch-limit",
                DEFAULT_HISTORY_FETCH_LIMIT,
                minimum=1,
            ),
        )

    @property
    def enabled(self) -> bool:
        return self.window_tokens > 0

    @property
    def input_tokens(self) -> int:
        if not self.enabled:
            return 0
        return max(self.window_tokens - self.reserve_tokens, 1)


@dataclass(frozen=True)
class ContextAssembly:
    """Final model context plus compaction diagnostics."""

    messages: list[Message]
    compacted: bool
    tokens_before: int
    tokens_after: int
    summary_message: Message | None = None
    frame: "ContextFrame | None" = None
    diagnostics: "ContextDiagnostics | None" = None


@dataclass(frozen=True)
class ContextFrame:
    """Structured model context before provider rendering."""

    prompt: list[Message] = field(default_factory=list)
    summaries: list[Message] = field(default_factory=list)
    history: list[Message] = field(default_factory=list)
    rag: list[Message] = field(default_factory=list)
    current: list[Message] = field(default_factory=list)
    rag_chunks: list[RagChunk] = field(default_factory=list)

    def to_messages(self) -> list[Message]:
        return self.prompt + self.summaries + self.history + self.rag + self.current


@dataclass(frozen=True)
class ContextDiagnostics:
    """Token diagnostics for the rendered context."""

    tokens_before: int
    tokens_after: int
    prompt_tokens: int
    summary_tokens: int
    history_tokens: int
    rag_tokens: int
    current_tokens: int
    compacted_message_count: int = 0


@dataclass(frozen=True)
class ContextUsageAnchor:
    """Provider-reported token usage for an already-rendered message prefix."""

    message_count: int
    total_tokens: int
    model_id: str | None = None


class ContextTokenCounter(typing.Protocol):
    async def count(self, messages: list[Message]) -> int:
        """Return provider/tokenizer token count for this model request."""


class ContextTokenCounterRequiredError(RuntimeError):
    """Raised when runtime compaction cannot access Host token counting."""


@dataclass(frozen=True)
class ConversationSummaryEntry:
    index: int
    role: str
    text: str


@dataclass(frozen=True)
class ConversationSummary:
    schema_version: str
    message_count: int
    entries: list[ConversationSummaryEntry]

    def render(self, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""

        lines = [
            SUMMARY_OPEN_TAG,
            f"v={self.schema_version.rsplit('.', 1)[-1]} count={self.message_count}",
        ]

        for entry in self.entries:
            prefix = f"{entry.index}. {entry.role}: "
            prefix_tokens = estimate_text_tokens(_close_summary_lines(lines + [prefix]))
            if prefix_tokens > max_tokens:
                break
            text = _truncate_text_to_tokens(entry.text, max_tokens - prefix_tokens)
            candidate = lines + [prefix + text]
            if estimate_text_tokens(_close_summary_lines(candidate)) > max_tokens:
                break
            lines = candidate

        rendered = _close_summary_lines(lines)
        if estimate_text_tokens(rendered) <= max_tokens:
            return rendered
        return _truncate_text_to_tokens(rendered, max_tokens)


@dataclass(frozen=True)
class CompactionCheckpoint:
    summary: str
    covers_until: str | None
    tokens_before: int | None = None
    created_at: int | None = None


class ContextSummarizer(typing.Protocol):
    async def summarize(self, messages: list[Message], max_tokens: int) -> str | None:
        """Return a model-facing summary message body or None to use deterministic fallback."""


class LLMContextSummarizer:
    """Generate Pi-style structured summaries through LangBot Host model APIs."""

    def __init__(
        self,
        api: typing.Any,
        model_id: str,
        *,
        remove_think: bool = False,
        reasoning_level: str = "provider_default",
    ):
        self.api = api
        self.model_id = model_id
        self.remove_think = remove_think
        self.reasoning_level = reasoning_level

    async def summarize(self, messages: list[Message], max_tokens: int) -> str | None:
        if not messages or max_tokens <= 0:
            return None

        previous_summary = _extract_previous_summary_text(messages)
        current_messages = [message for message in messages if not _is_conversation_summary_message(message)]
        if not current_messages:
            return None

        prompt = _build_llm_summary_prompt(current_messages, previous_summary=previous_summary)
        try:
            response = await self.api.invoke_llm(
                llm_model_uuid=self.model_id,
                messages=[
                    Message(role="system", content=SUMMARIZATION_SYSTEM_PROMPT),
                    Message(role="user", content=prompt),
                ],
                funcs=[],
                remove_think=self.remove_think,
                reasoning_level=self.reasoning_level,
            )
        except Exception:
            logger.warning("LLM context summarization failed; using deterministic fallback", exc_info=True)
            return None

        summary_text = _message_content_text(response).strip()
        if not summary_text:
            logger.warning("LLM context summarization returned empty content; using deterministic fallback")
            return None
        return _wrap_llm_summary(summary_text, max_tokens, message_count=len(messages))


class HostContextTokenCounter:
    """Count model input tokens through the run-scoped Host API."""

    def __init__(
        self,
        api: typing.Any,
        model_id: str,
        tools: list[typing.Any] | None = None,
        *,
        reasoning_level: str = "provider_default",
    ):
        self.api = api
        self.model_id = model_id
        self.tools = tools or []
        self.reasoning_level = reasoning_level
        self._counts: dict[tuple[str, str, bytes], int] = {}

    async def count(self, messages: list[Message]) -> int:
        count_tokens = getattr(self.api, "count_tokens", None)
        if not callable(count_tokens):
            raise ContextTokenCounterRequiredError(
                "Host count_tokens API is required for local-agent context budgeting"
            )
        payload = json.dumps([message.model_dump(mode="json") for message in messages], sort_keys=True)
        key = (self.model_id, self.reasoning_level, hashlib.sha256(payload.encode()).digest())
        if key in self._counts:
            return self._counts[key]
        tokens = await count_tokens(
            llm_model_uuid=self.model_id,
            messages=messages,
            funcs=[],
            reasoning_level=self.reasoning_level,
        )
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise ContextTokenCounterRequiredError(f"Host count_tokens returned invalid token count: {tokens!r}")
        # This counter belongs to one run; retain only a bounded set of input digests.
        if len(self._counts) >= 32:
            self._counts.pop(next(iter(self._counts)))
        self._counts[key] = tokens
        return tokens


class ContextAssembler:
    """Build the model-facing context for one Runner run."""

    def __init__(
        self,
        api: typing.Any,
        ctx: RunnerContext,
        budget: ContextBudget | None = None,
        summarizer: ContextSummarizer | None = None,
        token_counter: ContextTokenCounter | None = None,
    ):
        self.api = api
        self.ctx = ctx
        self.budget = budget or ContextBudget.from_context(ctx)
        self.summarizer = summarizer
        self.token_counter = token_counter

    async def assemble(self) -> ContextAssembly:
        user_text = self.ctx.input.to_text()
        rag_chunks = await self._retrieve_rag_chunks(user_text)
        rag_message = build_rag_context_message(format_rag_chunks(rag_chunks))
        checkpoint = await self._load_compaction_checkpoint()
        history_messages, history_cursors = await self._get_history_messages(checkpoint)

        prompt_messages = build_prompt_messages(await self._get_prompt_config())
        system_instructions = []
        if self.ctx.config.get("date-grounding", True) is not False:
            # Runtime clock, not the event timestamp: replayed events may be old.
            # UTC is explicit so a separate plugin process cannot imply Host/user time.
            date_guidance = (
                f"Current date: {datetime.now(timezone.utc).strftime('%Y-%m-%d (%A)')} UTC. "
                'Resolve relative time references (e.g. "today", "this quarter", "latest", '
                '"currently") based on this date, not your training cutoff. For anything '
                "time-sensitive that may have changed since training — stock prices, "
                "financial results, news, current events, exchange rates, or similar — "
                "verify with a search tool if one is available rather than answering from memory."
            )
            system_instructions.append(date_guidance)
        skills_message = build_skills_system_message(self.ctx)
        if skills_message is not None:
            system_instructions.append(skills_message.content)
        platform_tools_message = build_platform_tools_system_message(self.ctx)
        if platform_tools_message is not None:
            system_instructions.append(platform_tools_message.content)
        if system_instructions:
            # Strict chat templates only accept a system message at position zero.
            guidance = "\n\n".join(system_instructions)
            if prompt_messages and prompt_messages[0].role == "system":
                head = prompt_messages[0]
                if isinstance(head.content, str):
                    head.content += "\n\n" + guidance
                else:
                    head.content.append(ContentElement.from_text(guidance))
            else:
                prompt_messages.insert(0, Message(role="system", content=guidance))
        checkpoint_messages = self._checkpoint_messages(checkpoint)
        checkpoint_cursors = [checkpoint.covers_until for _ in checkpoint_messages] if checkpoint else []
        rag_messages = [rag_message] if rag_message is not None else []
        current_messages = []
        event_message = build_event_context_message(self.ctx)
        if event_message is not None:
            current_messages.append(event_message)
        user_message = build_user_message(
            user_text=user_text,
            input_contents=self.ctx.input.contents,
            input_attachments=self.ctx.input.attachments,
        )
        if user_message is not None:
            current_messages.append(user_message)

        assembly = await ContextCompactor(
            self.budget,
            summarizer=self.summarizer,
            token_counter=self.token_counter,
        ).compact_async(
            prompt_messages=prompt_messages,
            history_messages=checkpoint_messages + history_messages,
            rag_messages=rag_messages,
            current_messages=current_messages,
            rag_chunks=rag_chunks,
        )
        await self._store_compaction_checkpoint(
            assembly,
            checkpoint=checkpoint,
            compaction_cursors=checkpoint_cursors + history_cursors,
        )
        return assembly

    async def _get_prompt_config(self) -> list[dict[str, typing.Any]]:
        available_apis = getattr(getattr(self.ctx, "context", None), "available_apis", None)
        prompt_get = getattr(available_apis, "prompt_get", None)
        if bool(prompt_get) or (prompt_get is None and hasattr(self.api, "get_prompt")):
            try:
                prompt = await self.api.get_prompt()
                if isinstance(prompt, list):
                    # An empty effective prompt is an intentional Host override.
                    return prompt
            except Exception:
                logger.debug("Host prompt_get failed; falling back to static prompt", exc_info=True)
        return get_effective_prompt_config(self.ctx)

    async def _retrieve_rag_chunks(self, user_text: str) -> list[RagChunk]:
        allowed_kb_ids = set(kb.kb_id for kb in self.api.get_allowed_knowledge_bases())
        # TODO(agentic-rag): when AgenticRAG disables naive retrieval, Host should
        # pass no configured KBs here, or expose an explicit retrieval mode that
        # tells this runner to skip automatic RAG and rely on the query tool.
        kb_ids = get_knowledge_base_ids(self.ctx.config, allowed_kb_ids)
        if not kb_ids or not user_text:
            return []

        rerank_model_id, rerank_top_k = get_rerank_config(self.ctx.config)
        return await retrieve_rag_chunks(
            api=self.api,
            kb_ids=kb_ids,
            query_text=user_text,
            top_k=get_retrieval_top_k(self.ctx.config),
            rerank_model_id=rerank_model_id,
            rerank_top_k=rerank_top_k,
        )

    async def _get_history_messages(
        self,
        checkpoint: CompactionCheckpoint | None = None,
    ) -> tuple[list[Message], list[str | None]]:
        context = self.ctx.context
        if not context.available_apis.history_page or not context.conversation_id:
            return [], []

        direction = "forward" if checkpoint and checkpoint.covers_until else "backward"
        messages: list[Message] = []
        cursors: list[str | None] = []

        after_cursor = checkpoint.covers_until if direction == "forward" and checkpoint else None
        seen_page_cursors = {after_cursor} if after_cursor is not None else set()
        while True:
            kwargs: dict[str, typing.Any] = {
                "conversation_id": context.conversation_id,
                "limit": self.budget.history_fetch_limit,
                "direction": direction,
            }
            if direction == "forward":
                kwargs["after_cursor"] = after_cursor

            try:
                page = await self.api.history_page(**kwargs)
            except Exception:
                if checkpoint is not None:
                    logger.warning(
                        "Compaction checkpoint history cursor failed; falling back to recent tail", exc_info=True
                    )
                    return await self._get_history_messages(None)
                raise

            raw_items = list(_model_or_mapping_get(page, "items", []))
            iterable = raw_items if direction == "forward" else list(reversed(raw_items))
            for raw_item in iterable:
                item = _as_mapping(raw_item)
                if item is None:
                    continue
                message = _message_from_transcript_item(item, self.ctx.event.event_id)
                if message is not None:
                    messages.append(message)
                    cursor = item.get("cursor") or item.get("seq")
                    cursors.append(str(cursor) if cursor is not None else None)

            if direction != "forward" or not bool(_model_or_mapping_get(page, "has_more", False)):
                break

            raw_next_cursor = _model_or_mapping_get(page, "next_cursor")
            next_cursor = str(raw_next_cursor) if raw_next_cursor is not None else None
            if not next_cursor or next_cursor in seen_page_cursors:
                logger.warning("Compaction checkpoint history pagination stopped due to invalid next_cursor")
                break
            seen_page_cursors.add(next_cursor)
            after_cursor = next_cursor

        return messages, cursors

    def _state_api_available(self) -> bool:
        available_apis = getattr(getattr(self.ctx, "context", None), "available_apis", None)
        return (
            bool(getattr(available_apis, "state", False))
            and hasattr(self.api, "state_get")
            and hasattr(self.api, "state_set")
        )

    async def _load_compaction_checkpoint(self) -> CompactionCheckpoint | None:
        if not self._state_api_available():
            return None

        try:
            response = await self.api.state_get("conversation", CHECKPOINT_STATE_KEY)
        except Exception:
            logger.debug("Failed to read compaction checkpoint state", exc_info=True)
            return None

        value = response.get("value") if isinstance(response, dict) else None
        if not isinstance(value, dict):
            return None
        if value.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
            return None

        conversation_id = getattr(getattr(self.ctx, "context", None), "conversation_id", None)
        stored_conversation_id = value.get("conversation_id")
        if stored_conversation_id and conversation_id and stored_conversation_id != conversation_id:
            return None

        summary = value.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            return None

        covers_until = value.get("covers_until")
        return CompactionCheckpoint(
            summary=summary,
            covers_until=str(covers_until) if covers_until is not None else None,
            tokens_before=value.get("tokens_before") if isinstance(value.get("tokens_before"), int) else None,
            created_at=value.get("created_at") if isinstance(value.get("created_at"), int) else None,
        )

    def _checkpoint_messages(self, checkpoint: CompactionCheckpoint | None) -> list[Message]:
        if checkpoint is None or not checkpoint.summary:
            return []
        return [Message(role="system", content=checkpoint.summary)]

    async def _store_compaction_checkpoint(
        self,
        assembly: ContextAssembly,
        *,
        checkpoint: CompactionCheckpoint | None,
        compaction_cursors: list[str | None],
    ) -> None:
        if not self._state_api_available() or not assembly.compacted or assembly.summary_message is None:
            return

        compacted_count = assembly.diagnostics.compacted_message_count if assembly.diagnostics else 0
        covered_cursor = _last_non_empty(compaction_cursors[:compacted_count])
        if covered_cursor is None and checkpoint is not None:
            covered_cursor = checkpoint.covers_until
        if covered_cursor is None:
            return

        summary = _message_content_text(assembly.summary_message).strip()
        if not summary:
            return

        payload = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "summary": summary,
            "covers_until": covered_cursor,
            "tokens_before": assembly.tokens_before,
            "created_at": int(time.time()),
            "conversation_id": getattr(getattr(self.ctx, "context", None), "conversation_id", None),
        }

        try:
            await self.api.state_set("conversation", CHECKPOINT_STATE_KEY, payload)
        except Exception:
            logger.debug("Failed to write compaction checkpoint state", exc_info=True)


class ContextCompactor:
    """Compact old history into a summary message while keeping recent context."""

    def __init__(
        self,
        budget: ContextBudget,
        summarizer: ContextSummarizer | None = None,
        usage_anchor: ContextUsageAnchor | None = None,
        token_counter: ContextTokenCounter | None = None,
    ):
        self.budget = budget
        self.summarizer = summarizer
        self.usage_anchor = usage_anchor
        self.token_counter = token_counter

    def compact_messages(self, messages: list[Message]) -> ContextAssembly:
        """Compact an already-assembled runtime message list.

        Initial assembly knows prompt/history/current boundaries. Follow-up turns
        only have the loop's flat model context, so preserve leading prompt-like
        messages plus the current turn tail, and compact older runtime messages
        between them.
        """
        messages = sanitize_provider_messages(messages)
        prompt_messages, existing_summaries, runtime_messages = _split_leading_prompt_messages(messages)
        history_messages, current_messages = _split_runtime_history_and_current(runtime_messages)
        return self.compact(
            prompt_messages=prompt_messages,
            history_messages=existing_summaries + history_messages,
            current_messages=current_messages,
        )

    async def compact_messages_async(self, messages: list[Message]) -> ContextAssembly:
        self._require_token_counter()
        messages = sanitize_provider_messages(messages)
        prompt_messages, existing_summaries, runtime_messages = _split_leading_prompt_messages(messages)
        history_messages, current_messages = _split_runtime_history_and_current(runtime_messages)
        return await self.compact_async(
            prompt_messages=prompt_messages,
            history_messages=existing_summaries + history_messages,
            current_messages=current_messages,
        )

    def compact(
        self,
        *,
        prompt_messages: list[Message],
        history_messages: list[Message],
        current_messages: list[Message],
        rag_messages: list[Message] | None = None,
        rag_chunks: list[RagChunk] | None = None,
    ) -> ContextAssembly:
        prompt = sanitize_provider_messages(prompt_messages)
        prompt, prompt_summaries = _partition_summary_messages(prompt)
        history = sanitize_provider_messages(prompt_summaries + history_messages)
        rag = sanitize_provider_messages(rag_messages or [])
        current = sanitize_provider_messages(current_messages)
        original_messages = prompt + history + rag + current
        tokens_before = estimate_messages_tokens_with_anchor(original_messages, self.usage_anchor)

        if not self.budget.enabled or tokens_before <= self.budget.input_tokens:
            return self._build_assembly(
                prompt=prompt,
                summaries=[],
                history=history,
                rag=rag,
                current=current,
                rag_chunks=rag_chunks or [],
                compacted=False,
                tokens_before=tokens_before,
                compacted_message_count=0,
            )

        rag = self._fit_rag_before_history_budget(prompt=prompt, history=history, rag=rag, current=current)
        history_budget = max(self.budget.input_tokens - estimate_messages_tokens(prompt + rag + current), 0)
        if not history:
            return self._build_assembly(
                prompt=prompt,
                summaries=[],
                history=[],
                rag=rag,
                current=current,
                rag_chunks=rag_chunks or [],
                compacted=False,
                tokens_before=tokens_before,
                compacted_message_count=0,
            )
        if history_budget <= 0:
            summary_message = self._build_summary_message(history, self.budget.summary_tokens)
            return self._build_assembly(
                prompt=prompt,
                summaries=[summary_message] if summary_message is not None else [],
                history=[],
                rag=rag,
                current=current,
                rag_chunks=rag_chunks or [],
                compacted=True,
                tokens_before=tokens_before,
                summary_message=summary_message,
                compacted_message_count=len(history),
            )

        summary_budget = self._summary_budget(history_budget)
        recent_budget = max(history_budget - summary_budget, 0)
        first_kept_index = self._select_first_kept_index(history, recent_budget)

        omitted = history[:first_kept_index]
        recent = history[first_kept_index:]
        summary_message = self._build_summary_message(omitted, summary_budget)
        return self._build_assembly(
            prompt=prompt,
            summaries=[summary_message] if summary_message is not None else [],
            history=recent,
            rag=rag,
            current=current,
            rag_chunks=rag_chunks or [],
            compacted=bool(omitted),
            tokens_before=tokens_before,
            summary_message=summary_message,
            compacted_message_count=len(omitted),
        )

    async def compact_async(
        self,
        *,
        prompt_messages: list[Message],
        history_messages: list[Message],
        current_messages: list[Message],
        rag_messages: list[Message] | None = None,
        rag_chunks: list[RagChunk] | None = None,
    ) -> ContextAssembly:
        self._require_token_counter()
        prompt = sanitize_provider_messages(prompt_messages)
        prompt, prompt_summaries = _partition_summary_messages(prompt)
        history = sanitize_provider_messages(prompt_summaries + history_messages)
        rag = sanitize_provider_messages(rag_messages or [])
        current = sanitize_provider_messages(current_messages)
        original_messages = prompt + history + rag + current
        tokens_before = await self._count_messages_async(original_messages, allow_usage_anchor=True)

        if not self.budget.enabled or tokens_before <= self.budget.input_tokens:
            return await self._build_assembly_async(
                prompt=prompt,
                summaries=[],
                history=history,
                rag=rag,
                current=current,
                rag_chunks=rag_chunks or [],
                compacted=False,
                tokens_before=tokens_before,
                compacted_message_count=0,
            )

        rag = await self._fit_rag_before_history_budget_async(prompt=prompt, history=history, rag=rag, current=current)
        history_budget = max(self.budget.input_tokens - await self._count_messages_async(prompt + rag + current), 0)
        if not history:
            return await self._build_assembly_async(
                prompt=prompt,
                summaries=[],
                history=[],
                rag=rag,
                current=current,
                rag_chunks=rag_chunks or [],
                compacted=False,
                tokens_before=tokens_before,
                compacted_message_count=0,
            )
        if history_budget <= 0:
            summary_message = await self._build_summary_message_async(history, self.budget.summary_tokens)
            return await self._build_assembly_async(
                prompt=prompt,
                summaries=[summary_message] if summary_message is not None else [],
                history=[],
                rag=rag,
                current=current,
                rag_chunks=rag_chunks or [],
                compacted=True,
                tokens_before=tokens_before,
                summary_message=summary_message,
                compacted_message_count=len(history),
            )

        summary_budget = self._summary_budget(history_budget)
        recent_budget = max(history_budget - summary_budget, 0)
        first_kept_index = await self._select_first_kept_index_async(history, recent_budget)

        omitted = history[:first_kept_index]
        recent = history[first_kept_index:]
        summary_message = await self._build_summary_message_async(omitted, summary_budget)
        return await self._build_assembly_async(
            prompt=prompt,
            summaries=[summary_message] if summary_message is not None else [],
            history=recent,
            rag=rag,
            current=current,
            rag_chunks=rag_chunks or [],
            compacted=bool(omitted),
            tokens_before=tokens_before,
            summary_message=summary_message,
            compacted_message_count=len(omitted),
        )

    def _build_assembly(
        self,
        *,
        prompt: list[Message],
        summaries: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
        rag_chunks: list[RagChunk],
        compacted: bool,
        tokens_before: int,
        summary_message: Message | None = None,
        compacted_message_count: int,
    ) -> ContextAssembly:
        prompt, summaries, history, rag, current = self._fit_frame_to_budget(
            prompt=prompt,
            summaries=summaries,
            history=history,
            rag=rag,
            current=current,
        )
        frame = ContextFrame(
            prompt=_copy_messages(prompt),
            summaries=_copy_messages(summaries),
            history=_copy_messages(history),
            rag=_copy_messages(rag),
            current=_copy_messages(current),
            rag_chunks=list(rag_chunks),
        )
        messages = sanitize_provider_messages(frame.to_messages())
        tokens_after = estimate_messages_tokens(messages)
        diagnostics = ContextDiagnostics(
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            prompt_tokens=estimate_messages_tokens(frame.prompt),
            summary_tokens=estimate_messages_tokens(frame.summaries),
            history_tokens=estimate_messages_tokens(frame.history),
            rag_tokens=estimate_messages_tokens(frame.rag),
            current_tokens=estimate_messages_tokens(frame.current),
            compacted_message_count=compacted_message_count,
        )

        return ContextAssembly(
            messages=messages,
            compacted=compacted,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            summary_message=summary_message,
            frame=frame,
            diagnostics=diagnostics,
        )

    async def _build_assembly_async(
        self,
        *,
        prompt: list[Message],
        summaries: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
        rag_chunks: list[RagChunk],
        compacted: bool,
        tokens_before: int,
        summary_message: Message | None = None,
        compacted_message_count: int,
    ) -> ContextAssembly:
        prompt, summaries, history, rag, current = await self._fit_frame_to_budget_async(
            prompt=prompt,
            summaries=summaries,
            history=history,
            rag=rag,
            current=current,
        )
        frame = ContextFrame(
            prompt=_copy_messages(prompt),
            summaries=_copy_messages(summaries),
            history=_copy_messages(history),
            rag=_copy_messages(rag),
            current=_copy_messages(current),
            rag_chunks=list(rag_chunks),
        )
        messages = sanitize_provider_messages(frame.to_messages())
        tokens_after = await self._count_messages_async(messages)
        diagnostics = ContextDiagnostics(
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            prompt_tokens=await self._count_messages_async(frame.prompt),
            summary_tokens=await self._count_messages_async(frame.summaries),
            history_tokens=await self._count_messages_async(frame.history),
            rag_tokens=await self._count_messages_async(frame.rag),
            current_tokens=await self._count_messages_async(frame.current),
            compacted_message_count=compacted_message_count,
        )

        return ContextAssembly(
            messages=messages,
            compacted=compacted,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            summary_message=summary_message,
            frame=frame,
            diagnostics=diagnostics,
        )

    def _fit_rag_before_history_budget(
        self,
        *,
        prompt: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
    ) -> list[Message]:
        if not self.budget.enabled or not rag:
            return rag

        available_after_fixed = self.budget.input_tokens - estimate_messages_tokens(prompt + current)
        if available_after_fixed <= 0:
            return []

        if not history:
            return _fit_messages_to_budget(rag, available_after_fixed, keep_tail=False)

        history_reserve = min(self.budget.keep_recent_tokens, max(1, available_after_fixed // 2))
        rag_budget = max(available_after_fixed - history_reserve, 0)
        rag_budget = min(rag_budget, max(1, self.budget.input_tokens // RAG_CONTEXT_MAX_INPUT_FRACTION))
        return _fit_messages_to_budget(rag, rag_budget, keep_tail=False)

    async def _fit_rag_before_history_budget_async(
        self,
        *,
        prompt: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
    ) -> list[Message]:
        if not self.budget.enabled or not rag:
            return rag

        available_after_fixed = self.budget.input_tokens - await self._count_messages_async(prompt + current)
        if available_after_fixed <= 0:
            return []

        if not history:
            return await self._fit_messages_to_budget_async(rag, available_after_fixed, keep_tail=False)

        history_reserve = min(self.budget.keep_recent_tokens, max(1, available_after_fixed // 2))
        rag_budget = max(available_after_fixed - history_reserve, 0)
        rag_budget = min(rag_budget, max(1, self.budget.input_tokens // RAG_CONTEXT_MAX_INPUT_FRACTION))
        return await self._fit_messages_to_budget_async(rag, rag_budget, keep_tail=False)

    def _fit_frame_to_budget(
        self,
        *,
        prompt: list[Message],
        summaries: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
    ) -> tuple[list[Message], list[Message], list[Message], list[Message], list[Message]]:
        if not self.budget.enabled:
            return prompt, summaries, history, rag, current

        input_budget = self.budget.input_tokens
        if estimate_messages_tokens(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        rag = _fit_messages_to_budget(
            rag,
            input_budget - estimate_messages_tokens(prompt + summaries + history + current),
            keep_tail=False,
        )
        if estimate_messages_tokens(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        summaries = _fit_messages_to_budget(
            summaries,
            input_budget - estimate_messages_tokens(prompt + history + rag + current),
            keep_tail=False,
        )
        if estimate_messages_tokens(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        history = _fit_messages_to_budget(
            history,
            input_budget - estimate_messages_tokens(prompt + summaries + rag + current),
            keep_tail=True,
        )
        if estimate_messages_tokens(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        prompt = _fit_messages_to_budget(
            prompt,
            input_budget - estimate_messages_tokens(summaries + history + rag + current),
            keep_tail=True,
        )
        if estimate_messages_tokens(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        prompt, summaries, history, rag, current = self._preserve_current_with_sync_budget(
            prompt=prompt,
            summaries=summaries,
            history=history,
            rag=rag,
            current=current,
            input_budget=input_budget,
        )
        if estimate_messages_tokens(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        current = _fit_messages_to_budget(
            current,
            input_budget - estimate_messages_tokens(prompt + summaries + history + rag),
            keep_tail=True,
        )
        return prompt, summaries, history, rag, current

    async def _fit_frame_to_budget_async(
        self,
        *,
        prompt: list[Message],
        summaries: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
    ) -> tuple[list[Message], list[Message], list[Message], list[Message], list[Message]]:
        if not self.budget.enabled:
            return prompt, summaries, history, rag, current

        input_budget = self.budget.input_tokens
        if await self._count_messages_async(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        rag = await self._fit_messages_to_budget_async(
            rag,
            input_budget - await self._count_messages_async(prompt + summaries + history + current),
            keep_tail=False,
        )
        if await self._count_messages_async(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        summaries = await self._fit_messages_to_budget_async(
            summaries,
            input_budget - await self._count_messages_async(prompt + history + rag + current),
            keep_tail=False,
        )
        if await self._count_messages_async(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        history = await self._fit_messages_to_budget_async(
            history,
            input_budget - await self._count_messages_async(prompt + summaries + rag + current),
            keep_tail=True,
        )
        if await self._count_messages_async(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        prompt = await self._fit_messages_to_budget_async(
            prompt,
            input_budget - await self._count_messages_async(summaries + history + rag + current),
            keep_tail=True,
        )
        if await self._count_messages_async(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        prompt, summaries, history, rag, current = await self._preserve_current_with_async_budget(
            prompt=prompt,
            summaries=summaries,
            history=history,
            rag=rag,
            current=current,
            input_budget=input_budget,
        )
        if await self._count_messages_async(prompt + summaries + history + rag + current) <= input_budget:
            return prompt, summaries, history, rag, current

        current = await self._fit_messages_to_budget_async(
            current,
            input_budget - await self._count_messages_async(prompt + summaries + history + rag),
            keep_tail=True,
        )
        return prompt, summaries, history, rag, current

    def _preserve_current_with_sync_budget(
        self,
        *,
        prompt: list[Message],
        summaries: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
        input_budget: int,
    ) -> tuple[list[Message], list[Message], list[Message], list[Message], list[Message]]:
        if not current or input_budget <= 0:
            return prompt, summaries, history, rag, current

        current = _fit_messages_to_budget(current, input_budget, keep_tail=True)
        if not current:
            return [], [], [], [], []

        fixed_current_tokens = estimate_messages_tokens(current)
        remaining = max(input_budget - fixed_current_tokens, 0)
        if remaining <= 0:
            return [], [], [], [], current

        prompt = _fit_messages_to_budget(prompt, remaining, keep_tail=True)
        remaining = max(remaining - estimate_messages_tokens(prompt), 0)
        summaries = _fit_messages_to_budget(summaries, remaining, keep_tail=False)
        remaining = max(remaining - estimate_messages_tokens(summaries), 0)
        history = _fit_messages_to_budget(history, remaining, keep_tail=True)
        remaining = max(remaining - estimate_messages_tokens(history), 0)
        rag = _fit_messages_to_budget(rag, remaining, keep_tail=False)
        return prompt, summaries, history, rag, current

    async def _preserve_current_with_async_budget(
        self,
        *,
        prompt: list[Message],
        summaries: list[Message],
        history: list[Message],
        rag: list[Message],
        current: list[Message],
        input_budget: int,
    ) -> tuple[list[Message], list[Message], list[Message], list[Message], list[Message]]:
        if not current or input_budget <= 0:
            return prompt, summaries, history, rag, current

        current = await self._fit_messages_to_budget_async(current, input_budget, keep_tail=True)
        if not current:
            return [], [], [], [], []

        fixed_current_tokens = await self._count_messages_async(current)
        remaining = max(input_budget - fixed_current_tokens, 0)
        if remaining <= 0:
            return [], [], [], [], current

        prompt = await self._fit_messages_to_budget_async(prompt, remaining, keep_tail=True)
        remaining = max(remaining - await self._count_messages_async(prompt), 0)
        summaries = await self._fit_messages_to_budget_async(summaries, remaining, keep_tail=False)
        remaining = max(remaining - await self._count_messages_async(summaries), 0)
        history = await self._fit_messages_to_budget_async(history, remaining, keep_tail=True)
        remaining = max(remaining - await self._count_messages_async(history), 0)
        rag = await self._fit_messages_to_budget_async(rag, remaining, keep_tail=False)
        return prompt, summaries, history, rag, current

    def _summary_budget(self, history_budget: int) -> int:
        if self.budget.summary_tokens <= 0:
            return 0
        if history_budget > self.budget.keep_recent_tokens:
            return min(self.budget.summary_tokens, history_budget - self.budget.keep_recent_tokens)
        if history_budget >= 30:
            return min(self.budget.summary_tokens, max(20, history_budget // 3))
        return 0

    def _select_first_kept_index(self, history: list[Message], recent_budget: int) -> int:
        if recent_budget <= 0:
            return len(history)

        total = 0
        first_kept_index = len(history)
        for index in range(len(history) - 1, -1, -1):
            message_tokens = estimate_message_tokens(history[index])
            if first_kept_index < len(history) and total + message_tokens > recent_budget:
                break
            if first_kept_index == len(history) and message_tokens > recent_budget:
                break
            total += message_tokens
            first_kept_index = index

        return _move_cut_before_tool_result(history, first_kept_index)

    async def _select_first_kept_index_async(self, history: list[Message], recent_budget: int) -> int:
        if recent_budget <= 0:
            return len(history)

        total = 0
        first_kept_index = len(history)
        for index in range(len(history) - 1, -1, -1):
            message_tokens = await self._count_messages_async([history[index]])
            if first_kept_index < len(history) and total + message_tokens > recent_budget:
                break
            if first_kept_index == len(history) and message_tokens > recent_budget:
                break
            total += message_tokens
            first_kept_index = index

        return _move_cut_before_tool_result(history, first_kept_index)

    def _require_token_counter(self) -> None:
        if self.token_counter is None:
            raise ContextTokenCounterRequiredError(
                "Host count_tokens API is required for local-agent context budgeting"
            )

    async def _count_messages_async(self, messages: list[Message], *, allow_usage_anchor: bool = False) -> int:
        self._require_token_counter()
        if allow_usage_anchor and self.usage_anchor is not None:
            anchor = self.usage_anchor
            if 0 <= anchor.message_count <= len(messages) and anchor.total_tokens > 0:
                return anchor.total_tokens + await self._count_messages_async(messages[anchor.message_count :])
        return await self.token_counter.count(messages)

    async def _fit_messages_to_budget_async(
        self,
        messages: list[Message],
        max_tokens: int,
        *,
        keep_tail: bool,
    ) -> list[Message]:
        if max_tokens <= 0 or not messages:
            return []

        copied = _copy_messages(messages)
        if await self._count_messages_async(copied) <= max_tokens:
            return copied

        selected: list[Message] = []
        used_tokens = 0

        if keep_tail:
            end = len(copied)
            while end > 0:
                start = _tail_unit_start(copied, end)
                unit = copied[start:end]
                unit_tokens = await self._count_messages_async(unit)
                remaining = max_tokens - used_tokens
                if remaining <= 0:
                    break
                if unit_tokens <= remaining:
                    selected[0:0] = _copy_messages(unit)
                    used_tokens += unit_tokens
                    end = start
                    continue
                if not selected:
                    truncated = await self._fit_unit_to_budget_async(unit, remaining, keep_tail=True)
                    selected[0:0] = truncated
                break
            return selected

        for message in copied:
            remaining = max_tokens - used_tokens
            if remaining <= 0:
                break
            message_tokens = await self._count_messages_async([message])
            if message_tokens <= remaining:
                selected.append(message.model_copy(deep=True))
                used_tokens += message_tokens
                continue
            truncated = await self._truncate_message_to_tokens_async(message, remaining)
            if truncated is not None:
                selected.append(truncated)
            break

        return selected

    async def _fit_unit_to_budget_async(
        self,
        unit: list[Message],
        max_tokens: int,
        *,
        keep_tail: bool,
    ) -> list[Message]:
        if max_tokens <= 0 or not unit:
            return []
        if len(unit) == 1:
            message = await self._truncate_message_to_tokens_async(unit[0], max_tokens)
            return [message] if message is not None else []

        if unit[0].role == "assistant" and unit[0].tool_calls:
            assistant_tokens = await self._count_messages_async([unit[0]])
            if assistant_tokens > max_tokens:
                return []
            selected = [unit[0].model_copy(deep=True)]
            used_tokens = assistant_tokens
            for message in unit[1:]:
                remaining = max_tokens - used_tokens
                if remaining <= 0:
                    break
                message_tokens = await self._count_messages_async([message])
                if message_tokens <= remaining:
                    selected.append(message.model_copy(deep=True))
                    used_tokens += message_tokens
                    continue
                truncated = await self._truncate_message_to_tokens_async(message, remaining)
                if truncated is not None:
                    selected.append(truncated)
                break
            return selected

        selected: list[Message] = []
        used_tokens = 0
        iterable = reversed(unit) if keep_tail else iter(unit)
        for message in iterable:
            remaining = max_tokens - used_tokens
            if remaining <= 0:
                break
            message_tokens = await self._count_messages_async([message])
            if message_tokens <= remaining:
                if keep_tail:
                    selected.insert(0, message.model_copy(deep=True))
                else:
                    selected.append(message.model_copy(deep=True))
                used_tokens += message_tokens
                continue
            truncated = await self._truncate_message_to_tokens_async(message, remaining)
            if truncated is not None:
                if keep_tail:
                    selected.insert(0, truncated)
                else:
                    selected.append(truncated)
            break
        return selected

    async def _truncate_message_to_tokens_async(self, message: Message, max_tokens: int) -> Message | None:
        if max_tokens <= 0:
            return None
        if await self._count_messages_async([message]) <= max_tokens:
            return message.model_copy(deep=True)

        copied = message.model_copy(deep=True)
        content = copied.content
        copied.content = ""
        fixed_tokens = await self._count_messages_async([copied])
        available_tokens = max_tokens - fixed_tokens
        if available_tokens <= 0:
            return None

        if isinstance(content, str):
            copied.content = await self._truncate_text_to_tokens_async(
                content,
                available_tokens,
                message_template=copied,
            )
            return copied if _message_has_model_content(copied) or copied.role == "tool" else None

        if isinstance(content, list):
            fitted_content = []
            used_tokens = 0
            for item in content:
                remaining = available_tokens - used_tokens
                if remaining <= 0:
                    break
                item_type = getattr(item, "type", "")
                if item_type == "text" and getattr(item, "text", None):
                    fitted_item = item.model_copy(deep=True)
                    probe = copied.model_copy(deep=True)
                    probe.content = [fitted_item]
                    item_tokens = await self._count_messages_async([probe]) - fixed_tokens
                    if item_tokens > remaining:
                        fitted_item.text = await self._truncate_content_item_text_async(
                            copied,
                            item,
                            fixed_tokens + remaining,
                        )
                        if not fitted_item.text:
                            break
                        fitted_content.append(fitted_item)
                        break
                    fitted_content.append(fitted_item)
                    used_tokens += item_tokens
                elif isinstance(item_type, str) and item_type.startswith(("image", "file")):
                    probe = copied.model_copy(deep=True)
                    probe.content = [item]
                    item_tokens = await self._count_messages_async([probe]) - fixed_tokens
                    if item_tokens > remaining:
                        continue
                    fitted_content.append(item.model_copy(deep=True))
                    used_tokens += item_tokens
            copied.content = fitted_content
            return copied if _message_has_model_content(copied) or copied.role == "tool" else None

        return None

    async def _truncate_text_to_tokens_async(
        self,
        text: str,
        max_tokens: int,
        message_template: Message | None = None,
    ) -> str:
        if max_tokens <= 0:
            return ""

        def probe_message(content: str) -> Message:
            if message_template is None:
                return Message(role="user", content=content)
            copied = message_template.model_copy(deep=True)
            copied.content = content
            return copied

        empty_tokens = await self._count_messages_async([probe_message("")])
        target_total = max_tokens + empty_tokens
        if await self._count_messages_async([probe_message(text)]) <= target_total:
            return text

        low = 0
        high = len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if await self._count_messages_async([probe_message(text[:mid])]) <= target_total:
                low = mid
            else:
                high = mid - 1
        return text[:low]

    async def _truncate_content_item_text_async(
        self,
        message_template: Message,
        item: typing.Any,
        max_total_tokens: int,
    ) -> str:
        if max_total_tokens <= 0 or not getattr(item, "text", None):
            return ""

        def probe_message(content: str) -> Message:
            probe_item = item.model_copy(deep=True)
            probe_item.text = content
            probe = message_template.model_copy(deep=True)
            probe.content = [probe_item]
            return probe

        if await self._count_messages_async([probe_message(item.text)]) <= max_total_tokens:
            return item.text

        low = 0
        high = len(item.text)
        while low < high:
            mid = (low + high + 1) // 2
            if await self._count_messages_async([probe_message(item.text[:mid])]) <= max_total_tokens:
                low = mid
            else:
                high = mid - 1
        return item.text[:low]

    def _build_summary_message(self, omitted: list[Message], summary_budget: int) -> Message | None:
        if not omitted or summary_budget <= 0:
            return None

        summary = _attach_summary_references(
            summarize_messages(omitted, summary_budget),
            omitted,
            summary_budget,
        )
        if not summary:
            return None
        return Message(role="system", content=summary)

    async def _build_summary_message_async(self, omitted: list[Message], summary_budget: int) -> Message | None:
        if not omitted or summary_budget <= 0:
            return None

        summary = None
        if self.summarizer is not None:
            summary = await self.summarizer.summarize(omitted, summary_budget)
        if summary is None:
            summary = summarize_messages(omitted, summary_budget)
        summary = _attach_summary_references(summary, omitted, summary_budget)
        if not summary:
            return None
        return Message(role="system", content=summary)


def sanitize_provider_messages(messages: list[Message]) -> list[Message]:
    """Return model messages with provider-unsafe tool/thinking blocks removed.

    Anthropic-style providers require every tool result to be adjacent to the
    assistant tool use that produced it. Host transcript history can contain
    partial old turns, so normalize that shape before every model call.
    """
    cleaned = [_sanitize_message(message) for message in messages]
    cleaned = [message for message in cleaned if message is not None]

    normalized: list[Message] = []
    index = 0
    while index < len(cleaned):
        message = cleaned[index]
        if message.role == "tool":
            index += 1
            continue

        if message.role == "assistant" and message.tool_calls:
            next_index = index + 1
            tool_result_messages: list[Message] = []
            seen_result_ids: set[str] = set()
            valid_tool_call_ids = {
                tool_call.id
                for tool_call in message.tool_calls
                if isinstance(getattr(tool_call, "id", None), str) and tool_call.id
            }

            while next_index < len(cleaned) and cleaned[next_index].role == "tool":
                tool_message = cleaned[next_index]
                tool_call_id = tool_message.tool_call_id
                if (
                    isinstance(tool_call_id, str)
                    and tool_call_id in valid_tool_call_ids
                    and tool_call_id not in seen_result_ids
                ):
                    tool_result_messages.append(tool_message)
                    seen_result_ids.add(tool_call_id)
                next_index += 1

            if tool_result_messages:
                message.tool_calls = [tool_call for tool_call in message.tool_calls if tool_call.id in seen_result_ids]
                normalized.append(message)
                normalized.extend(tool_result_messages)
            else:
                message.tool_calls = None
                if _message_has_model_content(message):
                    normalized.append(message)
            index = next_index
            continue

        normalized.append(message)
        index += 1

    return normalized


def summarize_messages(messages: list[Message], max_tokens: int) -> str:
    """Create a deterministic compacted-history summary.

    This is intentionally not a model call yet. It provides the same structural
    shape as Pi compaction, while future iterations can replace the summary
    generator with an LLM + host state checkpoint.
    """
    if max_tokens <= 0:
        return ""

    entries: list[ConversationSummaryEntry] = []
    message_count = 0
    for index, message in enumerate(messages, start=1):
        parsed_summary = _parse_conversation_summary_message(message)
        if parsed_summary is not None:
            count, summary_entries = parsed_summary
            message_count += count
            for summary_entry in summary_entries:
                entries.append(
                    ConversationSummaryEntry(
                        index=len(entries) + 1,
                        role=summary_entry.role,
                        text=summary_entry.text,
                    )
                )
            continue

        message_count += 1
        text = message_to_text(message)
        if not text and message.tool_calls:
            text = "; ".join(tool_call.function.name for tool_call in message.tool_calls if tool_call.function)
        entries.append(ConversationSummaryEntry(index=len(entries) + 1, role=message.role, text=text))

    summary = ConversationSummary(
        schema_version=SUMMARY_SCHEMA_VERSION,
        message_count=message_count,
        entries=entries,
    )
    return summary.render(max_tokens)


def estimate_messages_tokens(messages: list[Message]) -> int:
    return sum(estimate_message_tokens(message) for message in messages)


def estimate_messages_tokens_with_anchor(messages: list[Message], anchor: ContextUsageAnchor | None) -> int:
    if anchor is None or anchor.message_count < 0 or anchor.total_tokens <= 0 or anchor.message_count > len(messages):
        return estimate_messages_tokens(messages)
    return anchor.total_tokens + estimate_messages_tokens(messages[anchor.message_count :])


def estimate_message_chars(message: Message) -> int:
    chars = len(message.role) + 8
    chars += _content_chars(message.content)
    if message.name:
        chars += len(message.name)
    if message.tool_call_id:
        chars += len(message.tool_call_id)
    if message.tool_calls:
        for tool_call in message.tool_calls:
            chars += len(tool_call.id) + len(tool_call.type)
            if tool_call.function:
                chars += len(tool_call.function.name) + len(tool_call.function.arguments)
    return chars


def estimate_message_tokens(message: Message) -> int:
    tokens = _chars_to_tokens(len(message.role) + 8)
    tokens += _content_tokens(message.content)
    if message.name:
        tokens += estimate_text_tokens(message.name)
    if message.tool_call_id:
        tokens += estimate_text_tokens(message.tool_call_id)
    if message.tool_calls:
        for tool_call in message.tool_calls:
            tokens += estimate_text_tokens(tool_call.id)
            tokens += estimate_text_tokens(tool_call.type)
            if tool_call.function:
                tokens += estimate_text_tokens(tool_call.function.name)
                tokens += estimate_text_tokens(tool_call.function.arguments)
    return tokens


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0

    tokens = 0
    non_cjk_chars = 0
    for char in text:
        if _is_cjk_token_char(char) or _is_symbol_token_char(char):
            tokens += _chars_to_tokens(non_cjk_chars)
            non_cjk_chars = 0
            tokens += 1
        else:
            non_cjk_chars += 1

    tokens += _chars_to_tokens(non_cjk_chars)
    return tokens


def message_to_text(message: Message) -> str:
    parts: list[str] = []
    content = message.content
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if item.type == "text" and item.text:
                parts.append(item.text)
            elif item.type.startswith("image"):
                parts.append("[image]")
            elif item.type.startswith("file"):
                parts.append(f"[file:{item.file_name or 'unnamed'}]")

    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function:
                parts.append(f"[tool_call:{tool_call.function.name} {tool_call.function.arguments}]")

    return "\n".join(parts)


def _message_from_transcript_item(item: dict[str, typing.Any], current_event_id: str) -> Message | None:
    if item.get("event_id") == current_event_id:
        return None

    content_json = item.get("content_json")
    if isinstance(content_json, dict):
        try:
            return Message.model_validate(content_json)
        except Exception:
            logger.debug("Failed to parse transcript content_json as Message", exc_info=True)

    role = item.get("role")
    content = item.get("content")
    if isinstance(role, str) and isinstance(content, str) and content:
        return Message(role=role, content=content)

    return None


def _as_mapping(value: typing.Any) -> dict[str, typing.Any] | None:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dumped
    return None


def _model_or_mapping_get(value: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _last_non_empty(values: list[str | None]) -> str | None:
    for value in reversed(values):
        if value:
            return value
    return None


def _copy_messages(messages: list[Message]) -> list[Message]:
    return [message.model_copy(deep=True) for message in messages]


def _sanitize_message(message: Message) -> Message | None:
    copied = message.model_copy(deep=True)
    copied.content = _sanitize_content(copied.content)
    if copied.tool_calls:
        copied.tool_calls = [
            tool_call
            for tool_call in copied.tool_calls
            if isinstance(getattr(tool_call, "id", None), str)
            and tool_call.id
            and getattr(tool_call, "function", None) is not None
            and isinstance(getattr(tool_call.function, "name", None), str)
            and tool_call.function.name
        ]
        if not copied.tool_calls:
            copied.tool_calls = None

    if copied.role == "tool" and not copied.tool_call_id:
        return None

    if copied.role not in {"system", "developer", "user", "assistant", "tool"}:
        return None

    if not _message_has_model_content(copied) and copied.role != "tool":
        return None

    return copied


def _sanitize_content(content: typing.Any) -> typing.Any:
    if not isinstance(content, list):
        return content

    safe_content = []
    for item in content:
        item_type = getattr(item, "type", "")
        if item_type == "text":
            if getattr(item, "text", None):
                safe_content.append(item)
        elif isinstance(item_type, str) and item_type.startswith(("image", "file")):
            safe_content.append(item)

    return safe_content if safe_content else ""


def _message_has_model_content(message: Message) -> bool:
    if message.tool_calls:
        return True
    if isinstance(message.content, str):
        return bool(message.content)
    if isinstance(message.content, list):
        return bool(message.content)
    return False


def _split_leading_prompt_messages(messages: list[Message]) -> tuple[list[Message], list[Message], list[Message]]:
    prompt_messages: list[Message] = []
    summary_messages: list[Message] = []
    first_history_index = 0
    for index, message in enumerate(messages):
        if _is_conversation_summary_message(message):
            summary_messages.append(message)
            first_history_index = index + 1
            continue
        if message.role not in {"system", "developer"}:
            first_history_index = index
            break
        prompt_messages.append(message)
    else:
        first_history_index = len(messages)

    return (
        _copy_messages(prompt_messages),
        _copy_messages(summary_messages),
        _copy_messages(messages[first_history_index:]),
    )


def _split_runtime_history_and_current(messages: list[Message]) -> tuple[list[Message], list[Message]]:
    current_start = _current_turn_tail_start(messages)
    if current_start >= len(messages):
        return _copy_messages(messages), []
    return _copy_messages(messages[:current_start]), _copy_messages(messages[current_start:])


def _current_turn_tail_start(messages: list[Message]) -> int:
    if not messages:
        return 0

    tool_tail_start = _tool_turn_tail_start(messages)
    if tool_tail_start is not None:
        return tool_tail_start

    last = messages[-1]
    if last.role == "user":
        return len(messages) - 1
    if last.role == "assistant" and last.tool_calls:
        return len(messages) - 1
    return len(messages)


def _tool_turn_tail_start(messages: list[Message]) -> int | None:
    if not messages or messages[-1].role != "tool":
        return None

    index = len(messages) - 1
    while index >= 0 and messages[index].role == "tool":
        index -= 1

    if index >= 0 and messages[index].role == "assistant" and messages[index].tool_calls:
        start = index
        scan = index - 1
        while scan >= 0 and messages[scan].role == "user":
            start = scan
            scan -= 1
        return start
    return None


def _content_chars(content: typing.Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        chars = 0
        for item in content:
            if item.type == "text" and item.text:
                chars += len(item.text)
            elif item.type.startswith(("image", "file")):
                chars += _attachment_tokens(item) * ESTIMATED_CHARS_PER_TOKEN
        return chars
    return 0


def _content_tokens(content: typing.Any) -> int:
    if isinstance(content, str):
        return estimate_text_tokens(content)
    if isinstance(content, list):
        tokens = 0
        for item in content:
            if item.type == "text" and item.text:
                tokens += estimate_text_tokens(item.text)
            elif item.type.startswith(("image", "file")):
                tokens += _attachment_tokens(item)
        return tokens
    return 0


def _attachment_tokens(item: typing.Any) -> int:
    payload_chars = 0
    for attr in ("image_base64", "file_base64"):
        value = getattr(item, attr, None)
        if isinstance(value, str):
            payload_chars += len(value)

    descriptor_tokens = 0
    for attr in ("image_url", "file_url", "file_name"):
        value = getattr(item, attr, None)
        if isinstance(value, str):
            descriptor_tokens += estimate_text_tokens(value)

    payload_tokens = _chars_to_tokens(payload_chars)
    return max(ESTIMATED_ATTACHMENT_TOKENS, payload_tokens, descriptor_tokens)


def _move_cut_before_tool_result(history: list[Message], first_kept_index: int) -> int:
    while first_kept_index > 0 and first_kept_index < len(history) and history[first_kept_index].role == "tool":
        first_kept_index -= 1
    return first_kept_index


def _partition_summary_messages(messages: list[Message]) -> tuple[list[Message], list[Message]]:
    prompts: list[Message] = []
    summaries: list[Message] = []
    for message in messages:
        if _is_conversation_summary_message(message):
            summaries.append(message)
        else:
            prompts.append(message)
    return _copy_messages(prompts), _copy_messages(summaries)


def _is_conversation_summary_message(message: Message) -> bool:
    return (
        message.role == "system"
        and isinstance(message.content, str)
        and SUMMARY_OPEN_TAG in message.content
        and SUMMARY_CLOSE_TAG in message.content
    )


def _conversation_summary_body(message: Message) -> str:
    if not _is_conversation_summary_message(message):
        return ""
    assert isinstance(message.content, str)
    return message.content.split(SUMMARY_OPEN_TAG, 1)[1].split(SUMMARY_CLOSE_TAG, 1)[0].strip()


def _parse_conversation_summary_message(message: Message) -> tuple[int, list[ConversationSummaryEntry]] | None:
    if not _is_conversation_summary_message(message):
        return None

    body = _conversation_summary_body(message)
    lines = [line for line in body.splitlines() if line.strip()]
    count = 0
    entries: list[ConversationSummaryEntry] = []
    for line in lines:
        count_match = SUMMARY_COUNT_RE.search(line)
        if count_match:
            count = int(count_match.group(1))
            continue

        entry_match = SUMMARY_ENTRY_RE.match(line)
        if entry_match:
            entries.append(
                ConversationSummaryEntry(
                    index=len(entries) + 1,
                    role=entry_match.group(1),
                    text=entry_match.group(2),
                )
            )

    if not entries and body:
        entries.append(ConversationSummaryEntry(index=1, role="summary", text=body))

    return max(count, len(entries), 1), entries


def _extract_previous_summary_text(messages: list[Message]) -> str:
    summaries = [
        _conversation_summary_body(message) for message in messages if _is_conversation_summary_message(message)
    ]
    summaries = [summary for summary in summaries if summary]
    return "\n\n---\n\n".join(summaries)


def _build_llm_summary_prompt(messages: list[Message], *, previous_summary: str) -> str:
    conversation_text = _serialize_messages_for_summary(messages)
    prompt_parts = [f"<conversation>\n{conversation_text}\n</conversation>"]
    if previous_summary:
        prompt_parts.append(f"<previous-summary>\n{previous_summary}\n</previous-summary>")
        prompt_parts.append(UPDATE_SUMMARIZATION_PROMPT)
    else:
        prompt_parts.append(SUMMARIZATION_PROMPT)
    return "\n\n".join(prompt_parts)


def _serialize_messages_for_summary(messages: list[Message]) -> str:
    parts: list[str] = []
    for index, message in enumerate(messages, start=1):
        text = message_to_text(message)
        if not text:
            text = "(empty)"
        parts.append(f'<message index="{index}" role="{message.role}">\n{text}\n</message>')
    return "\n\n".join(parts)


def _message_content_text(message: typing.Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if getattr(item, "type", None) == "text" and isinstance(getattr(item, "text", None), str):
                text_parts.append(item.text)
            elif isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "\n".join(text_parts)
    return ""


def _wrap_llm_summary(summary: str, max_tokens: int, *, message_count: int) -> str | None:
    summary = summary.strip()
    if not summary or max_tokens <= 0:
        return None

    prefix = f"{SUMMARY_OPEN_TAG}\nv=1 source=llm count={max(message_count, 1)}\n"
    suffix = f"\n{SUMMARY_CLOSE_TAG}"
    fixed_tokens = estimate_text_tokens(prefix + suffix)
    available_tokens = max_tokens - fixed_tokens
    if available_tokens <= 0:
        return None
    body = _truncate_text_to_tokens(summary, available_tokens).strip()
    if not body:
        return None
    return f"{prefix}{body}{suffix}"


def _attach_summary_references(summary: str | None, messages: list[Message], max_tokens: int) -> str:
    if not summary or max_tokens <= 0:
        return ""

    block = _summary_reference_block(messages)
    if not block:
        return summary

    summary = summary.strip()
    if SUMMARY_CLOSE_TAG in summary:
        body, close = summary.rsplit(SUMMARY_CLOSE_TAG, 1)
        combined = f"{body.rstrip()}\n\n{block}\n{SUMMARY_CLOSE_TAG}{close}"
    else:
        combined = f"{summary}\n\n{block}"
    if estimate_text_tokens(combined) <= max_tokens:
        return combined

    if SUMMARY_CLOSE_TAG in summary:
        minimal = f"{SUMMARY_OPEN_TAG}\nv=1 references=preserved\n{block}\n{SUMMARY_CLOSE_TAG}"
        if estimate_text_tokens(minimal) <= max_tokens:
            return minimal

    block_tokens = estimate_text_tokens(f"\n\n{block}\n{SUMMARY_CLOSE_TAG}")
    if SUMMARY_CLOSE_TAG in summary and block_tokens < max_tokens:
        body, close = summary.rsplit(SUMMARY_CLOSE_TAG, 1)
        truncated_body = _truncate_text_to_tokens(body.rstrip(), max_tokens - block_tokens).rstrip()
        return f"{truncated_body}\n\n{block}\n{SUMMARY_CLOSE_TAG}{close}"

    return _truncate_text_to_tokens(combined, max_tokens)


def _summary_reference_block(messages: list[Message]) -> str:
    critical_refs: list[str] = []
    files: list[str] = []
    seen_critical_refs: set[str] = set()
    seen_files: set[str] = set()

    def add_critical_ref(ref: str) -> None:
        ref = ref.strip().strip(".,;:)")
        if not ref or ref in seen_critical_refs:
            return
        seen_critical_refs.add(ref)
        critical_refs.append(f"- {ref}")

    def add_file(value: dict[str, typing.Any]) -> None:
        path = value.get("path")
        if not isinstance(path, str) or not path or path in seen_files:
            return
        seen_files.add(path)
        fields = [f"path={path}"]
        files.append("- " + " ".join(str(field) for field in fields))

    def walk(value: typing.Any, depth: int = 0) -> None:
        if depth > 6 or len(critical_refs) + len(files) >= SUMMARY_REFERENCE_LIMIT:
            return
        if isinstance(value, dict):
            add_file(value)
            for nested in value.values():
                if isinstance(nested, (dict, list, tuple)):
                    walk(nested, depth + 1)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item, depth + 1)
            return
        if isinstance(value, str):
            for ref in CRITICAL_REF_RE.findall(value):
                add_critical_ref(ref)

    for message in messages:
        if _is_conversation_summary_message(message):
            _copy_existing_reference_lines(_conversation_summary_body(message), critical_refs, files)
        content = message.content
        if isinstance(content, str):
            try:
                walk(json.loads(content))
            except Exception:
                for ref in CRITICAL_REF_RE.findall(content):
                    add_critical_ref(ref)
        elif isinstance(content, list):
            for item in content:
                if item.type == "text" and item.text:
                    for ref in CRITICAL_REF_RE.findall(item.text):
                        add_critical_ref(ref)
                elif item.type.startswith(("image", "file")) and item.file_name:
                    for ref in CRITICAL_REF_RE.findall(item.file_name):
                        add_critical_ref(ref)

    blocks: list[str] = []
    if critical_refs:
        blocks.append(
            "<critical_refs>\n"
            + CRITICAL_REF_GUIDANCE
            + "\n"
            + "\n".join(critical_refs[:SUMMARY_REFERENCE_LIMIT])
            + "\n</critical_refs>"
        )
    remaining = max(0, SUMMARY_REFERENCE_LIMIT - len(critical_refs))
    if files and remaining:
        blocks.append("<files>\n" + "\n".join(files[:remaining]) + "\n</files>")
    return "\n".join(blocks)


def _copy_existing_reference_lines(
    summary: str,
    critical_refs: list[str],
    files: list[str],
) -> None:
    for tag, target in (("critical_refs", critical_refs), ("files", files)):
        open_tag = f"<{tag}>"
        close_tag = f"</{tag}>"
        if open_tag not in summary or close_tag not in summary:
            continue
        block = summary.split(open_tag, 1)[1].split(close_tag, 1)[0]
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("- ") and line not in target:
                target.append(line)


def _close_summary_lines(lines: list[str]) -> str:
    return "\n".join(lines + [SUMMARY_CLOSE_TAG])


def _truncate_text_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    if estimate_text_tokens(text) <= max_tokens:
        return text

    low = 0
    high = len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if estimate_text_tokens(text[:mid]) <= max_tokens:
            low = mid
        else:
            high = mid - 1
    return text[:low]


def _fit_messages_to_budget(messages: list[Message], max_tokens: int, *, keep_tail: bool) -> list[Message]:
    if max_tokens <= 0 or not messages:
        return []

    copied = _copy_messages(messages)
    if estimate_messages_tokens(copied) <= max_tokens:
        return copied

    selected: list[Message] = []
    used_tokens = 0

    if keep_tail:
        end = len(copied)
        while end > 0:
            start = _tail_unit_start(copied, end)
            unit = copied[start:end]
            unit_tokens = estimate_messages_tokens(unit)
            remaining = max_tokens - used_tokens
            if remaining <= 0:
                break
            if unit_tokens <= remaining:
                selected[0:0] = _copy_messages(unit)
                used_tokens += unit_tokens
                end = start
                continue
            if not selected:
                truncated = _fit_unit_to_budget(unit, remaining, keep_tail=True)
                selected[0:0] = truncated
            break
        return selected

    for message in copied:
        remaining = max_tokens - used_tokens
        if remaining <= 0:
            break
        message_tokens = estimate_message_tokens(message)
        if message_tokens <= remaining:
            selected.append(message.model_copy(deep=True))
            used_tokens += message_tokens
            continue
        truncated = _truncate_message_to_tokens(message, remaining)
        if truncated is not None:
            selected.append(truncated)
        break

    return selected


def _fit_unit_to_budget(unit: list[Message], max_tokens: int, *, keep_tail: bool) -> list[Message]:
    if max_tokens <= 0 or not unit:
        return []
    if len(unit) == 1:
        message = _truncate_message_to_tokens(unit[0], max_tokens)
        return [message] if message is not None else []

    if unit[0].role == "assistant" and unit[0].tool_calls:
        assistant_tokens = estimate_message_tokens(unit[0])
        if assistant_tokens > max_tokens:
            return []
        selected = [unit[0].model_copy(deep=True)]
        used_tokens = assistant_tokens
        for message in unit[1:]:
            remaining = max_tokens - used_tokens
            if remaining <= 0:
                break
            message_tokens = estimate_message_tokens(message)
            if message_tokens <= remaining:
                selected.append(message.model_copy(deep=True))
                used_tokens += message_tokens
                continue
            truncated = _truncate_message_to_tokens(message, remaining)
            if truncated is not None:
                selected.append(truncated)
            break
        return selected

    selected: list[Message] = []
    used_tokens = 0
    iterable = reversed(unit) if keep_tail else iter(unit)
    for message in iterable:
        remaining = max_tokens - used_tokens
        if remaining <= 0:
            break
        message_tokens = estimate_message_tokens(message)
        if message_tokens <= remaining:
            if keep_tail:
                selected.insert(0, message.model_copy(deep=True))
            else:
                selected.append(message.model_copy(deep=True))
            used_tokens += message_tokens
            continue
        truncated = _truncate_message_to_tokens(message, remaining)
        if truncated is not None:
            if keep_tail:
                selected.insert(0, truncated)
            else:
                selected.append(truncated)
        break
    return selected


def _tail_unit_start(messages: list[Message], end: int) -> int:
    index = end - 1
    while index > 0 and messages[index].role == "tool":
        index -= 1
    if index >= 0 and messages[index].role == "assistant" and messages[index].tool_calls:
        return index
    return end - 1


def _truncate_message_to_tokens(message: Message, max_tokens: int) -> Message | None:
    if max_tokens <= 0:
        return None
    if estimate_message_tokens(message) <= max_tokens:
        return message.model_copy(deep=True)

    copied = message.model_copy(deep=True)
    content = copied.content
    copied.content = ""
    fixed_tokens = estimate_message_tokens(copied)
    available_tokens = max_tokens - fixed_tokens
    if available_tokens <= 0:
        return None

    if isinstance(content, str):
        copied.content = _truncate_text_to_tokens(content, available_tokens)
        return copied if _message_has_model_content(copied) or copied.role == "tool" else None

    if isinstance(content, list):
        fitted_content = []
        used_tokens = 0
        for item in content:
            remaining = available_tokens - used_tokens
            if remaining <= 0:
                break
            item_type = getattr(item, "type", "")
            if item_type == "text" and getattr(item, "text", None):
                item_tokens = estimate_text_tokens(item.text)
                fitted_item = item.model_copy(deep=True)
                if item_tokens > remaining:
                    fitted_item.text = _truncate_text_to_tokens(item.text, remaining)
                    if not fitted_item.text:
                        break
                    fitted_content.append(fitted_item)
                    break
                fitted_content.append(fitted_item)
                used_tokens += item_tokens
            elif isinstance(item_type, str) and item_type.startswith(("image", "file")):
                item_tokens = _attachment_tokens(item)
                if item_tokens > remaining:
                    continue
                fitted_content.append(item.model_copy(deep=True))
                used_tokens += item_tokens
        copied.content = fitted_content
        return copied if _message_has_model_content(copied) or copied.role == "tool" else None

    return None


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 32:
        return text[:max_chars]

    omitted = len(text) - max_chars
    suffix = f"\n[... {omitted} characters compacted]"
    return text[: max_chars - len(suffix)] + suffix


def _runtime_context_window_tokens(metadata: dict[str, typing.Any]) -> int | None:
    for key in (
        "model_context_window_tokens",
        "context_window_tokens",
        "model_context_tokens",
        "contextWindowTokens",
        "context_window",
    ):
        value = metadata.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            return value

    model = metadata.get("model")
    if isinstance(model, dict):
        for key in ("context_window_tokens", "contextWindowTokens", "context_window"):
            value = model.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int) and value > 0:
                return value

    return None


def _runtime_max_output_tokens(metadata: dict[str, typing.Any]) -> int | None:
    for key in (
        "model_max_output_tokens",
        "max_output_tokens",
        "model_output_tokens",
        "maxOutputTokens",
    ):
        value = metadata.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            return value

    model = metadata.get("model")
    if isinstance(model, dict):
        for key in ("max_output_tokens", "maxOutputTokens", "output_tokens"):
            value = model.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int) and value > 0:
                return value

    return None


def _clamp_reserve_tokens(window_tokens: int, reserve_tokens: int) -> int:
    if window_tokens <= 0 or reserve_tokens <= 0:
        return 0
    return min(reserve_tokens, max(1, window_tokens // 4))


def _config_token_value(
    config: dict[str, typing.Any],
    key: str,
    default: int | None,
    *,
    minimum: int,
) -> int | None:
    if key in config:
        return _config_int(config, key, default, minimum=minimum)
    return default


def _chars_to_tokens(chars: int) -> int:
    if chars <= 0:
        return 0
    return max(1, (chars + ESTIMATED_CHARS_PER_TOKEN - 1) // ESTIMATED_CHARS_PER_TOKEN)


def _is_cjk_token_char(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x1100 <= codepoint <= 0x11FF
        or 0x2E80 <= codepoint <= 0x2EFF
        or 0x2F00 <= codepoint <= 0x2FDF
        or 0x3000 <= codepoint <= 0x303F
        or 0x3040 <= codepoint <= 0x309F
        or 0x30A0 <= codepoint <= 0x30FF
        or 0x3100 <= codepoint <= 0x312F
        or 0x3130 <= codepoint <= 0x318F
        or 0x31A0 <= codepoint <= 0x31BF
        or 0x31F0 <= codepoint <= 0x31FF
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xAC00 <= codepoint <= 0xD7AF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0xFF00 <= codepoint <= 0xFFEF
    )


def _is_symbol_token_char(char: str) -> bool:
    codepoint = ord(char)
    if 0x1F000 <= codepoint <= 0x1FAFF or 0x2600 <= codepoint <= 0x27BF or 0xFE00 <= codepoint <= 0xFE0F:
        return True
    return unicodedata.category(char) == "So"


def _config_int(
    config: dict[str, typing.Any],
    key: str,
    default: int | None,
    *,
    minimum: int,
) -> int | None:
    value = config.get(key, default)
    if isinstance(value, bool):
        return default
    if not isinstance(value, int):
        return default
    if value < minimum:
        return default
    return value


def usage_total_tokens(usage: typing.Any) -> int | None:
    usage_map = _as_mapping(usage)
    if usage_map is None:
        return None

    total_tokens = _positive_usage_int(usage_map.get("total_tokens"))
    if total_tokens is not None:
        return total_tokens

    prompt_tokens = _positive_usage_int(usage_map.get("prompt_tokens")) or 0
    completion_tokens = _positive_usage_int(usage_map.get("completion_tokens")) or 0
    if prompt_tokens or completion_tokens:
        return prompt_tokens + completion_tokens

    return None


def _positive_usage_int(value: typing.Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value
