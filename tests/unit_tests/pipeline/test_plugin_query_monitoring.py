"""Plugin-owned Host Queries must still produce monitoring records (LANG-320)."""

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
