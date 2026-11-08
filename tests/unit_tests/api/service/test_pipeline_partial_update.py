import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.pipeline import PipelineService


@pytest.fixture
def service():
    config = {
        'trigger': {'keep': True},
        'safety': {'keep': True},
        'ai': {'n8n': {'webhook-url': 'https://example.invalid/secret', 'timeout': 30}},
        'output': {'keep': True},
    }
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=Mock(rowcount=1))),
        pipeline_mgr=SimpleNamespace(prepare_pipeline=AsyncMock(), publish_pipeline=Mock()),
        sess_mgr=SimpleNamespace(session_list=[]),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock()),
    )
    result = PipelineService(ap)
    result.get_pipeline = AsyncMock(return_value={'uuid': 'pipeline', 'config': config})
    return result


def stored_config(service):
    statement = service.ap.persistence_mgr.execute_async.await_args.args[0]
    return next(value.value for column, value in statement._values.items() if column.key == 'config')


def ai_section(model_selection):
    runner_id = 'plugin:example/Runner/default'
    return {'runner': {'id': runner_id}, 'runner_config': {runner_id: {'model': model_selection}}}


def runtime_model(abilities=('reasoning',), extra_args=None, requester='deepseek-chat-completions'):
    capabilities = {'supported': True, 'levels': ['provider_default', 'disabled', 'low', 'high', 'max']}
    return SimpleNamespace(
        model_entity=SimpleNamespace(name='deepseek-flash', abilities=list(abilities), extra_args=extra_args),
        provider=SimpleNamespace(
            provider_entity=SimpleNamespace(requester=requester),
            requester=SimpleNamespace(get_reasoning_capabilities=Mock(return_value=capabilities)),
        ),
    )


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
@pytest.mark.parametrize(
    ('selection', 'model_options', 'message'),
    [
        pytest.param(
            {'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'medium'}},
            {},
            'not supported by model deepseek-flash',
            id='primary',
        ),
        pytest.param(
            {'primary': 'other', 'fallbacks': ['model'], 'reasoning': {'model': 'medium'}},
            {},
            'not supported by model deepseek-flash',
            id='fallback',
        ),
        pytest.param(
            {'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'turbo'}},
            {},
            'Unsupported reasoning level',
            id='unknown-level',
        ),
        pytest.param(
            {'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'high'}},
            {'abilities': ()},
            'reasoning ability must be enabled',
            id='missing-ability',
        ),
        pytest.param(
            {'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'high'}},
            {'extra_args': {'reasoning_effort': 'high'}},
            'conflicts with advanced parameters',
            id='extra-args-conflict',
        ),
        pytest.param(
            {'primary': 'model', 'fallbacks': [], 'reasoning': 'high'},
            {},
            'reasoning settings must be an object',
            id='reasoning-string',
        ),
        pytest.param(
            {'primary': 'model', 'fallbacks': [], 'reasoning': None},
            {},
            'reasoning settings must be an object',
            id='reasoning-null',
        ),
    ],
)
async def test_invalid_reasoning_level_is_rejected_before_writing(service, selection, model_options, message):
    service.ap.model_mgr.get_model_by_uuid.return_value = runtime_model(**model_options)
    with pytest.raises(ValueError, match=message):
        await service.update_pipeline('workspace', 'pipeline', {'config': {'ai': ai_section(selection)}})
    service.ap.pipeline_mgr.prepare_pipeline.assert_not_awaited()
    service.ap.persistence_mgr.execute_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'model_options',
    [{}, {'abilities': (), 'requester': 'space-chat-completions'}],
    ids=['declared-ability', 'space-model-without-ability-flag'],
)
async def test_supported_reasoning_level_is_checked_and_saved(service, model_options):
    service.ap.model_mgr.get_model_by_uuid.return_value = runtime_model(**model_options)
    ai = ai_section({'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'high'}})
    await service.update_pipeline('workspace', 'pipeline', {'config': {'ai': ai}})
    service.ap.model_mgr.get_model_by_uuid.assert_awaited_once_with('workspace', 'model')
    assert stored_config(service)['ai'] == ai


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'reasoning',
    [{'model': 'provider_default'}, {'model': None}, {'unselected-model': 'high'}],
    ids=['provider-default', 'no-level', 'unselected-model'],
)
async def test_reasoning_entries_runners_ignore_need_no_model_lookup(service, reasoning):
    ai = ai_section({'primary': 'model', 'fallbacks': [], 'reasoning': reasoning})
    await service.update_pipeline('workspace', 'pipeline', {'config': {'ai': ai}})
    service.ap.model_mgr.get_model_by_uuid.assert_not_awaited()
    assert stored_config(service)['ai'] == ai


@pytest.mark.asyncio
async def test_model_selection_without_reasoning_key_needs_no_model_lookup(service):
    ai = ai_section({'primary': 'model', 'fallbacks': []})
    await service.update_pipeline('workspace', 'pipeline', {'config': {'ai': ai}})
    service.ap.model_mgr.get_model_by_uuid.assert_not_awaited()
    assert stored_config(service)['ai'] == ai


@pytest.mark.asyncio
async def test_deleted_model_does_not_block_saving(service):
    service.ap.model_mgr.get_model_by_uuid.side_effect = ValueError('LLM model model not found')
    ai = ai_section({'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'high'}})
    await service.update_pipeline('workspace', 'pipeline', {'config': {'ai': ai}})
    service.ap.model_mgr.get_model_by_uuid.assert_awaited_once_with('workspace', 'model')
    assert stored_config(service)['ai'] == ai


@pytest.mark.asyncio
@pytest.mark.parametrize('resend_ai', [False, True], ids=['partial-update', 'full-config-update'])
async def test_update_leaving_ai_unchanged_does_not_recheck_existing_level(service, resend_ai):
    ai = ai_section({'primary': 'model', 'fallbacks': [], 'reasoning': {'model': 'high'}})
    ai['n8n'] = {'webhook-url': 'https://example.invalid/secret'}
    service.get_pipeline.return_value['config']['ai'] = ai
    config = {'trigger': {'keep': False}}
    if resend_ai:
        config['ai'] = {**copy.deepcopy(ai), 'n8n': {'webhook-url': '***'}}
    await service.update_pipeline('workspace', 'pipeline', {'config': config})
    service.ap.model_mgr.get_model_by_uuid.assert_not_awaited()
    assert stored_config(service)['trigger'] == {'keep': False}
