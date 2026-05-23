"""Tests for artifact.created handling in orchestrator."""
import pytest
import base64
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from langbot.pkg.agent.runner.orchestrator import (
    AgentRunOrchestrator,
    MAX_ARTIFACT_INLINE_BYTES,
)
from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope, AgentBinding
from langbot.pkg.agent.runner.errors import RunnerProtocolError
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.event import ActorContext
from langbot.pkg.core import app


class TestArtifactCreatedValidation:
    """Test artifact.created validation and protocol errors."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        ap = MagicMock(spec=app.Application)
        ap.logger = MagicMock()
        ap.plugin_connector = MagicMock()
        ap.plugin_connector.is_enable_plugin = True
        ap.persistence_mgr = MagicMock()
        ap.persistence_mgr.get_db_engine = MagicMock()
        return ap

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        registry = MagicMock()
        registry.get = AsyncMock()
        return registry

    @pytest.fixture
    def mock_event(self):
        """Create mock event envelope."""
        event = MagicMock(spec=AgentEventEnvelope)
        event.event_id = str(uuid.uuid4())
        event.event_type = 'message.received'
        event.source = 'test'
        event.bot_id = str(uuid.uuid4())
        event.workspace_id = str(uuid.uuid4())
        event.conversation_id = str(uuid.uuid4())
        event.thread_id = None
        event.event_time = 1700000000
        event.actor = MagicMock(spec=ActorContext)
        event.actor.actor_type = 'user'
        event.actor.actor_id = 'user-123'
        event.actor.actor_name = 'Test User'
        event.subject = None
        event.input = MagicMock(spec=AgentInput)
        event.input.text = 'Hello'
        event.input.contents = []
        event.input.attachments = []
        return event

    @pytest.mark.asyncio
    async def test_run_id_mismatch_raises_protocol_error(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that run_id mismatch raises RunnerProtocolError."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())
        wrong_run_id = str(uuid.uuid4())

        result_dict = {
            'type': 'artifact.created',
            'run_id': wrong_run_id,
            'data': {
                'artifact_type': 'image',
            },
        }

        with pytest.raises(RunnerProtocolError) as exc_info:
            await orchestrator._handle_artifact_created(
                result_dict=result_dict,
                event=mock_event,
                run_id=run_id,
                runner_id='test-runner',
            )

        assert 'run_id mismatch' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_artifact_type_raises_protocol_error(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that missing artifact_type raises RunnerProtocolError."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())

        result_dict = {
            'type': 'artifact.created',
            'run_id': run_id,
            'data': {
                'artifact_id': str(uuid.uuid4()),
                # missing artifact_type
            },
        }

        with pytest.raises(RunnerProtocolError) as exc_info:
            await orchestrator._handle_artifact_created(
                result_dict=result_dict,
                event=mock_event,
                run_id=run_id,
                runner_id='test-runner',
            )

        assert 'missing required field' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_base64_raises_protocol_error(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that invalid base64 raises RunnerProtocolError."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())

        result_dict = {
            'type': 'artifact.created',
            'run_id': run_id,
            'data': {
                'artifact_type': 'image',
                'content_base64': '!!!invalid-base64!!!',
            },
        }

        with pytest.raises(RunnerProtocolError) as exc_info:
            await orchestrator._handle_artifact_created(
                result_dict=result_dict,
                event=mock_event,
                run_id=run_id,
                runner_id='test-runner',
            )

        assert 'invalid base64' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_oversized_content_raises_protocol_error(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that content exceeding limit raises RunnerProtocolError."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())

        # Create content larger than limit
        oversized_content = b'x' * (MAX_ARTIFACT_INLINE_BYTES + 1)
        content_base64 = base64.b64encode(oversized_content).decode('utf-8')

        result_dict = {
            'type': 'artifact.created',
            'run_id': run_id,
            'data': {
                'artifact_type': 'image',
                'content_base64': content_base64,
            },
        }

        with pytest.raises(RunnerProtocolError) as exc_info:
            await orchestrator._handle_artifact_created(
                result_dict=result_dict,
                event=mock_event,
                run_id=run_id,
                runner_id='test-runner',
            )

        assert 'exceeds limit' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_artifact_store_failure_raises_protocol_error(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that ArtifactStore failure raises RunnerProtocolError."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())

        result_dict = {
            'type': 'artifact.created',
            'run_id': run_id,
            'data': {
                'artifact_type': 'image',
            },
        }

        with patch('langbot.pkg.agent.runner.artifact_store.ArtifactStore') as MockArtifactStore:
            mock_artifact_store = MagicMock()
            mock_artifact_store.register_artifact = AsyncMock(
                side_effect=Exception('DB connection failed')
            )
            MockArtifactStore.return_value = mock_artifact_store

            with pytest.raises(RunnerProtocolError) as exc_info:
                await orchestrator._handle_artifact_created(
                    result_dict=result_dict,
                    event=mock_event,
                    run_id=run_id,
                    runner_id='test-runner',
                )

            assert 'failed to register artifact' in str(exc_info.value)


class TestArtifactCreatedSuccess:
    """Test successful artifact.created handling."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        ap = MagicMock(spec=app.Application)
        ap.logger = MagicMock()
        ap.plugin_connector = MagicMock()
        ap.plugin_connector.is_enable_plugin = True
        ap.persistence_mgr = MagicMock()
        ap.persistence_mgr.get_db_engine = MagicMock()
        return ap

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        registry = MagicMock()
        registry.get = AsyncMock()
        return registry

    @pytest.fixture
    def mock_event(self):
        """Create mock event envelope."""
        event = MagicMock(spec=AgentEventEnvelope)
        event.event_id = str(uuid.uuid4())
        event.event_type = 'message.received'
        event.source = 'test'
        event.bot_id = str(uuid.uuid4())
        event.workspace_id = str(uuid.uuid4())
        event.conversation_id = str(uuid.uuid4())
        event.thread_id = None
        event.event_time = 1700000000
        event.actor = MagicMock(spec=ActorContext)
        event.actor.actor_type = 'user'
        event.actor.actor_id = 'user-123'
        event.actor.actor_name = 'Test User'
        event.subject = None
        return event

    @pytest.mark.asyncio
    async def test_handle_artifact_created_registers_artifact(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that artifact.created registers artifact via ArtifactStore."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())
        runner_id = 'test-runner'

        # Create artifact.created result
        content = b'test artifact content'
        content_base64 = base64.b64encode(content).decode('utf-8')
        artifact_id = str(uuid.uuid4())

        result_dict = {
            'type': 'artifact.created',
            'run_id': run_id,
            'data': {
                'artifact_id': artifact_id,
                'artifact_type': 'image',
                'mime_type': 'image/png',
                'name': 'test.png',
                'size_bytes': len(content),
                'content_base64': content_base64,
            },
        }

        with patch('langbot.pkg.agent.runner.artifact_store.ArtifactStore') as MockArtifactStore:
            with patch('langbot.pkg.agent.runner.event_log_store.EventLogStore') as MockEventLogStore:
                mock_artifact_store = MagicMock()
                mock_artifact_store.register_artifact = AsyncMock(return_value=artifact_id)
                MockArtifactStore.return_value = mock_artifact_store

                mock_event_log_store = MagicMock()
                mock_event_log_store.append_event = AsyncMock()
                MockEventLogStore.return_value = mock_event_log_store

                # Call _handle_artifact_created
                result = await orchestrator._handle_artifact_created(
                    result_dict=result_dict,
                    event=mock_event,
                    run_id=run_id,
                    runner_id=runner_id,
                )

                # Verify artifact was registered
                mock_artifact_store.register_artifact.assert_called_once()
                call_kwargs = mock_artifact_store.register_artifact.call_args.kwargs
                assert call_kwargs['artifact_id'] == artifact_id
                assert call_kwargs['artifact_type'] == 'image'
                assert call_kwargs['mime_type'] == 'image/png'
                assert call_kwargs['name'] == 'test.png'
                assert call_kwargs['content'] == content
                assert call_kwargs['conversation_id'] == mock_event.conversation_id
                assert call_kwargs['run_id'] == run_id
                assert call_kwargs['runner_id'] == runner_id

                # Verify EventLog was written
                mock_event_log_store.append_event.assert_called_once()
                event_kwargs = mock_event_log_store.append_event.call_args.kwargs
                assert event_kwargs['event_type'] == 'artifact.created'
                assert event_kwargs['run_id'] == run_id

                # Verify artifact ref returned
                assert result is not None
                assert result['artifact_id'] == artifact_id
                assert result['artifact_type'] == 'image'

    @pytest.mark.asyncio
    async def test_handle_artifact_created_metadata_only(
        self, mock_app, mock_registry, mock_event
    ):
        """Test artifact.created without content (metadata-only)."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())

        result_dict = {
            'type': 'artifact.created',
            'run_id': run_id,
            'data': {
                'artifact_id': artifact_id,
                'artifact_type': 'file',
                'mime_type': 'application/pdf',
                'name': 'document.pdf',
                'size_bytes': 1024,
                'sha256': 'abc123',
                'metadata': {'source': 'external'},
            },
        }

        with patch('langbot.pkg.agent.runner.artifact_store.ArtifactStore') as MockArtifactStore:
            with patch('langbot.pkg.agent.runner.event_log_store.EventLogStore') as MockEventLogStore:
                mock_artifact_store = MagicMock()
                mock_artifact_store.register_artifact = AsyncMock(return_value=artifact_id)
                MockArtifactStore.return_value = mock_artifact_store

                mock_event_log_store = MagicMock()
                mock_event_log_store.append_event = AsyncMock()
                MockEventLogStore.return_value = mock_event_log_store

                result = await orchestrator._handle_artifact_created(
                    result_dict=result_dict,
                    event=mock_event,
                    run_id=run_id,
                    runner_id='test-runner',
                )

                # Verify artifact was registered without content
                call_kwargs = mock_artifact_store.register_artifact.call_args.kwargs
                assert call_kwargs['content'] is None
                assert call_kwargs['sha256'] == 'abc123'
                assert call_kwargs['metadata'] == {'source': 'external'}

                assert result is not None
                assert result['artifact_id'] == artifact_id


class TestArtifactRefsLifecycle:
    """Test artifact refs lifecycle in event-first flow."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        ap = MagicMock(spec=app.Application)
        ap.logger = MagicMock()
        ap.plugin_connector = MagicMock()
        ap.plugin_connector.is_enable_plugin = True
        ap.persistence_mgr = MagicMock()
        ap.persistence_mgr.get_db_engine = MagicMock()
        return ap

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        registry = MagicMock()
        registry.get = AsyncMock()
        return registry

    def test_merge_artifact_refs_deduplicates(
        self, mock_app, mock_registry
    ):
        """Test that _merge_artifact_refs deduplicates by artifact_id."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)

        pending_refs = [
            {'artifact_id': 'artifact-1', 'artifact_type': 'image'},
            {'artifact_id': 'artifact-2', 'artifact_type': 'file'},
        ]

        result_dict = {
            'type': 'message.completed',
            'data': {
                'message': {
                    'content': 'Hello',
                    'artifact_refs': [
                        {'artifact_id': 'artifact-2', 'artifact_type': 'file'},  # duplicate
                        {'artifact_id': 'artifact-3', 'artifact_type': 'voice'},
                    ],
                },
            },
        }

        merged = orchestrator._merge_artifact_refs(pending_refs, result_dict)

        # Should have 3 unique artifacts
        assert len(merged) == 3
        artifact_ids = {ref['artifact_id'] for ref in merged}
        assert artifact_ids == {'artifact-1', 'artifact-2', 'artifact-3'}

    def test_merge_artifact_refs_empty_pending(
        self, mock_app, mock_registry
    ):
        """Test merge with empty pending refs."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)

        pending_refs = []

        result_dict = {
            'type': 'message.completed',
            'data': {
                'message': {
                    'content': 'Hello',
                    'artifact_refs': [
                        {'artifact_id': 'artifact-1', 'artifact_type': 'image'},
                    ],
                },
            },
        }

        merged = orchestrator._merge_artifact_refs(pending_refs, result_dict)

        assert len(merged) == 1
        assert merged[0]['artifact_id'] == 'artifact-1'

    def test_merge_artifact_refs_empty_message_refs(
        self, mock_app, mock_registry
    ):
        """Test merge with no message artifact_refs."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)

        pending_refs = [
            {'artifact_id': 'artifact-1', 'artifact_type': 'image'},
        ]

        result_dict = {
            'type': 'message.completed',
            'data': {
                'message': {
                    'content': 'Hello',
                    # no artifact_refs
                },
            },
        }

        merged = orchestrator._merge_artifact_refs(pending_refs, result_dict)

        assert len(merged) == 1
        assert merged[0]['artifact_id'] == 'artifact-1'


class TestResultNormalizerArtifactCreated:
    """Test ResultNormalizer handling of artifact.created."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        ap = MagicMock(spec=app.Application)
        ap.logger = MagicMock()
        return ap

    @pytest.fixture
    def mock_descriptor(self):
        """Create mock descriptor."""
        descriptor = MagicMock()
        descriptor.id = 'test-runner'
        return descriptor

    @pytest.mark.asyncio
    async def test_normalize_artifact_created_returns_none(
        self, mock_app, mock_descriptor
    ):
        """Test that artifact.created is consumed (returns None)."""
        from langbot.pkg.agent.runner.result_normalizer import AgentResultNormalizer

        normalizer = AgentResultNormalizer(mock_app)

        result_dict = {
            'type': 'artifact.created',
            'run_id': 'test-run-id',
            'data': {
                'artifact_id': 'artifact-123',
                'artifact_type': 'image',
            },
        }

        result = await normalizer.normalize(result_dict, mock_descriptor)

        # Should return None (consumed)
        assert result is None

        # Debug log should be written
        mock_app.logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_normalize_unknown_type_warning(
        self, mock_app, mock_descriptor
    ):
        """Test that unknown result types still produce warnings."""
        from langbot.pkg.agent.runner.result_normalizer import AgentResultNormalizer

        normalizer = AgentResultNormalizer(mock_app)

        result_dict = {
            'type': 'unknown.type',
            'data': {},
        }

        result = await normalizer.normalize(result_dict, mock_descriptor)

        # Should return None
        assert result is None

        # Warning should be logged
        mock_app.logger.warning.assert_called()


class TestEventLogTranscriptIntegration:
    """Test EventLog and Transcript integration with artifact.created."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        ap = MagicMock(spec=app.Application)
        ap.logger = MagicMock()
        ap.plugin_connector = MagicMock()
        ap.plugin_connector.is_enable_plugin = True
        ap.persistence_mgr = MagicMock()
        ap.persistence_mgr.get_db_engine = MagicMock()
        return ap

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        registry = MagicMock()
        registry.get = AsyncMock()
        return registry

    @pytest.fixture
    def mock_event(self):
        """Create mock event envelope."""
        event = MagicMock(spec=AgentEventEnvelope)
        event.event_id = str(uuid.uuid4())
        event.event_type = 'message.received'
        event.source = 'test'
        event.bot_id = str(uuid.uuid4())
        event.workspace_id = str(uuid.uuid4())
        event.conversation_id = str(uuid.uuid4())
        event.thread_id = None
        event.event_time = 1700000000
        event.actor = MagicMock(spec=ActorContext)
        event.actor.actor_type = 'user'
        event.actor.actor_id = 'user-123'
        event.actor.actor_name = 'Test User'
        event.subject = None
        return event

    @pytest.mark.asyncio
    async def test_event_log_written_with_correct_event_type(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that EventLog is written with event_type='artifact.created'."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())

        result_dict = {
            'type': 'artifact.created',
            'run_id': run_id,
            'data': {
                'artifact_id': artifact_id,
                'artifact_type': 'image',
            },
        }

        with patch('langbot.pkg.agent.runner.artifact_store.ArtifactStore') as MockArtifactStore:
            with patch('langbot.pkg.agent.runner.event_log_store.EventLogStore') as MockEventLogStore:
                mock_artifact_store = MagicMock()
                mock_artifact_store.register_artifact = AsyncMock(return_value=artifact_id)
                MockArtifactStore.return_value = mock_artifact_store

                mock_event_log_store = MagicMock()
                mock_event_log_store.append_event = AsyncMock()
                MockEventLogStore.return_value = mock_event_log_store

                await orchestrator._handle_artifact_created(
                    result_dict=result_dict,
                    event=mock_event,
                    run_id=run_id,
                    runner_id='test-runner',
                )

                # Verify EventLog.append_event was called with correct event_type
                mock_event_log_store.append_event.assert_called_once()
                call_kwargs = mock_event_log_store.append_event.call_args.kwargs
                assert call_kwargs['event_type'] == 'artifact.created'
                assert call_kwargs['source'] == 'runner'
                assert call_kwargs['conversation_id'] == mock_event.conversation_id
                assert call_kwargs['run_id'] == run_id

    @pytest.mark.asyncio
    async def test_assistant_transcript_receives_artifact_refs(
        self, mock_app, mock_registry, mock_event
    ):
        """Test that assistant transcript receives artifact refs from artifact.created."""
        orchestrator = AgentRunOrchestrator(mock_app, mock_registry)
        run_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())

        # Create pending artifact refs
        pending_refs = [
            {'artifact_id': artifact_id, 'artifact_type': 'image', 'mime_type': 'image/png'},
        ]

        result_dict = {
            'type': 'message.completed',
            'data': {
                'message': {
                    'content': 'Here is your image',
                },
            },
        }

        with patch('langbot.pkg.agent.runner.transcript_store.TranscriptStore') as MockTranscriptStore:
            mock_transcript_store = MagicMock()
            mock_transcript_store.append_transcript = AsyncMock()
            MockTranscriptStore.return_value = mock_transcript_store

            await orchestrator._write_assistant_transcript(
                result_dict=result_dict,
                event=mock_event,
                run_id=run_id,
                runner_id='test-runner',
                artifact_refs=pending_refs,
            )

            # Verify transcript was written with artifact_refs
            mock_transcript_store.append_transcript.assert_called_once()
            call_kwargs = mock_transcript_store.append_transcript.call_args.kwargs
            assert call_kwargs['artifact_refs'] == pending_refs
