"""
Unit tests for BotService.

Tests bot CRUD operations with mocked persistence and runtime managers.

Source: src/langbot/pkg/api/http/service/bot.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace
import uuid

from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.entity.persistence.bot import Bot


pytestmark = pytest.mark.asyncio


def _create_mock_bot(
    bot_uuid: str = None,
    name: str = 'Test Bot',
    description: str = 'Test Description',
    adapter: str = 'telegram',
    adapter_config: dict = None,
    enable: bool = True,
    use_pipeline_uuid: str = None,
    use_pipeline_name: str = None,
) -> Mock:
    """Helper to create mock Bot entity."""
    bot = Mock(spec=Bot)
    bot.uuid = bot_uuid or str(uuid.uuid4())
    bot.name = name
    bot.description = description
    bot.adapter = adapter
    bot.adapter_config = adapter_config or {'token': 'test_token'}
    bot.enable = enable
    bot.use_pipeline_uuid = use_pipeline_uuid
    bot.use_pipeline_name = use_pipeline_name
    bot.pipeline_routing_rules = []
    return bot


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


class TestBotServiceGetBots:
    """Tests for get_bots method."""

    async def test_get_bots_empty_list(self):
        """Returns empty list when no bots exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity, masked_columns=None: {
                'uuid': entity.uuid,
                'name': entity.name,
                'adapter': entity.adapter,
            }
        )

        service = BotService(ap)

        # Execute
        result = await service.get_bots()

        # Verify
        assert result == []

    async def test_get_bots_returns_list_with_secrets(self):
        """Returns bot list including adapter_config by default."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        bot1 = _create_mock_bot(bot_uuid='uuid-1', name='Bot 1')
        bot2 = _create_mock_bot(bot_uuid='uuid-2', name='Bot 2')

        mock_result = _create_mock_result([bot1, bot2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity, masked_columns=None: {
                'uuid': entity.uuid,
                'name': entity.name,
                'adapter': entity.adapter,
                'adapter_config': entity.adapter_config if 'adapter_config' not in (masked_columns or []) else None,
            }
        )

        service = BotService(ap)

        # Execute
        result = await service.get_bots(include_secret=True)

        # Verify
        assert len(result) == 2
        assert result[0]['name'] == 'Bot 1'
        assert result[0]['adapter_config'] is not None

    async def test_get_bots_masks_secrets(self):
        """Returns bot list without adapter_config when include_secret=False."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        bot1 = _create_mock_bot(bot_uuid='uuid-1', name='Bot 1')

        mock_result = _create_mock_result([bot1])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity, masked_columns=None: {
                'uuid': entity.uuid,
                'name': entity.name,
                'adapter': entity.adapter,
                'adapter_config': entity.adapter_config if 'adapter_config' not in (masked_columns or []) else None,
            }
        )

        service = BotService(ap)

        # Execute
        result = await service.get_bots(include_secret=False)

        # Verify - adapter_config should be masked
        assert result[0]['adapter_config'] is None


class TestBotServiceGetBot:
    """Tests for get_bot method."""

    async def test_get_bot_by_uuid_found(self):
        """Returns bot when found by UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        bot = _create_mock_bot(bot_uuid='test-uuid', name='Found Bot')
        mock_result = _create_mock_result(first_item=bot)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'test-uuid',
                'name': 'Found Bot',
                'adapter': 'telegram',
            }
        )

        service = BotService(ap)

        # Execute
        result = await service.get_bot('test-uuid')

        # Verify
        assert result is not None
        assert result['uuid'] == 'test-uuid'
        assert result['name'] == 'Found Bot'

    async def test_get_bot_by_uuid_not_found(self):
        """Returns None when bot not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result(first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = BotService(ap)

        # Execute
        result = await service.get_bot('nonexistent-uuid')

        # Verify
        assert result is None


class TestBotServiceGetRuntimeBotInfo:
    """Tests for get_runtime_bot_info method."""

    async def test_get_runtime_bot_info_bot_not_found_raises(self):
        """Raises Exception when bot not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result(first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = BotService(ap)

        # Mock get_bot to return None
        service.get_bot = AsyncMock(return_value=None)

        # Execute & Verify
        with pytest.raises(Exception, match='Bot not found'):
            await service.get_runtime_bot_info('nonexistent-uuid')

    async def test_get_runtime_bot_info_returns_webhook_for_wecom(self):
        """Returns webhook URL for wecom adapter."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'api': {
                'webhook_prefix': 'http://127.0.0.1:5300',
                'extra_webhook_prefix': 'http://extra.example.com',
            }
        }
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=None)

        bot_data = {
            'uuid': 'wecom-uuid',
            'name': 'WeCom Bot',
            'adapter': 'wecom',
            'adapter_config': {'token': 'test'},
        }

        service = BotService(ap)
        service.get_bot = AsyncMock(return_value=bot_data)

        # Execute
        result = await service.get_runtime_bot_info('wecom-uuid')

        # Verify
        assert result['adapter_runtime_values']['webhook_url'] == '/bots/wecom-uuid'
        assert result['adapter_runtime_values']['webhook_full_url'] == 'http://127.0.0.1:5300/bots/wecom-uuid'

    async def test_get_runtime_bot_info_no_webhook_for_telegram(self):
        """Returns no webhook URL for non-webhook adapters like telegram."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'api': {}}
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=None)

        bot_data = {
            'uuid': 'telegram-uuid',
            'name': 'Telegram Bot',
            'adapter': 'telegram',
            'adapter_config': {'token': 'test'},
        }

        service = BotService(ap)
        service.get_bot = AsyncMock(return_value=bot_data)

        # Execute
        result = await service.get_runtime_bot_info('telegram-uuid')

        # Verify - no webhook for telegram
        assert result['adapter_runtime_values']['webhook_url'] is None
        assert result['adapter_runtime_values']['webhook_full_url'] is None

    async def test_get_runtime_bot_info_with_runtime_bot(self):
        """Returns bot_account_id when runtime bot exists."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'api': {}}
        ap.platform_mgr = SimpleNamespace()

        # Mock runtime bot with adapter
        runtime_bot = SimpleNamespace()
        runtime_bot.adapter = SimpleNamespace()
        runtime_bot.adapter.bot_account_id = 'runtime-account-123'
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=runtime_bot)

        bot_data = {
            'uuid': 'runtime-uuid',
            'name': 'Runtime Bot',
            'adapter': 'telegram',
            'adapter_config': {},
        }

        service = BotService(ap)
        service.get_bot = AsyncMock(return_value=bot_data)

        # Execute
        result = await service.get_runtime_bot_info('runtime-uuid')

        # Verify
        assert result['adapter_runtime_values']['bot_account_id'] == 'runtime-account-123'


class TestBotServiceCreateBot:
    """Tests for create_bot method."""

    async def test_create_bot_max_limit_reached_raises(self):
        """Raises ValueError when max_bots limit reached."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'system': {
                'limitation': {
                    'max_bots': 2
                }
            }
        }
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.load_bot = AsyncMock()

        # Mock get_bots to return 2 bots already
        bot1 = _create_mock_bot(bot_uuid='uuid-1')
        bot2 = _create_mock_bot(bot_uuid='uuid-2')
        mock_result = _create_mock_result([bot1, bot2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'uuid-1', 'name': 'Bot 1'}
        )

        service = BotService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='Maximum number of bots'):
            await service.create_bot({'name': 'New Bot'})

    async def test_create_bot_no_limit(self):
        """Creates bot without limit check when max_bots=-1."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'system': {
                'limitation': {
                    'max_bots': -1  # No limit
                }
            }
        }
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.load_bot = AsyncMock()

        # Mock pipeline query
        pipeline_result = Mock()
        pipeline_result.first = Mock(return_value=None)
        # Mock bot query after insert
        bot_result = Mock()
        bot_result.first = Mock(return_value=_create_mock_bot())

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return pipeline_result  # First call: check pipeline
            elif call_count == 3:
                return Mock()  # Insert
            return bot_result  # Get bot

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'new-uuid', 'name': 'New Bot'}
        )

        service = BotService(ap)

        # Execute
        bot_uuid = await service.create_bot({'name': 'New Bot', 'adapter': 'telegram', 'adapter_config': {}})

        # Verify
        assert bot_uuid is not None
        assert len(bot_uuid) == 36  # UUID format

    async def test_create_bot_sets_default_pipeline(self):
        """Sets default pipeline when one exists."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_bots': -1}}}
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.load_bot = AsyncMock()

        # Mock default pipeline
        mock_pipeline = SimpleNamespace()
        mock_pipeline.uuid = 'default-pipeline-uuid'
        mock_pipeline.name = 'Default Pipeline'
        pipeline_result = Mock()
        pipeline_result.first = Mock(return_value=mock_pipeline)

        # Mock bot after insert
        bot_result = Mock()
        bot_result.first = Mock(return_value=_create_mock_bot())

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return pipeline_result  # Check default pipeline
            elif call_count == 2:
                return Mock()  # Insert
            return bot_result  # Get bot

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'new-uuid',
                'name': 'New Bot',
                'use_pipeline_uuid': 'default-pipeline-uuid',
                'use_pipeline_name': 'Default Pipeline',
            }
        )

        service = BotService(ap)

        # Execute
        bot_data = {'name': 'New Bot', 'adapter': 'telegram', 'adapter_config': {}}
        bot_uuid = await service.create_bot(bot_data)

        # Verify - pipeline uuid and name were set
        assert 'use_pipeline_uuid' in bot_data
        assert 'use_pipeline_name' in bot_data
        assert bot_uuid is not None  # Verify UUID was returned


class TestBotServiceUpdateBot:
    """Tests for update_bot method."""

    async def test_update_bot_removes_uuid_from_data(self):
        """Does not persist caller-provided uuid in update payload."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.remove_bot = AsyncMock()

        # Mock pipeline query - not updating pipeline
        ap.persistence_mgr.execute_async = AsyncMock()
        ap.sess_mgr = SimpleNamespace()
        ap.sess_mgr.session_list = []

        service = BotService(ap)
        service.get_bot = AsyncMock(return_value={'uuid': 'test-uuid', 'name': 'Updated'})

        # Create mock runtime bot
        runtime_bot = SimpleNamespace()
        runtime_bot.enable = False
        ap.platform_mgr.load_bot = AsyncMock(return_value=runtime_bot)

        # Execute
        update_data = {'uuid': 'should-be-removed', 'name': 'Updated Name'}
        await service.update_bot('test-uuid', update_data)

        update_params = ap.persistence_mgr.execute_async.await_args_list[0].args[0].compile().params
        assert update_params['name'] == 'Updated Name'
        assert 'should-be-removed' not in update_params.values()

    async def test_update_bot_pipeline_not_found_raises(self):
        """Raises Exception when updating with nonexistent pipeline UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Mock pipeline query returns None
        pipeline_result = Mock()
        pipeline_result.first = Mock(return_value=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=pipeline_result)

        service = BotService(ap)

        # Execute & Verify
        with pytest.raises(Exception, match='Pipeline not found'):
            await service.update_bot('test-uuid', {'use_pipeline_uuid': 'nonexistent-pipeline'})

    async def test_update_bot_sets_pipeline_name(self):
        """Sets use_pipeline_name when updating use_pipeline_uuid."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.remove_bot = AsyncMock()

        # Mock pipeline query
        mock_pipeline = SimpleNamespace()
        mock_pipeline.name = 'Updated Pipeline'
        pipeline_result = Mock()
        pipeline_result.first = Mock(return_value=mock_pipeline)

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return pipeline_result
            return Mock()

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.sess_mgr = SimpleNamespace()
        ap.sess_mgr.session_list = []

        service = BotService(ap)
        service.get_bot = AsyncMock(return_value={'uuid': 'test-uuid'})

        runtime_bot = SimpleNamespace()
        runtime_bot.enable = False
        ap.platform_mgr.load_bot = AsyncMock(return_value=runtime_bot)

        # Execute
        await service.update_bot('test-uuid', {'use_pipeline_uuid': 'pipeline-uuid'})

        update_params = ap.persistence_mgr.execute_async.await_args_list[1].args[0].compile().params
        assert update_params['use_pipeline_uuid'] == 'pipeline-uuid'
        assert update_params['use_pipeline_name'] == 'Updated Pipeline'


class TestBotServiceDeleteBot:
    """Tests for delete_bot method."""

    async def test_delete_bot_calls_remove_and_delete(self):
        """Calls both platform_mgr.remove_bot and persistence delete."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.remove_bot = AsyncMock()

        service = BotService(ap)

        # Execute
        await service.delete_bot('test-uuid')

        # Verify
        ap.platform_mgr.remove_bot.assert_called_once_with('test-uuid')
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_delete_bot_nonexistent_uuid(self):
        """Delete operation completes even for nonexistent UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.remove_bot = AsyncMock()

        service = BotService(ap)

        # Execute - should not raise
        await service.delete_bot('nonexistent-uuid')

        # Verify - both called regardless
        ap.platform_mgr.remove_bot.assert_called_once()


class TestBotServiceListEventLogs:
    """Tests for list_event_logs method."""

    async def test_list_event_logs_bot_not_found_raises(self):
        """Raises Exception when runtime bot not found."""
        # Setup
        ap = SimpleNamespace()
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=None)

        service = BotService(ap)

        # Execute & Verify
        with pytest.raises(Exception, match='Bot not found'):
            await service.list_event_logs('nonexistent-uuid', 0, 10)

    async def test_list_event_logs_returns_logs(self):
        """Returns logs from runtime bot logger."""
        # Setup
        ap = SimpleNamespace()
        ap.platform_mgr = SimpleNamespace()

        # Mock runtime bot with logger
        runtime_bot = SimpleNamespace()
        runtime_bot.logger = SimpleNamespace()
        runtime_bot.logger.get_logs = AsyncMock(return_value=(
            [SimpleNamespace(to_json=Mock(return_value={'msg': 'log1'}))],
            5
        ))
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=runtime_bot)

        service = BotService(ap)

        # Execute
        logs, total = await service.list_event_logs('bot-uuid', 0, 10)

        # Verify
        assert len(logs) == 1
        assert logs[0] == {'msg': 'log1'}
        assert total == 5


class TestBotServiceSendMessage:
    """Tests for send_message method."""

    async def test_send_message_bot_not_found_raises(self):
        """Raises Exception when bot not found."""
        # Setup
        ap = SimpleNamespace()
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=None)

        service = BotService(ap)

        # Execute & Verify
        with pytest.raises(Exception, match='Bot not found'):
            await service.send_message('nonexistent-uuid', 'group', '123', {'test': 'data'})

    async def test_send_message_invalid_message_chain_raises(self):
        """Raises Exception when message_chain_data is invalid."""
        # Setup
        ap = SimpleNamespace()
        ap.platform_mgr = SimpleNamespace()

        runtime_bot = SimpleNamespace()
        runtime_bot.adapter = SimpleNamespace()
        runtime_bot.adapter.send_message = AsyncMock()
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=runtime_bot)

        service = BotService(ap)

        # Execute & Verify - invalid format should raise
        with pytest.raises(Exception, match='Invalid message_chain format'):
            await service.send_message('bot-uuid', 'group', '123', {'invalid': 'format'})

    async def test_send_message_valid_call(self):
        """Sends message through adapter when all valid."""
        # Setup
        ap = SimpleNamespace()
        ap.platform_mgr = SimpleNamespace()

        runtime_bot = SimpleNamespace()
        runtime_bot.adapter = SimpleNamespace()
        runtime_bot.adapter.send_message = AsyncMock()
        ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=runtime_bot)

        service = BotService(ap)

        # Execute with valid message chain format
        message_chain_data = {
            'messages': [
                {'type': 'text', 'data': {'text': 'Hello'}}
            ]
        }

        # Patch the import location - the module imports inside the function
        with patch('langbot_plugin.api.entities.builtin.platform.message.MessageChain') as MockMessageChain:
            mock_chain = Mock()
            MockMessageChain.model_validate = Mock(return_value=mock_chain)
            await service.send_message('bot-uuid', 'group', '123', message_chain_data)

        # Verify adapter.send_message was called
        runtime_bot.adapter.send_message.assert_called_once_with('group', '123', mock_chain)
