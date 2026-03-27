from __future__ import annotations

from types import SimpleNamespace

import pytest

import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.provider.session.sessionmgr import SessionManager


class FakeApp:
    def __init__(self):
        self.instance_config = SimpleNamespace(data={'concurrency': {'session': 1}})


@pytest.mark.asyncio
async def test_get_session_isolated_by_bot_uuid():
    mgr = SessionManager(FakeApp())

    query_a = SimpleNamespace(
        bot_uuid='bot-a',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id='person-1',
        sender_id='person-1',
    )
    query_b = SimpleNamespace(
        bot_uuid='bot-b',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id='person-1',
        sender_id='person-1',
    )

    session_a = await mgr.get_session(query_a)
    session_b = await mgr.get_session(query_b)

    assert session_a is not session_b


@pytest.mark.asyncio
async def test_get_conversation_does_not_reuse_same_pipeline_across_bots():
    mgr = SessionManager(FakeApp())

    query_a = SimpleNamespace(
        bot_uuid='bot-a',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id='person-1',
        sender_id='person-1',
    )

    session = await mgr.get_session(query_a)

    conv_a = await mgr.get_conversation(
        query=query_a,
        session=session,
        prompt_config=[],
        pipeline_uuid='pipeline-1',
        bot_uuid='bot-a',
    )

    conv_b = await mgr.get_conversation(
        query=query_a,
        session=session,
        prompt_config=[],
        pipeline_uuid='pipeline-1',
        bot_uuid='bot-b',
    )

    assert conv_a is not conv_b
    assert conv_a.bot_uuid == 'bot-a'
    assert conv_b.bot_uuid == 'bot-b'
