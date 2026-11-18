from __future__ import annotations

import pytest

from langbot_plugin.api.definition.components.base import BaseComponent, NoneComponent
from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.definition.components.knowledge_engine.engine import (
    KnowledgeEngine,
    KnowledgeEngineCapability,
)
from langbot_plugin.api.definition.components.page import (
    Page,
    PageRequest,
    PageResponse,
)
from langbot_plugin.api.definition.components.parser.parser import Parser
from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.command.context import CommandReturn
from langbot_plugin.api.entities.events import PersonMessageReceived


def test_base_and_none_components_initialize_as_noop():
    component = NoneComponent()
    assert isinstance(component, BaseComponent)


def test_event_listener_registers_multiple_handlers_for_event_type():
    listener = EventListener()

    async def first(_ctx):
        return None

    async def second(_ctx):
        return None

    assert listener.handler(PersonMessageReceived)(first) is first
    listener.handler(PersonMessageReceived)(second)

    assert listener.registered_handlers[PersonMessageReceived] == [first, second]


def test_command_subcommand_decorator_records_metadata():
    command = Command()

    async def handler(_ctx):
        yield CommandReturn(text="ok")

    assert (
        command.subcommand("run", help="Run", usage="/run", aliases=["r"])(handler)
        is handler
    )

    registered = command.registered_subcommands["run"]
    assert registered.help == "Run"
    assert registered.usage == "/run"
    assert registered.aliases == ["r"]


def test_command_subcommand_default_aliases_should_not_be_shared():
    first = Command()
    second = Command()

    async def first_handler(_ctx):
        yield CommandReturn(text="first")

    async def second_handler(_ctx):
        yield CommandReturn(text="second")

    first.subcommand("first")(first_handler)
    second.subcommand("second")(second_handler)
    first.registered_subcommands["first"].aliases.append("alias")

    assert second.registered_subcommands["second"].aliases == []


def test_page_request_response_helpers_and_default_handler():
    request = PageRequest(endpoint="/entries", method="GET", headers={"x": "1"})
    assert request.body is None
    assert request.headers == {"x": "1"}
    assert PageResponse.ok({"ok": True}).data == {"ok": True}
    assert PageResponse.fail("nope").error == "nope"


@pytest.mark.asyncio
async def test_page_default_handle_api_returns_not_implemented_failure():
    response = await Page().handle_api(PageRequest(endpoint="/", method="GET"))

    assert response.error == "Not implemented"


def test_knowledge_engine_default_capabilities():
    assert KnowledgeEngine.get_capabilities() == [
        KnowledgeEngineCapability.DOC_INGESTION
    ]


def test_abstract_component_kinds_are_stable():
    assert Command.__kind__ == "Command"
    assert EventListener.__kind__ == "EventListener"
    assert KnowledgeEngine.__kind__ == "KnowledgeEngine"
    assert Parser.__kind__ == "Parser"
    assert Tool.__kind__ == "Tool"
    assert Page.__kind__ == "Page"
