"""Agent run orchestrator for coordinating runner execution."""
from __future__ import annotations

import typing
import traceback
import asyncio
import time

from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query
from langbot_plugin.entities.io.errors import ActionCallTimeoutError

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .registry import AgentRunnerRegistry
from .context_builder import AgentRunContextBuilder, AgentRunContextPayload
from .resource_builder import AgentResourceBuilder
from .result_normalizer import AgentResultNormalizer
from .persistent_state_store import get_persistent_state_store, PersistentStateStore
from .session_registry import get_session_registry, AgentRunSessionRegistry
from .config_migration import ConfigMigration
from .host_models import AgentEventEnvelope, AgentBinding
from .pipeline_adapter import PipelineAdapter
from .state_scope import build_state_context
from .errors import (
    RunnerNotFoundError,
    RunnerExecutionError,
    RunnerProtocolError,
)


# Maximum inline artifact content size (1MB)
MAX_ARTIFACT_INLINE_BYTES = 1 * 1024 * 1024


class AgentRunOrchestrator:
    """Orchestrator for agent runner execution.

    Responsibilities:
    - Resolve runner ID from pipeline config (new or old format)
    - Get runner descriptor from registry
    - Provision AgentRunContext envelope from Query
    - Build AgentResources with permission filtering
    - Invoke plugin runtime RUN_AGENT action
    - Normalize AgentRunResult to Pipeline messages
    - Handle errors, timeouts, protocol errors
    - Maintain streaming card behavior

    Entry points:
    - run(event, binding): Main entry for event-first Protocol v1
    - run_from_query(query): Pipeline adapter wrapper
    """

    ap: app.Application

    registry: AgentRunnerRegistry

    context_builder: AgentRunContextBuilder

    resource_builder: AgentResourceBuilder

    result_normalizer: AgentResultNormalizer

    # Cached singleton references (set in __init__)
    _session_registry: AgentRunSessionRegistry
    _persistent_state_store: PersistentStateStore | None

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
        # Cache singleton references to avoid per-request getter calls
        self._session_registry = get_session_registry()
        self._persistent_state_store = None  # Lazy init on first use

    async def run(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        bound_plugins: list[str] | None = None,
        adapter_context: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run agent runner from event-first envelope.

        This is the main entry point for Protocol v1.
        Event Gateway -> AgentBindingResolver -> run(event, binding).

        Args:
            event: Event envelope from event gateway
            binding: Agent binding configuration
            bound_plugins: Optional list of bound plugin identities for authorization
            adapter_context: Optional adapter context from Pipeline adapter

        Yields:
            Message or MessageChunk for pipeline response

        Raises:
            RunnerNotFoundError: If runner not found
            RunnerNotAuthorizedError: If runner not authorized
            RunnerExecutionError: If runner execution failed
        """
        runner_id = binding.runner_id

        # Get runner descriptor
        descriptor = await self.registry.get(runner_id, bound_plugins)

        # Build resources from binding
        resources = await self.resource_builder.build_resources_from_binding(
            event=event,
            binding=binding,
            descriptor=descriptor,
        )

        # Build context from event + binding
        context = await self.context_builder.build_context_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )

        # Merge adapter context if provided (for Pipeline adapter)
        if adapter_context:
            # Merge params into adapter.extra
            if 'params' in adapter_context:
                context['adapter']['extra']['params'] = adapter_context['params']
            # Merge prompt into adapter.extra for Pipeline adapter consumers.
            if 'prompt' in adapter_context:
                context['adapter']['extra']['prompt'] = adapter_context['prompt']
            # Merge bootstrap if provided
            if adapter_context.get('bootstrap'):
                context['bootstrap'] = adapter_context['bootstrap']
                # Also expose the bootstrap window through adapter metadata.
                bootstrap_messages = adapter_context['bootstrap'].get('messages')
                if bootstrap_messages:
                    context['adapter']['adapter_messages'] = bootstrap_messages
            # Merge runtime metadata if provided
            if adapter_context.get('runtime_metadata'):
                context['runtime']['metadata'].update(adapter_context['runtime_metadata'])
            # Set query_id if provided
            if adapter_context.get('query_id'):
                context['runtime']['query_id'] = adapter_context['query_id']

        # Build state context for State API handlers
        state_context = build_state_context(event, binding, descriptor)

        # Register session for proxy action permission validation
        run_id = context['run_id']
        query_id = context['runtime'].get('query_id')  # May be None for pure event-first mode
        await self._session_registry.register(
            run_id=run_id,
            runner_id=descriptor.id,
            query_id=query_id,
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

        # Write incoming event to EventLog
        event_log_id = await self._write_event_log(
            event=event,
            binding=binding,
            run_id=run_id,
            runner_id=descriptor.id,
        )

        # Write user message to Transcript if message.received
        if event.event_type == 'message.received' and event.conversation_id:
            await self._write_user_transcript(
                event=event,
                event_log_id=event_log_id,
            )

        # Track artifact refs for assistant transcript (cleared after each message.completed)
        pending_artifact_refs: list[dict[str, typing.Any]] = []

        try:
            # Run via plugin connector
            async for result_dict in self._invoke_runner(descriptor, context):
                # Handle artifact.created first - consume before normalizer
                if result_dict.get('type') == 'artifact.created':
                    artifact_ref = await self._handle_artifact_created(
                        result_dict=result_dict,
                        event=event,
                        run_id=run_id,
                        runner_id=descriptor.id,
                    )
                    pending_artifact_refs.append(artifact_ref)
                    # Pass to normalizer for logging, but don't yield to pipeline
                    await self.result_normalizer.normalize(result_dict, descriptor)
                    continue

                # Handle state.updated first - consume before normalizer
                if result_dict.get('type') == 'state.updated':
                    await self._handle_state_updated_event(result_dict, event, binding, descriptor)
                    # Pass to normalizer for logging, but don't yield to pipeline
                    await self.result_normalizer.normalize(result_dict, descriptor)
                    continue

                # Handle message.completed - write to Transcript
                if result_dict.get('type') == 'message.completed' and event.conversation_id:
                    # Merge pending artifact refs with message's own refs
                    merged_refs = self._merge_artifact_refs(
                        pending_artifact_refs,
                        result_dict,
                    )
                    # Clear pending refs after attaching to this message
                    pending_artifact_refs.clear()

                    await self._write_assistant_transcript(
                        result_dict=result_dict,
                        event=event,
                        run_id=run_id,
                        runner_id=descriptor.id,
                        artifact_refs=merged_refs if merged_refs else None,
                    )

                # Normalize result for other types
                result = await self.result_normalizer.normalize(result_dict, descriptor)
                if result is not None:
                    yield result
        finally:
            # Unregister session after run completes (success or error)
            await self._session_registry.unregister(run_id)

    async def run_from_query(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run agent runner from pipeline query.

        This is the Pipeline adapter wrapper for the Query-based flow.
        It delegates to the event-first run(event, binding) method.

        For the new event-first Protocol v1, use run(event, binding) instead.

        Args:
            query: Pipeline query with pipeline_config, session, messages, etc.

        Yields:
            Message or MessageChunk for pipeline response

        Raises:
            RunnerNotFoundError: If runner not found
            RunnerNotAuthorizedError: If runner not authorized
            RunnerExecutionError: If runner execution failed
        """
        # Resolve runner ID using ConfigMigration
        runner_id = ConfigMigration.resolve_runner_id(query.pipeline_config)
        if not runner_id:
            raise RunnerNotFoundError('no runner configured')

        # Convert Query to event-first envelope
        event = PipelineAdapter.query_to_event(query)

        # Convert Pipeline config to binding
        binding = PipelineAdapter.pipeline_config_to_binding(query, runner_id)

        # Extract bound plugins for authorization
        bound_plugins = query.variables.get('_pipeline_bound_plugins')

        # Build adapter context for Pipeline-specific fields
        adapter_context = PipelineAdapter.build_adapter_context(query, binding)

        # Delegate to event-first run()
        async for result in self.run(
            event,
            binding,
            bound_plugins=bound_plugins,
            adapter_context=adapter_context,
        ):
            yield result

    async def _invoke_runner(
        self,
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Invoke runner via plugin connector.

        Args:
            descriptor: Runner descriptor
            context: AgentRunContext dict

        Yields:
            Raw result dicts from plugin runtime

        Raises:
            RunnerExecutionError: If plugin system disabled or runtime error
        """
        if not self.ap.plugin_connector.is_enable_plugin:
            raise RunnerExecutionError(
                descriptor.id,
                'Plugin system is disabled',
                retryable=False,
            )

        try:
            gen = self.ap.plugin_connector.run_agent(
                plugin_author=descriptor.plugin_author,
                plugin_name=descriptor.plugin_name,
                runner_name=descriptor.runner_name,
                context=context,
            )

            while True:
                try:
                    result_dict = await self._next_with_deadline(gen, descriptor, context)
                except StopAsyncIteration:
                    break
                yield result_dict

        except asyncio.TimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                'Runner timed out (code: runner.timeout)',
                retryable=True,
            ) from e
        except ActionCallTimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                f'{e} (code: runner.timeout)',
                retryable=True,
            ) from e
        except RunnerExecutionError:
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.ap.logger.error(
                f'Runner {descriptor.id} unexpected error: {traceback.format_exc()}'
            )
            raise RunnerExecutionError(
                descriptor.id,
                str(e),
                retryable=False,
            )

    async def _next_with_deadline(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> dict[str, typing.Any]:
        """Read the next runner result while enforcing the run deadline."""
        remaining = self._remaining_deadline_seconds(context)
        if remaining is not None and remaining <= 0:
            await self._close_generator(gen, descriptor)
            raise asyncio.TimeoutError

        try:
            if remaining is None:
                return await anext(gen)
            return await asyncio.wait_for(anext(gen), timeout=remaining)
        except StopAsyncIteration:
            if self._is_deadline_exhausted(context):
                raise asyncio.TimeoutError
            raise
        except asyncio.TimeoutError:
            await self._close_generator(gen, descriptor)
            raise

    def _remaining_deadline_seconds(
        self,
        context: AgentRunContextPayload,
    ) -> float | None:
        runtime = context.get('runtime') or {}
        deadline_at = runtime.get('deadline_at')
        if deadline_at is None:
            return None
        try:
            return float(deadline_at) - time.time()
        except (TypeError, ValueError):
            return None

    def _is_deadline_exhausted(self, context: AgentRunContextPayload) -> bool:
        remaining = self._remaining_deadline_seconds(context)
        return remaining is not None and remaining <= 0

    async def _close_generator(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        try:
            await gen.aclose()
        except Exception as e:
            self.ap.logger.warning(f'Failed to close timed-out runner {descriptor.id}: {e}')

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution.

        Args:
            query: Pipeline query

        Returns:
            Runner ID string, or None
        """
        return ConfigMigration.resolve_runner_id(query.pipeline_config)

    async def _handle_state_updated_event(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        """Handle state.updated result in event-first mode.

        Persists state to database via PersistentStateStore.

        Args:
            result_dict: Raw result dict with type='state.updated'
            event: Event envelope
            binding: Agent binding configuration
            descriptor: Runner descriptor
        """
        data = result_dict.get('data', {})

        scope = data.get('scope')
        if not scope:
            raise RunnerProtocolError(
                descriptor.id,
                'state.updated missing required field: scope',
            )

        # Extract key and value
        key = data.get('key')
        value = data.get('value')

        if not key:
            raise RunnerProtocolError(
                descriptor.id,
                'state.updated missing required field: key',
            )

        # Lazy init persistent state store
        if self._persistent_state_store is None:
            self._persistent_state_store = get_persistent_state_store(
                self.ap.persistence_mgr.get_db_engine()
            )

        # Apply update to persistent state store
        success, error = await self._persistent_state_store.apply_update_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            scope=scope,
            key=key,
            value=value,
            logger=self.ap.logger,
        )

        if success:
            self.ap.logger.debug(
                f'Runner {descriptor.id} state.updated (event mode): scope={scope}, key={key}'
            )
        elif error:
            self.ap.logger.warning(
                f'Runner {descriptor.id} state.updated rejected: {error}'
            )

    async def _write_event_log(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        run_id: str,
        runner_id: str,
    ) -> str:
        """Write incoming event to EventLog.

        Args:
            event: Event envelope
            binding: Agent binding
            run_id: Run ID
            runner_id: Runner ID

        Returns:
            Event log ID
        """
        import datetime

        from .event_log_store import EventLogStore
        store = EventLogStore(self.ap.persistence_mgr.get_db_engine())

        # Build input summary
        input_summary = None
        input_json = None
        if event.input:
            if event.input.text:
                input_summary = event.input.text[:1000]
            input_json = {
                'text': event.input.text,
                'contents': [c.model_dump(mode='json') if hasattr(c, 'model_dump') else c for c in event.input.contents],
                'attachments': [a.model_dump(mode='json') if hasattr(a, 'model_dump') else a for a in event.input.attachments],
            }

        return await store.append_event(
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            conversation_id=event.conversation_id,
            thread_id=event.thread_id,
            actor_type=event.actor.actor_type if event.actor else None,
            actor_id=event.actor.actor_id if event.actor else None,
            actor_name=event.actor.actor_name if event.actor else None,
            subject_type=event.subject.subject_type if event.subject else None,
            subject_id=event.subject.subject_id if event.subject else None,
            input_summary=input_summary,
            input_json=input_json,
            run_id=run_id,
            runner_id=runner_id,
            event_time=datetime.datetime.fromtimestamp(event.event_time) if event.event_time else None,
        )

    async def _write_user_transcript(
        self,
        event: AgentEventEnvelope,
        event_log_id: str,
    ) -> None:
        """Write user message to Transcript.

        Args:
            event: Event envelope
            event_log_id: Event log ID
        """
        from .transcript_store import TranscriptStore
        store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())

        # Build content
        content = event.input.text if event.input else None
        content_json = None
        if event.input:
            content_json = {
                'role': 'user',
                'content': [c.model_dump(mode='json') if hasattr(c, 'model_dump') else c for c in event.input.contents] if event.input.contents else [],
            }

        # Build artifact refs
        artifact_refs = []
        if event.input and event.input.attachments:
            for a in event.input.attachments:
                artifact_refs.append(a.model_dump(mode='json') if hasattr(a, 'model_dump') else a)

        await store.append_transcript(
            transcript_id=None,  # Auto-generate
            event_id=event_log_id,
            conversation_id=event.conversation_id,
            role='user',
            content=content,
            content_json=content_json,
            artifact_refs=artifact_refs if artifact_refs else None,
            thread_id=event.thread_id,
            item_type='message',
            metadata={
                'actor_type': event.actor.actor_type if event.actor else None,
                'actor_id': event.actor.actor_id if event.actor else None,
            },
        )

    async def _handle_artifact_created(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
    ) -> dict[str, typing.Any]:
        """Handle artifact.created result - register artifact and write EventLog.

        Args:
            result_dict: Raw result dict with type='artifact.created'
            event: Event envelope
            run_id: Current run ID
            runner_id: Runner ID

        Returns:
            Artifact reference dict for Transcript

        Raises:
            RunnerProtocolError: On validation failures or registration errors
        """
        import base64
        import uuid

        from .artifact_store import ArtifactStore
        from .event_log_store import EventLogStore

        data = result_dict.get('data', {})

        # Validate run_id matches current context
        result_run_id = result_dict.get('run_id')
        if result_run_id and result_run_id != run_id:
            raise RunnerProtocolError(
                runner_id,
                f'artifact.created run_id mismatch: expected {run_id}, got {result_run_id}',
            )

        # Extract artifact fields
        artifact_id = data.get('artifact_id') or str(uuid.uuid4())
        artifact_type = data.get('artifact_type')
        if not artifact_type:
            raise RunnerProtocolError(
                runner_id,
                'artifact.created missing required field: artifact_type',
            )

        mime_type = data.get('mime_type')
        name = data.get('name')
        size_bytes = data.get('size_bytes')
        sha256 = data.get('sha256')
        metadata = data.get('metadata')
        content_base64 = data.get('content_base64')

        # Decode and validate content if provided
        content: bytes | None = None
        if content_base64:
            try:
                content = base64.b64decode(content_base64, validate=True)
            except Exception as e:
                raise RunnerProtocolError(
                    runner_id,
                    f'artifact.created invalid base64 content: {e}',
                )

            # Validate content size
            if len(content) > MAX_ARTIFACT_INLINE_BYTES:
                raise RunnerProtocolError(
                    runner_id,
                    f'artifact.created content size {len(content)} bytes exceeds limit {MAX_ARTIFACT_INLINE_BYTES} bytes',
                )

        # Register artifact via ArtifactStore
        artifact_store = ArtifactStore(self.ap.persistence_mgr.get_db_engine())
        try:
            registered_id = await artifact_store.register_artifact(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                source='runner',
                mime_type=mime_type,
                name=name,
                size_bytes=size_bytes,
                sha256=sha256,
                conversation_id=event.conversation_id,
                run_id=run_id,
                runner_id=runner_id,
                bot_id=event.bot_id,
                workspace_id=event.workspace_id,
                metadata=metadata,
                content=content,
            )
        except Exception as e:
            raise RunnerProtocolError(
                runner_id,
                f'artifact.created failed to register artifact: {e}',
            )

        # Write to EventLog
        event_log_store = EventLogStore(self.ap.persistence_mgr.get_db_engine())
        await event_log_store.append_event(
            event_id=str(uuid.uuid4()),
            event_type='artifact.created',
            source='runner',
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            conversation_id=event.conversation_id,
            thread_id=event.thread_id,
            actor_type=event.actor.actor_type if event.actor else None,
            actor_id=event.actor.actor_id if event.actor else None,
            actor_name=event.actor.actor_name if event.actor else None,
            input_summary=f'Artifact created: {artifact_type}',
            input_json={
                'artifact_id': registered_id,
                'artifact_type': artifact_type,
                'mime_type': mime_type,
                'name': name,
                'size_bytes': size_bytes,
            },
            run_id=run_id,
            runner_id=runner_id,
        )

        # Return artifact ref for Transcript
        return {
            'artifact_id': registered_id,
            'artifact_type': artifact_type,
            'mime_type': mime_type,
            'name': name,
        }

    def _merge_artifact_refs(
        self,
        pending_refs: list[dict[str, typing.Any]],
        result_dict: dict[str, typing.Any],
    ) -> list[dict[str, typing.Any]]:
        """Merge pending artifact refs with message's own refs, deduplicating by artifact_id.

        Args:
            pending_refs: Artifact refs accumulated from artifact.created events
            result_dict: Result dict that may contain message with artifact_refs

        Returns:
            Merged and deduplicated list of artifact refs
        """
        # Start with pending refs
        merged = list(pending_refs)
        seen_ids = {ref.get('artifact_id') for ref in pending_refs if ref.get('artifact_id')}

        # Extract refs from message data if present
        data = result_dict.get('data', {})
        message = data.get('message', {})
        message_refs = message.get('artifact_refs', [])

        if isinstance(message_refs, list):
            for ref in message_refs:
                if isinstance(ref, dict):
                    artifact_id = ref.get('artifact_id')
                    if artifact_id and artifact_id not in seen_ids:
                        merged.append(ref)
                        seen_ids.add(artifact_id)

        return merged

    async def _write_assistant_transcript(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
        artifact_refs: list[dict[str, typing.Any]] | None = None,
    ) -> None:
        """Write assistant message to Transcript.

        Args:
            result_dict: Result dict from runner
            event: Original event envelope
            run_id: Run ID
            runner_id: Runner ID
            artifact_refs: Optional artifact references to include
        """
        import uuid

        from .transcript_store import TranscriptStore
        store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())

        data = result_dict.get('data', {})
        message = data.get('message', {})

        # Build content
        content = None
        content_json = None

        if isinstance(message.get('content'), str):
            content = message['content']
            content_json = message
        elif isinstance(message.get('content'), list):
            # Extract text from content list
            text_parts = []
            for c in message['content']:
                if isinstance(c, dict) and c.get('type') == 'text':
                    text_parts.append(c.get('text', ''))
            content = ' '.join(text_parts) if text_parts else None
            content_json = message

        # Generate a unique event ID for assistant message
        assistant_event_id = str(uuid.uuid4())

        await store.append_transcript(
            transcript_id=str(uuid.uuid4()),
            event_id=assistant_event_id,
            conversation_id=event.conversation_id,
            role='assistant',
            content=content,
            content_json=content_json,
            artifact_refs=artifact_refs,
            thread_id=event.thread_id,
            item_type='message',
            run_id=run_id,
            runner_id=runner_id,
            metadata={
                'run_id': run_id,
                'runner_id': runner_id,
            },
        )
