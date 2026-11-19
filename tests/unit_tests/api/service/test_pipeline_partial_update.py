import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.pipeline import PipelineService


@pytest.fixture
def service():
    config = {
        'speech': {'keep': True},
        'ai': {'n8n': {'webhook-url': 'https://example.invalid/secret', 'timeout': 30}},
        'output': {'keep': True},
    }
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=Mock(rowcount=1))),
        pipeline_mgr=SimpleNamespace(prepare_pipeline=AsyncMock(), publish_pipeline=Mock()),
        sess_mgr=SimpleNamespace(session_list=[]),
    )
    result = PipelineService(ap)
    result.get_pipeline = AsyncMock(return_value={'uuid': 'pipeline', 'config': config})
    return result


def stored_config(service):
    statement = service.ap.persistence_mgr.execute_async.await_args.args[0]
    return next(value.value for column, value in statement._values.items() if column.key == 'config')


@pytest.mark.asyncio
async def test_partial_config_preserves_sections_and_replaces_supplied_section(service):
    original = copy.deepcopy(service.get_pipeline.return_value['config'])
    request = {'config': {'ai': {'n8n': {'timeout': 60}}}}
    await service.update_pipeline('workspace', 'pipeline', request)
    assert stored_config(service) == {**original, 'ai': {'n8n': {'timeout': 60}}}
    assert service.get_pipeline.return_value['config'] == original
    assert request == {'config': {'ai': {'n8n': {'timeout': 60}}}}


@pytest.mark.asyncio
async def test_partial_config_restores_secret_placeholders(service):
    original = copy.deepcopy(service.get_pipeline.return_value['config'])
    await service.update_pipeline(
        'workspace', 'pipeline', {'config': {'ai': {'n8n': {'webhook-url': '***', 'timeout': 60}}}}
    )
    expected = copy.deepcopy(original)
    expected['ai']['n8n']['timeout'] = 60
    assert stored_config(service) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('section', ['trigger', 'safety', 'ai', 'output', 'speech'])
@pytest.mark.parametrize('value', [None, [], 'invalid'])
async def test_non_object_section_is_rejected_before_writing(service, section, value):
    with pytest.raises(ValueError, match=rf'config\.{section} must be an object'):
        await service.update_pipeline('workspace', 'pipeline', {'config': {section: value}})
    service.ap.persistence_mgr.execute_async.assert_not_awaited()
    service.ap.pipeline_mgr.prepare_pipeline.assert_not_awaited()


@pytest.mark.asyncio
async def test_partial_config_cannot_bypass_manual_migration(service):
    service.get_pipeline.return_value['config']['ai'] = {'runner': 'local-agent'}
    with pytest.raises(ValueError, match='manual_migration_required'):
        await service.update_pipeline(
            'workspace', 'pipeline', {'config': {'ai': {'runner': {'id': 'plugin:example/Runner/default'}}}}
        )
    service.ap.persistence_mgr.execute_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('config', [None, [], 'invalid'])
async def test_non_object_config_is_rejected(service, config):
    with pytest.raises(ValueError, match='config must be an object'):
        await service.update_pipeline('workspace', 'pipeline', {'config': config})
    service.ap.persistence_mgr.execute_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_settings_moved_to_the_message_policy_are_accepted_and_ignored(service):
    """A client that predates the message policy still submits these keys."""
    original = copy.deepcopy(service.get_pipeline.return_value['config'])
    await service.update_pipeline(
        'workspace',
        'pipeline',
        {
            'config': {
                'trigger': {'group-respond-rules': {'at': True, 'prefix': [], 'regexp': [], 'random': 0}},
                'safety': {'rate-limit': {'window-length': 60, 'limitation': 1, 'strategy': 'drop'}},
                'output': {
                    'long-text-processing': {'threshold': 10, 'strategy': 'forward', 'font-path': ''},
                    'force-delay': {'min': 1, 'max': 2},
                    'misc': {'at-sender': True, 'quote-origin': True, 'remove-think': True},
                },
            }
        },
    )
    assert stored_config(service) == {**original, 'output': {'misc': {'remove-think': True}}}
