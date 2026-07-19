from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.sources.openclaw_weixin import OpenClawWeixinAdapter


def make_adapter(*, execution_context: ExecutionContext | None):
    app = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid='instance-a',
                    workspace_uuid='workspace-a',
                    placement_generation=1,
                )
            )
        ),
    )
    logger = SimpleNamespace(
        ap=app,
        execution_context=execution_context,
        warning=AsyncMock(),
    )
    adapter = OpenClawWeixinAdapter.model_construct(
        config={'token': 'refreshed-token'},
        logger=logger,
        client=Mock(),
        bot_account_id='',
        listeners={},
        name='openclaw-weixin',
    )
    adapter._bot_uuid = 'shared-bot-uuid'
    return adapter, app, logger


@pytest.mark.asyncio
async def test_persist_config_scopes_duplicate_bot_uuid_to_workspace():
    adapter, app, _ = make_adapter(
        execution_context=ExecutionContext(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            placement_generation=1,
            bot_uuid='shared-bot-uuid',
        )
    )

    await adapter._persist_config()

    app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'workspace-a',
        expected_generation=1,
    )
    statement = app.persistence_mgr.execute_async.await_args.args[0]
    params = statement.compile().params
    assert 'workspace-a' in params.values()
    assert 'shared-bot-uuid' in params.values()
    assert {'workspace_uuid', 'uuid'} <= {comparison.left.name for comparison in statement._where_criteria}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'execution_context',
    [
        None,
        ExecutionContext(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            placement_generation=1,
            bot_uuid='another-bot-uuid',
        ),
    ],
    ids=['missing-context', 'mismatched-bot'],
)
async def test_persist_config_fails_closed_without_matching_execution_context(execution_context):
    adapter, app, logger = make_adapter(execution_context=execution_context)

    await adapter._persist_config()

    app.persistence_mgr.execute_async.assert_not_awaited()
    logger.warning.assert_awaited_once()
