"""Regression coverage for the NVIDIA NIM requester manifest."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import litellm
import pytest
import yaml

from langbot.pkg.discover.engine import ComponentDiscoveryEngine
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.modelmgr.requesters import litellmchat
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from langbot_plugin.api.entities.builtin.provider.message import Message
from tests.unit_tests.provider.conftest import TEST_EXECUTION_CONTEXT
from tests.unit_tests.provider.test_reasoning_control import _runtime_model

MANIFEST_PATH = 'pkg/provider/modelmgr/requesters/nvidiachatcmpl.yaml'
NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'
NVIDIA_MODEL = 'nvidia/nemotron-3.5-super-vl-120b-a12b'


def _load_component():
    engine = ComponentDiscoveryEngine(SimpleNamespace())
    return engine.load_component_manifest(MANIFEST_PATH)


def test_nvidia_manifest_is_llm_requester():
    component = _load_component()

    assert component is not None
    assert component.kind == 'LLMAPIRequester'
    assert component.metadata.name == 'nvidia-chat-completions'
    assert component.metadata.icon == 'nvidia.svg'
    assert component.spec['litellm_provider'] == 'openai'
    assert component.spec['support_type'] == ['llm']
    assert component.execution is None
    icon = Path(__file__).parents[4] / 'src/langbot' / component.icon_rel_path
    assert icon.is_file()

    fields = {item['name']: item for item in component.spec['config']}
    assert fields['base_url']['default'] == NVIDIA_BASE_URL
    assert fields['base_url']['type'] == 'string'
    assert fields['timeout']['default'] == 120
    assert 'model' not in fields


def test_nvidia_manifest_has_no_hard_coded_key():
    manifest = yaml.safe_load((Path(__file__).parents[4] / 'src/langbot' / MANIFEST_PATH).read_text(encoding='utf-8'))
    assert 'api_key' not in json.dumps(manifest)


@pytest.mark.asyncio
async def test_nvidia_provider_routes_through_litellm(mock_app_for_modelmgr):
    app = mock_app_for_modelmgr
    app.discover = ComponentDiscoveryEngine(app)
    app.discover.load_component_manifest(MANIFEST_PATH)

    model_mgr = ModelManager(app)
    await model_mgr.initialize()
    assert 'nvidia-chat-completions' not in model_mgr.requester_dict
    assert model_mgr.get_available_requester_manifest_by_name('nvidia-chat-completions') is not None

    runtime_provider = await model_mgr.load_provider(
        TEST_EXECUTION_CONTEXT,
        {
            'uuid': 'nvidia-provider',
            'name': 'NVIDIA NIM',
            'requester': 'nvidia-chat-completions',
            'base_url': NVIDIA_BASE_URL,
            'api_keys': ['test'],
        },
    )
    adapter = runtime_provider.requester
    assert isinstance(adapter, LiteLLMRequester)
    assert adapter.requester_cfg['custom_llm_provider'] == 'openai'
    assert adapter.requester_cfg['base_url'] == NVIDIA_BASE_URL

    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return litellm.ModelResponse(
            model=NVIDIA_MODEL,
            choices=[{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}],
            usage={'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
        )

    model = _runtime_model(adapter, name=NVIDIA_MODEL, abilities=[])
    model.provider.token_mgr.get_token = Mock(return_value='test')
    with patch.object(litellmchat, 'acompletion', new=AsyncMock(side_effect=fake_acompletion)):
        result, _ = await adapter.invoke_llm(None, model, [Message(role='user', content='hello')])

    assert result.content == 'ok'
    assert calls[0]['model'] == f'openai/{NVIDIA_MODEL}'
    assert calls[0]['api_base'] == NVIDIA_BASE_URL
    assert calls[0]['api_key'] == 'test'
    await adapter.aclose()
