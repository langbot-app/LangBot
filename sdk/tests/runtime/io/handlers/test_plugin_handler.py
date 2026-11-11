from __future__ import annotations

import asyncio
import logging
import time
from types import SimpleNamespace

import pytest

import langbot_plugin.runtime.plugin.container  # noqa: F401
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIException
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.box.actions import LangBotToBoxAction
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.models import BoxSpec
from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction,
    RuntimeToLangBotAction,
    RuntimeToPluginAction,
)
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding
from langbot_plugin.runtime.io.handler import ActionResponse, Handler
from langbot_plugin.runtime.io.handlers import plugin as plugin_handler_module
from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler
from tests.helpers.protocol import ProtocolConnection, ProtocolSession


class FakeManifest:
    def __init__(self, author="tester", name="demo"):
        self.metadata = SimpleNamespace(author=author, name=name)

    def model_dump(self, **kwargs):
        return {
            "metadata": {"author": self.metadata.author, "name": self.metadata.name}
        }


class FakePluginContainer:
    def __init__(self, runtime_handler=None):
        self._runtime_plugin_handler = runtime_handler
        self.manifest = FakeManifest()

    def model_dump(self, **kwargs):
        return {"manifest": self.manifest.model_dump()}


class FakeControlHandler:
    def __init__(self):
        self.calls = []
        self.results = {}

    async def call_action(
        self,
        action,
        data,
        timeout=15.0,
        action_context=None,
        cancel_peer_on_cancel=False,
    ):
        if action_context is None:
            self.calls.append((action, data, timeout))
        else:
            self.calls.append((action, data, timeout, action_context))
        return self.results.get(action, {"ok": True})


class FakePluginManager:
    def __init__(self):
        self.plugins = []
        self.calls = []
        self.tools = []
        self.commands = []

    async def register_plugin(
        self,
        handler,
        plugin_container,
        debug_plugin,
        registration_capability=None,
    ):
        self.calls.append(
            (
                "register_plugin",
                handler,
                plugin_container,
                debug_plugin,
                registration_capability,
            )
        )

    async def remove_plugin_container(self, plugin_container):
        self.calls.append(("remove_plugin_container", plugin_container))

    async def list_tools(self):
        self.calls.append(("list_tools",))
        return self.tools

    async def call_tool(self, tool_name, tool_parameters, session, query_id):
        self.calls.append(("call_tool", tool_name, tool_parameters, session, query_id))
        return {"text": "tool response"}

    async def list_commands(self):
        self.calls.append(("list_commands",))
        return self.commands


class FakeTool:
    def __init__(self, name):
        self.metadata = SimpleNamespace(name=name)

    def to_plain_dict(self):
        return {"name": self.metadata.name}


class Dumpable:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self, **kwargs):
        return self.payload


def _action_context(workspace_uuid="workspace-a", installation_uuid=None):
    return ActionContext(
        instance_uuid="instance-1",
        workspace_uuid=workspace_uuid,
        placement_generation=3,
        installation_uuid=installation_uuid,
    )


def _installation_binding(runtime_revision=1):
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=3,
        installation_uuid="installation-1",
        runtime_revision=runtime_revision,
        artifact_digest="a" * 64,
    )


def _handler(debug_plugin=False, action_context=None, *, runtime_profile=None):
    valid_tokens = {"key"}
    control_handler = FakeControlHandler()
    manager = FakePluginManager()
    context = SimpleNamespace(
        control_handler=control_handler,
        plugin_mgr=manager,
        workspace_binding=action_context,
        workspace_debug_tokens=SimpleNamespace(
            binding_for_token=lambda token: (
                action_context if token in valid_tokens else None
            )
        ),
    )
    if runtime_profile is not None:
        context.runtime_profile = runtime_profile
    handler = PluginConnectionHandler(
        ProtocolConnection(),
        context,
        debug_plugin=debug_plugin,
    )
    handler.debug_workspace_binding = action_context
    handler.debug_auth_token = (
        "key" if debug_plugin and action_context is not None else None
    )
    return handler, manager, control_handler


def test_reserved_decode_capacity_is_consumed_by_first_message_only():
    handler, _manager, _control = _handler()
    handler._certified_shared_stdio = True

    assert handler._uses_reserved_decode_capacity("not registration") is True
    assert handler._uses_reserved_decode_capacity("still not registration") is False
    assert handler._registration_codec_available is True


def test_decoded_registration_can_retain_control_scope_after_first_decode():
    handler, _manager, _control = _handler()
    handler._certified_shared_stdio = True
    registration = {"action": PluginToRuntimeAction.REGISTER_PLUGIN.value}

    assert handler._uses_reserved_decode_capacity("opaque registration payload") is True
    assert handler._uses_reserved_action_capacity(registration) is True
    assert handler._registration_codec_available is False


async def test_bound_plugin_handler_accepts_legacy_api_call_without_context():
    """An installed SDK 0.4.x worker omits envelopes; host binding stays authoritative."""

    binding = _installation_binding()
    handler, _manager, control = _handler()
    handler.bind_action_context(binding)
    handler.context.is_current_installation_binding = lambda action_context: (
        action_context == binding
    )
    control.results[PluginToRuntimeAction.GET_LLM_MODELS] = {"llm_models": ["model-a"]}

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_LLM_MODELS.value,
            {},
            action_context=None,
        )

    assert response["code"] == 0
    assert response["data"] == {"llm_models": ["model-a"]}
    assert control.calls == [(PluginToRuntimeAction.GET_LLM_MODELS, {}, 15.0, binding)]


async def test_shared_plugin_handler_forwards_validated_current_binding_to_host():
    binding = _installation_binding()
    handler, manager, control = _handler(runtime_profile="shared")
    manager.plugins_for_binding = (
        lambda candidate: [FakePluginContainer(runtime_handler=handler)]
        if candidate == binding
        else []
    )
    handler.context.is_current_installation_binding = (
        lambda candidate: candidate == binding
    )
    handler.set_shared_pool_bindings(binding.artifact_digest, {binding})

    async with ProtocolSession(handler) as session:
        host_response = await session.request(
            PluginToRuntimeAction.GET_BOTS.value,
            {},
            action_context=binding,
        )
        storage_response = await session.request(
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE.value,
            {"key": "shared"},
            seq_id=2,
            action_context=binding,
        )

    assert host_response["code"] == 0
    assert storage_response["code"] == 0
    assert control.calls == [
        (PluginToRuntimeAction.GET_BOTS, {}, 15.0, binding),
        (
            RuntimeToLangBotAction.GET_BINARY_STORAGE,
            {"key": "shared", "owner_type": "workspace", "owner": "workspace-a"},
            15.0,
            binding,
        ),
    ]


async def test_debug_handler_rejects_actions_after_credential_expiry():
    binding = ActionContext(
        instance_uuid="i", workspace_uuid="w", placement_generation=1
    )
    handler, _manager, _control = _handler(debug_plugin=True, action_context=binding)
    handler.bind_action_context(binding)
    handler.context.workspace_debug_tokens.binding_for_token = lambda supplied_token: (
        None
    )

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_BOTS.value,
            {},
        )

    assert response["code"] != 0
    assert "expired" in response["message"].lower()


async def test_plugin_handler_registers_plugin_when_debug_key_matches():
    binding = ActionContext(
        instance_uuid="i", workspace_uuid="w", placement_generation=1
    )
    handler, manager, _control = _handler(debug_plugin=True, action_context=binding)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.REGISTER_PLUGIN.value,
            {"plugin_container": {"id": "plugin"}, "plugin_debug_key": "key"},
        )

    assert response["code"] == 0
    assert manager.calls == [("register_plugin", handler, {"id": "plugin"}, True, None)]


def test_shared_plugin_handler_rejects_unregistered_and_revoked_worker_actions():
    manager = FakePluginManager()
    binding = _installation_binding()
    current_binding = binding
    context = SimpleNamespace(
        control_handler=FakeControlHandler(),
        plugin_mgr=manager,
        workspace_binding=None,
        runtime_profile="shared",
        is_current_installation_binding=lambda candidate: candidate == current_binding,
    )
    handler = PluginConnectionHandler(ProtocolConnection(), context)

    with pytest.raises(ValueError, match="must register"):
        handler.validate_inbound_action_context(
            PluginToRuntimeAction.GET_BOTS.value,
            None,
        )

    handler.bind_action_context(binding)
    current_binding = binding.model_copy(update={"runtime_revision": 2})
    with pytest.raises(ValueError, match="revoked"):
        handler.validate_inbound_action_context(
            PluginToRuntimeAction.GET_BOTS.value,
            None,
        )


async def test_plugin_handler_rejects_plugin_with_invalid_debug_key():
    binding = ActionContext(
        instance_uuid="i", workspace_uuid="w", placement_generation=1
    )
    handler, manager, _control = _handler(debug_plugin=True, action_context=binding)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.REGISTER_PLUGIN.value,
            {"plugin_container": {"id": "plugin"}, "plugin_debug_key": "wrong"},
        )

    assert response["code"] == 1
    assert response["message"] == "Plugin debug key verification failed"
    assert manager.calls == []


async def test_plugin_handler_prod_registration_disables_debug_mode():
    handler, manager, _control = _handler(debug_plugin=True)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.REGISTER_PLUGIN.value,
            {
                "plugin_container": {"id": "plugin"},
                "prod_mode": True,
                "registration_capability": "registration-capability",
            },
        )

    assert response["code"] == 0
    assert handler.debug_plugin is False
    assert manager.calls == [
        (
            "register_plugin",
            handler,
            {"id": "plugin"},
            False,
            "registration-capability",
        )
    ]


async def test_windows_prod_registration_is_not_prebound_as_debug_worker():
    binding = ActionContext(
        instance_uuid="i", workspace_uuid="w", placement_generation=1
    )
    handler, manager, _control = _handler(
        debug_plugin=True,
        action_context=binding,
        runtime_profile="oss_dev",
    )

    assert handler.bound_action_context is None
    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.REGISTER_PLUGIN.value,
            {
                "plugin_container": {"id": "plugin"},
                "prod_mode": True,
                "registration_capability": "registration-capability",
            },
        )

    assert response["code"] == 0
    assert handler.debug_plugin is False
    assert manager.calls == [
        (
            "register_plugin",
            handler,
            {"id": "plugin"},
            False,
            "registration-capability",
        )
    ]


async def test_plugin_handler_rejects_prod_registration_without_capability():
    handler, manager, _control = _handler(debug_plugin=True)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.REGISTER_PLUGIN.value,
            {
                "plugin_container": {"id": "plugin"},
                "prod_mode": True,
                "plugin_debug_key": "key",
            },
        )

    assert response["code"] == 1
    assert response["message"] == (
        "Production plugin registration capability is required"
    )
    assert manager.calls == []


async def test_plugin_handler_forwards_invoke_llm_with_validated_timeout():
    handler, _manager, control = _handler()
    control.results[PluginToRuntimeAction.INVOKE_LLM] = {
        "message": "ok",
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.INVOKE_LLM.value,
            {"messages": [], "timeout": -1},
        )

    assert response["data"] == {
        "message": "ok",
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }
    assert control.calls == [
        (PluginToRuntimeAction.INVOKE_LLM, {"messages": []}, 120.0)
    ]


@pytest.mark.parametrize(
    ("action", "payload", "expected_action", "expected_payload", "expected_timeout"),
    [
        (
            PluginToRuntimeAction.REPLY_MESSAGE,
            {"query_id": 1, "message": "hi"},
            PluginToRuntimeAction.REPLY_MESSAGE,
            {"query_id": 1, "message": "hi"},
            180,
        ),
        (
            PluginToRuntimeAction.GET_BOT_UUID,
            {"query_id": 2},
            PluginToRuntimeAction.GET_BOT_UUID,
            {"query_id": 2},
            15.0,
        ),
        (
            PluginToRuntimeAction.SET_QUERY_VAR,
            {"query_id": 3, "key": "k", "value": "v"},
            PluginToRuntimeAction.SET_QUERY_VAR,
            {"query_id": 3, "key": "k", "value": "v"},
            15.0,
        ),
        (
            PluginToRuntimeAction.GET_QUERY_VAR,
            {"query_id": 3, "key": "k"},
            PluginToRuntimeAction.GET_QUERY_VAR,
            {"query_id": 3, "key": "k"},
            15.0,
        ),
        (
            PluginToRuntimeAction.GET_QUERY_VARS,
            {"query_id": 3},
            PluginToRuntimeAction.GET_QUERY_VARS,
            {"query_id": 3},
            15.0,
        ),
        (
            PluginToRuntimeAction.CREATE_NEW_CONVERSATION,
            {"query_id": 4, "ignored": "value"},
            PluginToRuntimeAction.CREATE_NEW_CONVERSATION,
            {"query_id": 4},
            15.0,
        ),
        (
            PluginToRuntimeAction.GET_LANGBOT_VERSION,
            {},
            PluginToRuntimeAction.GET_LANGBOT_VERSION,
            {},
            15.0,
        ),
        (
            PluginToRuntimeAction.GET_BOTS,
            {},
            PluginToRuntimeAction.GET_BOTS,
            {},
            15.0,
        ),
        (
            PluginToRuntimeAction.GET_BOT_INFO,
            {"bot_uuid": "bot-1"},
            PluginToRuntimeAction.GET_BOT_INFO,
            {"bot_uuid": "bot-1"},
            15.0,
        ),
        (
            PluginToRuntimeAction.SEND_MESSAGE,
            {"bot_uuid": "bot-1", "message": "hi"},
            PluginToRuntimeAction.SEND_MESSAGE,
            {"bot_uuid": "bot-1", "message": "hi"},
            60.0,
        ),
        (
            PluginToRuntimeAction.GET_LLM_MODELS,
            {},
            PluginToRuntimeAction.GET_LLM_MODELS,
            {},
            15.0,
        ),
        (
            PluginToRuntimeAction.INVOKE_EMBEDDING,
            {"model": "embed", "texts": ["hello"]},
            PluginToRuntimeAction.INVOKE_EMBEDDING,
            {"model": "embed", "texts": ["hello"]},
            60,
        ),
        (
            PluginToRuntimeAction.INVOKE_RERANK,
            {"model": "rerank", "query": "q", "docs": ["d"]},
            PluginToRuntimeAction.INVOKE_RERANK,
            {"model": "rerank", "query": "q", "docs": ["d"]},
            60,
        ),
        (
            PluginToRuntimeAction.VECTOR_UPSERT,
            {"collection_id": "kb", "points": []},
            PluginToRuntimeAction.VECTOR_UPSERT,
            {"collection_id": "kb", "points": []},
            60,
        ),
        (
            PluginToRuntimeAction.VECTOR_SEARCH,
            {"collection_id": "kb", "vector": [0.1]},
            PluginToRuntimeAction.VECTOR_SEARCH,
            {"collection_id": "kb", "vector": [0.1]},
            30,
        ),
        (
            PluginToRuntimeAction.VECTOR_DELETE,
            {"collection_id": "kb", "ids": ["p1"]},
            PluginToRuntimeAction.VECTOR_DELETE,
            {"collection_id": "kb", "ids": ["p1"]},
            30,
        ),
        (
            PluginToRuntimeAction.LIST_KNOWLEDGE_BASES,
            {},
            PluginToRuntimeAction.LIST_KNOWLEDGE_BASES,
            {},
            15.0,
        ),
        (
            PluginToRuntimeAction.RETRIEVE_KNOWLEDGE,
            {"query": "hello"},
            PluginToRuntimeAction.RETRIEVE_KNOWLEDGE,
            {"query": "hello"},
            120.0,
        ),
        (
            PluginToRuntimeAction.LIST_PIPELINE_KNOWLEDGE_BASES,
            {"query_id": 5},
            PluginToRuntimeAction.LIST_PIPELINE_KNOWLEDGE_BASES,
            {"query_id": 5},
            15.0,
        ),
        (
            PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE,
            {"query_id": 5, "query": "hello"},
            PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE,
            {"query_id": 5, "query": "hello"},
            120.0,
        ),
        (
            PluginToRuntimeAction.LIST_PARSERS,
            {},
            PluginToRuntimeAction.LIST_PARSERS,
            {},
            30,
        ),
        (
            PluginToRuntimeAction.INVOKE_PARSER,
            {"parser": "pdf", "file_key": "file"},
            PluginToRuntimeAction.INVOKE_PARSER,
            {"parser": "pdf", "file_key": "file"},
            300,
        ),
    ],
)
async def test_plugin_handler_proxies_control_actions(
    action,
    payload,
    expected_action,
    expected_payload,
    expected_timeout,
):
    handler, _manager, control = _handler()
    control.results[expected_action] = {"proxied": expected_action.value}

    async with ProtocolSession(handler) as session:
        response = await session.request(action.value, dict(payload))

    assert response["data"] == {"proxied": expected_action.value}
    assert control.calls == [(expected_action, expected_payload, expected_timeout)]


async def test_plugin_handler_forwards_invoke_llm_with_custom_timeout():
    handler, _manager, control = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.INVOKE_LLM.value,
            {"messages": [], "timeout": 30},
        )

    assert response["code"] == 0
    assert control.calls == [(PluginToRuntimeAction.INVOKE_LLM, {"messages": []}, 30.0)]


async def test_plugin_handler_forwards_invoke_rerank_with_caller_identity():
    handler, manager, control = _handler()
    manager.plugins = [FakePluginContainer(runtime_handler=handler)]
    control.results[PluginToRuntimeAction.INVOKE_RERANK] = {
        "results": [{"index": 0, "relevance_score": 0.95}]
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.INVOKE_RERANK.value,
            {
                "run_id": "run-1",
                "rerank_model_uuid": "rerank-model",
                "query": "query",
                "documents": ["doc"],
                "top_k": 1,
                "extra_args": {},
                "caller_plugin_identity": "spoofed/plugin",
            },
        )

    assert response["data"] == {"results": [{"index": 0, "relevance_score": 0.95}]}
    assert control.calls == [
        (
            PluginToRuntimeAction.INVOKE_RERANK,
            {
                "run_id": "run-1",
                "rerank_model_uuid": "rerank-model",
                "query": "query",
                "documents": ["doc"],
                "top_k": 1,
                "extra_args": {},
                "caller_plugin_identity": "tester/demo",
            },
            60,
        )
    ]


async def test_plugin_handler_adds_plugin_owner_for_binary_storage():
    handler, manager, control = _handler()
    manager.plugins = [FakePluginContainer(runtime_handler=handler)]

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.SET_PLUGIN_STORAGE.value,
            {"key": "cache", "value_base64": "dmFsdWU="},
        )

    assert response["code"] == 0
    assert control.calls == [
        (
            RuntimeToLangBotAction.SET_BINARY_STORAGE,
            {
                "key": "cache",
                "value_base64": "dmFsdWU=",
                "owner_type": "plugin",
                "owner": "tester/demo",
                "caller_plugin_identity": "tester/demo",
            },
            15.0,
        )
    ]


@pytest.mark.parametrize(
    ("action", "expected_action"),
    [
        (
            PluginToRuntimeAction.GET_PLUGIN_STORAGE,
            RuntimeToLangBotAction.GET_BINARY_STORAGE,
        ),
        (
            PluginToRuntimeAction.GET_PLUGIN_STORAGE_KEYS,
            RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS,
        ),
        (
            PluginToRuntimeAction.DELETE_PLUGIN_STORAGE,
            RuntimeToLangBotAction.DELETE_BINARY_STORAGE,
        ),
    ],
)
async def test_plugin_handler_plugin_storage_actions_add_owner(action, expected_action):
    handler, manager, control = _handler()
    manager.plugins = [FakePluginContainer(runtime_handler=handler)]

    async with ProtocolSession(handler) as session:
        response = await session.request(action.value, {"key": "cache"})

    assert response["code"] == 0
    assert control.calls == [
        (
            expected_action,
            {
                "key": "cache",
                "owner_type": "plugin",
                "owner": "tester/demo",
                "caller_plugin_identity": "tester/demo",
            },
            15.0,
        )
    ]


async def test_plugin_handler_workspace_storage_fails_without_runtime_binding():
    handler, _manager, control = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE.value,
            {"key": "shared"},
        )

    assert response["code"] == 1
    assert "Plugin Runtime is not bound to a Workspace" in response["message"]
    assert control.calls == []


@pytest.mark.parametrize(
    ("action", "expected_action"),
    [
        (
            PluginToRuntimeAction.SET_WORKSPACE_STORAGE,
            RuntimeToLangBotAction.SET_BINARY_STORAGE,
        ),
        (
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE,
            RuntimeToLangBotAction.GET_BINARY_STORAGE,
        ),
        (
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE_KEYS,
            RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS,
        ),
        (
            PluginToRuntimeAction.DELETE_WORKSPACE_STORAGE,
            RuntimeToLangBotAction.DELETE_BINARY_STORAGE,
        ),
    ],
)
async def test_plugin_handler_workspace_storage_actions_use_bound_owner(
    action,
    expected_action,
):
    action_context = _action_context()
    handler, _manager, control = _handler(action_context=action_context)

    async with ProtocolSession(handler) as session:
        response = await session.request(action.value, {"key": "shared"})

    assert response["code"] == 0
    assert control.calls == [
        (
            expected_action,
            {
                "key": "shared",
                "owner_type": "workspace",
                "owner": "workspace-a",
            },
            15.0,
            action_context,
        )
    ]


async def test_plugin_handler_strips_forged_scope_from_host_api_payload():
    action_context = _action_context(installation_uuid="installation-1")
    handler, _manager, control = _handler(action_context=action_context)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_BOTS.value,
            {
                "workspace_uuid": "workspace-b",
                "instance_uuid": "instance-forged",
                "placement_generation": 99,
                "installation_uuid": "installation-forged",
                "context": {"workspace_uuid": "workspace-b"},
            },
        )

    assert response["code"] == 0
    assert control.calls == [
        (
            PluginToRuntimeAction.GET_BOTS,
            {},
            15.0,
            action_context,
        )
    ]


async def test_plugin_handler_rejects_forged_action_envelope():
    handler, _manager, control = _handler(action_context=_action_context())

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_BOTS.value,
            {},
            action_context=_action_context(workspace_uuid="workspace-b"),
        )

    assert response["code"] == 1
    assert "does not match connection Workspace" in response["message"]
    assert control.calls == []


async def test_plugin_handler_forwards_config_file_requests_to_langbot():
    handler, _manager, control = _handler()
    control.results[RuntimeToLangBotAction.GET_CONFIG_FILE] = {
        "file_base64": "Y29uZmln"
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_CONFIG_FILE.value,
            {"file_key": "settings.yaml"},
        )

    assert response["data"] == {"file_base64": "Y29uZmln"}
    assert control.calls == [
        (
            RuntimeToLangBotAction.GET_CONFIG_FILE,
            {
                "file_key": "settings.yaml",
                "run_id": None,
                "caller_plugin_identity": None,
            },
            15.0,
        )
    ]


async def test_plugin_handler_get_knowledge_file_stream_repackages_file(monkeypatch):
    handler, _manager, control = _handler()
    file_ops = []
    control.results[PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM] = {
        "file_key": "host-file"
    }

    async def fake_read_control_file(file_key, *, action_context=None):
        file_ops.append(("control-read", file_key, action_context))
        return b"file-bytes"

    async def fake_delete_control_file(file_key, *, action_context=None):
        file_ops.append(("control-delete", file_key, action_context))

    async def reject_plugin_storage_read(file_key):
        raise AssertionError(
            f"host file must not be read from plugin storage: {file_key}"
        )

    async def fake_send_file(file_bytes, extension):
        file_ops.append(("send", file_bytes, extension))
        return "plugin-file"

    control.read_local_file = fake_read_control_file
    control.delete_local_file = fake_delete_control_file
    monkeypatch.setattr(handler, "read_local_file", reject_plugin_storage_read)
    monkeypatch.setattr(handler, "send_file", fake_send_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM.value,
            {"storage_path": "kb/doc"},
        )

    assert file_ops == [
        ("control-read", "host-file", None),
        ("control-delete", "host-file", None),
        ("send", b"file-bytes", ""),
    ]
    assert response["data"] == {"file_key": "plugin-file"}


async def test_plugin_handler_get_knowledge_file_stream_returns_empty_result():
    handler, _manager, control = _handler()
    control.results[PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM] = {"file_key": ""}

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM.value,
            {"storage_path": "kb/doc"},
        )

    assert response["data"] == {"file_key": ""}


async def test_plugin_handler_lists_tools_and_reports_missing_tool_detail():
    handler, manager, control = _handler()
    manager.tools = [FakeTool("weather")]
    control.results[PluginToRuntimeAction.LIST_TOOLS] = {"tools": [{"name": "weather"}]}
    control.results[PluginToRuntimeAction.GET_TOOL_DETAIL] = {
        "tool": {"name": "missing"},
    }

    async with ProtocolSession(handler) as session:
        listed = await session.request(PluginToRuntimeAction.LIST_TOOLS.value, seq_id=1)
        missing = await session.request(
            PluginToRuntimeAction.GET_TOOL_DETAIL.value,
            {"tool_name": "missing"},
            seq_id=2,
        )

    assert listed["data"] == {"tools": [{"name": "weather"}]}
    assert missing["data"] == {"tool": {"name": "missing"}}
    assert control.calls == [
        (PluginToRuntimeAction.LIST_TOOLS, {}, 30),
        (
            PluginToRuntimeAction.GET_TOOL_DETAIL,
            {"tool_name": "missing"},
            30,
        ),
    ]


async def test_plugin_handler_get_tool_detail_returns_matching_tool():
    handler, manager, control = _handler()
    manager.tools = [FakeTool("weather")]
    control.results[PluginToRuntimeAction.GET_TOOL_DETAIL] = {
        "tool": {"name": "weather"}
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.GET_TOOL_DETAIL.value,
            {"tool_name": "weather"},
        )

    assert response["data"] == {"tool": {"name": "weather"}}
    assert control.calls == [
        (
            PluginToRuntimeAction.GET_TOOL_DETAIL,
            {"tool_name": "weather"},
            30,
        )
    ]


async def test_plugin_handler_calls_registered_runtime_tool():
    handler, _manager, control = _handler()
    control.results[PluginToRuntimeAction.CALL_TOOL] = {
        "tool_response": {"text": "tool response"}
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.CALL_TOOL.value,
            {
                "tool_name": "weather",
                "tool_parameters": {"city": "Shanghai"},
                "session": {"id": "s"},
                "query_id": 7,
            },
        )

    assert response["data"] == {"tool_response": {"text": "tool response"}}
    assert control.calls == [
        (
            PluginToRuntimeAction.CALL_TOOL,
            {
                "tool_name": "weather",
                "tool_parameters": {"city": "Shanghai"},
                "session": {"id": "s"},
                "query_id": 7,
            },
            180.0,
        )
    ]


async def test_plugin_handler_forwards_runner_tool_envelope():
    handler, _manager, control = _handler()
    control.results[PluginToRuntimeAction.CALL_TOOL] = {
        "result": {"text": "tool response"}
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.CALL_TOOL.value,
            {
                "run_id": "run-1",
                "tool_name": "weather",
                "parameters": {"city": "Shanghai"},
            },
        )

    assert response["data"] == {"result": {"text": "tool response"}}
    assert control.calls == [
        (
            PluginToRuntimeAction.CALL_TOOL,
            {
                "run_id": "run-1",
                "tool_name": "weather",
                "parameters": {"city": "Shanghai"},
            },
            180.0,
        )
    ]


@pytest.mark.parametrize("with_binding", [False, True])
@pytest.mark.parametrize("interruption", ["cancel", "deadline", "legacy"])
async def test_tool_cancellation_reaches_box_only_for_run_calls(
    with_binding, interruption
):
    binding = (
        _action_context(installation_uuid="installation-1") if with_binding else None
    )
    relay, _manager, _control = _handler(action_context=binding)
    caller, control, host, box_caller, box_peer = (
        Handler(ProtocolConnection()) for _ in range(5)
    )
    relay.context.control_handler = control
    if binding is not None:
        caller.bind_action_context(binding)
    handlers = [caller, relay, control, host, box_caller, box_peer]
    for left, right in ((caller, relay), (control, host), (box_caller, box_peer)):
        left.conn.send = right.conn.incoming.put
        right.conn.send = left.conn.incoming.put
    box_client = ActionRPCBoxClient(logger=logging.getLogger(__name__))
    box_client.set_handler(box_caller)
    started = {name: asyncio.Event() for name in ("target", "sibling")}
    release = {name: asyncio.Event() for name in started}
    cancelled = {name: asyncio.Event() for name in started}
    finished = {name: asyncio.Event() for name in started}
    host_finished = {name: asyncio.Event() for name in started}

    @box_peer.action(LangBotToBoxAction.EXEC)
    async def execute(data):
        name = data["session_id"]
        assert box_peer.current_action_context == binding
        started[name].set()
        try:
            await release[name].wait()
        except asyncio.CancelledError:
            cancelled[name].set()
            raise
        finished[name].set()
        return ActionResponse.success(
            {
                "session_id": name,
                "backend_name": "test",
                "status": "completed",
                "exit_code": 0,
                "stdout": name,
                "duration_ms": 1,
            }
        )

    @host.action(PluginToRuntimeAction.CALL_TOOL)
    async def call_tool(data):
        assert host.current_action_context == binding
        parameters = data.get("parameters", data.get("tool_parameters"))
        result = await box_client.execute(
            BoxSpec(session_id=parameters["session_id"], cmd="sleep 8"),
            action_context=host.current_action_context,
        )
        host_finished[parameters["session_id"]].set()
        return ActionResponse.success({"result": {"stdout": result.stdout}})

    def runner(name, deadline_at=None):
        ctx = RunnerContext.model_validate(
            {
                "run_id": name,
                "trigger": {"type": "user_message"},
                "event": {
                    "event_id": name,
                    "event_type": "message.received",
                    "source": "test",
                },
                "input": {"content": "test"},
                "delivery": {"surface": "test"},
                "runtime": {"deadline_at": deadline_at},
                "resources": {
                    "tools": [{"tool_name": "shell", "operations": ["call"]}]
                },
            }
        )
        return RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=caller)

    loops = [asyncio.create_task(handler.run()) for handler in handlers]
    sibling = asyncio.create_task(
        runner("sibling").call_tool("shell", {"session_id": "sibling"})
    )
    if interruption == "legacy":
        target_call = caller.call_action(
            PluginToRuntimeAction.CALL_TOOL,
            {"tool_name": "shell", "tool_parameters": {"session_id": "target"}},
            cancel_peer_on_cancel=True,
        )
    else:
        deadline_at = time.time() + 0.5 if interruption == "deadline" else None
        target_call = runner("target", deadline_at).call_tool(
            "shell", {"session_id": "target"}
        )
    target = asyncio.create_task(target_call)
    try:
        await asyncio.wait_for(
            asyncio.gather(*(event.wait() for event in started.values())), 2
        )
        relay_target = relay._action_tasks_by_seq[caller.seq_id_index]
        if interruption == "deadline":
            with pytest.raises(AgentAPIException) as exc:
                await asyncio.wait_for(target, 2)
            assert exc.value.error.code == "deadline_exceeded"
        else:
            target.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(target, 2)
        if interruption == "legacy":
            # Even an explicit cancellation at the plugin hop must leave the
            # legacy Host action running until it completes normally.
            await asyncio.wait_for(
                asyncio.gather(relay_target, return_exceptions=True), 2
            )
            release["target"].set()
            await asyncio.wait_for(host_finished["target"].wait(), 2)
            assert not cancelled["target"].is_set()
        else:
            await asyncio.wait_for(cancelled["target"].wait(), 2)
            assert not finished["target"].is_set()
        assert not cancelled["sibling"].is_set()
        assert not sibling.done()
        release["sibling"].set()
        assert await asyncio.wait_for(sibling, 2) == {"stdout": "sibling"}
        assert caller.resp_waiters == {}
    finally:
        for event in release.values():
            event.set()
        for task in (target, sibling):
            task.cancel()
        await asyncio.gather(target, sibling, return_exceptions=True)
        actions = [task for handler in handlers for task in handler._action_tasks]
        for task in actions:
            task.cancel()
        await asyncio.gather(*actions, return_exceptions=True)
        for task in loops:
            task.cancel()
        await asyncio.gather(*loops, return_exceptions=True)


async def test_plugin_handler_lists_plugin_manifests():
    handler, manager, control = _handler()
    manager.plugins = [FakePluginContainer()]
    control.results[PluginToRuntimeAction.LIST_PLUGINS_MANIFEST] = {
        "plugins": [{"metadata": {"author": "tester", "name": "demo"}}]
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.LIST_PLUGINS_MANIFEST.value
        )

    assert response["data"] == {
        "plugins": [{"metadata": {"author": "tester", "name": "demo"}}]
    }
    assert control.calls == [(PluginToRuntimeAction.LIST_PLUGINS_MANIFEST, {}, 30)]


async def test_plugin_handler_lists_commands():
    handler, manager, control = _handler()
    manager.commands = [Dumpable({"name": "admin"})]
    control.results[PluginToRuntimeAction.LIST_COMMANDS] = {
        "commands": [{"name": "admin"}]
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(PluginToRuntimeAction.LIST_COMMANDS.value)

    assert response["data"] == {"commands": [{"name": "admin"}]}
    assert control.calls == [(PluginToRuntimeAction.LIST_COMMANDS, {}, 30)]


async def test_plugin_connection_handler_peer_call_helpers(monkeypatch):
    handler, _manager, _control = _handler()
    calls = []

    async def fake_call_action(action, data, timeout=15.0):
        calls.append((action, data, timeout))
        return {"action": action.value, "data": data}

    monkeypatch.setattr(handler, "call_action", fake_call_action)

    assert await handler.initialize_plugin({"enabled": True}) == {
        "action": RuntimeToPluginAction.INITIALIZE_PLUGIN.value,
        "data": {"plugin_settings": {"enabled": True}},
    }
    assert await handler.get_plugin_container() == {
        "action": RuntimeToPluginAction.GET_PLUGIN_CONTAINER.value,
        "data": {},
    }
    assert await handler.get_plugin_icon() == {
        "action": RuntimeToPluginAction.GET_PLUGIN_ICON.value,
        "data": {},
    }
    assert await handler.get_plugin_readme("zh") == {
        "action": RuntimeToPluginAction.GET_PLUGIN_README.value,
        "data": {"language": "zh"},
    }
    assert await handler.get_plugin_assets_file("asset.txt") == {
        "action": RuntimeToPluginAction.GET_PLUGIN_ASSETS_FILE.value,
        "data": {"file_key": "asset.txt"},
    }
    assert await handler.call_page_api(
        page_id="settings",
        endpoint="/save",
        method="POST",
        body={"enabled": True},
    ) == {
        "action": RuntimeToPluginAction.PAGE_API.value,
        "data": {
            "page_id": "settings",
            "endpoint": "/save",
            "method": "POST",
            "body": {"enabled": True},
        },
    }
    assert await handler.emit_event({"event_name": "PersonMessageReceived"}) == {
        "action": RuntimeToPluginAction.EMIT_EVENT.value,
        "data": {"event_context": {"event_name": "PersonMessageReceived"}},
    }
    assert await handler.call_tool("weather", {"city": "Paris"}, {"id": "s"}, 9) == {
        "action": RuntimeToPluginAction.CALL_TOOL.value,
        "data": {
            "tool_name": "weather",
            "tool_parameters": {"city": "Paris"},
            "session": {"id": "s"},
            "query_id": 9,
        },
    }
    assert await handler.retrieve_knowledge("kb", {"query": "hi"}) == {
        "action": RuntimeToPluginAction.RETRIEVE_KNOWLEDGE.value,
        "data": {"retriever_name": "kb", "retrieval_context": {"query": "hi"}},
    }
    assert (
        RuntimeToPluginAction.RETRIEVE_KNOWLEDGE,
        {"retriever_name": "kb", "retrieval_context": {"query": "hi"}},
        plugin_handler_module.KNOWLEDGE_RETRIEVAL_TIMEOUT,
    ) in calls
    assert await handler.shutdown_plugin() == {
        "action": RuntimeToPluginAction.SHUTDOWN.value,
        "data": {},
    }
    assert await handler.rag_ingest_document({"document_id": "doc-1"}) == {
        "action": RuntimeToPluginAction.INGEST_DOCUMENT.value,
        "data": {"context": {"document_id": "doc-1"}},
    }
    assert await handler.rag_delete_document("kb-1", "doc-1") == {
        "action": RuntimeToPluginAction.DELETE_DOCUMENT.value,
        "data": {"kb_id": "kb-1", "document_id": "doc-1"},
    }
    assert await handler.rag_on_kb_create("kb-1", {"top_k": 3}) == {
        "action": RuntimeToPluginAction.ON_KB_CREATE.value,
        "data": {"kb_id": "kb-1", "config": {"top_k": 3}},
    }
    assert await handler.rag_on_kb_delete("kb-1") == {
        "action": RuntimeToPluginAction.ON_KB_DELETE.value,
        "data": {"kb_id": "kb-1"},
    }
    assert await handler.get_rag_capabilities() == {
        "action": RuntimeToPluginAction.GET_RAG_CAPABILITIES.value,
        "data": {},
    }
    assert calls[-1] == (RuntimeToPluginAction.GET_RAG_CAPABILITIES, {}, 10)


async def test_plugin_connection_handler_notify_plugin_diagnostic_helper(monkeypatch):
    handler, _manager, _control = _handler()
    calls = []

    async def fake_call_action(action, data, timeout=15.0):
        calls.append((action, data, timeout))
        return {"ok": True}

    monkeypatch.setattr(handler, "call_action", fake_call_action)

    result = await handler.notify_plugin_diagnostic({"level": "ERROR"})

    assert result == {"ok": True}
    assert calls == [(RuntimeToPluginAction.PLUGIN_DIAGNOSTIC, {"level": "ERROR"}, 5)]


async def test_plugin_connection_handler_execute_command_and_parse_document_helpers(
    monkeypatch,
):
    handler, _manager, _control = _handler()
    calls = []

    async def fake_generator(action, data, timeout=15.0):
        calls.append(("generator", action, data, timeout))
        yield {"command_response": {"text": "one"}}
        yield {"command_response": {"text": "two"}}

    async def fake_send_file(file_bytes, extension):
        calls.append(("send_file", file_bytes, extension))
        return "file-key"

    async def fake_call_action(action, data, timeout=15.0):
        calls.append(("call_action", action, data, timeout))
        return {"parsed": data}

    monkeypatch.setattr(handler, "call_action_generator", fake_generator)
    monkeypatch.setattr(handler, "send_file", fake_send_file)
    monkeypatch.setattr(handler, "call_action", fake_call_action)

    command_chunks = [
        chunk async for chunk in handler.execute_command({"command": "admin"})
    ]
    parse_result = await handler.parse_document({"filename": "a.pdf"}, b"pdf")

    assert command_chunks == [
        {"command_response": {"text": "one"}},
        {"command_response": {"text": "two"}},
    ]
    assert calls[0] == (
        "generator",
        RuntimeToPluginAction.EXECUTE_COMMAND,
        {"command_context": {"command": "admin"}},
        plugin_handler_module.LONG_RUNNING_OPERATION_TIMEOUT,
    )
    assert parse_result == {
        "parsed": {"context": {"filename": "a.pdf", "file_key": "file-key"}}
    }
    assert calls[-2:] == [
        ("send_file", b"pdf", ""),
        (
            "call_action",
            RuntimeToPluginAction.PARSE_DOCUMENT,
            {"context": {"filename": "a.pdf", "file_key": "file-key"}},
            300,
        ),
    ]


async def test_reply_stream_forwarder_uses_trusted_plugin_identity():
    handler, manager, control = _handler()
    manager.plugins = [FakePluginContainer(runtime_handler=handler)]
    control.results[PluginToRuntimeAction.REPLY_STREAM] = {"result": {"status": "open"}}
    async with ProtocolSession(handler) as session:
        response = await session.request(
            PluginToRuntimeAction.REPLY_STREAM.value,
            {
                "run_id": "run-1",
                "stream_id": "stream-1",
                "operation": "update",
                "text": "hello",
                "caller_plugin_identity": "spoofed/plugin",
            },
        )
        missing_run = await session.request(
            PluginToRuntimeAction.REPLY_STREAM.value, {"text": "hello"}
        )
    assert response["code"] == 0
    assert missing_run["code"] != 0
    assert len(control.calls) == 1
    action, payload, timeout = control.calls[0]
    assert action == PluginToRuntimeAction.REPLY_STREAM
    assert payload["caller_plugin_identity"] == "tester/demo"
    assert payload["text"] == "hello"
    assert timeout == 30


def _shared_pool_handler(binding):
    handler, manager, control = _handler(runtime_profile="shared")
    handler.set_shared_pool_bindings(binding.artifact_digest, {binding})
    return handler, manager, control


async def test_shared_pool_dispatch_uses_inflight_control_binding():
    """A dispatch made while a Control action runs carries that binding."""

    binding = _installation_binding()
    handler, manager, _control = _shared_pool_handler(binding)
    manager._current_control_binding = lambda: binding

    async with ProtocolSession(handler):
        dispatch = asyncio.create_task(
            handler.call_action(
                RuntimeToPluginAction.INITIALIZE_PLUGIN,
                {"plugin_settings": {}},
            )
        )
        (message,) = await handler.conn.sent_messages(1)
        await handler.conn.send_peer_response(message["seq_id"])
        assert await dispatch == {}

    assert message["context"] == binding.model_dump()


async def test_shared_pool_dispatch_falls_back_to_task_local_binding():
    """A worker relay runs in another task, so the dispatch carries its binding."""

    binding = _installation_binding()
    handler, manager, _control = _shared_pool_handler(binding)
    manager._current_control_binding = lambda: None

    # The in-flight plugin action owns the binding; the Control contextvar that
    # the relay task cannot observe stays empty.
    token = handler._current_action_context.set(binding)
    try:
        async with ProtocolSession(handler):
            dispatch = asyncio.create_task(
                handler.call_action(RuntimeToPluginAction.SHUTDOWN, {})
            )
            (message,) = await handler.conn.sent_messages(1)
            await handler.conn.send_peer_response(message["seq_id"])
            await dispatch
    finally:
        handler._current_action_context.reset(token)

    assert message["context"] == binding.model_dump()


async def test_shared_pool_dispatch_rejects_unattached_control_binding():
    """A binding that is not an attached slot must never reach the worker."""

    binding = _installation_binding()
    unattached = _installation_binding(runtime_revision=2)
    handler, manager, _control = _shared_pool_handler(binding)
    manager._current_control_binding = lambda: unattached

    with pytest.raises(ValueError, match="requires an attached binding"):
        await handler.call_action(RuntimeToPluginAction.SHUTDOWN, {})


def test_shared_pool_relay_requires_an_attached_binding():
    binding = _installation_binding()
    handler, manager, _control = _shared_pool_handler(binding)
    manager._current_control_binding = lambda: None

    with pytest.raises(ValueError, match="requires an attached binding"):
        handler.resolve_outbound_action_context(None)


@pytest.mark.parametrize(
    ("timeout", "expected_timeout"),
    [
        (120, 120.0),
        (2.5, 2.5),
        (-1, 60.0),
        (0, 60.0),
        ("30", 60.0),
        (True, 60.0),
        (None, 60.0),
    ],
)
async def test_plugin_handler_forwards_send_message_with_plugin_timeout(
    timeout, expected_timeout
):
    handler, _manager, control = _handler()
    control.results[PluginToRuntimeAction.SEND_MESSAGE] = {"result": None}

    async with ProtocolSession(handler) as session:
        await session.request(
            PluginToRuntimeAction.SEND_MESSAGE.value,
            {"bot_uuid": "bot-1", "message": "hi", "timeout": timeout},
        )

    # The timeout is consumed by the Runtime and never forwarded to the host.
    assert control.calls == [
        (
            PluginToRuntimeAction.SEND_MESSAGE,
            {"bot_uuid": "bot-1", "message": "hi"},
            expected_timeout,
        )
    ]
