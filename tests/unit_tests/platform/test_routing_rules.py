"""RuntimeBot event binding and route observability unit tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


class TestEventRouteTrace:
    """Test structured event route trace logging."""

    @staticmethod
    def _make_bot(event_bindings: list[dict]):
        from langbot.pkg.platform.botmgr import RuntimeBot

        bot = object.__new__(RuntimeBot)
        bot.bot_entity = SimpleNamespace(uuid='bot-1', event_bindings=event_bindings)
        bot.logger = SimpleNamespace(
            info=AsyncMock(),
            warning=AsyncMock(),
            error=AsyncMock(),
        )
        return bot

    @pytest.mark.asyncio
    async def test_dispatch_no_matching_route_records_trace(self):
        """A route miss is visible as structured route trace metadata."""
        bot = self._make_bot([])

        await bot._dispatch_eba_event_to_agent(SimpleNamespace(type='platform.member.joined'), Mock())

        bot.logger.info.assert_awaited_once()
        _, kwargs = bot.logger.info.await_args
        metadata = kwargs['metadata']
        assert metadata['kind'] == 'event_route_trace'
        assert metadata['event_type'] == 'platform.member.joined'
        assert metadata['status'] == 'not_matched'
        assert metadata['failure_code'] == 'route_not_found'

    @pytest.mark.asyncio
    async def test_record_event_route_trace_includes_binding_and_target(self):
        """Trace metadata preserves binding and processor identifiers."""
        bot = self._make_bot([])

        await bot._record_event_route_trace(
            event_type='platform.member.joined',
            status='failed',
            level='warning',
            binding={
                'id': 'binding-1',
                'event_pattern': 'platform.member.*',
                'target_type': 'agent',
                'target_uuid': 'agent-1',
            },
            failure_code='processor_disabled',
            reason='Agent target is disabled',
            text='disabled',
        )

        bot.logger.warning.assert_awaited_once()
        _, kwargs = bot.logger.warning.await_args
        metadata = kwargs['metadata']
        assert metadata['binding_id'] == 'binding-1'
        assert metadata['event_pattern'] == 'platform.member.*'
        assert metadata['target_type'] == 'agent'
        assert metadata['target_uuid'] == 'agent-1'
        assert metadata['status'] == 'failed'

    @pytest.mark.asyncio
    async def test_dispatch_test_event_suppresses_agent_output_delivery(self):
        """Synthetic test dispatch runs the route but does not call the real adapter."""
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        async def fake_run(envelope, binding):
            yield provider_message.Message(role='assistant', content='test response')

        bot = self._make_bot(
            [
                {
                    'id': 'agent-binding',
                    'enabled': True,
                    'event_pattern': 'message.received',
                    'target_type': 'agent',
                    'target_uuid': 'agent-1',
                    'priority': 0,
                    'order': 0,
                }
            ]
        )
        bot.ap = SimpleNamespace(
            agent_service=SimpleNamespace(
                get_agent=AsyncMock(
                    return_value={
                        'uuid': 'agent-1',
                        'kind': 'agent',
                        'enabled': True,
                        'supported_event_patterns': ['message.received'],
                        'config': {'runner': {'id': 'runner-1'}, 'runner_config': {'runner-1': {}}},
                    }
                )
            ),
            agent_run_orchestrator=SimpleNamespace(run=fake_run),
        )
        bot.adapter = SimpleNamespace(
            bot_account_id='bot-account',
            config={},
            logger=bot.logger,
            send_message=AsyncMock(),
        )

        result = await bot.dispatch_test_event('message.received', {'chat_id': 'user-1', 'message_text': 'hello'})

        bot.adapter.send_message.assert_not_awaited()
        assert result['dispatched'] is True
        assert result['status'] == 'delivered'
        assert result['suppressed_outputs'][0]['method'] == 'send_message'

    @pytest.mark.asyncio
    async def test_dispatch_test_event_pipeline_receives_synthetic_adapter(self):
        """Pipeline route tests enqueue queries with the no-op adapter."""
        bot = self._make_bot(
            [
                {
                    'id': 'pipeline-binding',
                    'enabled': True,
                    'event_pattern': 'message.received',
                    'target_type': 'pipeline',
                    'target_uuid': 'pipeline-1',
                    'priority': 0,
                    'order': 0,
                }
            ]
        )
        bot.ap = SimpleNamespace(
            msg_aggregator=SimpleNamespace(add_message=AsyncMock()),
        )
        bot.adapter = SimpleNamespace(
            bot_account_id='bot-account',
            config={},
            logger=bot.logger,
            send_message=AsyncMock(),
        )

        result = await bot.dispatch_test_event(
            'message.received',
            {'chat_id': 'user-1', 'message_text': 'hello'},
        )

        bot.adapter.send_message.assert_not_awaited()
        bot.ap.msg_aggregator.add_message.assert_awaited_once()
        _, kwargs = bot.ap.msg_aggregator.add_message.await_args
        query_adapter = kwargs['adapter']
        assert query_adapter is not bot.adapter
        assert getattr(query_adapter, 'source') is bot.adapter
        assert result['dispatched'] is True
        assert result['status'] == 'delivered'
        assert result['suppressed_outputs'] == []

    @pytest.mark.asyncio
    async def test_dispatch_test_event_reports_unmatched_route_as_failure(self):
        """Synthetic dispatch does not report success when no saved route matches."""
        bot = self._make_bot([])
        bot.adapter = SimpleNamespace(
            bot_account_id='bot-account',
            config={},
            logger=bot.logger,
        )

        result = await bot.dispatch_test_event(
            'message.received',
            {'chat_id': 'user-1', 'message_text': 'hello'},
        )

        assert result['dispatched'] is False
        assert result['status'] == 'not_matched'
        assert result['failure_code'] == 'route_not_found'
        assert result['reason'] == 'No event route matched'

    @pytest.mark.asyncio
    async def test_synthetic_adapter_suppresses_platform_side_effect_apis(self):
        """Synthetic adapter blocks optional platform APIs that mutate external state."""
        from langbot.pkg.platform.botmgr import SyntheticRouteTestAdapter
        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        source = SimpleNamespace(
            bot_account_id='bot-account',
            config={},
            logger=Mock(),
            get_supported_apis=Mock(
                return_value=[
                    'send_message',
                    'delete_message',
                    'get_group_info',
                    'call_platform_api',
                ]
            ),
            delete_message=AsyncMock(),
            call_platform_api=AsyncMock(),
        )
        adapter = SyntheticRouteTestAdapter(source)

        await adapter.delete_message('group', 'group-1', 'message-1')
        await adapter.call_platform_api('set_title', {'name': 'New Title'})
        upload_result = await adapter.upload_file(b'data', 'test.txt')

        source.delete_message.assert_not_awaited()
        source.call_platform_api.assert_not_awaited()
        assert upload_result == 'suppressed:test.txt'
        assert [item['method'] for item in adapter.suppressed_outputs] == [
            'delete_message',
            'call_platform_api',
            'upload_file',
        ]
        assert adapter.get_supported_apis() == ['get_group_info']
        assert adapter._message_to_payload(platform_message.MessageChain([platform_message.Plain(text='ok')]))

    def test_build_test_platform_event_message_received_uses_payload(self):
        """Synthetic message events preserve common route filter fields."""
        from langbot.pkg.platform.botmgr import RuntimeBot

        event = RuntimeBot._build_test_platform_event(
            'message.received',
            {
                'chat_type': 'group',
                'chat_id': 'group-1',
                'group_name': 'QA Group',
                'user_id': 'user-1',
                'user_name': 'QA User',
                'message_text': 'hello',
            },
        )

        assert event.type == 'message.received'
        assert str(event.chat_id) == 'group-1'
        assert event.group.name == 'QA Group'
        assert event.sender.nickname == 'QA User'
        assert str(event.message_chain) == 'hello'


class TestEventLoggerMetadata:
    """Test platform EventLogger metadata compatibility."""

    @pytest.mark.asyncio
    async def test_metadata_is_serialized_without_breaking_no_throw_position(self):
        """Metadata is optional and no_throw remains the fourth positional argument."""
        from langbot.pkg.platform.logger import EventLogger

        logger = EventLogger(name='test', ap=SimpleNamespace())

        await logger.info('plain log', None, None, False)
        await logger.info(
            'route trace',
            metadata={'kind': 'event_route_trace', 'status': 'matched'},
        )

        assert logger.logs[0].to_json()['metadata'] is None
        assert logger.logs[1].to_json()['metadata'] == {
            'kind': 'event_route_trace',
            'status': 'matched',
        }


class TestRuntimeBotLifecycle:
    """Test RuntimeBot startup and shutdown lifecycle edges."""

    @pytest.mark.asyncio
    async def test_shutdown_before_run_is_idempotent(self):
        """A newly loaded Bot can be removed even before its task starts."""
        from langbot.pkg.platform.botmgr import RuntimeBot

        task_mgr = SimpleNamespace(cancel_task=Mock())
        bot = RuntimeBot(
            ap=SimpleNamespace(task_mgr=task_mgr),
            bot_entity=SimpleNamespace(enable=True),
            adapter=SimpleNamespace(kill=AsyncMock()),
            logger=Mock(),
        )

        await bot.shutdown()

        bot.adapter.kill.assert_awaited_once()
        task_mgr.cancel_task.assert_not_called()


class TestEBAEventBindings:
    """Test RuntimeBot EBA event binding helpers."""

    @staticmethod
    def _make_bot(bindings):
        from langbot.pkg.platform.botmgr import RuntimeBot

        bot = object.__new__(RuntimeBot)
        bot.bot_entity = SimpleNamespace(event_bindings=bindings)
        return bot

    def test_resolve_eba_event_binding_uses_enabled_pattern_filters_priority_and_order(self):
        """The selected binding is the first matching highest-priority binding."""
        bot = self._make_bot(
            [
                {
                    'id': 'disabled',
                    'enabled': False,
                    'event_pattern': 'platform.member.joined',
                    'target_type': 'agent',
                    'target_uuid': 'agent-disabled',
                    'priority': 100,
                    'order': 0,
                },
                {
                    'id': 'wrong-room',
                    'event_pattern': 'platform.member.joined',
                    'target_type': 'agent',
                    'target_uuid': 'agent-wrong-room',
                    'filters': [{'field': 'room.id', 'operator': 'eq', 'value': 'room-2'}],
                    'priority': 50,
                    'order': 1,
                },
                {
                    'id': 'first-high',
                    'event_pattern': 'platform.member.joined',
                    'target_type': 'agent',
                    'target_uuid': 'agent-first',
                    'filters': [{'field': 'room.id', 'operator': 'eq', 'value': 'room-1'}],
                    'priority': 10,
                    'order': 2,
                },
                {
                    'id': 'second-high',
                    'event_pattern': 'platform.member.*',
                    'target_type': 'agent',
                    'target_uuid': 'agent-second',
                    'filters': [{'field': 'room.id', 'operator': 'eq', 'value': 'room-1'}],
                    'priority': 10,
                    'order': 3,
                },
                {
                    'id': 'fallback',
                    'event_pattern': '*',
                    'target_type': 'discard',
                    'priority': 1,
                    'order': 4,
                },
            ]
        )

        selected = bot._resolve_eba_event_binding(
            {'room': {'id': 'room-1'}},
            'platform.member.joined',
        )

        assert selected['id'] == 'first-high'
        assert selected['target_uuid'] == 'agent-first'

    def test_agent_product_to_binding_projects_runner_config_and_policies(self):
        """Agent products become bot-scoped runner bindings for EBA dispatch."""
        from langbot.pkg.platform.botmgr import RuntimeBot

        binding = RuntimeBot._agent_product_to_binding(
            {
                'uuid': 'agent-1',
                'component_ref': 'plugin:test/fallback/default',
                'config': {
                    'runner': {'id': 'plugin:test/runner/default'},
                    'runner_config': {
                        'plugin:test/runner/default': {
                            'temperature': 0.2,
                            'max_tokens': 1000,
                        }
                    },
                },
            },
            {'id': 'binding-1'},
            'platform.member.joined',
            'bot-1',
        )

        assert binding is not None
        assert binding.binding_id == 'bot:bot-1:binding-1'
        assert binding.scope.scope_type == 'bot'
        assert binding.scope.scope_id == 'bot-1'
        assert binding.event_types == ['platform.member.joined']
        assert binding.runner_id == 'plugin:test/runner/default'
        assert binding.runner_config == {'temperature': 0.2, 'max_tokens': 1000}
        assert binding.delivery_policy.enable_streaming is False
        assert binding.delivery_policy.enable_reply is True
        assert binding.state_policy.state_scopes == ['conversation', 'actor', 'subject', 'runner']
        assert binding.agent_id == 'agent-1'
