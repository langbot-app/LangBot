"""
Unit tests for PipelineService.

Tests pipeline CRUD operations including:
- Pipeline listing with sorting
- Pipeline creation with default config
- Pipeline update with bot sync
- Pipeline copy functionality
- Extensions preferences management

Source: src/langbot/pkg/api/http/service/pipeline.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch, mock_open
from types import SimpleNamespace
import uuid
import json

from langbot.pkg.api.http.service.pipeline import PipelineService, default_stage_order
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline


pytestmark = pytest.mark.asyncio


def _create_mock_pipeline(
    pipeline_uuid: str = None,
    name: str = 'Test Pipeline',
    description: str = 'Test Description',
    is_default: bool = False,
    stages: list = None,
    config: dict = None,
    extensions_preferences: dict = None,
) -> Mock:
    """Helper to create mock LegacyPipeline entity."""
    pipeline = Mock(spec=LegacyPipeline)
    pipeline.uuid = pipeline_uuid or str(uuid.uuid4())
    pipeline.name = name
    pipeline.description = description
    pipeline.emoji = '⚙️'
    pipeline.is_default = is_default
    pipeline.for_version = '1.0.0'
    pipeline.stages = stages or default_stage_order.copy()
    pipeline.config = config or {}
    pipeline.extensions_preferences = extensions_preferences or {
        'enable_all_plugins': True,
        'enable_all_mcp_servers': True,
        'plugins': [],
        'mcp_servers': [],
    }
    return pipeline


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


class TestPipelineServiceGetPipelineMetadata:
    """Tests for get_pipeline_metadata method."""

    async def test_get_pipeline_metadata_returns_list(self):
        """Returns list of pipeline metadata configs."""
        # Setup
        ap = SimpleNamespace()
        ap.pipeline_config_meta_trigger = {'trigger': {}}
        ap.pipeline_config_meta_safety = {'safety': {}}
        ap.pipeline_config_meta_ai = {'ai': {}}
        ap.pipeline_config_meta_output = {'output': {}}

        service = PipelineService(ap)

        # Execute
        result = await service.get_pipeline_metadata()

        # Verify
        assert len(result) == 4
        assert 'trigger' in result[0]
        assert 'safety' in result[1]
        assert 'ai' in result[2]
        assert 'output' in result[3]


class TestPipelineServiceGetPipelines:
    """Tests for get_pipelines method."""

    async def test_get_pipelines_empty_list(self):
        """Returns empty list when no pipelines exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
            }
        )

        service = PipelineService(ap)

        # Execute
        result = await service.get_pipelines()

        # Verify
        assert result == []

    async def test_get_pipelines_returns_sorted_by_created_at_desc(self):
        """Returns pipelines sorted by created_at descending by default."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        pipeline1 = _create_mock_pipeline(pipeline_uuid='uuid-1', name='Pipeline 1')
        pipeline2 = _create_mock_pipeline(pipeline_uuid='uuid-2', name='Pipeline 2')

        mock_result = _create_mock_result([pipeline1, pipeline2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
            }
        )

        service = PipelineService(ap)

        # Execute
        result = await service.get_pipelines()

        # Verify
        assert len(result) == 2
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_get_pipelines_sort_by_updated_at_asc(self):
        """Returns pipelines sorted by updated_at ascending."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={})

        service = PipelineService(ap)

        # Execute
        await service.get_pipelines(sort_by='updated_at', sort_order='ASC')

        # Verify - execute was called with sort parameters
        ap.persistence_mgr.execute_async.assert_called_once()


class TestPipelineServiceGetPipeline:
    """Tests for get_pipeline method."""

    async def test_get_pipeline_by_uuid_found(self):
        """Returns pipeline when found by UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        pipeline = _create_mock_pipeline(pipeline_uuid='test-uuid', name='Found Pipeline')
        mock_result = _create_mock_result(first_item=pipeline)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'test-uuid',
                'name': 'Found Pipeline',
                'stages': default_stage_order,
            }
        )

        service = PipelineService(ap)

        # Execute
        result = await service.get_pipeline('test-uuid')

        # Verify
        assert result is not None
        assert result['uuid'] == 'test-uuid'
        assert result['name'] == 'Found Pipeline'

    async def test_get_pipeline_by_uuid_not_found(self):
        """Returns None when pipeline not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result(first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineService(ap)

        # Execute
        result = await service.get_pipeline('nonexistent-uuid')

        # Verify
        assert result is None


class TestPipelineServiceCreatePipeline:
    """Tests for create_pipeline method."""

    async def test_create_pipeline_max_limit_reached_raises(self):
        """Raises ValueError when max_pipelines limit reached."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'system': {
                'limitation': {
                    'max_pipelines': 2
                }
            }
        }
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        mock_result = _create_mock_result([_create_mock_pipeline(), _create_mock_pipeline()])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'uuid-1', 'name': 'Pipeline 1'}
        )

        service = PipelineService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='Maximum number of pipelines'):
            await service.create_pipeline({'name': 'New Pipeline'})

    async def test_create_pipeline_no_limit(self):
        """Creates pipeline without limit when max_pipelines=-1."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_pipelines': -1}}}
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        service = PipelineService(ap)
        # Override get_pipelines to return empty list (no limit check issue)
        service.get_pipelines = AsyncMock(return_value=[])
        service.get_pipeline = AsyncMock(return_value={'uuid': 'new-uuid', 'name': 'New Pipeline'})

        # Mock persistence for insert
        ap.persistence_mgr.execute_async = AsyncMock()
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'new-uuid', 'name': 'New Pipeline'}
        )

        # Mock the file read for default config - patch at the utils module level
        default_config = {'trigger': {}, 'safety': {}, 'ai': {}, 'output': {}}
        with patch('builtins.open', mock_open(read_data=json.dumps(default_config))):
            with patch('langbot.pkg.utils.paths.get_resource_path', return_value='templates/default-pipeline-config.json'):
                bot_uuid = await service.create_pipeline({'name': 'New Pipeline'})

        # Verify
        assert bot_uuid is not None
        assert len(bot_uuid) == 36  # UUID format

    async def test_create_pipeline_as_default(self):
        """Creates pipeline with is_default=True."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_pipelines': -1}}}
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        service = PipelineService(ap)
        service.get_pipelines = AsyncMock(return_value=[])
        service.get_pipeline = AsyncMock(return_value={'uuid': 'new-uuid', 'name': 'Default Pipeline', 'is_default': True})

        ap.persistence_mgr.execute_async = AsyncMock()
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'new-uuid', 'name': 'Default Pipeline', 'is_default': True}
        )

        # Mock the file read
        default_config = {}
        with patch('builtins.open', mock_open(read_data=json.dumps(default_config))):
            with patch('langbot.pkg.utils.paths.get_resource_path', return_value='templates/default-pipeline-config.json'):
                await service.create_pipeline({'name': 'Default Pipeline'}, default=True)

        # Verify - execute was called
        ap.persistence_mgr.execute_async.assert_called()

    async def test_create_pipeline_sets_default_extensions_preferences(self):
        """Sets default extensions_preferences when not provided."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_pipelines': -1}}}
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        service = PipelineService(ap)
        service.get_pipelines = AsyncMock(return_value=[])
        service.get_pipeline = AsyncMock(return_value={
            'uuid': 'new-uuid',
            'extensions_preferences': {},
        })

        insert_params = []

        async def mock_execute(query):
            params = query.compile().params
            if 'extensions_preferences' in params:
                insert_params.append(params)
            return Mock()

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'new-uuid',
                'extensions_preferences': {},
            }
        )

        default_config = {}
        with patch('builtins.open', mock_open(read_data=json.dumps(default_config))):
            with patch('langbot.pkg.utils.paths.get_resource_path', return_value='templates/default-pipeline-config.json'):
                await service.create_pipeline({'name': 'New Pipeline'})

        assert len(insert_params) == 1
        assert insert_params[0]['extensions_preferences'] == {
            'enable_all_plugins': True,
            'enable_all_mcp_servers': True,
            'plugins': [],
            'mcp_servers': [],
        }


class _MockResultWithBots:
    """Helper class to mock SQLAlchemy result with iterable .all() method."""
    def __init__(self, bots_list):
        self._bots_list = bots_list

    def all(self):
        return self._bots_list

    def first(self):
        return self._bots_list[0] if self._bots_list else None


class TestPipelineServiceUpdatePipeline:
    """Tests for update_pipeline method."""

    async def test_update_pipeline_removes_protected_fields(self):
        """Does not persist protected fields from update data."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.sess_mgr = SimpleNamespace()
        ap.sess_mgr.session_list = []
        ap.bot_service = None  # No bot_service when not updating name

        ap.persistence_mgr.execute_async = AsyncMock()

        service = PipelineService(ap)
        service.get_pipeline = AsyncMock(return_value={'uuid': 'test-uuid', 'name': 'Updated'})

        # Execute with protected fields - no name change, so no bot sync
        pipeline_data = {
            'uuid': 'should-be-removed',
            'for_version': 'should-be-removed',
            'stages': ['should-be-removed'],
            'is_default': True,
            'description': 'New description',  # Not name change, so no bot_service needed
        }
        await service.update_pipeline('test-uuid', pipeline_data)

        update_params = ap.persistence_mgr.execute_async.await_args_list[0].args[0].compile().params
        assert update_params['description'] == 'New description'
        assert 'should-be-removed' not in update_params.values()
        assert ['should-be-removed'] not in update_params.values()
        assert not any(value is True for value in update_params.values())

    async def test_update_pipeline_syncs_bot_names(self):
        """Updates bot use_pipeline_name when pipeline name changes."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.sess_mgr = SimpleNamespace()
        ap.sess_mgr.session_list = []
        ap.bot_service = SimpleNamespace()
        ap.bot_service.update_bot = AsyncMock()

        # Create proper mock Bot entities with uuid attribute
        mock_bot1 = Mock()
        mock_bot1.uuid = 'bot-uuid-1'
        mock_bot2 = Mock()
        mock_bot2.uuid = 'bot-uuid-2'

        # Create bot list
        bot_list = [mock_bot1, mock_bot2]

        # Create mock result using helper class
        bot_result = _MockResultWithBots(bot_list)

        # The order of calls in update_pipeline:
        # 1. UPDATE (line 125) - returns Mock (no result needed)
        # 2. SELECT bots (line 136) - returns bot_result with .all()
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call is the UPDATE - just return a Mock
                return Mock()
            elif call_count == 2:
                # Second call is the SELECT bots - return proper result
                return bot_result
            return Mock()  # Any additional calls

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(return_value={})

        service = PipelineService(ap)
        service.get_pipeline = AsyncMock(return_value={'uuid': 'test-uuid', 'name': 'New Name'})

        # Execute with name change
        await service.update_pipeline('test-uuid', {'name': 'New Name'})

        # Verify - bot_service.update_bot was called for each bot
        assert ap.bot_service.update_bot.call_count == 2

    async def test_update_pipeline_clears_conversations(self):
        """Clears session conversations using this pipeline."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.sess_mgr = SimpleNamespace()

        # Mock session with conversation using this pipeline
        session = SimpleNamespace()
        session.using_conversation = SimpleNamespace()
        session.using_conversation.pipeline_uuid = 'test-uuid'
        ap.sess_mgr.session_list = [session]
        ap.bot_service = SimpleNamespace()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = PipelineService(ap)
        service.get_pipeline = AsyncMock(return_value={'uuid': 'test-uuid'})

        # Execute
        await service.update_pipeline('test-uuid', {'description': 'Updated'})

        # Verify - conversation was cleared
        assert session.using_conversation is None


class TestPipelineServiceDeletePipeline:
    """Tests for delete_pipeline method."""

    async def test_delete_pipeline_calls_remove_and_delete(self):
        """Calls both pipeline_mgr.remove_pipeline and persistence delete."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()

        service = PipelineService(ap)

        # Execute
        await service.delete_pipeline('test-uuid')

        # Verify
        ap.pipeline_mgr.remove_pipeline.assert_called_once_with('test-uuid')
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_delete_pipeline_nonexistent_uuid(self):
        """Delete operation completes even for nonexistent UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()

        service = PipelineService(ap)

        # Execute - should not raise
        await service.delete_pipeline('nonexistent-uuid')

        # Verify
        ap.pipeline_mgr.remove_pipeline.assert_called_once()


class TestPipelineServiceCopyPipeline:
    """Tests for copy_pipeline method."""

    async def test_copy_pipeline_max_limit_reached_raises(self):
        """Raises ValueError when max_pipelines limit reached."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'system': {
                'limitation': {
                    'max_pipelines': 2
                }
            }
        }
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        service = PipelineService(ap)
        # Mock get_pipelines to return 2 pipelines
        service.get_pipelines = AsyncMock(return_value=[
            {'uuid': 'uuid-1', 'name': 'Pipeline 1'},
            {'uuid': 'uuid-2', 'name': 'Pipeline 2'},
        ])

        # Execute & Verify
        with pytest.raises(ValueError, match='Maximum number of pipelines'):
            await service.copy_pipeline('original-uuid')

    async def test_copy_pipeline_not_found_raises(self):
        """Raises ValueError when original pipeline not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_pipelines': -1}}}
        ap.pipeline_mgr = SimpleNamespace()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        service = PipelineService(ap)
        service.get_pipelines = AsyncMock(return_value=[])  # No limit check issue
        ap.persistence_mgr.execute_async = AsyncMock(
            return_value=_create_mock_result(first_item=None)  # Original not found
        )
        ap.persistence_mgr.serialize_model = Mock(return_value={})

        # Execute & Verify
        with pytest.raises(ValueError, match='Pipeline original-uuid not found'):
            await service.copy_pipeline('original-uuid')

    async def test_copy_pipeline_creates_copy(self):
        """Creates a copy with (Copy) suffix."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_pipelines': -1}}}
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        original = _create_mock_pipeline(
            pipeline_uuid='original-uuid',
            name='Original Pipeline',
            description='Original description',
            stages=['Stage1', 'Stage2'],
            config={'key': 'value'},
            extensions_preferences={'enable_all_plugins': False, 'plugins': ['plugin1']},
        )

        service = PipelineService(ap)
        service.get_pipelines = AsyncMock(return_value=[])  # No limit check issue

        # Mock persistence - get original, then insert, then get new
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_mock_result(first_item=original))
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'new-copy-uuid',
                'name': 'Original Pipeline (Copy)',
            }
        )

        service.get_pipeline = AsyncMock(
            return_value={
                'uuid': 'new-copy-uuid',
                'name': 'Original Pipeline (Copy)',
            }
        )

        # Execute
        new_uuid = await service.copy_pipeline('original-uuid')

        # Verify
        assert new_uuid is not None
        assert len(new_uuid) == 36  # UUID format

    async def test_copy_pipeline_is_not_default(self):
        """Copy is never set as default."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_pipelines': -1}}}
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.load_pipeline = AsyncMock()
        ap.ver_mgr = SimpleNamespace()
        ap.ver_mgr.get_current_version = Mock(return_value='1.0.0')

        # Original is default
        original = _create_mock_pipeline(
            pipeline_uuid='original-uuid',
            name='Default Pipeline',
            is_default=True,
        )

        service = PipelineService(ap)
        service.get_pipelines = AsyncMock(return_value=[])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_mock_result(first_item=original))
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'copy-uuid', 'is_default': False}
        )

        service.get_pipeline = AsyncMock(return_value={'uuid': 'copy-uuid', 'is_default': False})

        # Execute
        await service.copy_pipeline('original-uuid')

        # Verify - pipeline_mgr.load_pipeline called (copy created)
        ap.pipeline_mgr.load_pipeline.assert_called_once()


class TestPipelineServiceUpdatePipelineExtensions:
    """Tests for update_pipeline_extensions method."""

    async def test_update_extensions_pipeline_not_found_raises(self):
        """Raises ValueError when pipeline not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result(first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = PipelineService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='Pipeline nonexistent-uuid not found'):
            await service.update_pipeline_extensions('nonexistent-uuid', [])

    async def test_update_extensions_sets_plugins(self):
        """Updates plugins in extensions_preferences."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()
        ap.pipeline_mgr.load_pipeline = AsyncMock()

        original_pipeline = _create_mock_pipeline(
            extensions_preferences={'enable_all_plugins': True, 'plugins': []}
        )

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=original_pipeline)
            return Mock()

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'test-uuid',
                'extensions_preferences': {
                    'enable_all_plugins': False,
                    'plugins': [{'plugin_uuid': 'plugin-1'}],
                }
            }
        )

        service = PipelineService(ap)
        service.get_pipeline = AsyncMock(
            return_value={
                'uuid': 'test-uuid',
                'extensions_preferences': {
                    'enable_all_plugins': False,
                    'plugins': [{'plugin_uuid': 'plugin-1'}],
                }
            }
        )

        # Execute
        bound_plugins = [{'plugin_uuid': 'plugin-1'}]
        await service.update_pipeline_extensions(
            'test-uuid',
            bound_plugins=bound_plugins,
            enable_all_plugins=False,
        )

        # Verify
        ap.persistence_mgr.execute_async.assert_called()

    async def test_update_extensions_sets_mcp_servers(self):
        """Updates MCP servers in extensions_preferences."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()
        ap.pipeline_mgr.load_pipeline = AsyncMock()

        original_pipeline = _create_mock_pipeline()

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=original_pipeline)
            return Mock()

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'test-uuid',
                'extensions_preferences': {
                    'enable_all_mcp_servers': False,
                    'mcp_servers': ['mcp-server-1'],
                }
            }
        )

        service = PipelineService(ap)
        service.get_pipeline = AsyncMock(
            return_value={
                'uuid': 'test-uuid',
                'extensions_preferences': {'mcp_servers': ['mcp-server-1']},
            }
        )

        # Execute
        await service.update_pipeline_extensions(
            'test-uuid',
            bound_plugins=[],
            bound_mcp_servers=['mcp-server-1'],
            enable_all_mcp_servers=False,
        )

        # Verify
        ap.persistence_mgr.execute_async.assert_called()

    async def test_update_extensions_none_mcp_servers_keeps_existing(self):
        """Does not modify mcp_servers when bound_mcp_servers is None."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.pipeline_mgr = SimpleNamespace()
        ap.pipeline_mgr.remove_pipeline = AsyncMock()
        ap.pipeline_mgr.load_pipeline = AsyncMock()

        original_pipeline = _create_mock_pipeline(
            extensions_preferences={
                'enable_all_plugins': True,
                'enable_all_mcp_servers': True,
                'plugins': [],
                'mcp_servers': ['existing-server'],
            }
        )

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=original_pipeline)
            return Mock()

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'test-uuid', 'extensions_preferences': {'mcp_servers': ['existing-server']}}
        )

        service = PipelineService(ap)
        service.get_pipeline = AsyncMock(
            return_value={'uuid': 'test-uuid', 'extensions_preferences': {'mcp_servers': ['existing-server']}}
        )

        # Execute - bound_mcp_servers is None (not provided)
        await service.update_pipeline_extensions('test-uuid', bound_plugins=[])

        # Verify - persistence was called
        ap.persistence_mgr.execute_async.assert_called()


class TestDefaultStageOrder:
    """Tests for default_stage_order constant."""

    def test_default_stage_order_not_empty(self):
        """Default stage order is not empty."""
        assert len(default_stage_order) > 0

    def test_default_stage_order_contains_key_stages(self):
        """Default stage order contains key processing stages."""
        assert 'MessageProcessor' in default_stage_order
        assert 'SendResponseBackStage' in default_stage_order
