"""Preparation must not publish or evict a previously usable runtime."""

import copy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.pipeline.pipelinemgr import PipelineManager


@pytest.mark.asyncio
async def test_prepare_is_unpublished_and_failure_retains_old_runtime(monkeypatch):
    assert hasattr(PipelineManager, 'prepare_pipeline'), 'runtime preparation seam missing'
    ctx = ExecutionContext('instance', 'workspace', 1, pipeline_uuid='pipeline')
    ap = NS(workspace_service=NS(get_execution_binding=AsyncMock()), logger=Mock())
    mgr = PipelineManager(ap)
    mgr.stage_dict = {}
    source = dict(
        uuid='pipeline',
        workspace_uuid='workspace',
        name='old',
        description='',
        stages=[],
        config={},
        extensions_preferences={},
    )
    await mgr.load_pipeline(ctx, copy.deepcopy(source))
    old = mgr.pipelines[0]
    candidate = await mgr.prepare_pipeline(ctx, {**copy.deepcopy(source), 'name': 'new'})
    assert mgr.pipelines == [old]
    mgr.publish_pipeline(candidate)
    assert mgr.pipelines == [candidate]
    assert candidate.pipeline_entity.name == 'new'

    class BrokenStage:
        def __init__(self, ap):
            pass

        async def initialize(self, config):
            raise RuntimeError('preparation failed')

    mgr.stage_dict = {'broken': BrokenStage}
    with pytest.raises(RuntimeError, match='preparation failed'):
        await mgr.prepare_pipeline(ctx, {**copy.deepcopy(source), 'stages': ['broken']})
    assert mgr.pipelines == [candidate]
