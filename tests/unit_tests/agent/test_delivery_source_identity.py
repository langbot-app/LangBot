import datetime
from types import SimpleNamespace

from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain, Source


def test_delivery_retains_source_id_after_pipeline_text_rewrite():
    original = MessageChain([Source(id='wecom-original', time=datetime.datetime.now()), Plain(text='input')])
    query = SimpleNamespace(
        message_chain=MessageChain([Plain(text='filtered')]),
        message_event=SimpleNamespace(message_chain=original),
        launcher_type='person',
        launcher_id='user-1',
        adapter=None,
    )
    assert QueryEntryAdapter._build_delivery_context(query).reply_target['message_id'] == 'wecom-original'


def test_delivery_does_not_send_missing_source_sentinel():
    query = SimpleNamespace(
        message_chain=MessageChain([Plain(text='input')]),
        message_event=None,
        launcher_type='person',
        launcher_id='user-1',
        adapter=None,
    )
    assert QueryEntryAdapter._build_delivery_context(query).reply_target['message_id'] is None
