from __future__ import annotations

import pytest

from langbot_plugin.api.entities.builtin.platform.message import File, Image, Plain
from langbot_plugin.api.entities.builtin.provider.message import (
    ContentElement,
    FunctionCall,
    Message,
    MessageChunk,
    ToolCall,
)


def test_content_element_factories_and_string_representations():
    assert str(ContentElement.from_text("hello")) == "hello"
    assert str(ContentElement.from_image_url("https://example.com/a.png")) == (
        "[Image](https://example.com/a.png)"
    )
    assert str(ContentElement.from_image_base64("abc")) == "[Image](base64)"
    assert str(ContentElement.from_file_url("https://example.com/a.txt", "a.txt")) == (
        "[File](https://example.com/a.txt)"
    )
    assert str(ContentElement.from_file_base64("abc", "a.txt")) == "[File](a.txt)"
    assert str(ContentElement(type="unknown")) == "Unknown content"


def test_image_url_content_string_is_truncated():
    long_url = "https://example.com/" + "a" * 200
    element = ContentElement.from_image_url(long_url)

    assert str(element.image_url).endswith("...")
    assert len(str(element.image_url)) == 131


def test_message_string_content_converts_to_plain_message_chain_with_prefix():
    message = Message(role="user", content="hello")
    chain = message.get_content_platform_message_chain(prefix_text="[p] ")

    assert len(chain) == 1
    assert isinstance(chain[0], Plain)
    assert chain[0].text == "[p] hello"
    assert message.readable_str() == "user: hello"


@pytest.mark.parametrize("message_type", [Message, MessageChunk])
def test_message_list_content_converts_supported_elements_to_platform_chain(
    message_type,
):
    message = message_type(
        role="user",
        content=[
            ContentElement.from_image_url("https://example.com/a.png"),
            ContentElement.from_file_url("https://example.com/a.txt", "a.txt"),
            ContentElement.from_image_base64("YmFzZTY0"),
            ContentElement.from_file_base64("aGVsbG8=", "report.txt"),
            ContentElement.from_text("hello"),
        ],
    )

    chain = message.get_content_platform_message_chain(prefix_text="[p] ")

    assert [type(component) for component in chain] == [Image, File, Image, File, Plain]
    assert chain[3].base64 == "aGVsbG8="
    assert chain[3].name == "report.txt"
    assert chain[-1].text == "[p] hello"


@pytest.mark.parametrize("message_type", [Message, MessageChunk])
@pytest.mark.parametrize("file_name", ["report.txt", None])
def test_serialized_base64_file_survives_platform_conversion(message_type, file_name):
    message = message_type.model_validate(
        {
            "role": "assistant",
            "content": [
                {
                    "type": "file_base64",
                    "file_base64": "aGVsbG8=",
                    "file_name": file_name,
                }
            ],
        }
    )

    chain = message.get_content_platform_message_chain(prefix_text="[p] ")

    assert len(chain) == 2
    assert isinstance(chain[0], Plain)
    assert chain[0].text == "[p] "
    assert isinstance(chain[1], File)
    assert chain[1].base64 == "aGVsbG8="
    assert chain[1].name == (file_name or "")


@pytest.mark.parametrize("message_type", [Message, MessageChunk])
def test_base64_file_without_payload_is_skipped(message_type):
    message = message_type(
        role="assistant",
        content=[ContentElement(type="file_base64", file_name="a.txt")],
    )

    assert len(message.get_content_platform_message_chain()) == 0


def test_message_prefix_is_inserted_when_no_text_component_exists():
    message = Message(
        role="user",
        content=[ContentElement.from_image_url("https://example.com/a.png")],
    )

    chain = message.get_content_platform_message_chain(prefix_text="[p] ")

    assert isinstance(chain[0], Plain)
    assert chain[0].text == "[p] "
    assert isinstance(chain[1], Image)


def test_message_without_content_returns_none_and_tool_call_readable_string():
    call = ToolCall(
        id="call-1",
        type="function",
        function=FunctionCall(name="search", arguments="{}"),
    )
    assert Message(role="assistant").get_content_platform_message_chain() is None
    assert Message(role="assistant", tool_calls=[call]).readable_str() == (
        "Call tool: call-1"
    )
    assert Message(role="assistant").readable_str() == "Unknown message"


def test_message_chunk_matches_message_content_conversion():
    chunk = MessageChunk(
        role="assistant",
        content=[ContentElement.from_text("partial")],
        is_final=False,
        msg_sequence=3,
    )

    chain = chunk.get_content_platform_message_chain(prefix_text="[chunk] ")

    assert chain[0].text == "[chunk] partial"
    assert chunk.readable_str() == "assistant: partial"


def test_message_image_url_content_should_validate_required_payload():
    message = Message(role="user", content=[ContentElement(type="image_url")])

    with pytest.raises(ValueError):
        message.get_content_platform_message_chain()
