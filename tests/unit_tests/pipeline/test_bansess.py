"""
BanSessionCheckStage unit tests

Tests the actual BanSessionCheckStage implementation from pkg.pipeline.bansess
"""

import pytest
from importlib import import_module
import langbot_plugin.api.entities.builtin.provider.session as provider_session


def get_modules():
    """Lazy import to ensure proper initialization order"""
    # Import pipelinemgr first to trigger proper stage registration
    bansess = import_module('langbot.pkg.pipeline.bansess.bansess')
    entities = import_module('langbot.pkg.pipeline.entities')
    return bansess, entities


@pytest.mark.asyncio
async def test_whitelist_allow(mock_app, sample_query):
    """Test whitelist allows matching session"""
    bansess, entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {'trigger': {'access-control': {'mode': 'whitelist', 'whitelist': ['person_12345']}}}

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE
    assert result.new_query == sample_query


@pytest.mark.asyncio
async def test_whitelist_deny(mock_app, sample_query):
    """Test whitelist denies non-matching session"""
    bansess, entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '99999'
    sample_query.pipeline_config = {'trigger': {'access-control': {'mode': 'whitelist', 'whitelist': ['person_12345']}}}

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_blacklist_allow(mock_app, sample_query):
    """Test blacklist allows non-matching session"""
    bansess, entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {'trigger': {'access-control': {'mode': 'blacklist', 'blacklist': ['person_99999']}}}

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_blacklist_deny(mock_app, sample_query):
    """Test blacklist denies matching session"""
    bansess, entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {'trigger': {'access-control': {'mode': 'blacklist', 'blacklist': ['person_12345']}}}

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_wildcard_group(mock_app, sample_query):
    """Test group wildcard matching"""
    bansess, entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {'trigger': {'access-control': {'mode': 'whitelist', 'whitelist': ['group_*']}}}

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_wildcard_person(mock_app, sample_query):
    """Test person wildcard matching"""
    bansess, entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {'trigger': {'access-control': {'mode': 'whitelist', 'whitelist': ['person_*']}}}

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_user_id_wildcard(mock_app, sample_query):
    """Test user ID wildcard matching (*_id format)"""
    bansess, entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.launcher_id = '12345'
    sample_query.sender_id = '67890'
    sample_query.pipeline_config = {'trigger': {'access-control': {'mode': 'whitelist', 'whitelist': ['*_67890']}}}

    stage = bansess.BanSessionCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'BanSessionCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE
