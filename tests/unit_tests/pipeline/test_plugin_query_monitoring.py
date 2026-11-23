"""Plugin-owned Host Queries must still produce monitoring records (LANG-320)."""

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.pipeline.monitoring_helper import (
    PLUGIN_ATTRIBUTION_VAR,
    MonitoringHelper,
    monitoring_platform,
    monitoring_session_id,
)
from langbot.pkg.plugin.handler import _build_plugin_action_query, _PluginInstallationIdentity
from langbot_plugin.entities.io.context import InstallationBinding


def _binding() -> InstallationBinding:
    return InstallationBinding(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
        installation_uuid='installation-a',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )


def _identity() -> _PluginInstallationIdentity:
    return _PluginInstallationIdentity(
        workspace_uuid='workspace-a',
        plugin_author='author',
        plugin_name='plugin',
        installation_uuid='installation-a',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )


def test_plugin_action_query_is_labelled_with_the_calling_plugin():
    query = _build_plugin_action_query(_binding(), _identity())

    assert query.variables[PLUGIN_ATTRIBUTION_VAR] == 'author/plugin'
    assert query.variables['_monitoring_pipeline_name'] == 'plugin:author/plugin'
    assert monitoring_platform(query) is None
    assert monitoring_session_id(query) == 'plugin:author/plugin'


def test_unlabelled_plugin_action_query_keeps_the_legacy_shape():
    query = _build_plugin_action_query(_binding())

    assert query.variables == {}
    assert monitoring_session_id(query) == 'unknown'


def test_pipeline_query_session_id_is_unchanged(sample_query):
    expected = f'{sample_query.launcher_type.value}_{sample_query.launcher_id}'
    assert monitoring_session_id(sample_query) == expected
    assert monitoring_platform(sample_query) == sample_query.launcher_type.value


def test_group_query_session_id_includes_sender_id_when_present():
    group_query = SimpleNamespace(
        launcher_type=SimpleNamespace(value='group'),
        launcher_id='group-100',
        sender_id='user-42',
        variables={},
    )
    assert monitoring_session_id(group_query) == 'groupmember_9_group-100_user-42'

    group_query_without_sender = SimpleNamespace(
        launcher_type=SimpleNamespace(value='group'),
        launcher_id='group-100',
        sender_id=None,
        variables={},
    )
    assert monitoring_session_id(group_query_without_sender) == 'group_group-100'


def test_extract_sender_name_supports_group_sender_methods_and_variables():
    from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
    from langbot_plugin.api.entities.builtin.platform import events as platform_events
    from langbot_plugin.api.entities.builtin.platform import message as platform_message

    sdk_group_event = platform_events.GroupMessage(
        sender=platform_entities.GroupMember(
            id='user-42',
            member_name='Alice',
            permission=platform_entities.Permission.Member,
            group=platform_entities.Group(
                id='group-100', name='Dev Group', permission=platform_entities.Permission.Member
            ),
        ),
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
    )
    sdk_group_query = SimpleNamespace(
        message_event=sdk_group_event,
        variables={},
    )
    assert MonitoringHelper._extract_sender_name(sdk_group_query) == 'Alice'

    group_query = SimpleNamespace(
        message_event=SimpleNamespace(
            group=SimpleNamespace(name='  Dev Group  '),
            sender=SimpleNamespace(nickname='Alice'),
        ),
        variables={},
    )
    assert MonitoringHelper._extract_sender_name(group_query) == 'Alice'

    getter_query = SimpleNamespace(
        message_event=SimpleNamespace(
            group=SimpleNamespace(name='Ignored Group Name'),
            sender=SimpleNamespace(get_name=lambda: '  Getter Name  ', nickname='Fallback'),
        ),
        variables={},
    )
    assert MonitoringHelper._extract_sender_name(getter_query) == 'Getter Name'

    remark_query = SimpleNamespace(
        message_event=SimpleNamespace(
            group=None,
            sender=SimpleNamespace(member_name='', nickname='  ', remark='  Remark Name  '),
        ),
        variables={},
    )
    assert MonitoringHelper._extract_sender_name(remark_query) == 'Remark Name'

    var_query = SimpleNamespace(
        message_event=SimpleNamespace(group=SimpleNamespace(name='Only Group Name'), sender=None),
        variables={'sender_name': '  Lark User  '},
    )
    assert MonitoringHelper._extract_sender_name(var_query) == 'Lark User'


@pytest.mark.asyncio
async def test_llm_call_from_plugin_action_query_is_recorded():
    """Regression: ``'Query' object has no attribute 'launcher_type'`` dropped the record."""
    query = _build_plugin_action_query(_binding(), _identity())
    service = SimpleNamespace(record_llm_call=AsyncMock(return_value='call-id'))
    logger = Mock()
    ap = SimpleNamespace(monitoring_service=service, logger=logger)

    await MonitoringHelper.record_llm_call(
        ap=ap,
        query=query,
        bot_id='unknown',
        bot_name='Plugin',
        pipeline_id='unknown',
        pipeline_name='plugin:author/plugin',
        model_name='model-a',
        input_tokens=1,
        output_tokens=2,
        duration_ms=3,
    )

    logger.error.assert_not_called()
    service.record_llm_call.assert_awaited_once()
    assert service.record_llm_call.await_args.kwargs['session_id'] == 'plugin:author/plugin'


@pytest.mark.asyncio
async def test_group_query_monitoring_session_id_is_consistent_across_all_writers_without_splitting_conversation():
    """Monitoring and model context split by member; the ledger keeps its original conversation ID."""
    import contextvars
    from sqlalchemy.ext.asyncio import create_async_engine
    import sqlalchemy as sa

    from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
    from langbot.pkg.api.http.context import ExecutionContext
    from langbot.pkg.api.http.service.monitoring import MonitoringService
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.workspace import Workspace
    from langbot.pkg.persistence.mgr import PersistenceManager
    from langbot.pkg.persistence.tenant_uow import TenantUnitOfWork
    from langbot.pkg.platform.botmgr import RuntimeBot
    from langbot.pkg.provider.tools.toolmgr import ToolManager
    from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
    from langbot_plugin.api.entities.builtin.platform import events as platform_events
    from langbot_plugin.api.entities.builtin.platform import message as platform_message
    from langbot_plugin.api.entities.builtin.provider import session as provider_session

    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                sa.insert(Workspace).values(uuid='workspace-1', instance_uuid='inst-1', name='W', slug='w')
            )

        class Persistence:
            serialize_model = PersistenceManager.serialize_model
            active_transaction = contextvars.ContextVar('group-session-test-tx', default=None)

            def tenant_uow(self, workspace):
                return TenantUnitOfWork(engine, workspace, active_transaction=self.active_transaction)

            @contextlib.asynccontextmanager
            async def tenant_write_uow(self, workspace, *, operation='artifact'):
                async with self.tenant_uow(workspace) as uow:
                    yield uow

            def get_db_engine(self):
                return engine

            async def execute_async(self, statement):
                async with engine.begin() as conn:
                    return await conn.execute(statement)

        ap = SimpleNamespace(
            persistence_mgr=Persistence(),
            logger=SimpleNamespace(warning=Mock(), error=Mock(), debug=Mock(), info=Mock()),
        )
        monitoring_service = MonitoringService(ap)
        ap.monitoring_service = monitoring_service

        exec_ctx = ExecutionContext(
            instance_uuid='inst-1',
            workspace_uuid='workspace-1',
            placement_generation=1,
            bot_uuid='bot-1',
        )

        group_event = platform_events.GroupMessage(
            sender=platform_entities.GroupMember(
                id='user-42',
                member_name='Alice',
                permission=platform_entities.Permission.Member,
                group=platform_entities.Group(
                    id='group-100',
                    name='Dev Group',
                    permission=platform_entities.Permission.Member,
                ),
            ),
            message_chain=platform_message.MessageChain([platform_message.Plain(text='hello group')]),
        )

        query = SimpleNamespace(
            query_id=1,
            launcher_type=provider_session.LauncherTypes.GROUP,
            launcher_id='group-100',
            sender_id='user-42',
            bot_uuid='bot-1',
            pipeline_uuid='pipe-1',
            workspace_uuid='workspace-1',
            _execution_context=exec_ctx,
            message_event=group_event,
            message_chain=group_event.message_chain,
            resp_message_chain=[platform_message.MessageChain([platform_message.Plain(text='hi Alice')])],
            session=SimpleNamespace(
                launcher_type=provider_session.LauncherTypes.GROUP,
                launcher_id='group-100',
                using_conversation=None,
            ),
            variables={},
        )

        # 1. Ingress event recorded with conversation_id = 'group_group-100' and actor_id = 'user-42'
        await monitoring_service.record_ingress_event(
            exec_ctx,
            event_id='evt-1',
            event_type='message.received',
            bot_id='bot-1',
            bot_name='Bot One',
            platform='group',
            payload={'text': 'hello group'},
            actor_id='user-42',
            actor_name='Alice',
            conversation_id='group_group-100',
        )

        # Verify uncovered ingress already projects to 'groupmember_9_group-100_user-42' while EventLog.conversation_id stays 'group_group-100'
        sessions_before, total_before = await monitoring_service.get_sessions(exec_ctx, bot_ids=['bot-1'])
        assert total_before == 1
        assert sessions_before[0]['session_id'] == 'groupmember_9_group-100_user-42'
        assert sessions_before[0]['user_id'] == 'user-42'
        assert sessions_before[0]['user_name'] == 'Alice'

        # 2. Pipeline message start + response
        msg_id = await MonitoringHelper.record_query_start(
            ap,
            query,
            bot_id='bot-1',
            bot_name='Bot One',
            pipeline_id='pipe-1',
            pipeline_name='Main Pipeline',
            runner_name='local-agent',
        )
        assert msg_id is not None
        await monitoring_service.link_execution_message(exec_ctx, msg_id, 'run-1', 'evt-1')
        await MonitoringHelper.record_query_response(
            ap,
            query,
            bot_id='bot-1',
            bot_name='Bot One',
            pipeline_id='pipe-1',
            pipeline_name='Main Pipeline',
            runner_name='local-agent',
        )

        # 3. LLM call recording
        await MonitoringHelper.record_llm_call(
            ap=ap,
            query=query,
            bot_id='bot-1',
            bot_name='Bot One',
            pipeline_id='pipe-1',
            pipeline_name='Main Pipeline',
            model_name='gpt-4o-mini',
            input_tokens=10,
            output_tokens=20,
            duration_ms=150,
        )

        # 4. Tool call recording via ToolManager
        tool_mgr = ToolManager(ap)
        await tool_mgr._record_tool_call(
            name='weather_lookup',
            source='plugin:demo/weather',
            parameters={'city': 'Shanghai'},
            query=query,
            duration_ms=45,
            status='success',
            result={'temp': 22},
        )

        # 5. Discarded message recording via RuntimeBot._record_discarded_message
        dummy_bot = SimpleNamespace(
            ap=ap,
            execution_context=exec_ctx,
            bot_entity=SimpleNamespace(uuid='bot-1', name='Bot One'),
            PIPELINE_DISCARD=RuntimeBot.PIPELINE_DISCARD,
            PIPELINE_DISCARD_DISPLAY_NAME=RuntimeBot.PIPELINE_DISCARD_DISPLAY_NAME,
            logger=SimpleNamespace(error=AsyncMock()),
        )
        await RuntimeBot._record_discarded_message(
            dummy_bot,
            provider_session.LauncherTypes.GROUP,
            'group-100',
            'user-42',
            group_event,
            group_event.message_chain,
        )

        # Verify all writers converged on the exact same monitoring session_id
        sessions, total = await monitoring_service.get_sessions(exec_ctx, bot_ids=['bot-1'])
        assert total == 1
        assert sessions[0]['session_id'] == 'groupmember_9_group-100_user-42'
        assert sessions[0]['user_name'] == 'Alice'
        assert sessions[0]['message_count'] == 3  # start + response + discarded (ingress covered)
        # Filter by group launcher_id returns the per-sender group session
        filtered_sessions, filtered_total = await monitoring_service.get_sessions(
            exec_ctx, bot_ids=['bot-1'], launcher_id='group-100'
        )
        assert filtered_total == 1
        assert filtered_sessions[0]['session_id'] == 'groupmember_9_group-100_user-42'

        analysis = await monitoring_service.get_session_analysis(
            exec_ctx,
            'groupmember_9_group-100_user-42',
            bot_id='bot-1',
        )
        assert analysis['found'] is True
        assert analysis['message_stats']['total'] == 3  # start + response + discarded
        assert analysis['llm_stats']['total_calls'] == 1
        assert analysis['tool_stats']['total_calls'] == 1
        assert len(analysis['tool_calls']) == 1
        assert analysis['tool_calls'][0]['tool_name'] == 'weather_lookup'

        messages, msg_total = await monitoring_service.get_messages(
            exec_ctx,
            bot_ids=['bot-1'],
            session_ids=['groupmember_9_group-100_user-42'],
        )
        assert msg_total == 3
        user_messages = [m for m in messages if m['role'] == 'user']
        assert all(m['user_name'] == 'Alice' for m in user_messages)

        conversation_ctx = QueryEntryAdapter._build_conversation_context(query)
        assert conversation_ctx.session_id == 'groupmember_9_group-100_user-42'
        assert QueryEntryAdapter.query_to_event(query).ledger_conversation_id == 'group_group-100'

        async with engine.connect() as conn:
            stored_conv_id = (
                await conn.execute(sa.select(EventLog.conversation_id).where(EventLog.event_id == 'evt-1'))
            ).scalar_one()
        assert stored_conv_id == 'group_group-100'
    finally:
        await engine.dispose()
