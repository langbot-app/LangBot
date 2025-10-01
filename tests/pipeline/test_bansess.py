"""
BanSessionCheckStage stage unit tests
"""

import pytest
from unittest.mock import Mock
import sys
from importlib import import_module

import langbot_plugin.api.entities.builtin.provider.session as provider_session


# Lazy import to avoid circular dependency issues
def get_bansess_module():
    return import_module('pkg.pipeline.bansess.bansess')


def get_entities_module():
    return import_module('pkg.pipeline.entities')


@pytest.mark.asyncio
async def test_bansess_whitelist_allow(mock_app, sample_query):
    """Test whitelist mode allows access"""
    bansess = get_bansess_module()
    entities = get_entities_module()

    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': [f'{sample_query.launcher_type.value}_{sample_query.launcher_id}'],
        }
    }

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_bansess_whitelist_deny(mock_app, sample_query):
    """Test whitelist mode denies access"""
    bansess = get_bansess_module()
    entities = get_entities_module()

    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': ['person_99999'],  # Not in whitelist
        }
    }

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_bansess_blacklist_allow(mock_app, sample_query):
    """Test blacklist mode allows access"""
    bansess = get_bansess_module()
    entities = get_entities_module()

    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'blacklist',
            'blacklist': ['person_99999'],  # Not in blacklist
        }
    }

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_bansess_blacklist_deny(mock_app, sample_query):
    """Test blacklist mode denies access"""
    bansess = get_bansess_module()
    entities = get_entities_module()

    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'blacklist',
            'blacklist': [f'{sample_query.launcher_type.value}_{sample_query.launcher_id}'],
        }
    }

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_bansess_wildcard_group(mock_app, sample_query):
    """Test group wildcard"""
    bansess = get_bansess_module()
    entities = get_entities_module()

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': ['group_*'],  # All groups
        }
    }

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_bansess_wildcard_person(mock_app, sample_query):
    """Test person wildcard"""
    bansess = get_bansess_module()
    entities = get_entities_module()

    sample_query.pipeline_config['trigger'] = {
        'access-control': {
            'mode': 'whitelist',
            'whitelist': ['person_*'],  # All persons
        }
    }

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE
