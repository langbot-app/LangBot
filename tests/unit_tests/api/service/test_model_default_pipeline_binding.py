import json
import sys
import types
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.model import LLMModelsService


def _service(default_pipeline, runner_service):
    app = Mock()
    app.persistence_mgr = Mock()
    app.persistence_mgr.execute_async = AsyncMock()
    result = Mock()
    result.first.return_value = default_pipeline
    app.persistence_mgr.execute_async.return_value = result
    app.runner_default_config_service = runner_service
    app.model_mgr = Mock()
    app.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())
    app.model_mgr.cache_llm_model = AsyncMock()
    app.provider_service = Mock()
    app.pipeline_service = Mock()
    app.pipeline_service.update_pipeline = AsyncMock()
    return LLMModelsService(app)


@pytest.mark.asyncio
async def test_model_creation_delegates_default_pipeline_binding_to_runner_schema(monkeypatch):
    """The pre-4.11 ai['local-agent'] container must never be touched directly.

    Assigning into ai['local-agent'] raised KeyError on 4.11 Workspaces, which
    turned "add the first model" into a 500 -- and the model never reached the
    default pipeline, so every agent run failed with "No authorized model".
    """
    pipeline = types.SimpleNamespace(
        uuid='pipeline-a', config={'ai': {'runner': {'id': 'plugin:langbot-team/LocalAgent/default'}}}
    )
    runner_service = Mock()
    runner_service.set_pipeline_llm_model_if_empty = AsyncMock(return_value=True)

    service = _service(pipeline, runner_service)

    monkeypatch.setattr(sys.modules['langbot.pkg.api.http.service.model'], '_require_workspace_provider', AsyncMock())
    monkeypatch.setattr(
        sys.modules['langbot.pkg.api.http.service.model'], '_assert_cloud_managed_provider_mutable', AsyncMock()
    )
    monkeypatch.setattr(sys.modules['langbot.pkg.api.http.service.model'], '_validate_provider_supports', AsyncMock())
    monkeypatch.setattr(sys.modules['langbot.pkg.api.http.service.model'], '_require_runtime_provider', AsyncMock())
    monkeypatch.setattr(
        sys.modules['langbot.pkg.api.http.service.model'], '_normalize_llm_reasoning', lambda data: None
    )
    monkeypatch.setattr(
        sys.modules['langbot.pkg.api.http.service.model'], '_validate_llm_reasoning_capability', lambda *a, **k: None
    )

    uuid_value = await service.create_llm_model(
        'workspace-a',
        {
            'name': 'deepseek-chat',
            'provider_uuid': 'provider-a',
            'abilities': ['func_call'],
        },
    )

    assert uuid_value
    runner_service.set_pipeline_llm_model_if_empty.assert_awaited_once()
    args = runner_service.set_pipeline_llm_model_if_empty.await_args.args
    assert args[0] == 'workspace-a'
    assert args[1] is pipeline
    assert args[2] == uuid_value
    # No legacy write path should remain.
    assert 'local-agent' not in json.dumps(pipeline.config)


@pytest.mark.asyncio
async def test_unmigrated_pipeline_still_gets_a_legacy_model(monkeypatch):
    """A pipeline that has not run the 4.11 migration keeps its old shape."""
    pipeline = types.SimpleNamespace(
        uuid='pipeline-b',
        config={'ai': {'local-agent': {'model': {'primary': '', 'fallbacks': []}}}},
    )
    runner_service = Mock()
    runner_service.set_pipeline_llm_model_if_empty = AsyncMock(return_value=False)

    service = _service(pipeline, runner_service)
    monkeypatch.setattr(sys.modules['langbot.pkg.api.http.service.model'], '_require_workspace_provider', AsyncMock())
    monkeypatch.setattr(
        sys.modules['langbot.pkg.api.http.service.model'], '_assert_cloud_managed_provider_mutable', AsyncMock()
    )
    monkeypatch.setattr(sys.modules['langbot.pkg.api.http.service.model'], '_validate_provider_supports', AsyncMock())
    monkeypatch.setattr(sys.modules['langbot.pkg.api.http.service.model'], '_require_runtime_provider', AsyncMock())
    monkeypatch.setattr(
        sys.modules['langbot.pkg.api.http.service.model'], '_normalize_llm_reasoning', lambda data: None
    )
    monkeypatch.setattr(
        sys.modules['langbot.pkg.api.http.service.model'], '_validate_llm_reasoning_capability', lambda *a, **k: None
    )

    uuid_value = await service.create_llm_model(
        'workspace-a',
        {'name': 'deepseek-chat', 'provider_uuid': 'provider-a', 'abilities': ['func_call']},
    )

    assert pipeline.config['ai']['local-agent']['model']['primary'] == uuid_value
    service.ap.pipeline_service.update_pipeline.assert_awaited_once()
