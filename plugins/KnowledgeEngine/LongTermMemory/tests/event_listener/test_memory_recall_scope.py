from __future__ import annotations

import json

import pytest

from components.event_listener.memory_injector import MemoryInjector
from langbot_plugin.api.entities import context, events
from store.memory_store import MemoryStore


class FakePlugin:
    def __init__(self):
        self.storage = {
            'kb_configs': json.dumps({'memory-kb': {'embedding_model_uuid': 'embedding', 'isolation': 'session'}}).encode(),
        }
        self.memory_store = MemoryStore(self)
        self.plugin_runtime_handler = object()

    async def get_plugin_storage_keys(self):
        return list(self.storage)

    async def get_plugin_storage(self, key):
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def set_plugin_storage(self, key, value):
        self.storage[key] = value


class FakeQueryAPI:
    def __init__(self, *, failure=False):
        self.query_vars = {'_knowledge_base_uuids': ['docs-kb', 'memory-kb'], 'user_message_text': 'Recall the event'}
        self.failure = failure
        self.calls = []

    async def list_pipeline_knowledge_bases(self):
        return [{'uuid': kb_id} for kb_id in self.query_vars['_knowledge_base_uuids']]

    async def get_query_vars(self):
        return self.query_vars

    async def set_query_var(self, key, value):
        self.calls.append(('set', key))
        self.query_vars[key] = value

    async def get_bot_uuid(self):
        return 'bot-1'

    async def retrieve_knowledge(self, kb_id, query_text, top_k):
        # The Host authorizes query-scoped retrieval against this selection.
        assert kb_id in self.query_vars['_knowledge_base_uuids']
        self.calls.append(('retrieve', kb_id))
        if self.failure:
            raise RuntimeError('retrieval unavailable')
        return [{'content': [{'type': 'text', 'text': 'The event happened on 7 May 2023.'}]}]


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [False, True])
async def test_memory_recall_precedes_automatic_retrieval_suppression(monkeypatch, failure):
    api = FakeQueryAPI(failure=failure)
    monkeypatch.setattr('components.event_listener.memory_injector.QueryBasedAPIProxy', lambda **_: api)
    plugin = FakePlugin()
    injector = MemoryInjector()
    injector.plugin = plugin
    event = events.PromptPreProcessing(session_name='group_1', default_prompt=[], prompt=[])
    event_ctx = context.EventContext(query_id=1, event_name='PromptPreProcessing', event=event)

    await injector._inject_profile(event_ctx)

    assert api.calls[0] == ('retrieve', 'memory-kb')
    assert api.calls[1] == ('set', '_knowledge_base_uuids')
    assert api.query_vars['_knowledge_base_uuids'] == ['docs-kb']
    if failure:
        assert event_ctx.event.prompt == []
    else:
        assert '7 May 2023' in event_ctx.event.prompt[0].content
    assert (await plugin.memory_store.get_injection_snapshot('bot-1:group_1'))['naive_rag_suppressed'] is True
