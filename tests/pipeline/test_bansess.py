"""
BanSessionCheckStage stage unit tests
"""

import pytest
from unittest.mock import Mock

from pkg.pipeline.bansess.bansess import BanSessionCheckStage
from pkg.pipeline import entities as pipeline_entities
import langbot_plugin.api.entities.builtin.provider.session as provider_session


@pytest.mark.asyncio
async def test_bansess_whitelist_allow(mock_app, sample_query):
    """Test whitelist mode allows access"""
    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': [f'{sample_query.launcher_type.value}_{sample_query.launcher_id}'],
        }
    }

    stage = BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_bansess_whitelist_deny(mock_app, sample_query):
    """Test whitelist mode denies access"""
    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': ['person_99999'],  # Not in whitelist
        }
    }

    stage = BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == pipeline_entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_bansess_blacklist_allow(mock_app, sample_query):
    """Test blacklist mode allows access"""
    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'blacklist',
            'blacklist': ['person_99999'],  # Not in blacklist
        }
    }

    stage = BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_bansess_blacklist_deny(mock_app, sample_query):
    """Test blacklist mode denies access"""
    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'blacklist',
            'blacklist': [f'{sample_query.launcher_type.value}_{sample_query.launcher_id}'],
        }
    }

    stage = BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == pipeline_entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_bansess_wildcard_group(mock_app, sample_query):
    """Test group wildcard"""
    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': ['group_*'],  # All groups
        }
    }

    stage = BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_bansess_wildcard_person(mock_app, sample_query):
    """Test person wildcard"""
    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': ['person_*'],  # All persons
        }
    }

    stage = BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE
