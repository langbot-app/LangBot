from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_create_pipeline_preserves_submitted_config_and_keeps_template_defaults():
    executed_statements = []

    async def fake_execute_async(statement):
        executed_statements.append(statement)
        return None

    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={}),
        ver_mgr=SimpleNamespace(get_current_version=lambda: 'test-version'),
        persistence_mgr=SimpleNamespace(execute_async=fake_execute_async),
        pipeline_mgr=SimpleNamespace(load_pipeline=AsyncMock()),
    )

    from langbot.pkg.api.http.service.pipeline import PipelineService

    service = PipelineService(ap)
    service.get_pipeline = AsyncMock(return_value={'uuid': 'created-pipeline'})

    submitted_config = {
        'ai': {
            'runner': {
                'runner': 'dify-service-api',
            },
            'dify-service-api': {
                'base-url': 'https://example-dify.invalid/v1',
                'app-type': 'workflow',
                'api-key': 'secret-key',
                'base-prompt': 'Use submitted dify prompt',
            },
        }
    }

    await service.create_pipeline(
        {
            'name': 'New Pipeline',
            'description': 'created from test',
            'config': submitted_config,
        }
    )

    insert_statement = executed_statements[0]
    inserted_config = insert_statement.compile().params['config']

    assert inserted_config['ai']['runner']['runner'] == 'dify-service-api'
    assert inserted_config['ai']['dify-service-api']['base-url'] == 'https://example-dify.invalid/v1'
    assert inserted_config['ai']['dify-service-api']['app-type'] == 'workflow'
    assert inserted_config['ai']['dify-service-api']['api-key'] == 'secret-key'
    assert inserted_config['ai']['dify-service-api']['base-prompt'] == 'Use submitted dify prompt'

    # Unspecified sections should still inherit defaults from the template.
    assert inserted_config['trigger']['group-respond-rules']['at'] is True
    assert inserted_config['output']['misc']['exception-handling'] == 'show-hint'
