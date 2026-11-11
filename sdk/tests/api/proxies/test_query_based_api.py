from __future__ import annotations

import pytest

from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class FakeHandler:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    async def call_action(self, action, data, timeout=None):
        self.calls.append((action, data, timeout))
        return self.responses.get(action, {})


@pytest.mark.asyncio
async def test_query_based_proxy_reply_serializes_query_and_message_chain():
    handler = FakeHandler()
    proxy = QueryBasedAPIProxy.model_construct(
        query_id=123, plugin_runtime_handler=handler
    )

    await proxy.reply(MessageChain([Plain(text="hi")]), quote_origin=True)

    assert handler.calls == [
        (
            PluginToRuntimeAction.REPLY_MESSAGE,
            {
                "query_id": 123,
                "message_chain": [{"type": "Plain", "text": "hi"}],
                "quote_origin": True,
            },
            180,
        )
    ]
    assert proxy.model_dump() == {"query_id": 123}


@pytest.mark.asyncio
async def test_query_based_proxy_query_var_helpers():
    handler = FakeHandler(
        {
            PluginToRuntimeAction.GET_BOT_UUID: {"bot_uuid": "bot"},
            PluginToRuntimeAction.GET_QUERY_VAR: {"value": "v"},
            PluginToRuntimeAction.GET_QUERY_VARS: {"vars": {"k": "v"}},
            PluginToRuntimeAction.CREATE_NEW_CONVERSATION: {"uuid": "conv"},
        }
    )
    proxy = QueryBasedAPIProxy.model_construct(
        query_id=7, plugin_runtime_handler=handler
    )

    assert await proxy.get_bot_uuid() == "bot"
    await proxy.set_query_var("k", "v")
    assert await proxy.get_query_var("k") == "v"
    assert await proxy.get_query_vars() == {"k": "v"}
    assert await proxy.create_new_conversation() == {"uuid": "conv"}

    assert handler.calls[1] == (
        PluginToRuntimeAction.SET_QUERY_VAR,
        {"query_id": 7, "key": "k", "value": "v"},
        None,
    )


@pytest.mark.asyncio
async def test_query_based_proxy_prefers_opaque_query_uuid_without_breaking_legacy_id():
    handler = FakeHandler({PluginToRuntimeAction.GET_QUERY_VARS: {"vars": {}}})
    proxy = QueryBasedAPIProxy.model_construct(
        query_id=7,
        query_uuid="query-opaque-uuid",
        plugin_runtime_handler=handler,
    )

    await proxy.get_query_vars()

    assert handler.calls == [
        (
            PluginToRuntimeAction.GET_QUERY_VARS,
            {"query_id": 7, "query_uuid": "query-opaque-uuid"},
            None,
        )
    ]


@pytest.mark.asyncio
async def test_query_based_proxy_pipeline_knowledge_helpers():
    handler = FakeHandler(
        {
            PluginToRuntimeAction.LIST_PIPELINE_KNOWLEDGE_BASES: {
                "knowledge_bases": [{"uuid": "kb"}]
            },
            PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE: {
                "results": [{"content": "hit"}]
            },
        }
    )
    proxy = QueryBasedAPIProxy.model_construct(
        query_id=7, plugin_runtime_handler=handler
    )

    assert await proxy.list_pipeline_knowledge_bases() == [{"uuid": "kb"}]
    assert await proxy.retrieve_knowledge("kb", "query", top_k=3) == [
        {"content": "hit"}
    ]
    assert handler.calls[-1] == (
        PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE,
        {
            "query_id": 7,
            "kb_id": "kb",
            "query_text": "query",
            "top_k": 3,
            "filters": {},
        },
        None,
    )
