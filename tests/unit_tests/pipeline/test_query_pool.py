"""
QueryPool unit tests
"""

import pytest

import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger

from langbot.pkg.pipeline.pool import QueryPool


class DummyEventLogger(abstract_platform_logger.AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


class DummyAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    async def send_message(self, target_type, target_id, message):
        pass

    async def reply_message(self, message_source, message, quote_origin=False):
        pass

    def register_listener(self, event_type, callback):
        pass

    def unregister_listener(self, event_type, callback):
        pass

    async def run_async(self):
        pass

    async def kill(self):
        return True


@pytest.mark.asyncio
async def test_add_query_returns_created_query_and_preserves_side_effects(
    sample_message_chain,
    sample_message_event,
):
    """add_query returns the created Query while keeping pool/cache updates."""
    query_pool = QueryPool()
    adapter = DummyAdapter(config={}, logger=DummyEventLogger())

    query = await query_pool.add_query(
        bot_uuid='test-bot-uuid',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=67890,
        message_event=sample_message_event,
        message_chain=sample_message_chain,
        adapter=adapter,
        pipeline_uuid='test-pipeline-uuid',
        routed_by_rule=True,
    )

    assert query is query_pool.queries[0]
    assert query_pool.cached_queries[0] is query
    assert query_pool.query_id_counter == 1
    assert query.query_id == 0
    assert query.bot_uuid == 'test-bot-uuid'
    assert query.pipeline_uuid == 'test-pipeline-uuid'
    assert query.variables == {'_routed_by_rule': True}
