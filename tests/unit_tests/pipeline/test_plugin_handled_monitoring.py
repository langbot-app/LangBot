"""Messages taken over by plugins stay visible in monitoring (LANG-320)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from langbot.pkg.pipeline import plugin_diagnostics
from langbot.pkg.pipeline.monitoring_helper import (
    HANDLED_BY_VAR,
    ORIGIN_VAR,
    PLUGIN_ATTRIBUTION_VAR,
    MonitoringHelper,
    attribute_to_origin,
    mark_plugin_handled,
    monitoring_bot_id,
    monitoring_pipeline_id,
    monitoring_session_id,
)
from langbot.pkg.pipeline.pool import get_query_execution_context
from tests.unit_tests.plugin.test_handler_actions import make_handler
from tests.utils.plugin_installations import installed_legacy_plugin  # noqa: F401


def _event_ctx(response_sources=None, emitted_plugins=None):
    event_ctx = SimpleNamespace()
    if response_sources is not None:
        event_ctx._response_sources = response_sources
    event_ctx._emitted_plugins = emitted_plugins or []
    return event_ctx


def _emitted(author: str, name: str) -> dict:
    return {'manifest': {'metadata': {'author': author, 'name': name}}}


def _monitoring_service():
    return SimpleNamespace(
        record_message=AsyncMock(return_value='plugin-message'),
        record_error=AsyncMock(),
        record_llm_call=AsyncMock(),
        update_message_status=AsyncMock(),
    )


class TestPreventDefaultAttribution:
    def test_runtime_reported_source_wins(self):
        event_ctx = _event_ctx(
            response_sources=[
                {'kind': 'reply_message_chain', 'plugin': {'author': 'a', 'name': 'replier'}},
                {'kind': 'prevent_default', 'plugin': {'author': 'a', 'name': 'taker'}},
            ],
            emitted_plugins=[_emitted('a', 'replier'), _emitted('a', 'taker')],
        )
        assert plugin_diagnostics.get_prevent_default_plugin(event_ctx) == {'author': 'a', 'name': 'taker'}

    def test_legacy_runtime_with_single_emitted_plugin_is_attributed(self):
        event_ctx = _event_ctx(response_sources=[], emitted_plugins=[_emitted('a', 'only')])
        assert plugin_diagnostics.get_prevent_default_plugin(event_ctx) == {'author': 'a', 'name': 'only'}

    def test_ambiguous_legacy_runtime_is_unknown(self, sample_query):
        event_ctx = _event_ctx(response_sources=[], emitted_plugins=[_emitted('a', 'x'), _emitted('a', 'y')])
        assert plugin_diagnostics.get_prevent_default_plugin(event_ctx) is None
        mark_plugin_handled(sample_query, event_ctx)
        assert sample_query.variables[HANDLED_BY_VAR] == 'plugin:unknown'

    def test_reply_attribution_ignores_prevent_default_sources(self):
        sources = plugin_diagnostics._build_plugin_sources(
            [{'kind': 'prevent_default', 'plugin': {'author': 'a', 'name': 'taker'}}], None, 'event'
        )
        assert sources == []


class TestFinishQuery:
    @pytest.mark.asyncio
    async def test_plugin_handled_message_clears_runner_and_records_handler(self, sample_query):
        service = _monitoring_service()
        ap = SimpleNamespace(monitoring_service=service, logger=Mock())
        mark_plugin_handled(
            sample_query,
            _event_ctx(response_sources=[{'kind': 'prevent_default', 'plugin': {'author': 'a', 'name': 'waifu'}}]),
        )

        await MonitoringHelper.finish_query(ap, sample_query, 'user-message', 'success')

        service.update_message_status.assert_awaited_once_with(
            get_query_execution_context(sample_query),
            message_id='user-message',
            status='success',
            level='info',
            handled_by='plugin:a/waifu',
            clear_runner_name=True,
        )

    @pytest.mark.asyncio
    async def test_runner_handled_message_keeps_runner(self, sample_query):
        service = _monitoring_service()
        ap = SimpleNamespace(monitoring_service=service, logger=Mock())
        sample_query.variables[HANDLED_BY_VAR] = 'runner:plugin:langbot-team/LocalAgent/default'

        await MonitoringHelper.finish_query(ap, sample_query, 'user-message', 'success')

        kwargs = service.update_message_status.await_args.kwargs
        assert kwargs['handled_by'] == 'runner:plugin:langbot-team/LocalAgent/default'
        assert kwargs['clear_runner_name'] is False

    @pytest.mark.asyncio
    async def test_unattributed_message_keeps_the_legacy_update(self, sample_query):
        service = _monitoring_service()
        ap = SimpleNamespace(monitoring_service=service, logger=Mock())

        await MonitoringHelper.finish_query(ap, sample_query, 'user-message', 'error')

        service.update_message_status.assert_awaited_once_with(
            get_query_execution_context(sample_query), message_id='user-message', status='error', level='error'
        )


class TestOriginAttribution:
    def test_plugin_query_inherits_monitoring_identity_only(self, sample_query):
        sample_query.variables.update(
            {
                '_monitoring_message_id': 'user-message',
                '_monitoring_bot_name': 'Bot',
                '_monitoring_pipeline_name': 'Pipeline',
                '_pipeline_bound_plugins': ['secret/plugin'],
            }
        )
        plugin_query = SimpleNamespace(
            bot_uuid=None,
            pipeline_uuid=None,
            variables={PLUGIN_ATTRIBUTION_VAR: 'a/waifu', '_monitoring_pipeline_name': 'plugin:a/waifu'},
        )

        attribute_to_origin(plugin_query, sample_query)

        assert plugin_query.variables['_monitoring_message_id'] == 'user-message'
        assert plugin_query.variables['_monitoring_pipeline_name'] == 'Pipeline'
        assert '_pipeline_bound_plugins' not in plugin_query.variables
        assert plugin_query.variables[ORIGIN_VAR]['pipeline_id'] == 'test-pipeline-uuid'
        # The plugin Query itself gains no pipeline/bot authority.
        assert plugin_query.bot_uuid is None and plugin_query.pipeline_uuid is None
        assert monitoring_bot_id(plugin_query) == 'test-bot-uuid'
        assert monitoring_pipeline_id(plugin_query) == 'test-pipeline-uuid'
        assert monitoring_session_id(plugin_query) == monitoring_session_id(sample_query)


class TestPluginReplyRecording:
    @pytest.mark.asyncio
    async def test_reply_is_recorded_as_child_of_the_user_message(self, sample_query, sample_message_chain):
        service = _monitoring_service()
        ap = SimpleNamespace(monitoring_service=service, logger=Mock())
        sample_query.variables.update(
            {'_monitoring_message_id': 'user-message', '_monitoring_bot_name': 'Bot', '_monitoring_pipeline_name': 'P'}
        )

        result = await MonitoringHelper.record_plugin_reply(ap, sample_query, 'plugin:a/waifu', sample_message_chain)

        assert result == 'plugin-message'
        kwargs = service.record_message.await_args.kwargs
        assert kwargs['role'] == 'assistant'
        assert kwargs['handled_by'] == 'plugin:a/waifu'
        assert kwargs['parent_message_id'] == 'user-message'
        assert kwargs['runner_name'] is None
        assert kwargs['status'] == 'success'
        assert kwargs['session_id'] == monitoring_session_id(sample_query)
        service.record_error.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failed_reply_records_an_error(self, sample_query, sample_message_chain):
        service = _monitoring_service()
        ap = SimpleNamespace(monitoring_service=service, logger=Mock())

        await MonitoringHelper.record_plugin_reply(
            ap, sample_query, 'plugin:a/waifu', sample_message_chain, error=RuntimeError('CDN upload failed')
        )

        assert service.record_message.await_args.kwargs['status'] == 'error'
        error_kwargs = service.record_error.await_args.kwargs
        assert error_kwargs['error_type'] == 'PluginReplyError'
        assert 'plugin:a/waifu' in error_kwargs['error_message']
        assert 'CDN upload failed' in error_kwargs['error_message']
        assert error_kwargs['message_id'] == 'plugin-message'

    @pytest.mark.asyncio
    async def test_monitoring_failure_never_breaks_delivery(self, sample_query, sample_message_chain):
        service = _monitoring_service()
        service.record_message.side_effect = RuntimeError('database down')
        logger = Mock()
        ap = SimpleNamespace(monitoring_service=service, logger=logger)

        assert await MonitoringHelper.record_plugin_reply(ap, sample_query, 'plugin:a/b', sample_message_chain) == ''
        logger.error.assert_called_once()


def _serve_query(app, query, query_uuid='query-1'):
    """Make the handler resolve ``query_uuid`` to ``query`` in the test Workspace."""
    for field, value in (
        ('instance_uuid', 'instance-a'),
        ('workspace_uuid', 'workspace-a'),
        ('placement_generation', 1),
    ):
        object.__setattr__(query, field, value)
    app.query_pool.get_query = AsyncMock(
        side_effect=lambda workspace_uuid, uuid: query
        if (workspace_uuid, uuid) == ('workspace-a', query_uuid)
        else None
    )


def _handler_app(service):
    app = Mock()
    app.logger = Mock()
    app.monitoring_service = service
    app.query_pool = Mock()
    app.query_pool.cached_queries = {}
    app._test_plugin_identity = 'a/waifu'
    return app


@pytest.mark.usefixtures('installed_legacy_plugin')
class TestPluginActions:
    @pytest.mark.asyncio
    async def test_ctx_reply_is_delivered_and_recorded(self, sample_query):
        service = _monitoring_service()
        app = _handler_app(service)
        sample_query.variables['_monitoring_message_id'] = 'user-message'
        runtime_handler = make_handler(app)
        _serve_query(app, sample_query)

        response = await runtime_handler.actions[PluginToRuntimeAction.REPLY_MESSAGE.value](
            {
                'query_id': 1,
                'query_uuid': 'query-1',
                'message_chain': [{'type': 'Plain', 'text': '喵～'}],
                'quote_origin': False,
            }
        )

        assert response.code == 0, response.message
        sample_query.adapter.reply_message.assert_awaited_once()
        kwargs = service.record_message.await_args.kwargs
        assert kwargs['handled_by'] == 'plugin:a/waifu'
        assert kwargs['parent_message_id'] == 'user-message'

    @pytest.mark.asyncio
    async def test_failed_ctx_reply_still_fails_and_is_recorded(self, sample_query):
        service = _monitoring_service()
        app = _handler_app(service)
        sample_query.adapter.reply_message.side_effect = RuntimeError('platform rejected')
        runtime_handler = make_handler(app)
        _serve_query(app, sample_query)

        # The delivery failure still reaches the plugin exactly as before.
        with pytest.raises(RuntimeError, match='platform rejected'):
            await runtime_handler.actions[PluginToRuntimeAction.REPLY_MESSAGE.value](
                {
                    'query_id': 1,
                    'query_uuid': 'query-1',
                    'message_chain': [{'type': 'Plain', 'text': 'hi'}],
                    'quote_origin': False,
                }
            )

        assert service.record_error.await_args.kwargs['error_type'] == 'PluginReplyError'

    @pytest.mark.asyncio
    @pytest.mark.parametrize('with_origin', [True, False])
    async def test_send_message_is_recorded_with_optional_origin(self, sample_query, with_origin):
        service = _monitoring_service()
        app = _handler_app(service)
        sample_query.variables.update({'_monitoring_message_id': 'user-message', '_monitoring_pipeline_name': 'P'})
        send_message = AsyncMock(return_value={'message_id': 'sent'})
        app.platform_mgr.get_bot_by_uuid = AsyncMock(
            return_value=SimpleNamespace(
                adapter=SimpleNamespace(send_message=send_message),
                bot_entity=SimpleNamespace(uuid='bot', name='QQ Bot'),
            )
        )
        app.persistence_mgr.execute_async = AsyncMock(
            return_value=SimpleNamespace(first=Mock(return_value=SimpleNamespace(uuid='bot')))
        )
        runtime_handler = make_handler(app)
        _serve_query(app, sample_query)
        data = {
            'bot_uuid': 'bot',
            'target_type': 'person',
            'target_id': 'user-1',
            'message_chain': [{'type': 'Plain', 'text': 'good morning'}],
        }
        if with_origin:
            data['origin_query_uuid'] = 'query-1'

        response = await runtime_handler.actions[PluginToRuntimeAction.SEND_MESSAGE.value](data)

        assert response.code == 0, response.message
        assert response.data['result'] == {'message_id': 'sent'}
        kwargs = service.record_message.await_args.kwargs
        assert kwargs['handled_by'] == 'plugin:a/waifu'
        assert kwargs['session_id'] == 'person_user-1'
        assert kwargs['user_id'] == 'user-1'
        assert kwargs['bot_name'] == 'QQ Bot'
        if with_origin:
            assert kwargs['parent_message_id'] == 'user-message'
            assert kwargs['pipeline_id'] == 'test-pipeline-uuid'
        else:
            assert kwargs['parent_message_id'] is None
            assert kwargs['pipeline_id'] == ''

    @pytest.mark.asyncio
    async def test_unknown_origin_is_ignored(self, sample_query):
        service = _monitoring_service()
        app = _handler_app(service)
        runtime_handler = make_handler(app)
        plugin_query = SimpleNamespace(variables={})

        await runtime_handler._attribute_plugin_query_to_origin(
            plugin_query, {'origin_query_uuid': 'not-a-live-query'}, runtime_handler._current_action_context.get()
        )

        assert ORIGIN_VAR not in plugin_query.variables
