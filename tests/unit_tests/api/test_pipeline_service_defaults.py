"""Tests for dynamic default pipeline config rendering."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.api.http.service.pipeline import PipelineService


class FakeLogger:
    def warning(self, msg):
        pass


class FakeRegistry:
    def __init__(self, runners):
        self.runners = runners

    async def list_runners(self, bound_plugins=None):
        return self.runners


def make_runner(runner_id: str, config_schema: list[dict]):
    parts = runner_id.removeprefix('plugin:').split('/')
    return AgentRunnerDescriptor(
        id=runner_id,
        source='plugin',
        label={'en_US': runner_id},
        plugin_author=parts[0],
        plugin_name=parts[1],
        runner_name=parts[2],
        config_schema=config_schema,
    )


@pytest.mark.asyncio
async def test_default_pipeline_config_uses_first_installed_runner_schema():
    local_agent = make_runner(
        'plugin:langbot/local-agent/default',
        [
            {'name': 'model', 'type': 'model-fallback-selector', 'default': {'primary': '', 'fallbacks': []}},
            {'name': 'prompt', 'type': 'prompt-editor', 'default': [{'role': 'system', 'content': 'Hello'}]},
        ],
    )
    custom_agent = make_runner(
        'plugin:alice/custom-agent/default',
        [{'name': 'api-key', 'type': 'string', 'default': ''}],
    )
    ap = SimpleNamespace(
        logger=FakeLogger(),
        agent_runner_registry=FakeRegistry([custom_agent, local_agent]),
    )

    config = await PipelineService(ap).get_default_pipeline_config()

    assert config['ai']['runner']['id'] == 'plugin:alice/custom-agent/default'
    assert config['ai']['runner_config'] == {
        'plugin:alice/custom-agent/default': {
            'api-key': '',
        },
    }


@pytest.mark.asyncio
async def test_default_pipeline_config_stays_neutral_without_installed_runners():
    ap = SimpleNamespace(
        logger=FakeLogger(),
        agent_runner_registry=FakeRegistry([]),
    )

    config = await PipelineService(ap).get_default_pipeline_config()

    assert config['ai']['runner']['id'] == ''
    assert config['ai']['runner_config'] == {}
