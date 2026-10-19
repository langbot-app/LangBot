"""Runner selection must survive restricted extension preferences on disk."""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa

from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from tests.unit_tests.api.service.test_pipeline_migration import env, context, RID  # noqa: F401


@pytest.mark.asyncio
async def test_edit_and_copy_do_not_expand_extension_permissions(env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        'langbot.pkg.api.http.service.workspace_limits.workspace_limits',
        AsyncMock(return_value={}),
    )
    env.ap.ver_mgr = NS(get_current_version=Mock(return_value='4.10'))
    env.ap.pipeline_mgr.load_pipeline = AsyncMock()
    env.ap.pipeline_mgr.remove_pipeline = AsyncMock()
    service = PipelineService(env.ap)
    config = {'ai': {'runner': {'id': RID}, 'runner_config': {RID: {}}}}
    prefs = {'enable_all_plugins': False, 'plugins': [], 'enable_all_mcp_servers': False, 'mcp_servers': []}
    # Existing, pre-fix configuration: selected Runner with no extensions.
    async with env.engine.begin() as conn:
        await conn.execute(
            sa.update(LegacyPipeline)
            .where(LegacyPipeline.uuid == 'one')
            .values(
                config=config,
                extensions_preferences=prefs,
            )
        )
    await service.update_pipeline(context(), 'one', {'config': config, 'name': 'Edited'})
    copied = await service.copy_pipeline(context(), 'one')
    for pid in ('one', copied):
        saved = await service.get_pipeline(context(), pid, include_secret=True)
        assert saved['config'] == config
        assert saved['extensions_preferences']['plugins'] == []
        assert saved['extensions_preferences']['enable_all_plugins'] is False
    with pytest.raises(WorkspaceNotFoundError):
        await service.copy_pipeline(context(), 'foreign')
