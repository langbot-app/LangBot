"""Unit tests for telemetry heartbeat payload (pkg/telemetry/heartbeat.py)."""

from __future__ import annotations

import json

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

    return ap


class TestBuildHeartbeatPayload:
    @pytest.mark.asyncio
    async def test_payload_shape(self):
        heartbeat = get_heartbeat_module()
        ap = make_app()
        payload = await heartbeat.build_heartbeat_payload(ap)

        assert payload['event_type'] == 'instance_heartbeat'
        assert payload['query_id'] == ''
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
        payload = await heartbeat.build_heartbeat_payload(make_app())
        json.dumps(payload)

    @pytest.mark.asyncio
    async def test_count_failure_yields_minus_one(self):
        heartbeat = get_heartbeat_module()
        ap = make_app()
        ap.persistence_mgr.execute_async = AsyncMock(side_effect=RuntimeError('db down'))
        payload = await heartbeat.build_heartbeat_payload(ap)
        assert payload['features']['pipeline_count'] == -1

    @pytest.mark.asyncio
    async def test_no_user_content_fields(self):
        """The heartbeat must never carry message content / credentials keys."""
        heartbeat = get_heartbeat_module()
        payload = await heartbeat.build_heartbeat_payload(make_app())
        flat = json.dumps(payload).lower()
        for forbidden in ('api_key', 'password', 'token', 'message_content'):
            assert forbidden not in flat
