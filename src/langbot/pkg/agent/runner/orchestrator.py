"""Agent run orchestrator for coordinating runner execution."""

from __future__ import annotations

import typing

from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from ...core import app
from .binding_resolver import AgentBindingResolver
from .context_builder import AgentRunContextBuilder, AgentRunContextPayload
from .descriptor import AgentRunnerDescriptor
from .host_models import AgentBinding, AgentEventEnvelope
from .invoker import AgentRunnerInvoker
from .query_bridge import QueryRunBridge
from .registry import AgentRunnerRegistry
from .resource_builder import AgentResourceBuilder
from .result_normalizer import AgentResultNormalizer
from .run_journal import AgentRunJournal, MAX_ARTIFACT_INLINE_BYTES as _MAX_ARTIFACT_INLINE_BYTES
from .session_registry import AgentRunSessionRegistry, get_session_registry
from .state_scope import build_state_context


MAX_ARTIFACT_INLINE_BYTES = _MAX_ARTIFACT_INLINE_BYTES


class AgentRunOrchestrator:
    """Coordinate one AgentRunner execution.

    The orchestrator keeps the run state machine readable and delegates
    transport, Query bridging, and persistence side effects to narrower
    collaborators.
    """

    ap: app.Application
    registry: AgentRunnerRegistry
    context_builder: AgentRunContextBuilder
    resource_builder: AgentResourceBuilder
    result_normalizer: AgentResultNormalizer
    binding_resolver: AgentBindingResolver
    query_bridge: QueryRunBridge
    invoker: AgentRunnerInvoker
    journal: AgentRunJournal
    _session_registry: AgentRunSessionRegistry

    def __init__(
        self,
        ap: app.Application,
        registry: AgentRunnerRegistry,
    ):
        self.ap = ap
        self.registry = registry
        self.context_builder = AgentRunContextBuilder(ap)
        self.resource_builder = AgentResourceBuilder(ap)
        self.result_normalizer = AgentResultNormalizer(ap)
        self.binding_resolver = AgentBindingResolver()
        self.query_bridge = QueryRunBridge(self.binding_resolver)
        self.invoker = AgentRunnerInvoker(ap)
        self.journal = AgentRunJournal(ap)
        self._session_registry = get_session_registry()

    async def run(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        bound_plugins: list[str] | None = None,
        adapter_context: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run an AgentRunner from an event-first envelope."""
        runner_id = binding.runner_id
        descriptor = await self.registry.get(runner_id, bound_plugins)

        resources = await self.resource_builder.build_resources_from_binding(
            event=event,
            binding=binding,
            descriptor=descriptor,
        )

        context = await self.context_builder.build_context_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )

        session_query_id = None
        if adapter_context:
            session_query_id = adapter_context.get('query_id')
            if 'params' in adapter_context:
                context['adapter']['extra']['params'] = adapter_context['params']
            if adapter_context.get('prompt_get'):
                context['context']['available_apis']['prompt_get'] = True

        state_context = build_state_context(event, binding, descriptor)
        run_id = context['run_id']
        await self._session_registry.register(
            run_id=run_id,
            runner_id=descriptor.id,
            query_id=session_query_id,
            plugin_identity=descriptor.get_plugin_id(),
            resources=resources,
            permissions=descriptor.permissions or {},
            conversation_id=event.conversation_id,
            state_policy={
                'enable_state': binding.state_policy.enable_state,
                'state_scopes': list(binding.state_policy.state_scopes),
            },
            state_context=state_context,
        )

        event_log_id = await self.journal.write_event_log(
            event=event,
            binding=binding,
            run_id=run_id,
            runner_id=descriptor.id,
        )
        await self.journal.register_input_artifacts(
            event=event,
            run_id=run_id,
            runner_id=descriptor.id,
        )
        if event.event_type == 'message.received' and event.conversation_id:
            await self.journal.write_user_transcript(
                event=event,
                event_log_id=event_log_id,
            )

        pending_artifact_refs: list[dict[str, typing.Any]] = []

        try:
            async for result_dict in self.invoker.invoke(descriptor, context):
                result_type = result_dict.get('type')

                if result_type == 'artifact.created':
                    artifact_ref = await self.journal.handle_artifact_created(
                        result_dict=result_dict,
                        event=event,
                        run_id=run_id,
                        runner_id=descriptor.id,
                    )
                    pending_artifact_refs.append(artifact_ref)
                    await self.result_normalizer.normalize(result_dict, descriptor)
                    continue

                if result_type == 'state.updated':
                    await self.journal.handle_state_updated_event(result_dict, event, binding, descriptor)
                    await self.result_normalizer.normalize(result_dict, descriptor)
                    continue

                if result_type == 'message.completed' and event.conversation_id:
                    merged_refs = self.journal.merge_artifact_refs(
                        pending_artifact_refs,
                        result_dict,
                    )
                    pending_artifact_refs.clear()

                    await self.journal.write_assistant_transcript(
                        result_dict=result_dict,
                        event=event,
                        run_id=run_id,
                        runner_id=descriptor.id,
                        artifact_refs=merged_refs if merged_refs else None,
                    )

                result = await self.result_normalizer.normalize(result_dict, descriptor)
                if result is not None:
                    yield result
        finally:
            await self._session_registry.unregister(run_id)

    async def run_from_query(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run an AgentRunner from the current Pipeline Query entry point."""
        plan = self.query_bridge.build_plan(query)
        async for result in self.run(
            plan.event,
            plan.binding,
            bound_plugins=plan.bound_plugins,
            adapter_context=plan.adapter_context,
        ):
            yield result

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution."""
        return self.query_bridge.resolve_runner_id_for_telemetry(query)

    async def _invoke_runner(
        self,
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Compatibility delegate for older tests and internal callers."""
        async for result in self.invoker.invoke(descriptor, context):
            yield result

    async def _next_with_deadline(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> dict[str, typing.Any]:
        return await self.invoker._next_with_deadline(gen, descriptor, context)

    def _remaining_deadline_seconds(
        self,
        context: AgentRunContextPayload,
    ) -> float | None:
        return self.invoker._remaining_deadline_seconds(context)

    def _is_deadline_exhausted(self, context: AgentRunContextPayload) -> bool:
        return self.invoker._is_deadline_exhausted(context)

    async def _close_generator(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        await self.invoker._close_generator(gen, descriptor)

    async def _handle_state_updated_event(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        await self.journal.handle_state_updated_event(result_dict, event, binding, descriptor)

    async def _write_event_log(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        run_id: str,
        runner_id: str,
    ) -> str:
        return await self.journal.write_event_log(event, binding, run_id, runner_id)

    async def _register_input_artifacts(
        self,
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
    ) -> None:
        await self.journal.register_input_artifacts(event, run_id, runner_id)

    def _decode_attachment_content(
        self,
        content: typing.Any,
    ) -> tuple[bytes | None, str | None]:
        return self.journal.decode_attachment_content(content)

    async def _write_user_transcript(
        self,
        event: AgentEventEnvelope,
        event_log_id: str,
    ) -> None:
        await self.journal.write_user_transcript(event, event_log_id)

    async def _handle_artifact_created(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
    ) -> dict[str, typing.Any]:
        return await self.journal.handle_artifact_created(result_dict, event, run_id, runner_id)

    def _merge_artifact_refs(
        self,
        pending_refs: list[dict[str, typing.Any]],
        result_dict: dict[str, typing.Any],
    ) -> list[dict[str, typing.Any]]:
        return self.journal.merge_artifact_refs(pending_refs, result_dict)

    async def _write_assistant_transcript(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
        artifact_refs: list[dict[str, typing.Any]] | None = None,
    ) -> None:
        await self.journal.write_assistant_transcript(
            result_dict=result_dict,
            event=event,
            run_id=run_id,
            runner_id=runner_id,
            artifact_refs=artifact_refs,
        )
