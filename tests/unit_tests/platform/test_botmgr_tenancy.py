from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.bot import Bot
from langbot.pkg.platform.botmgr import PlatformManager, RuntimeBot
from langbot.pkg.workspace.entities import WorkspaceExecutionBinding
from langbot.pkg.workspace.errors import WorkspaceInvariantError
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
    with pytest.raises(ValueError, match='stale'):
        await manager.get_bot_by_uuid(_context(WORKSPACE_A, BOT_A, generation=5), BOT_A)


@pytest.mark.asyncio
async def test_generation_advance_shuts_down_and_prunes_old_workspace_bots():
    class NoGlobalIterationDict(dict):
        def __iter__(self):
            raise AssertionError('generation advance scanned every bot runtime')

        def items(self):
            raise AssertionError('generation advance scanned every bot runtime')

        def values(self):
            raise AssertionError('generation advance scanned every bot runtime')

    manager = PlatformManager(SimpleNamespace())
    old_bot = SimpleNamespace(
        workspace_uuid=WORKSPACE_A,
        placement_generation=4,
        enable=True,
        shutdown=AsyncMock(),
    )
    other_bot = SimpleNamespace(
        workspace_uuid=WORKSPACE_B,
        placement_generation=4,
        enable=True,
        shutdown=AsyncMock(),
    )
    unrelated_bots = [
        SimpleNamespace(
            workspace_uuid=f'workspace-{index}',
            placement_generation=4,
            enable=False,
            shutdown=AsyncMock(),
        )
        for index in range(1_000)
    ]
    manager.bots = [old_bot, other_bot, *unrelated_bots]
    old_context = _context(WORKSPACE_A, BOT_A, generation=4)
    next_context = _context(WORKSPACE_A, BOT_A, generation=5)

    await manager._observe_execution_context(old_context)
    manager._bots_by_key = NoGlobalIterationDict(manager._bots_by_key)
    await manager._observe_execution_context(next_context)
    manager._bots_by_key = dict(manager._bots_by_key)

    old_bot.shutdown.assert_awaited_once_with()
    assert manager.bots == [other_bot, *unrelated_bots]
    with pytest.raises(WorkspaceInvariantError, match='rolled back'):
        await manager._observe_execution_context(old_context)


@pytest.mark.asyncio
async def test_concurrent_websocket_proxy_creation_reuses_one_runtime():
    created_adapters = []

    class WebsocketAdapter:
        def __init__(self, *_args, **_kwargs):
            created_adapters.append(self)

        def register_listener(self, *_args):
            pass

    application = SimpleNamespace(workspace_service=_WorkspaceService())
    manager = PlatformManager(application)
    manager.adapter_dict = {'websocket': WebsocketAdapter}
    context = ExecutionContext(
        instance_uuid='instance',
        workspace_uuid=WORKSPACE_A,
        placement_generation=4,
    )

    runtimes = await asyncio.gather(*(manager.get_websocket_proxy_bot(context) for _ in range(20)))

    assert len(created_adapters) == 1
    assert len({id(runtime) for runtime in runtimes}) == 1
    assert manager.websocket_proxy_bots == {WORKSPACE_A: runtimes[0]}


@pytest.mark.asyncio
async def test_websocket_proxy_cache_evicts_oldest_idle_workspace():
    created_adapters = []

    class WebsocketAdapter:
        def __init__(self, *_args, **_kwargs):
            self.kill = AsyncMock()
            self.inbound_listener_tasks = set()
            created_adapters.append(self)

        def register_listener(self, *_args):
            pass

    application = SimpleNamespace(
        workspace_service=_WorkspaceService(),
        instance_config=SimpleNamespace(
            data={
                'system': {
                    'websocket_retention': {'max_workspace_proxies': 1},
                }
            }
        ),
    )
    manager = PlatformManager(application)
    manager.adapter_dict = {'websocket': WebsocketAdapter}

    await manager.get_websocket_proxy_bot(
        ExecutionContext(
            instance_uuid='instance',
            workspace_uuid=WORKSPACE_A,
            placement_generation=4,
        )
    )
    second = await manager.get_websocket_proxy_bot(
        ExecutionContext(
            instance_uuid='instance',
            workspace_uuid=WORKSPACE_B,
            placement_generation=4,
        )
    )

    created_adapters[0].kill.assert_awaited_once_with()
    assert manager.websocket_proxy_bots == {WORKSPACE_B: second}
    assert WORKSPACE_A not in manager._proxy_last_accessed


@pytest.mark.asyncio
async def test_reload_stops_and_drops_existing_platform_runtimes():
    old_bot = SimpleNamespace(enable=True, shutdown=AsyncMock())
    old_proxy = SimpleNamespace(enable=True, shutdown=AsyncMock())
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
    )
    application = SimpleNamespace(
        logger=SimpleNamespace(info=lambda *_args: None, warning=lambda *_args: None),
        persistence_mgr=persistence_mgr,
        workspace_service=SimpleNamespace(),
    )
    manager = PlatformManager(application)
    manager.bots = [old_bot]
    manager.websocket_proxy_bots = {WORKSPACE_A: old_proxy}
    manager._scope_generations = {('instance', WORKSPACE_A): 4}

    await manager.load_bots_from_db()

    old_bot.shutdown.assert_awaited_once_with()
    old_proxy.shutdown.assert_awaited_once_with()
    assert manager.bots == []
    assert manager.websocket_proxy_bots == {}
    assert manager._scope_generations == {}


@pytest.mark.asyncio
async def test_cloud_startup_reuses_validated_platform_binding():
    class TenantUow:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class ProbeAdapter:
        def __init__(self, _config, _logger):
            self.listeners = []

        def register_listener(self, event_type, listener):
            self.listeners.append((event_type, listener))

        async def kill(self):
            return None

    binding = WorkspaceExecutionBinding(
        instance_uuid='instance',
        workspace_uuid=WORKSPACE_A,
        placement_generation=4,
        write_fenced=False,
        state='active',
    )
    bot = Bot(
        uuid=BOT_A,
        workspace_uuid=WORKSPACE_A,
        name='Probe',
        description='',
        adapter='probe',
        adapter_config={},
        enable=False,
        pipeline_routing_rules=[],
    )
    workspace_service = SimpleNamespace(
        list_active_execution_bindings=AsyncMock(return_value=[binding]),
        get_execution_binding=AsyncMock(
            side_effect=AssertionError('startup platform loader repeated a validated binding lookup')
        ),
    )
    application = SimpleNamespace(
        logger=SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            warning=lambda *_args, **_kwargs: None,
            error=lambda *_args, **_kwargs: None,
        ),
        persistence_mgr=SimpleNamespace(
            mode=SimpleNamespace(value='cloud_runtime'),
            tenant_uow=lambda _workspace_uuid: TenantUow(),
            execute_async=AsyncMock(return_value=SimpleNamespace(all=lambda: [bot])),
        ),
        workspace_service=workspace_service,
    )
    manager = PlatformManager(application)
    manager.adapter_dict = {'probe': ProbeAdapter}

    await manager.load_bots_from_db()

    assert len(manager.bots) == 1
    workspace_service.get_execution_binding.assert_not_awaited()


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
