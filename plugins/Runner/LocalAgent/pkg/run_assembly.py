"""Run-scoped capability assembly for the local-agent runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.resource.tool import LLMTool
from langbot_plugin.api.entities.builtin.runner import RunnerContext

from pkg.agent_core import AgentLoopHooks, LangBotContextHooks, LangBotToolExecutor
from pkg.agent_core.langbot import LangBotSteeringPuller
from pkg.config import (
    get_max_tool_iterations,
    get_max_tool_result_chars,
    get_remove_think,
    get_tool_execution_mode,
    model_reasoning_levels,
    parse_model_config,
)
from pkg.context_pipeline import ContextAssembler, ContextBudget, HostContextTokenCounter, LLMContextSummarizer
from pkg.model_calling import build_llm_tools


class NoAuthorizedModelError(Exception):
    """Raised when no configured model is available for this run."""


@dataclass(frozen=True)
class AgentRunAssembly:
    """Everything the LangBot adapter needs to construct an AgentLoop."""

    model_ids: list[str]
    messages: list[Message]
    tools: list[LLMTool]
    tool_executor: LangBotToolExecutor
    hooks: AgentLoopHooks
    streaming: bool
    max_tool_iterations: int
    tool_execution_mode: str
    remove_think: bool


class AgentRunAssembler:
    """Assemble LangBot-authorized run capabilities into AgentLoop inputs."""

    def __init__(self, api: Any, ctx: RunnerContext):
        self.api = api
        self.ctx = ctx

    async def assemble(self) -> AgentRunAssembly:
        model_ids = self._resolve_model_ids()
        if not model_ids:
            raise NoAuthorizedModelError("No authorized model for local-agent")

        allowed_tools = self._allowed_tool_names()

        max_tool_iterations = get_max_tool_iterations(self.ctx.config)
        max_tool_result_chars = get_max_tool_result_chars(self.ctx.config)
        tool_execution_mode = get_tool_execution_mode(self.ctx.config)
        remove_think = get_remove_think(self.ctx.config)
        context_budget = ContextBudget.from_context(self.ctx)
        reasoning_level = model_reasoning_levels(self.ctx.config).get(model_ids[0], "provider_default")
        summarizer = LLMContextSummarizer(
            self.api, model_ids[0], remove_think=remove_think, reasoning_level=reasoning_level
        )
        tools = await self._build_tools(allowed_tools)
        token_counter = HostContextTokenCounter(self.api, model_ids[0], tools, reasoning_level=reasoning_level)

        context_assembly = await ContextAssembler(
            self.api,
            self.ctx,
            budget=context_budget,
            summarizer=summarizer,
            token_counter=token_counter,
        ).assemble()

        return AgentRunAssembly(
            model_ids=model_ids,
            messages=context_assembly.messages,
            tools=tools,
            tool_executor=LangBotToolExecutor(
                self.api,
                allowed_tools,
                max_result_chars=max_tool_result_chars,
            ),
            hooks=LangBotContextHooks(
                context_budget,
                summarizer=summarizer,
                token_counter=token_counter,
                steering_puller=LangBotSteeringPuller(self.api),
            ),
            streaming=self._streaming_supported(),
            max_tool_iterations=max_tool_iterations,
            tool_execution_mode=tool_execution_mode,
            remove_think=remove_think,
        )

    def _resolve_model_ids(self) -> list[str]:
        allowed_model_ids = {model.model_id for model in self.api.get_allowed_models()}
        return parse_model_config(self.ctx.config.get("model"), allowed_model_ids)

    def _allowed_tool_names(self) -> set[str]:
        from pkg.box import SANDBOX_TOOLS

        names = {tool.tool_name for tool in self.api.get_allowed_tools()}
        if not self.ctx.config.get("box-enabled", True) or not self.ctx.context.available_apis.box:
            names -= SANDBOX_TOOLS
        return names

    def _streaming_supported(self) -> bool:
        metadata = getattr(self.ctx.runtime, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            runtime_supported = True
        else:
            runtime_supported = bool(metadata.get("streaming_supported", True))
        delivery = getattr(self.ctx, "delivery", None)
        delivery_supported = bool(getattr(delivery, "supports_streaming", False))
        return runtime_supported and delivery_supported

    async def _build_tools(self, allowed_tools: set[str]) -> list[LLMTool]:
        resources = getattr(self.ctx, "resources", None)
        tool_resources = getattr(resources, "tools", None) if resources else None
        return await build_llm_tools(self.api, allowed_tools, tool_resources)


__all__ = ["AgentRunAssembler", "AgentRunAssembly", "NoAuthorizedModelError"]
