from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider.message import Message

logger = logging.getLogger(__name__)

RAG_PRIORITY_SYSTEM_PROMPT = """# Knowledge Retrieval Policy

For questions involving facts, policies, rules, procedures, product behavior, configuration, or other domain-specific information, prefer calling the `query_knowledge` tool before answering.

Treat the configured knowledge bases as the primary source of truth for this conversation. Your own pretrained knowledge may be outdated or incomplete for in-scope topics.

Rules:
- If the answer depends on knowledge-base content, call `query_knowledge` instead of relying on memory.
- If you are unsure whether your answer is fully accurate, call `query_knowledge`.
- Start by listing available knowledge bases, then query the most relevant one or ones with a focused query.
- If retrieval is insufficient, refine the query and try again rather than guessing.

No automatic knowledge-base retrieval will happen unless you call `query_knowledge`."""


class DisableNaiveRAG(EventListener):
    """Disable the pipeline's automatic pre-processing RAG retrieval.

    When AgenticRAG is installed, knowledge base retrieval should go through
    the agent's query_knowledge tool instead of the automatic pre-processing
    stage.  This listener clears ``_knowledge_base_uuids`` during
    PromptPreProcessing so the runner skips naive RAG entirely.

    Plugins that handle their own retrieval (e.g. LongTermMemory) should
    remove their KB from ``_knowledge_base_uuids`` independently before
    this listener runs, so there is no ordering dependency.
    """

    def __init__(self):
        super().__init__()

        @self.handler(events.PromptPreProcessing)
        async def on_prompt_preprocess(event_ctx: context.EventContext):
            query_vars = await event_ctx.get_query_vars()
            kb_uuids: list[str] = query_vars.get("_knowledge_base_uuids", [])
            if kb_uuids:
                llm_model_uuid = getattr(event_ctx.event.query, "use_llm_model_uuid", None)
                if not await self._tool_call_supported(llm_model_uuid):
                    logger.info(
                        "[AgenticRAG] keeping naive RAG enabled because current model does not support tool calls: query_id=%s llm_model_uuid=%s kb_count=%s",
                        event_ctx.query_id,
                        llm_model_uuid,
                        len(kb_uuids),
                    )
                    return

                await event_ctx.set_query_var("_knowledge_base_uuids", [])
                event_ctx.event.default_prompt.append(
                    Message(role="system", content=RAG_PRIORITY_SYSTEM_PROMPT)
                )
                logger.info(
                    "[AgenticRAG] disabled naive RAG pre-processing and injected RAG-priority system prompt: query_id=%s removed_kbs=%s",
                    event_ctx.query_id,
                    kb_uuids,
                )

    async def _tool_call_supported(self, llm_model_uuid: str | None) -> bool:
        """Best-effort detection of tool-call capability for the active LLM."""
        if not llm_model_uuid:
            return False

        try:
            llm_models = await self.plugin.get_llm_models()
        except Exception:
            logger.exception(
                "[AgenticRAG] failed to load llm model metadata for tool-call capability check"
            )
            return False

        for model in llm_models:
            if self._model_uuid(model) != llm_model_uuid:
                continue

            supported = self._tool_support_flag(model)
            if supported is None:
                logger.warning(
                    "[AgenticRAG] current model metadata has no tool-call capability flag; falling back to naive RAG: llm_model_uuid=%s",
                    llm_model_uuid,
                )
                return False
            return supported

        logger.warning(
            "[AgenticRAG] active llm model not found in model list; falling back to naive RAG: llm_model_uuid=%s",
            llm_model_uuid,
        )
        return False

    @staticmethod
    def _model_uuid(model: Any) -> str | None:
        if isinstance(model, dict):
            value = model.get("uuid")
        else:
            value = getattr(model, "uuid", None)
        return str(value) if value is not None else None

    @staticmethod
    def _tool_support_flag(model: Any) -> bool | None:
        if isinstance(model, dict):
            value = model.get("tool_call_supported")
        else:
            value = getattr(model, "tool_call_supported", None)

        if isinstance(value, bool):
            return value
        return None
