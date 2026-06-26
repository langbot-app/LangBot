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


def _compiled_update_values(statement):
    """Return update values without SQLAlchemy WHERE bind params."""
    return {
        key: value
        for key, value in statement.compile().params.items()
        if not key.startswith('uuid_')
    }


def _create_mock_discover(adapter_webhook_flags: dict[str, bool] = None):
    """Create mock ComponentDiscoveryEngine exposing MessagePlatformAdapter manifests.

    adapter_webhook_flags maps adapter name -> whether its manifest declares a
    webhook-url config item (mirrors _adapter_declares_webhook_url's lookup).
    """
    components = []
    for name, has_webhook in (adapter_webhook_flags or {}).items():
        component = SimpleNamespace()
        component.metadata = SimpleNamespace(name=name)
        component.spec = {'config': ([{'name': 'webhook_url', 'type': 'webhook-url'}] if has_webhook else [])}
        components.append(component)
    discover = SimpleNamespace()
    discover.get_components_by_kind = Mock(return_value=components)
    return discover


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
        ap.discover = _create_mock_discover({'wecom': True})

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
        ap.discover = _create_mock_discover({'telegram': False})

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
        ap.discover = _create_mock_discover({'telegram': False})

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
        ap.instance_config.data = {'system': {'limitation': {'max_bots': 2}}}
        ap.platform_mgr = SimpleNamespace()
        ap.platform_mgr.load_bot = AsyncMock()

        # Mock get_bots to return 2 bots already
        bot1 = _create_mock_bot(bot_uuid='uuid-1')
        bot2 = _create_mock_bot(bot_uuid='uuid-2')
        mock_result = _create_mock_result([bot1, bot2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'uuid-1', 'name': 'Bot 1'})

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
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'new-uuid', 'name': 'New Bot'})

        service = BotService(ap)

        # Execute
        bot_uuid = await service.create_bot({'name': 'New Bot', 'adapter': 'telegram', 'adapter_config': {}})

        # Verify
        assert bot_uuid is not None
        assert len(bot_uuid) == 36  # UUID format


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


class TestBotServiceEventBindings:
    """Tests for EBA event binding validation and persistence."""

    async def test_normalize_event_bindings_validates_targets_and_preserves_order(self):
        """Valid bindings are normalized with stable order and target data."""
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(
            side_effect=[
                _create_mock_result(first_item=SimpleNamespace(uuid='pipeline-1')),
                _create_mock_result(
                    first_item=SimpleNamespace(
                        uuid='agent-1',
                        supported_event_patterns=['platform.member.*'],
                    )
                ),
            ]
        )
        service = BotService(ap)

        normalized = await service._normalize_event_bindings(
            [
                {
                    'event_pattern': ' message.received ',
                    'target_type': 'pipeline',
                    'target_uuid': ' pipeline-1 ',
                    'filters': [{'field': 'sender.id', 'operator': 'eq', 'value': '1000'}],
                    'priority': '5',
                    'enabled': False,
                    'description': 'Route message events',
                },
                {
                    'id': 'agent-binding',
                    'event_pattern': 'platform.member.joined',
                    'target_type': 'agent',
                    'target_uuid': 'agent-1',
                    'priority': 7,
                },
                {
                    'event_pattern': 'platform.member.left',
                    'target_type': 'discard',
                    'target_uuid': 'ignored-target',
                },
            ]
        )

        uuid.UUID(normalized[0]['id'])
        assert normalized == [
            {
                'id': normalized[0]['id'],
                'event_pattern': 'message.received',
                'target_type': 'pipeline',
                'target_uuid': 'pipeline-1',
                'filters': [{'field': 'sender.id', 'operator': 'eq', 'value': '1000'}],
                'priority': 5,
                'enabled': False,
                'description': 'Route message events',
                'order': 0,
            },
            {
                'id': 'agent-binding',
                'event_pattern': 'platform.member.joined',
                'target_type': 'agent',
                'target_uuid': 'agent-1',
                'filters': [],
                'priority': 7,
                'enabled': True,
                'description': '',
                'order': 1,
            },
            {
                'id': normalized[2]['id'],
                'event_pattern': 'platform.member.left',
                'target_type': 'discard',
                'target_uuid': '',
                'filters': [],
                'priority': 0,
                'enabled': True,
                'description': '',
                'order': 2,
            },
        ]

    async def test_normalize_event_bindings_rejects_pipeline_for_non_message_event(self):
        """Pipeline targets are limited to message events."""
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace(execute_async=AsyncMock())
        service = BotService(ap)

        with pytest.raises(ValueError, match='Pipeline can only be bound to message events'):
            await service._normalize_event_bindings(
                [
                    {
                        'event_pattern': 'platform.member.joined',
                        'target_type': 'pipeline',
                        'target_uuid': 'pipeline-1',
                    }
                ]
            )

        ap.persistence_mgr.execute_async.assert_not_awaited()

    @pytest.mark.parametrize(
        ('agent', 'error'),
        [
            (None, 'Agent not found'),
            (
                SimpleNamespace(uuid='agent-1', supported_event_patterns=['message.*']),
                'Agent does not support this event pattern',
            ),
        ],
    )
    async def test_normalize_event_bindings_rejects_invalid_agent_target(self, agent, error):
        """Agent targets must exist and support the requested event pattern."""
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace(
            execute_async=AsyncMock(return_value=_create_mock_result(first_item=agent))
        )
        service = BotService(ap)

        with pytest.raises(ValueError, match=error):
            await service._normalize_event_bindings(
                [
                    {
                        'event_pattern': 'platform.member.joined',
                        'target_type': 'agent',
                        'target_uuid': 'agent-1',
                    }
                ]
            )

    async def test_update_bot_persists_normalized_event_bindings_and_reloads_runtime_bot(self):
        """update_bot stores normalized bindings before reloading the runtime bot."""
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(
            side_effect=[
                _create_mock_result(
                    first_item=SimpleNamespace(
                        uuid='agent-1',
                        supported_event_patterns=['platform.member.*'],
                    )
                ),
                Mock(),
            ]
        )
        runtime_bot = SimpleNamespace(enable=True, run=AsyncMock())
        loaded_bot = {'uuid': 'bot-1', 'name': 'Bot with bindings'}
        ap.platform_mgr = SimpleNamespace(
            remove_bot=AsyncMock(),
            load_bot=AsyncMock(return_value=runtime_bot),
        )
        bot_session = SimpleNamespace(using_conversation=SimpleNamespace(bot_uuid='bot-1'))
        other_session = SimpleNamespace(using_conversation=SimpleNamespace(bot_uuid='other-bot'))
        ap.sess_mgr = SimpleNamespace(session_list=[bot_session, other_session])
        service = BotService(ap)
        service.get_bot = AsyncMock(return_value=loaded_bot)

        await service.update_bot(
            'bot-1',
            {
                'event_bindings': [
                    {
                        'id': 'binding-1',
                        'event_pattern': 'platform.member.joined',
                        'target_type': 'agent',
                        'target_uuid': 'agent-1',
                        'priority': '9',
                    }
                ]
            },
        )

        update_values = _compiled_update_values(ap.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert update_values['event_bindings'] == [
            {
                'id': 'binding-1',
                'event_pattern': 'platform.member.joined',
                'target_type': 'agent',
                'target_uuid': 'agent-1',
                'filters': [],
                'priority': 9,
                'enabled': True,
                'description': '',
                'order': 0,
            }
        ]
        ap.platform_mgr.remove_bot.assert_awaited_once_with('bot-1')
        service.get_bot.assert_awaited_once_with('bot-1')
        ap.platform_mgr.load_bot.assert_awaited_once_with(loaded_bot)
        runtime_bot.run.assert_awaited_once()
        assert bot_session.using_conversation is None
        assert other_session.using_conversation.bot_uuid == 'other-bot'


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
        runtime_bot.logger.get_logs = AsyncMock(
            return_value=([SimpleNamespace(to_json=Mock(return_value={'msg': 'log1'}))], 5)
        )
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
        message_chain_data = {'messages': [{'type': 'text', 'data': {'text': 'Hello'}}]}

        # Patch the import location - the module imports inside the function
        with patch('langbot_plugin.api.entities.builtin.platform.message.MessageChain') as MockMessageChain:
            mock_chain = Mock()
            MockMessageChain.model_validate = Mock(return_value=mock_chain)
            await service.send_message('bot-uuid', 'group', '123', message_chain_data)

        # Verify adapter.send_message was called
        runtime_bot.adapter.send_message.assert_called_once_with('group', '123', mock_chain)
