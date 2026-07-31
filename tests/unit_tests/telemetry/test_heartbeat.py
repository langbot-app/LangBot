"""Unit tests for telemetry heartbeat payload (pkg/telemetry/heartbeat.py)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module


def get_heartbeat_module():
    return import_module('langbot.pkg.telemetry.heartbeat')


def make_app():
    ap = Mock()
    ap.instance_config = Mock()
    ap.instance_config.data = {
        'database': {'use': 'postgresql'},
        'vdb': {'use': 'chroma'},
        'box': {'enabled': True, 'backend': 'nsjail'},
    }

    # persistence counts
    result = Mock()
    result.scalar.return_value = 3
    ap.persistence_mgr = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(return_value=result)

    # box service
    ap.box_service = Mock()
    ap.box_service.enabled = True
    ap.box_service.available = False
    ap.box_service.shares_filesystem_with_box = False

    # platform manager with one enabled bot
    bot = Mock()
    bot.enable = True
    bot.adapter = Mock()
    bot.adapter.__class__.__name__ = 'TelegramAdapter'
    ap.platform_mgr = Mock()
    ap.platform_mgr.bots = [bot]

    # plugin connector
    ap.plugin_connector = Mock()
    ap.plugin_connector.list_plugins = AsyncMock(return_value=[{}, {}])

    # skills
    ap.skill_mgr = Mock()
    ap.skill_mgr.skills = {'a': {}, 'b': {}, 'c': {}}
    ap.skill_mgr.total_cached_skill_count.return_value = 3

    return ap


class TestBuildHeartbeatPayload:
    @pytest.mark.asyncio
    async def test_payload_shape(self):
        heartbeat = get_heartbeat_module()
        ap = make_app()
        payload = await heartbeat.build_heartbeat_payload(ap, workspace_uuid='workspace-a')

        assert payload['event_type'] == 'instance_heartbeat'
        assert payload['query_id'] == ''
        assert payload['workspace_uuid'] == 'workspace-a'
        assert 'instance_id' not in payload
        assert 'instance_create_ts' in payload
        assert 'timestamp' in payload
        f = payload['features']
        assert f['database'] == 'postgresql'
        assert f['vdb'] == 'chroma'
        assert f['box'] == {
            'enabled': True,
            'available': False,
            'backend': 'nsjail',
            'shares_fs': False,
        }
        assert f['adapters'] == ['TelegramAdapter']
        assert f['bot_count'] == 1
        assert f['plugin_count'] == 2
        assert f['skill_count'] == 3
        assert f['pipeline_count'] == 3
        assert f['mcp_server_count'] == 3
        assert f['knowledge_base_count'] == 3

    @pytest.mark.asyncio
    async def test_payload_is_json_serializable(self):
        heartbeat = get_heartbeat_module()
        payload = await heartbeat.build_heartbeat_payload(make_app(), workspace_uuid='workspace-a')
        json.dumps(payload)

    @pytest.mark.asyncio
    async def test_count_failure_yields_minus_one(self):
        heartbeat = get_heartbeat_module()
        ap = make_app()
        ap.persistence_mgr.execute_async = AsyncMock(side_effect=RuntimeError('db down'))
        payload = await heartbeat.build_heartbeat_payload(ap, workspace_uuid='workspace-a')
        assert payload['features']['pipeline_count'] == -1

    @pytest.mark.asyncio
    async def test_cloud_counts_loaded_registries_without_tenant_sql(self):
        heartbeat = get_heartbeat_module()
        ap = make_app()
        ap.persistence_mgr.mode = SimpleNamespace(value='cloud_runtime')
        ap.persistence_mgr.execute_async = AsyncMock(
            side_effect=AssertionError('Cloud heartbeat must not issue per-tenant COUNTs')
        )
        ap.pipeline_mgr = SimpleNamespace(
            _pipelines_by_key={
                ('instance-a', 'workspace-a', 'pipeline-a'): object(),
                ('instance-a', 'workspace-a', 'pipeline-b'): object(),
            },
        )
        adapter_a = type('WorkspaceAAdapter', (), {})()
        adapter_b = type('WorkspaceBAdapter', (), {})()
        ap.platform_mgr._bots_by_key = {
            ('instance-a', 'workspace-a', 'bot-a'): SimpleNamespace(enable=True, adapter=adapter_a),
        }
        ap.tool_mgr = SimpleNamespace(
            mcp_tool_loader=SimpleNamespace(
                _sessions={
                    ('instance-a', 'workspace-a', 1, 'mcp-a'): object(),
                    ('instance-a', 'workspace-a', 1, 'mcp-b'): object(),
                    ('instance-a', 'workspace-a', 1, 'mcp-c'): object(),
                },
            ),
        )
        ap.rag_mgr = SimpleNamespace(
            knowledge_bases={('workspace-a', 'kb-a'): object()},
        )
        ap.plugin_connector._workspace_installations = {
            'workspace-a': {'plugin-a', 'plugin-b'},
        }
        ap.skill_mgr._skills_by_scope = {
            ('instance-a', 'workspace-a', 1): {'skill-a': {}, 'skill-b': {}},
            ('instance-a', 'workspace-b', 1): {'skill-c': {}},
        }
        ap.workspace_service.list_active_execution_bindings = AsyncMock(
            return_value=[
                SimpleNamespace(workspace_uuid='workspace-a', placement_generation=7),
                SimpleNamespace(workspace_uuid='workspace-b', placement_generation=9),
            ],
        )
        ap.platform_mgr._bots_by_key[('instance-a', 'workspace-b', 'bot-b')] = SimpleNamespace(
            enable=True, adapter=adapter_b
        )

        payloads = await heartbeat.build_heartbeat_payloads(ap)

        assert [payload['workspace_uuid'] for payload in payloads] == ['workspace-a', 'workspace-b']
        assert all('instance_id' not in payload for payload in payloads)
        by_workspace = {payload['workspace_uuid']: payload['features'] for payload in payloads}
        assert by_workspace['workspace-a']['pipeline_count'] == 2
        assert by_workspace['workspace-a']['mcp_server_count'] == 3
        assert by_workspace['workspace-a']['knowledge_base_count'] == 1
        assert by_workspace['workspace-a']['bot_count'] == 1
        assert by_workspace['workspace-a']['plugin_count'] == 2
        assert by_workspace['workspace-a']['extension_count'] == 5
        assert by_workspace['workspace-a']['skill_count'] == 2
        assert by_workspace['workspace-a']['execution_generation'] == 7
        assert by_workspace['workspace-a']['adapters'] == ['WorkspaceAAdapter']
        assert by_workspace['workspace-b']['bot_count'] == 1
        assert by_workspace['workspace-b']['pipeline_count'] == 0
        assert by_workspace['workspace-b']['skill_count'] == 1
        assert by_workspace['workspace-b']['execution_generation'] == 9
        assert by_workspace['workspace-b']['adapters'] == ['WorkspaceBAdapter']
        assert 'workspace_resources' not in by_workspace['workspace-a']
        ap.persistence_mgr.execute_async.assert_not_awaited()
        ap.workspace_service.list_active_execution_bindings.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_user_content_fields(self):
        """The heartbeat must never carry message content / credentials keys."""
        heartbeat = get_heartbeat_module()
        payload = await heartbeat.build_heartbeat_payload(make_app(), workspace_uuid='workspace-a')
        flat = json.dumps(payload).lower()
        for forbidden in ('api_key', 'password', 'token', 'message_content'):
            assert forbidden not in flat
