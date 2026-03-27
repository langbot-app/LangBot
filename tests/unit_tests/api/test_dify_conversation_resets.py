from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class FakeConversationStore:
    def __init__(self, raise_on_delete: bool = False):
        self.raise_on_delete = raise_on_delete
        self.delete_calls: list[tuple[str, str, str, str]] = []

    async def delete_conversation_id(self, bot_uuid: str, pipeline_uuid: str, launcher_type: str, launcher_id: str):
        self.delete_calls.append((bot_uuid, pipeline_uuid, launcher_type, launcher_id))
        if self.raise_on_delete:
            raise RuntimeError('forced delete failure')


class LauncherType:
    def __init__(self, value: str):
        self.value = value


def _make_session(bot_uuid: str, pipeline_uuid: str, launcher_type='person', launcher_id='u-1'):
    return SimpleNamespace(
        launcher_type=LauncherType(launcher_type) if launcher_type is not None else None,
        launcher_id=launcher_id,
        using_conversation=SimpleNamespace(bot_uuid=bot_uuid, pipeline_uuid=pipeline_uuid),
    )


def _warning_messages(mock_logger: MagicMock) -> list[str]:
    return [str(call.args[0]) for call in mock_logger.warning.call_args_list if call.args]


@pytest.mark.asyncio
async def test_plugin_create_new_conversation_deletes_persisted_binding_when_scope_exists(monkeypatch):
    import langbot.pkg.plugin.handler as plugin_handler_module

    store = FakeConversationStore()
    monkeypatch.setattr(plugin_handler_module, '_get_dify_conversation_store', lambda ap: store)

    query = SimpleNamespace(
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        session=SimpleNamespace(
            launcher_type=LauncherType('person'),
            launcher_id='user-1',
            using_conversation=SimpleNamespace(bot_uuid='bot-1', pipeline_uuid='pipe-1'),
        ),
    )

    mock_ap = SimpleNamespace(
        query_pool=SimpleNamespace(cached_queries={'q-1': query}),
        logger=MagicMock(),
    )

    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    handler = RuntimeConnectionHandler(
        connection=MagicMock(),
        disconnect_callback=AsyncMock(return_value=False),
        ap=mock_ap,
    )

    action = handler.actions[PluginToRuntimeAction.CREATE_NEW_CONVERSATION.value]
    response = await action({'query_id': 'q-1'})

    assert response.code == 0
    assert query.session.using_conversation is None
    assert store.delete_calls == [('bot-1', 'pipe-1', 'person', 'user-1')]


@pytest.mark.asyncio
async def test_plugin_create_new_conversation_store_getter_none_still_resets_in_memory(monkeypatch):
    import langbot.pkg.plugin.handler as plugin_handler_module

    monkeypatch.setattr(plugin_handler_module, '_get_dify_conversation_store', lambda ap: None)

    query = SimpleNamespace(
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        session=SimpleNamespace(
            launcher_type=LauncherType('person'),
            launcher_id='user-1',
            using_conversation=SimpleNamespace(bot_uuid='bot-1', pipeline_uuid='pipe-1'),
        ),
    )

    mock_ap = SimpleNamespace(
        query_pool=SimpleNamespace(cached_queries={'q-1': query}),
        logger=MagicMock(),
    )

    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    handler = RuntimeConnectionHandler(
        connection=MagicMock(),
        disconnect_callback=AsyncMock(return_value=False),
        ap=mock_ap,
    )

    action = handler.actions[PluginToRuntimeAction.CREATE_NEW_CONVERSATION.value]
    response = await action({'query_id': 'q-1'})

    assert response.code == 0
    assert query.session.using_conversation is None


@pytest.mark.asyncio
async def test_plugin_create_new_conversation_incomplete_scope_skips_delete_but_resets(monkeypatch):
    import langbot.pkg.plugin.handler as plugin_handler_module

    store = FakeConversationStore()
    monkeypatch.setattr(plugin_handler_module, '_get_dify_conversation_store', lambda ap: store)

    query = SimpleNamespace(
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        session=SimpleNamespace(
            launcher_type=None,
            launcher_id='user-1',
            using_conversation=SimpleNamespace(bot_uuid='bot-1', pipeline_uuid='pipe-1'),
        ),
    )

    mock_ap = SimpleNamespace(
        query_pool=SimpleNamespace(cached_queries={'q-1': query}),
        logger=MagicMock(),
    )

    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    handler = RuntimeConnectionHandler(
        connection=MagicMock(),
        disconnect_callback=AsyncMock(return_value=False),
        ap=mock_ap,
    )

    action = handler.actions[PluginToRuntimeAction.CREATE_NEW_CONVERSATION.value]
    response = await action({'query_id': 'q-1'})

    assert response.code == 0
    assert query.session.using_conversation is None
    assert store.delete_calls == []


@pytest.mark.asyncio
async def test_plugin_create_new_conversation_delete_failure_logs_scope_and_does_not_fail(monkeypatch):
    import langbot.pkg.plugin.handler as plugin_handler_module

    store = FakeConversationStore(raise_on_delete=True)
    monkeypatch.setattr(plugin_handler_module, '_get_dify_conversation_store', lambda ap: store)

    query = SimpleNamespace(
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        session=SimpleNamespace(
            launcher_type=LauncherType('group'),
            launcher_id='group-1',
            using_conversation=SimpleNamespace(bot_uuid='bot-1', pipeline_uuid='pipe-1'),
        ),
    )

    mock_ap = SimpleNamespace(
        query_pool=SimpleNamespace(cached_queries={'q-1': query}),
        logger=MagicMock(),
    )

    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    handler = RuntimeConnectionHandler(
        connection=MagicMock(),
        disconnect_callback=AsyncMock(return_value=False),
        ap=mock_ap,
    )

    action = handler.actions[PluginToRuntimeAction.CREATE_NEW_CONVERSATION.value]
    response = await action({'query_id': 'q-1'})

    assert response.code == 0
    assert query.session.using_conversation is None
    assert store.delete_calls == [('bot-1', 'pipe-1', 'group', 'group-1')]
    warnings = _warning_messages(mock_ap.logger)
    assert any('bot_uuid=bot-1' in msg for msg in warnings)
    assert any('pipeline_uuid=pipe-1' in msg for msg in warnings)
    assert any('launcher_type=group' in msg for msg in warnings)
    assert any('launcher_id=group-1' in msg for msg in warnings)


@pytest.mark.asyncio
async def test_bot_update_bot_deletes_persisted_bindings_for_matching_sessions(monkeypatch):
    import langbot.pkg.api.http.service.bot as bot_service_module

    store = FakeConversationStore()
    monkeypatch.setattr(bot_service_module, '_get_dify_conversation_store', lambda ap: store)

    runtime_bot = SimpleNamespace(enable=False, run=AsyncMock())

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        platform_mgr=SimpleNamespace(remove_bot=AsyncMock(), load_bot=AsyncMock(return_value=runtime_bot)),
        sess_mgr=SimpleNamespace(
            session_list=[
                _make_session('bot-1', 'pipe-1', 'person', 'user-1'),
                _make_session('bot-2', 'pipe-1', 'person', 'user-2'),
                _make_session('bot-1', 'pipe-2', 'group', 'group-1'),
                _make_session('bot-1', 'pipe-3', 'person', None),
            ]
        ),
        logger=MagicMock(),
    )

    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(ap)
    service.get_bot = AsyncMock(return_value={'uuid': 'bot-1'})

    await service.update_bot('bot-1', {'name': 'new name'})

    assert store.delete_calls == [
        ('bot-1', 'pipe-1', 'person', 'user-1'),
        ('bot-1', 'pipe-2', 'group', 'group-1'),
    ]
    assert ap.sess_mgr.session_list[0].using_conversation is None
    assert ap.sess_mgr.session_list[1].using_conversation is not None
    assert ap.sess_mgr.session_list[2].using_conversation is None
    assert ap.sess_mgr.session_list[3].using_conversation is None


@pytest.mark.asyncio
async def test_bot_update_bot_store_getter_none_still_clears_in_memory(monkeypatch):
    import langbot.pkg.api.http.service.bot as bot_service_module

    monkeypatch.setattr(bot_service_module, '_get_dify_conversation_store', lambda ap: None)

    runtime_bot = SimpleNamespace(enable=False, run=AsyncMock())
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        platform_mgr=SimpleNamespace(remove_bot=AsyncMock(), load_bot=AsyncMock(return_value=runtime_bot)),
        sess_mgr=SimpleNamespace(session_list=[_make_session('bot-1', 'pipe-1', 'person', 'user-1')]),
        logger=MagicMock(),
    )

    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(ap)
    service.get_bot = AsyncMock(return_value={'uuid': 'bot-1'})

    await service.update_bot('bot-1', {'name': 'new'})

    assert ap.sess_mgr.session_list[0].using_conversation is None


@pytest.mark.asyncio
async def test_bot_update_bot_incomplete_scope_skips_delete_but_clears_in_memory(monkeypatch):
    import langbot.pkg.api.http.service.bot as bot_service_module

    store = FakeConversationStore()
    monkeypatch.setattr(bot_service_module, '_get_dify_conversation_store', lambda ap: store)

    runtime_bot = SimpleNamespace(enable=False, run=AsyncMock())
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        platform_mgr=SimpleNamespace(remove_bot=AsyncMock(), load_bot=AsyncMock(return_value=runtime_bot)),
        sess_mgr=SimpleNamespace(session_list=[_make_session('bot-1', 'pipe-1', 'person', None)]),
        logger=MagicMock(),
    )

    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(ap)
    service.get_bot = AsyncMock(return_value={'uuid': 'bot-1'})

    await service.update_bot('bot-1', {'name': 'new'})

    assert store.delete_calls == []
    assert ap.sess_mgr.session_list[0].using_conversation is None


@pytest.mark.asyncio
async def test_pipeline_update_pipeline_deletes_persisted_bindings_for_matching_sessions(monkeypatch):
    import langbot.pkg.api.http.service.pipeline as pipeline_service_module

    store = FakeConversationStore()
    monkeypatch.setattr(pipeline_service_module, '_get_dify_conversation_store', lambda ap: store)

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        pipeline_mgr=SimpleNamespace(remove_pipeline=AsyncMock(), load_pipeline=AsyncMock()),
        sess_mgr=SimpleNamespace(
            session_list=[
                _make_session('bot-1', 'pipe-1', 'person', 'user-1'),
                _make_session('bot-2', 'pipe-2', 'person', 'user-2'),
                _make_session('bot-3', 'pipe-1', 'group', 'group-1'),
                _make_session('bot-4', 'pipe-1', None, 'missing-type'),
            ]
        ),
        logger=MagicMock(),
    )

    from langbot.pkg.api.http.service.pipeline import PipelineService

    service = PipelineService(ap)
    service.get_pipeline = AsyncMock(return_value={'uuid': 'pipe-1'})

    await service.update_pipeline('pipe-1', {'description': 'changed'})

    assert store.delete_calls == [
        ('bot-1', 'pipe-1', 'person', 'user-1'),
        ('bot-3', 'pipe-1', 'group', 'group-1'),
    ]
    assert ap.sess_mgr.session_list[0].using_conversation is None
    assert ap.sess_mgr.session_list[1].using_conversation is not None
    assert ap.sess_mgr.session_list[2].using_conversation is None
    assert ap.sess_mgr.session_list[3].using_conversation is None


@pytest.mark.asyncio
async def test_pipeline_update_pipeline_store_getter_none_still_clears_in_memory(monkeypatch):
    import langbot.pkg.api.http.service.pipeline as pipeline_service_module

    monkeypatch.setattr(pipeline_service_module, '_get_dify_conversation_store', lambda ap: None)

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        pipeline_mgr=SimpleNamespace(remove_pipeline=AsyncMock(), load_pipeline=AsyncMock()),
        sess_mgr=SimpleNamespace(session_list=[_make_session('bot-1', 'pipe-1', 'person', 'user-1')]),
        logger=MagicMock(),
    )

    from langbot.pkg.api.http.service.pipeline import PipelineService

    service = PipelineService(ap)
    service.get_pipeline = AsyncMock(return_value={'uuid': 'pipe-1'})

    await service.update_pipeline('pipe-1', {'description': 'new'})

    assert ap.sess_mgr.session_list[0].using_conversation is None


@pytest.mark.asyncio
async def test_pipeline_update_pipeline_incomplete_scope_skips_delete_but_clears_in_memory(monkeypatch):
    import langbot.pkg.api.http.service.pipeline as pipeline_service_module

    store = FakeConversationStore()
    monkeypatch.setattr(pipeline_service_module, '_get_dify_conversation_store', lambda ap: store)

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        pipeline_mgr=SimpleNamespace(remove_pipeline=AsyncMock(), load_pipeline=AsyncMock()),
        sess_mgr=SimpleNamespace(session_list=[_make_session('bot-1', 'pipe-1', None, 'user-1')]),
        logger=MagicMock(),
    )

    from langbot.pkg.api.http.service.pipeline import PipelineService

    service = PipelineService(ap)
    service.get_pipeline = AsyncMock(return_value={'uuid': 'pipe-1'})

    await service.update_pipeline('pipe-1', {'description': 'new'})

    assert store.delete_calls == []
    assert ap.sess_mgr.session_list[0].using_conversation is None


@pytest.mark.asyncio
async def test_service_reset_delete_failure_warning_contains_scope_fields(monkeypatch):
    import langbot.pkg.api.http.service.bot as bot_service_module
    import langbot.pkg.api.http.service.pipeline as pipeline_service_module

    bot_store = FakeConversationStore(raise_on_delete=True)
    pipeline_store = FakeConversationStore(raise_on_delete=True)
    monkeypatch.setattr(bot_service_module, '_get_dify_conversation_store', lambda ap: bot_store)
    monkeypatch.setattr(pipeline_service_module, '_get_dify_conversation_store', lambda ap: pipeline_store)

    runtime_bot = SimpleNamespace(enable=False, run=AsyncMock())
    bot_ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        platform_mgr=SimpleNamespace(remove_bot=AsyncMock(), load_bot=AsyncMock(return_value=runtime_bot)),
        sess_mgr=SimpleNamespace(session_list=[_make_session('bot-1', 'pipe-1', 'person', 'user-1')]),
        logger=MagicMock(),
    )

    pipeline_ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        pipeline_mgr=SimpleNamespace(remove_pipeline=AsyncMock(), load_pipeline=AsyncMock()),
        sess_mgr=SimpleNamespace(session_list=[_make_session('bot-1', 'pipe-1', 'person', 'user-1')]),
        logger=MagicMock(),
    )

    from langbot.pkg.api.http.service.bot import BotService
    from langbot.pkg.api.http.service.pipeline import PipelineService

    bot_service = BotService(bot_ap)
    bot_service.get_bot = AsyncMock(return_value={'uuid': 'bot-1'})

    pipeline_service = PipelineService(pipeline_ap)
    pipeline_service.get_pipeline = AsyncMock(return_value={'uuid': 'pipe-1'})

    await bot_service.update_bot('bot-1', {'name': 'new'})
    await pipeline_service.update_pipeline('pipe-1', {'description': 'new'})

    assert bot_ap.sess_mgr.session_list[0].using_conversation is None
    assert pipeline_ap.sess_mgr.session_list[0].using_conversation is None

    bot_warnings = _warning_messages(bot_ap.logger)
    pipeline_warnings = _warning_messages(pipeline_ap.logger)

    assert any('bot_uuid=bot-1' in msg for msg in bot_warnings)
    assert any('pipeline_uuid=pipe-1' in msg for msg in bot_warnings)
    assert any('launcher_type=person' in msg for msg in bot_warnings)
    assert any('launcher_id=user-1' in msg for msg in bot_warnings)

    assert any('bot_uuid=bot-1' in msg for msg in pipeline_warnings)
    assert any('pipeline_uuid=pipe-1' in msg for msg in pipeline_warnings)
    assert any('launcher_type=person' in msg for msg in pipeline_warnings)
    assert any('launcher_id=user-1' in msg for msg in pipeline_warnings)
