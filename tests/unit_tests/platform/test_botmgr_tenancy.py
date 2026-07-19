from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.botmgr import PlatformManager, RuntimeBot
import langbot_plugin.api.entities.builtin.platform.events as platform_events


WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'
BOT_A = '10000000-0000-0000-0000-00000000000a'
BOT_B = '10000000-0000-0000-0000-00000000000b'


def _context(workspace_uuid: str, bot_uuid: str, generation: int = 4) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid='instance',
        workspace_uuid=workspace_uuid,
        placement_generation=generation,
        bot_uuid=bot_uuid,
    )


def _runtime(application, workspace_uuid: str, bot_uuid: str) -> RuntimeBot:
    entity = SimpleNamespace(
        uuid=bot_uuid,
        workspace_uuid=workspace_uuid,
        name='Same Name',
        enable=True,
        pipeline_routing_rules=[],
        use_pipeline_uuid=None,
    )
    return RuntimeBot(
        ap=application,
        bot_entity=entity,
        adapter=SimpleNamespace(),
        logger=SimpleNamespace(),
        execution_context=_context(workspace_uuid, bot_uuid),
    )


class _WorkspaceService:
    async def get_execution_binding(self, workspace_uuid, expected_generation=None):
        if workspace_uuid not in {WORKSPACE_A, WORKSPACE_B} or expected_generation != 4:
            raise ValueError('stale')
        return SimpleNamespace(
            instance_uuid='instance',
            workspace_uuid=workspace_uuid,
            placement_generation=4,
        )


@pytest.fixture
def manager():
    application = SimpleNamespace(workspace_service=_WorkspaceService())
    platform_manager = PlatformManager(application)
    platform_manager.bots = [
        _runtime(application, WORKSPACE_A, BOT_A),
        _runtime(application, WORKSPACE_B, BOT_B),
    ]
    return platform_manager


@pytest.mark.asyncio
async def test_runtime_lookup_cannot_guess_another_workspace_bot(manager):
    assert await manager.get_bot_by_uuid(_context(WORKSPACE_A, BOT_A), BOT_A) is manager.bots[0]
    assert await manager.get_bot_by_uuid(_context(WORKSPACE_B, BOT_A), BOT_A) is None
    assert await manager.get_bot_by_uuid(_context(WORKSPACE_A, BOT_B), BOT_B) is None


@pytest.mark.asyncio
async def test_public_route_key_resolves_bound_runtime_and_rejects_non_opaque_input(manager):
    assert await manager.resolve_public_bot(BOT_A) is manager.bots[0]
    assert await manager.resolve_public_bot('Same Name') is None
    assert await manager.resolve_public_bot('not-a-uuid') is None


@pytest.mark.asyncio
async def test_stale_runtime_generation_is_not_returned(manager):
    assert await manager.get_bot_by_uuid(_context(WORKSPACE_A, BOT_A, generation=5), BOT_A) is None


@pytest.mark.asyncio
async def test_runtime_bot_revalidates_its_generation_before_handling_events(manager):
    runtime_bot = manager.bots[0]

    await runtime_bot.assert_execution_active()

    runtime_bot.placement_generation = 5
    with pytest.raises(ValueError, match='stale'):
        await runtime_bot.assert_execution_active()


def test_runtime_bot_rejects_workspace_mismatch():
    application = SimpleNamespace()
    entity = SimpleNamespace(
        uuid=BOT_A,
        workspace_uuid=WORKSPACE_A,
        name='Bot',
        enable=True,
        pipeline_routing_rules=[],
        use_pipeline_uuid=None,
    )
    with pytest.raises(WorkspaceRequiredError):
        RuntimeBot(
            ap=application,
            bot_entity=entity,
            adapter=SimpleNamespace(),
            logger=SimpleNamespace(),
            execution_context=_context(WORKSPACE_B, BOT_A),
        )


class _ScopeOnlyPersistenceManager:
    mode = SimpleNamespace(value='cloud_runtime')

    def __init__(self):
        self.active_workspace = None

    @contextlib.asynccontextmanager
    async def tenant_scope(self, workspace_uuid: str):
        assert self.active_workspace is None
        self.active_workspace = workspace_uuid
        try:
            yield
        finally:
            self.active_workspace = None

    def current_session(self):
        return None


class _ListenerAdapter:
    def __init__(self):
        self.listeners = {}

    def register_listener(self, event_type, listener):
        self.listeners[event_type] = listener


@pytest.mark.asyncio
async def test_platform_callback_carries_scope_without_holding_database_session():
    persistence_mgr = _ScopeOnlyPersistenceManager()
    adapter = _ListenerAdapter()

    async def push_person_message(*_args, **_kwargs):
        assert persistence_mgr.active_workspace == WORKSPACE_A
        assert persistence_mgr.current_session() is None
        return True

    application = SimpleNamespace(
        persistence_mgr=persistence_mgr,
        workspace_service=_WorkspaceService(),
        webhook_pusher=SimpleNamespace(push_person_message=push_person_message),
    )
    entity = SimpleNamespace(
        uuid=BOT_A,
        workspace_uuid=WORKSPACE_A,
        name='Bot',
        enable=True,
        pipeline_routing_rules=[],
        use_pipeline_uuid=None,
    )
    logger = SimpleNamespace(info=AsyncMock(), error=AsyncMock())
    runtime = RuntimeBot(
        ap=application,
        bot_entity=entity,
        adapter=adapter,
        logger=logger,
        execution_context=_context(WORKSPACE_A, BOT_A),
    )
    await runtime.initialize()

    listener = adapter.listeners[platform_events.FriendMessage]
    event = SimpleNamespace(message_chain=[], sender=SimpleNamespace(id='user'))
    await listener(event, adapter)

    assert persistence_mgr.active_workspace is None
    logger.info.assert_awaited()
