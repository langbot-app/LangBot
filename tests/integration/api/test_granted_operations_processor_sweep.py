"""Integration sweep verifying processor principal execution across all in-scope operations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.granted_operations import call
from langbot.pkg.api.application.operation_docs import OPERATION_DOCS, get_operation_doc
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def sweep_app(monkeypatch):
    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))

    @asynccontextmanager
    async def tenant_scope(workspace):
        yield

    mock_db_res = Mock()
    mock_db_res.first = Mock(return_value=None)
    mock_db_res.all = Mock(return_value=[])
    mock_db_res.scalar_one_or_none = Mock(return_value=None)

    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'database': {'use': 'sqlite'}}),
        logger=Mock(),
        persistence_mgr=SimpleNamespace(tenant_scope=tenant_scope, execute_async=AsyncMock(return_value=mock_db_res)),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(instance_uuid='sweep-instance', placement_generation=1)
            )
        ),
        workspace_settings_service=SimpleNamespace(
            effective_level=AsyncMock(return_value=1),
            record=AsyncMock(),
        ),
        pipeline_service=Mock(),
        llm_model_service=Mock(),
        embedding_models_service=Mock(),
        rerank_models_service=Mock(),
        provider_service=Mock(),
        bot_service=Mock(),
        agent_service=Mock(),
        knowledge_service=Mock(),
        mcp_service=Mock(),
        skill_service=Mock(),
        monitoring_service=Mock(),
        platform_mgr=Mock(),
        plugin_connector=Mock(),
        tool_mgr=Mock(),
        model_mgr=Mock(),
        sess_mgr=SimpleNamespace(session_list=[]),
        query_pool=SimpleNamespace(get_query_count=lambda execution: 0),
    )

    # Pipeline service
    ap.pipeline_service.get_pipelines = AsyncMock(return_value=[])
    ap.pipeline_service.get_pipeline = AsyncMock(
        return_value={'uuid': 'p-1', 'name': 'Pipeline 1', 'extensions_preferences': {}}
    )
    ap.pipeline_service.get_pipeline_metadata = AsyncMock(return_value=[])
    ap.pipeline_service.get_default_pipeline_config = AsyncMock(return_value={})
    ap.pipeline_service.get_pipeline_extensions = AsyncMock(return_value={})
    ap.pipeline_service.create_pipeline = AsyncMock(return_value='p-1')
    ap.pipeline_service.update_pipeline = AsyncMock(return_value=None)
    ap.pipeline_service.delete_pipeline = AsyncMock(return_value=None)

    # LLM Model service
    ap.llm_model_service.get_llm_models = AsyncMock(return_value=[])
    ap.llm_model_service.get_llm_models_by_provider = AsyncMock(return_value=[])
    ap.llm_model_service.get_llm_model = AsyncMock(return_value={'uuid': 'm-1'})
    ap.llm_model_service.get_starred_model = AsyncMock(return_value='m-1')
    ap.llm_model_service.get_default_model = AsyncMock(return_value='m-1')
    ap.llm_model_service.create_llm_model = AsyncMock(return_value='m-1')
    ap.llm_model_service.update_llm_model = AsyncMock(return_value=None)
    ap.llm_model_service.delete_llm_model = AsyncMock(return_value=None)

    # Embedding model service
    ap.embedding_models_service.get_embedding_models = AsyncMock(return_value=[])
    ap.embedding_models_service.get_embedding_models_by_provider = AsyncMock(return_value=[])
    ap.embedding_models_service.get_embedding_model = AsyncMock(return_value={'uuid': 'em-1'})

    # Rerank model service
    ap.rerank_models_service.get_rerank_models = AsyncMock(return_value=[])
    ap.rerank_models_service.get_rerank_models_by_provider = AsyncMock(return_value=[])
    ap.rerank_models_service.get_rerank_model = AsyncMock(return_value={'uuid': 'rm-1'})

    # Provider service
    ap.provider_service.get_providers = AsyncMock(return_value=[])
    ap.provider_service.get_provider = AsyncMock(return_value={'uuid': 'pr-1'})
    ap.provider_service.get_provider_model_counts = AsyncMock(return_value={'llm': 0, 'embedding': 0, 'rerank': 0})
    ap.provider_service.create_provider = AsyncMock(return_value='pr-1')
    ap.provider_service.update_provider = AsyncMock(return_value=None)
    ap.provider_service.delete_provider = AsyncMock(return_value=None)

    # Bot service
    ap.bot_service.get_bots = AsyncMock(return_value=[])
    ap.bot_service.get_bot = AsyncMock(return_value={'uuid': 'b-1'})
    ap.bot_service.get_bot_admins = AsyncMock(return_value=[])
    ap.bot_service.list_event_logs = AsyncMock(return_value=([], 0))
    ap.bot_service.preview_group_filter_migration = AsyncMock(return_value={})
    ap.bot_service.list_event_route_statuses = AsyncMock(return_value={})
    ap.bot_service.get_runtime_bot_info = AsyncMock(return_value={})
    ap.bot_service.dry_run_event_route = AsyncMock(return_value={})
    ap.bot_service.create_bot = AsyncMock(return_value='b-1')
    ap.bot_service.update_bot = AsyncMock(return_value=None)
    ap.bot_service.delete_bot = AsyncMock(return_value=None)

    # Agent service
    ap.agent_service.get_agents = AsyncMock(return_value=[])
    ap.agent_service.get_agent = AsyncMock(return_value={'uuid': 'a-1'})
    ap.agent_service.get_agent_metadata = AsyncMock(return_value={})
    ap.agent_service.get_processor_runs = AsyncMock(return_value={'runs': []})
    ap.agent_service.get_processor_run_events = AsyncMock(return_value={'events': []})
    ap.agent_service.create_agent = AsyncMock(return_value={'agent_uuid': 'a-1'})
    ap.agent_service.update_agent = AsyncMock(return_value=None)
    ap.agent_service.delete_agent = AsyncMock(return_value=None)

    # Knowledge service
    ap.knowledge_service.get_knowledge_bases = AsyncMock(return_value=[])
    ap.knowledge_service.get_knowledge_base = AsyncMock(return_value={'uuid': 'kb-1'})
    ap.knowledge_service.retrieve_knowledge_base = AsyncMock(return_value=[])
    ap.knowledge_service.get_files_by_knowledge_base = AsyncMock(return_value=[])
    ap.knowledge_service.list_knowledge_engines = AsyncMock(return_value=[])
    ap.knowledge_service.get_engine_creation_schema = AsyncMock(return_value={})
    ap.knowledge_service.get_engine_retrieval_schema = AsyncMock(return_value={})
    ap.knowledge_service.list_parsers = AsyncMock(return_value=[])
    ap.knowledge_service.create_knowledge_base = AsyncMock(return_value='kb-1')
    ap.knowledge_service.update_knowledge_base = AsyncMock(return_value=None)
    ap.knowledge_service.delete_knowledge_base = AsyncMock(return_value=None)

    # MCP service
    ap.mcp_service.get_mcp_servers = AsyncMock(return_value=[])
    ap.mcp_service.get_mcp_server_by_name = AsyncMock(return_value={'uuid': 'mcp-1'})
    ap.mcp_service.get_mcp_server_logs = AsyncMock(return_value=[])
    ap.mcp_service.get_runtime_info = AsyncMock(return_value={})
    ap.mcp_service.get_mcp_server_resources = AsyncMock(return_value=[])
    ap.mcp_service.read_mcp_server_resource_envelope = AsyncMock(return_value={})
    ap.mcp_service.get_mcp_server_resource_templates = AsyncMock(return_value=[])
    ap.mcp_service.delete_mcp_server = AsyncMock(return_value=None)
    ap.mcp_service.test_mcp_server = AsyncMock(return_value=0)

    # Skill service
    ap.skill_service.list_skills = AsyncMock(return_value=[])
    ap.skill_service.get_skill = AsyncMock(return_value={'name': 'sk-1'})
    ap.skill_service.list_skill_files = AsyncMock(return_value={'files': []})
    ap.skill_service.read_skill_file = AsyncMock(return_value={'content': ''})
    ap.skill_service.preview_install_from_github = AsyncMock(return_value=[])
    ap.skill_service.create_skill = AsyncMock(return_value={})
    ap.skill_service.update_skill = AsyncMock(return_value={})
    ap.skill_service.delete_skill = AsyncMock(return_value=True)

    # Monitoring service
    ap.monitoring_service.get_overview_metrics = AsyncMock(return_value={})
    ap.monitoring_service.get_messages = AsyncMock(return_value=([], 0))
    ap.monitoring_service.get_message_details = AsyncMock(return_value={})
    ap.monitoring_service.get_sessions = AsyncMock(return_value=([], 0))
    ap.monitoring_service.get_session_analysis = AsyncMock(return_value={})
    ap.monitoring_service.get_token_statistics = AsyncMock(return_value={})
    ap.monitoring_service.get_errors = AsyncMock(return_value=([], 0))
    ap.monitoring_service.get_inflight_snapshot = AsyncMock(return_value={})
    ap.monitoring_service.get_executions = AsyncMock(return_value={})
    ap.monitoring_service.get_llm_calls = AsyncMock(return_value=([], 0))
    ap.monitoring_service.get_embedding_calls = AsyncMock(return_value=([], 0))
    ap.monitoring_service.get_tool_calls = AsyncMock(return_value=([], 0))
    ap.monitoring_service.get_feedback_list = AsyncMock(return_value=([], 0))
    ap.monitoring_service.get_feedback_stats = AsyncMock(return_value={})
    ap.monitoring_service.get_execution_detail = AsyncMock(return_value={})
    ap.monitoring_service.reset_session_context = AsyncMock(return_value={})

    # Platform manager
    ap.platform_mgr.get_available_adapters_info = lambda: [{'name': 'aiocqhttp'}]
    ap.platform_mgr.get_available_adapter_info_by_name = lambda name: {'name': name}
    proxy_bot = SimpleNamespace(adapter=SimpleNamespace(get_websocket_messages=lambda p, s: []))
    ap.platform_mgr.get_websocket_proxy_bot = AsyncMock(return_value=proxy_bot)

    # Plugin connector
    ap.plugin_connector.is_enable_plugin = False
    ap.plugin_connector.require_workspace_context = AsyncMock()
    ap.plugin_connector.list_plugins = AsyncMock(return_value=[])
    ap.plugin_connector.get_plugin_info = AsyncMock(
        return_value={'author': 'a', 'name': 'p', 'manifest': {'config': {}}, 'plugin_config': {}}
    )
    ap.plugin_connector.get_plugin_readme = AsyncMock(return_value='# Plugin README')
    ap.plugin_connector.get_debug_info = AsyncMock(
        return_value={'debug_url': 'http://test', 'plugin_debug_key': 'k', 'expires_at': '2026-01-01'}
    )
    ap.plugin_connector.get_plugin_logs = AsyncMock(return_value={'logs': []})

    # Tool and model managers
    ap.tool_mgr.get_resolved_tool_catalog = AsyncMock(return_value=[{'name': 'test_tool'}])
    ap.model_mgr.get_available_requesters_info = lambda model_type=None: []
    ap.model_mgr.get_available_requester_info_by_name = lambda name: {'name': name}

    api = ApplicationAPI(ap)
    ap.application_api = api
    return ap


def make_processor_context(allowed_ids: frozenset[str]) -> RequestContext:
    return RequestContext(
        instance_uuid='sweep-instance',
        placement_generation=1,
        request_id='req-proc-sweep',
        auth_type='processor',
        principal=PrincipalContext(
            principal_type=PrincipalType.PROCESSOR,
            processor_kind='agent',
            processor_uuid='agent-sweep',
            run_id='run-sweep',
        ),
        workspace=WorkspaceContext(
            workspace_uuid='ws-sweep',
            membership_uuid=None,
            role=None,
            permissions=frozenset({p.value for p in Permission}),
        ),
        allowed_operation_ids=allowed_ids,
    )


MIN_READ_PARAMS = {
    'adapter.get': {'adapter_name': 'aiocqhttp'},
    'agent.get': {'agent_uuid': 'a-1'},
    'agent.runs.events': {'processor_id': 'proc-1', 'run_id': 'run-1'},
    'agent.runs.list': {'processor_id': 'proc-1'},
    'bot.admins.list': {'bot_uuid': 'b-1'},
    'bot.get': {'bot_uuid': 'b-1'},
    'bot.group_filter.preview': {'bot_uuid': 'b-1'},
    'bot.logs': {'bot_uuid': 'b-1', 'from_index': 0, 'max_count': 10},
    'bot.routes.preview': {'bot_uuid': 'b-1', 'event_type': 'message'},
    'bot.routes.status': {'bot_uuid': 'b-1'},
    'bot.runtime.get': {'bot_uuid': 'b-1'},
    'knowledge.base.get': {'kb_uuid': 'kb-1'},
    'knowledge.base.retrieve': {'kb_uuid': 'kb-1', 'query': 'test'},
    'knowledge.engine.creation_schema': {'plugin_id': 'plug-1'},
    'knowledge.engine.retrieval_schema': {'plugin_id': 'plug-1'},
    'knowledge.file.list': {'kb_uuid': 'kb-1'},
    'mcp.resource.list': {'server_name': 'srv-1'},
    'mcp.resource.read': {'server_name': 'srv-1', 'uri': 'file:///test'},
    'mcp.resource.templates': {'server_name': 'srv-1'},
    'mcp.server.get': {'server_name': 'srv-1'},
    'mcp.server.logs': {'server_name': 'srv-1'},
    'mcp.server.runtime': {'server_name': 'srv-1'},
    'model.embedding.get': {'model_uuid': 'em-1'},
    'model.embedding.list_by_provider': {'provider_uuid': 'pr-1'},
    'model.llm.get': {'model_uuid': 'm-1'},
    'model.llm.list_by_provider': {'provider_uuid': 'pr-1'},
    'model.rerank.get': {'model_uuid': 'rm-1'},
    'model.rerank.list_by_provider': {'provider_uuid': 'pr-1'},
    'monitoring.execution.detail': {'source': 'agent', 'execution_id': 'exec-1'},
    'monitoring.message.detail': {'message_id': 'msg-1'},
    'monitoring.session.analysis': {'session_id': 'sess-1'},
    'pipeline.chat.connections': {'pipeline_uuid': 'p-1'},
    'pipeline.chat.history': {'pipeline_uuid': 'p-1', 'session_type': 'person'},
    'pipeline.extensions.get': {'pipeline_uuid': 'p-1'},
    'pipeline.get': {'pipeline_uuid': 'p-1'},
    'plugin.config.get': {'author': 'a', 'plugin_name': 'p'},
    'plugin.get': {'author': 'a', 'plugin_name': 'p'},
    'plugin.github.assets': {'owner': 'o', 'repo': 'r', 'release_id': 1},
    'plugin.github.releases': {'repo_url': 'https://github.com/langbot-app/test/tree/main'},
    'plugin.logs': {'author': 'a', 'plugin_name': 'p'},
    'plugin.readme': {'author': 'a', 'plugin_name': 'p'},
    'provider.get': {'provider_uuid': 'pr-1'},
    'provider.models.count': {'provider_uuid': 'pr-1'},
    'requester.get': {'requester_name': 'req-1'},
    'skill.file.list': {'skill_name': 'sk-1'},
    'skill.file.read': {'skill_name': 'sk-1', 'path': 'README.md'},
    'skill.get': {'skill_name': 'sk-1'},
    'skill.github.preview': {'data': {}},
    'tool.get': {'tool_name': 'test_tool'},
}


async def test_processor_sweep_all_in_scope_read_operations(sweep_app):
    """Execute all 85 read operations with exposure=='all' under processor context."""
    api = sweep_app.application_api
    read_op_ids = [
        op_id
        for op_id, spec in sorted(api._operations.items())
        if op_id in OPERATION_DOCS
        and get_operation_doc(op_id, side_effect=spec.side_effect).exposure == 'all'
        and not spec.side_effect
    ]
    assert len(read_op_ids) == 85

    proc_ctx = make_processor_context(frozenset(read_op_ids))

    with patch('langbot.pkg.api.application.plugin_operations._github_json', AsyncMock(return_value={'assets': []})):
        for op_id in read_op_ids:
            args = MIN_READ_PARAMS.get(op_id, {})
            result = await call(sweep_app, proc_ctx, op_id, args, consumer='processor', granted=read_op_ids)
            assert result['ok'] is True, f'Read operation {op_id} failed: {result.get("error")}'
            assert result['operation']['id'] == op_id
            assert result['operation']['side_effect'] is False


WRITE_SAMPLES = [
    # agent
    ('agent.create', {'agent_data': {'name': 'A1'}}),
    ('agent.update', {'agent_uuid': 'a-1', 'agent_data': {'name': 'A2'}}),
    ('agent.delete', {'agent_uuid': 'a-1'}),
    # bot
    ('bot.create', {'bot_data': {'name': 'B1'}}),
    ('bot.update', {'bot_uuid': 'b-1', 'bot_data': {'name': 'B2'}}),
    ('bot.delete', {'bot_uuid': 'b-1'}),
    # knowledge
    ('knowledge.base.create', {'kb_data': {'name': 'K1'}}),
    ('knowledge.base.update', {'kb_uuid': 'kb-1', 'kb_data': {'name': 'K2'}}),
    ('knowledge.base.delete', {'kb_uuid': 'kb-1'}),
    # mcp (delete and test are exposure=='all')
    ('mcp.server.test', {'server_name': 's-1', 'server_data': {}}),
    ('mcp.server.delete', {'server_uuid': 's-1'}),
    # model
    ('model.llm.create', {'model_data': {'name': 'M1'}}),
    ('model.llm.update', {'model_uuid': 'm-1', 'model_data': {'name': 'M2'}}),
    ('model.llm.delete', {'model_uuid': 'm-1'}),
    # monitoring
    ('monitoring.session.reset', {'bot_id': 'b-1', 'session_id': 's-1'}),
    # pipeline
    ('pipeline.create', {'pipeline_data': {'name': 'P1'}}),
    ('pipeline.update', {'pipeline_uuid': 'p-1', 'pipeline_data': {'name': 'P2'}}),
    ('pipeline.delete', {'pipeline_uuid': 'p-1'}),
    # provider
    ('provider.create', {'provider_data': {'name': 'PR1'}}),
    ('provider.update', {'provider_uuid': 'pr-1', 'provider_data': {'name': 'PR2'}}),
    ('provider.delete', {'provider_uuid': 'pr-1'}),
    # skill
    ('skill.create', {'data': {}}),
    ('skill.update', {'skill_name': 'sk-1', 'data': {}}),
    ('skill.delete', {'skill_name': 'sk-1'}),
]


async def test_processor_sweep_sampled_write_operations(sweep_app):
    """Sample create, update, delete write operations across all domains for processor."""
    write_op_ids = [op[0] for op in WRITE_SAMPLES]
    assert len(write_op_ids) == 24

    proc_ctx = make_processor_context(frozenset(write_op_ids))

    for op_id, args in WRITE_SAMPLES:
        result = await call(sweep_app, proc_ctx, op_id, args, consumer='processor', granted=write_op_ids)
        assert result['ok'] is True, f'Write operation {op_id} failed: {result.get("error")}'
        assert result['operation']['id'] == op_id
        assert result['operation']['side_effect'] is True


async def test_processor_cannot_call_assistant_only_operation(sweep_app):
    """Verify processor is denied from calling assistant-only operations."""
    proc_ctx = make_processor_context(frozenset({'mcp.server.create', 'bot.list'}))

    # mcp.server.create is exposure='assistant', not 'all'
    result = await call(
        sweep_app,
        proc_ctx,
        'mcp.server.create',
        {'server_data': {'name': 's1', 'command': 'ls'}},
        consumer='processor',
        granted=['mcp.server.create'],
    )
    assert result['ok'] is False
    assert result['error']['code'] == 'not_found'
