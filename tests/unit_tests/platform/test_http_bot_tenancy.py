from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.sources.http_bot import HttpBotAdapter


def _session(key):
    session = SimpleNamespace()
    session._langbot_session_key = key
    return session


def _adapter(app, execution_context) -> HttpBotAdapter:
    adapter = HttpBotAdapter.model_construct(
        config={'signature_required': False},
        logger=SimpleNamespace(execution_context=execution_context),
        bot_uuid='bot-a',
        outbound_states={},
        idempotency_cache={},
        sync_waiters={},
    )
    object.__setattr__(adapter, 'ap', app)
    return adapter


@pytest.mark.asyncio
async def test_http_bot_reset_removes_only_exact_execution_scope():
    context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=3,
        bot_uuid='bot-a',
    )
    target_key = ('instance-a', 'workspace-a', 3, 'bot-a', 'person', 'shared-session')
    retained_keys = [
        ('instance-b', 'workspace-a', 3, 'bot-a', 'person', 'shared-session'),
        ('instance-a', 'workspace-b', 3, 'bot-a', 'person', 'shared-session'),
        ('instance-a', 'workspace-a', 4, 'bot-a', 'person', 'shared-session'),
        ('instance-a', 'workspace-a', 3, 'bot-b', 'person', 'shared-session'),
        ('instance-a', 'workspace-a', 3, 'bot-a', 'group', 'shared-session'),
        ('instance-a', 'workspace-a', 3, 'bot-a', 'person', 'other-session'),
    ]
    sessions = [_session(target_key), *[_session(key) for key in retained_keys], SimpleNamespace()]
    app = SimpleNamespace(sess_mgr=SimpleNamespace(session_list=sessions))
    adapter = _adapter(app, context)

    removed = await adapter._reset_session('person', 'shared-session')

    assert removed is True
    assert [getattr(session, '_langbot_session_key', None) for session in app.sess_mgr.session_list] == [
        *retained_keys,
        None,
    ]


@pytest.mark.asyncio
async def test_http_bot_reset_fails_closed_without_trusted_scope():
    app = SimpleNamespace(sess_mgr=SimpleNamespace(session_list=[]))
    adapter = _adapter(app, None)

    with pytest.raises(RuntimeError, match='trusted execution scope'):
        await adapter._reset_session('person', 'shared-session')
